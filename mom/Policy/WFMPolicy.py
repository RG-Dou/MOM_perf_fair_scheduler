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
from Parser import Evaluator
from Parser import get_code
from Parser import PolicyError

DEFAULT_POLICY_NAME = "50_main_"

MinLoc = 900000

class WFMPolicy:
	def __init__(self):
		self.logger = logging.getLogger('mom.Policy')
		self.policy_sem = threading.Semaphore()
		self.fields = set(['VM', 'Used', 'Swap', 'Worksize', 
							'Balloon', 'User', 'Start-time', 
							'IOwait', 'Softirq', 'System',
							'Total', 'Allocated', 
							'Pagefault'])
		self.total_used = {}
		self.VM_Infos = {}

	def _validate_config(self, host, guest_list):
		for id, guest in guest_list:
			total = guest.GetVar('mem_available')
			if total <= self.vmpres_threshold:
				self.logger.error("invalid 'vmpres_threshold'")
				return False
		total = host.GetVar('mem_available')
		if total <= self.hostpres_threshold:
			self.logger.error("invalid 'hostpres_threshold'")
			return False
		return True

	def set_policy(self, total_mem, plot_dir):
		self.total_mem_ratio = total_mem
		name = 'Policy'
		if plot_dir != '':
			self.plotter = Plotter(plot_dir, name)
			self.plotter.setFields(self.fields)
		else:
			self.plotter = None

	def setBalloon(self, vm, target):
		vm.Control('balloon_target', target)
		
	def evaluate(self, host, guest_list):

		total_mem = host.mem_available * float(self.total_mem_ratio)
		demands = {}
		allocation = {}
		wei_allo = {}

		for guest in guest_list:
			name = guest.Prop('name')
			if name not in self.VM_Infos or self.VM_Infos[name] is None:
				info = VM_Info(name)
				info.initAttribute(guest)
				self.VM_Infos[name] = info
			else:
				info = self.VM_Infos[name]
				info.update(guest)

			if name not in self.total_used or self.total_used[name] is None:
				self.total_used[name] = 0

			allocation[name] = MinLoc
			total_mem -= MinLoc
			demands[name] = info.getAttribute('Worksize')

			self.total_used[name] += info.getAttribute('Used') - 150000
			wei_allo[name] = self.total_used[name]/info.getAttribute('Weight')


		rank_l = sorted(wei_allo.items(), lambda x, y: cmp(x[1], y[1]))
		print rank_l
		index = 0

		while total_mem > 0 and index < len(rank_l):
			name = rank_l[index][0]
			demand = demands[name]
			index += 1
			if demand > MinLoc:
				demand = demand - MinLoc
				if demand > total_mem:
					allocation[name] += total_mem
					total_mem = 0
				else:
					total_mem -= demand
					allocation[name] += demand


		for name, alloc in allocation.iteritems():
			info = self.VM_Infos[name]
			info.setAttribute('Allocated', alloc)


		for name, info in self.VM_Infos.iteritems():
			info.setBalloon()


		if self.plotter is not None:
			for name, info in self.VM_Infos.iteritems():
				data = info.getData(self.fields)
				self.plotter.plot(data)


class VM_Info:

	def __init__(self, name):
		self.logger = logging.getLogger('mom.Policy.VM_Info')
		self.name = name
		self.attributes = {}
		self.keys = set(['Configured', 'Used', 'Free', 'Swap',
						 'Min', 'Balloon', 'Speed', 'Weight', 
						 'Allocated', 'Worksize', 'User', 'Total',
						 'Start-time', 'Rate', 'VM', 'Estimated',
						 'IOwait', 'Softirq', 'System',
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


	def initAttribute(self, guest):
		self.setAttribute('Min', MinLoc)
		self.setAttribute('Configured', guest.balloon_max)
		self.setAttribute('Weight', guest.Prop('weight-vm'))
		self.setAttribute('Allocated', 0)
		self.setAttribute('Speed', 0)
		self.setAttribute('Start-time', guest.total)
		self.setAttribute('Start-user', guest.user)
		self.setAttribute('User', guest.user)
		self.setAttribute('Pagefault', guest.major_fault)
		self.setAttribute('Rate', 0)
		self.update(guest)


	def update(self, guest):
		self.guest = guest
		self.setAttribute('Free', guest.mem_unused)
		self.setAttribute('Balloon', guest.balloon_cur)
		self.setAttribute('Swap', guest.swap_usage)
		self.setAttribute('IOwait', guest.iowait)
		self.setAttribute('Softirq', guest.softirq)
		self.setAttribute('System', guest.system)
		self.setAttribute('Total', guest.total)
		self.setAttribute('User', guest.user)
		self.setAttribute('Pagefault', guest.major_fault)
		if guest.user == self.getAttribute('Start-user'):
			self.setAttribute('Start-time', guest.total)

		self.updateUsed()
		self.updateWorksize()


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