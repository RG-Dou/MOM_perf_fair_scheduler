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
from mom.Plotter import Plotter

DEFAULT_POLICY_NAME = "50_main_"
Max_free = 200000
Min_share = 80000

class RPPolicy:
	def __init__(self):
		self.logger = logging.getLogger('mom.RPPolicy')
		self.policy_sem = threading.Semaphore()
		self.start = True
		self.fields = set(['VM', 'Used', 'Swap', 'Worksize', 'Balloon', 'User', 'Start-time', 'Total', 'Speed', 'Rate', 'Allocated', 'Pagefault'])
		self.VM_Infos = {}


	def set_policy(self, type, total_mem, plot_dir):
		self.type = type
		self.total_mem_ratio = total_mem
		name = 'Policy'
		if plot_dir != '':
			self.plotter = Plotter(plot_dir, name)
			self.plotter.setFields(self.fields)
		else:
			self.plotter = None


	def firstTime(self, total_mem):
		num = len(self.VM_Infos)
		share = total_mem / num
		for name, info in self.VM_Infos.iteritems():
			info.setAttribute('Allocated', share)
			info.setBalloon()


	def dynamic_allocate(self):
		ranks = {}
		for name, info in self.VM_Infos.iteritems():
			rate = info.getAttribute('Rate')
			ranks[info] = rate

		rank_l = sorted(ranks.items(), lambda x, y: cmp(x[1], y[1]))

		max_info = None
		max_share = 0
		max_index = 0
		min_info = None
		min_share = 0
		min_index = 0
		for i in range(0, len(rank_l)):
			info = rank_l[i][0]
			if info.dist2high() > 0:
				min_info = info
				min_share = info.dist2high()
				min_index = i
				break

		for i in range(len(rank_l)-1, -1, -1):
			info = rank_l[i][0]
			if info.dist2low() > 0:
				max_info = info
				max_share = info.dist2low()
				max_index = i
				break

		if min_index >= max_index:
			return
		share = min(max_share, min_share, Min_share)

		max_info.addAttribute('Allocated', -share)
		min_info.addAttribute('Allocated', share)
		for name, info in self.VM_Infos.iteritems():
			info.setBalloon()


	def meanByFree(self, active, inactive):
		total = 0
		for info in inactive:
			share = min(info.getAttribute('Free') - Max_free, \
				info.getAttribute('Allocated') - info.getAttribute('Min'))
			if share <= 0:
				continue
			info.addAttribute('Allocated', -share)
			total += share
		ave_share = total / len(active)
		for info in active:
			info.addAttribute('Allocated', ave_share)

		for name, info in self.VM_Infos.iteritems():
			info.setBalloon()


	def check(self):
		active = []
		inactive = []
		for name, info in self.VM_Infos.iteritems():
			if info.getAttribute('Free') < Max_free:
				active.append(info)
			else:
				inactive.append(info)
		if len(active) == 0:
			return False
		elif len(inactive) == 0:
			return True
		else:
			self.meanByFree(active, inactive)
			return False


	def evaluate(self, host, guest_list):

		total_mem = host.mem_available * float(self.total_mem_ratio)

		for guest in guest_list:
			name = guest.Prop('name')
			if name not in self.VM_Infos or self.VM_Infos[name] is None:
				info = VM_Info(name)
				info.initAttribute(guest)
				self.VM_Infos[name] = info
			else:
				info = self.VM_Infos[name]
				info.update(guest)

		if self.start:
			self.firstTime(total_mem)
			self.start = False
			return

		if self.check():
			self.dynamic_allocate()

		if self.plotter is not None:
			for name, info in self.VM_Infos.iteritems():
				data = info.getData(self.fields)
				self.plotter.plot(data)


class VM_Info:

	def __init__(self, name):
		self.logger = logging.getLogger('mom.Policy.VM_Info')
		self.name = name
		self.attributes = {}
		self.status = 2 # enough memory is 1, else is 2
		self.keys = set(['Configured', 'Used', 'Free', 'Swap',
						 'Min', 'Balloon', 'Speed', 'Weight', 
						 'Allocated', 'Worksize', 'User', 'Total',
						 'Start-time', 'Slope', 'Rate', 'VM',
						 'Start-user', 'Pagefault'])
		self.setAttribute('VM', name)


	def setAttribute(self, key, value):
		if key in self.keys:
			self.attributes[key] = value
		else:
			self.logger.error("invalid attribute: %s", key)


	def getAttribute(self, key):
		if key in self.keys:
			return self.attributes[key]
		else:
			self.logger.error("invalid attribute: %s", key)


	def addAttribute(self, key, value):
		if key in self.keys:
			self.attributes[key] = self.attributes[key] + value
		else:
			self.logger.error("invalid attribute: %s", key)


	def updateUsed(self):
		used = self.getAttribute('Balloon') - self.getAttribute('Free') + 150000
		self.setAttribute('Used', used)


	def updateWorksize(self):
		worksize = self.getAttribute('Used') + self.getAttribute('Swap')
		self.setAttribute('Worksize', worksize)


	def updateSpeed(self):
		standard = (self.getAttribute('Total') - self.getAttribute('Start-time'))*self.getAttribute('Slope')
		if standard > 0:
			speed = float(self.getAttribute('User')) / float(standard)
			self.setAttribute('Speed', speed)
			self.setAttribute('Rate', speed / self.getAttribute('Weight'))


	def initAttribute(self, guest):
		self.setAttribute('Min', 800000)
		self.setAttribute('Configured', guest.balloon_max)
		self.setAttribute('Weight', guest.Prop('weight-vm'))
		self.setAttribute('Allocated', 0)
		self.setAttribute('Speed', 0)
		self.setAttribute('Slope', guest.Prop('slope'))
		self.setAttribute('Start-time', guest.total)
		self.setAttribute('Start-user', guest.user)
		self.setAttribute('Rate', 0)
		self.update(guest)


	def update(self, guest):
		self.guest = guest
		self.setAttribute('Pagefault', guest.major_fault)
		self.setAttribute('Free', guest.mem_unused)
		self.setAttribute('Balloon', guest.balloon_cur)
		self.setAttribute('Swap', guest.swap_usage)
		self.setAttribute('User', guest.user - self.getAttribute('Start-user'))
		self.setAttribute('Total', guest.total)
		if guest.user == self.getAttribute('Start-user'):
			self.setAttribute('Start-time', guest.total)

		self.updateUsed()
		self.updateWorksize()
		self.updateSpeed()


	def dist2low(self):
		return self.getAttribute('Allocated') - self.getAttribute('Min')


	def dist2high(self):
		ratio = Max_free - self.getAttribute('Free')
		if ratio < 0:
			return 0
		else:
			return ratio


	def setBalloon(self):
		share = self.getAttribute('Allocated')
		if share <= self.getAttribute('Configured') and share >= self.getAttribute('Min'):
			self.guest.Control('balloon_target', self.getAttribute('Allocated'))
		else:
			self.logger.error("invalid allocation: %s", share)


	def getData(self, keys):
		data = {}
		for key in keys:
			data[key] = self.getAttribute(key)

		return data