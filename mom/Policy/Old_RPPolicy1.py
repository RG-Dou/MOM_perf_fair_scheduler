# Memory Overcommitment Manager
# Copyright (C) 2010 Adam Litke, IBM Corporation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import threading
import operator
import math
import time
from mom.Plotter import Plotter

DEFAULT_POLICY_NAME = "50_main_"

class Old_RPPolicy1:
	def __init__(self):
		self.logger = logging.getLogger('mom.RPPolicy')
		self.policy_sem = threading.Semaphore()
		self.algorithm = Algorithm()

		self.last_time = {}
		self.this_time = {}

		self.standard = {}
		self.vm_state = {} # 1 represents "be-adjusted", 2 represents "standard-extracted"

		self.progress = {}

		self.start = time.time()
		self.time = []
		self.time2user = []
		self.time2total = []
		self.time2efftotal = []



	def setBalloon(self, target, vm):
		vm.Control('balloon_target', target)


	def set_policy(self, type, total_mem, plot_dir):
		self.type = type
		self.total_mem_ratio = total_mem


	def update_stat(self, guest):
		name = guest.Prop('name')

		pf = guest.major_fault
		user = guest.user
		nice = guest.nice
		system = guest.system
		idle = guest.idle
		iowait = guest.iowait
		irq = guest.irq
		softirq = guest.softirq
		steal = guest.steal
		total = user+nice+system+idle+iowait+irq+softirq+steal


		if name not in self.last_time or self.last_time[name] is None:
			self.last_time[name] = {}
			self.last_time[name]['pf'] = pf
			self.last_time[name]['user'] = user
			self.last_time[name]['total'] = total

			self.this_time[name] = {}
			return False

		self.this_time[name]['pf'] = pf - self.last_time[name]['pf']
		self.this_time[name]['user'] = user - self.last_time[name]['user']
		self.this_time[name]['total'] = total - self.last_time[name]['total']

		self.last_time[name]['pf'] = pf
		self.last_time[name]['user'] = user
		self.last_time[name]['total'] = total


	def update_standard(self, name):
		if name not in self.standard or self.standard[name] is None:
			self.standard[name] = {}
			self.standard[name]['user'] = float(self.this_time[name]['user'])
			self.standard[name]['total'] = float(self.this_time[name]['total'])
			self.standard[name]['value'] = self.standard[name]['user']/self.standard[name]['total']
			return

		self.standard[name]['user'] += float(self.this_time[name]['user'])
		self.standard[name]['total'] += float(self.this_time[name]['total'])
		self.standard[name]['value'] = self.standard[name]['user']/self.standard[name]['total']

		self.progress[name] += self.this_time[name]['total']


	def calc_prog(self, name):
		total = self.this_time[name]['user'] / self.standard[name]['value']
		
		self.logger.info("standard = %f", self.standard[name]['value'])
		self.time2efftotal.append(int(total))
		self.progress[name] += total


	def evaluate(self, host, guest_list):

		total_mem = host.mem_available * float(self.total_mem_ratio)

		for guest in guest_list:
			name = guest.Prop('name')

			if self.update_stat(guest) is False:
				return


			currtime = int(time.time() - self.start)
			self.time.append(currtime)
			self.time2user.append(self.this_time[name]['user'])
			self.time2total.append(self.this_time[name]['total'])

			cur_mem = guest.balloon_cur

			if name not in self.progress or self.progress[name] is None:
				self.progress[name] = 0

			if cur_mem > 3000000:
				if self.this_time[name]['user'] > 0:
					self.update_standard(name)
					self.time2efftotal.append(self.this_time[name]['total'])
				else:
					self.time2efftotal.append(0)
			else:
				self.calc_prog(name)

			self.logger.info("progress = %d", self.progress[name])

			self.logger.info("time = %s", self.time)
			self.logger.info("user = %s", self.time2user)
			self.logger.info("total = %s", self.time2total)
			self.logger.info("effitotal = %s", self.time2efftotal)

			# if time.time() - self.start > 50:
			# 	self.setBalloon(700000, guest)


class Algorithm:
	def __init__(self):
		self.logger = logging.getLogger('mom.Algorithm')
