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
		#self.fields = set(['Used', 'User', 'System', 'Nice', 'Idle', 'IOwait', 'Irq', 'Softirq', 'Total', 'Pagefault', 'Swapin', 'Swapout'])
		self.fields = set(['Used', 'User', 'System', 'Nice', 'Idle', 'IOwait', 'Irq', 'Softirq', 'Total', 'Pagefault'])
		self.VM_Infos = {}


	def set_policy(self, type, total_mem, plot_dir, alpha, beta):
		self.type = type
		self.total_mem_ratio = total_mem
		name = 'Policy'
		if plot_dir != '':
			self.plotter = Plotter(plot_dir, name)
			self.plotter.setFields(self.fields)
		else:
			self.plotter = None


	def evaluate(self, host, guest_list):

		for guest in guest_list:
			name = guest.Prop('name')
			if name not in self.VM_Infos or self.VM_Infos[name] is None:
				info = VM_Info(name)
				info.initAttribute(guest)
				self.VM_Infos[name] = info
			else:
				info = self.VM_Infos[name]
				info.update(guest)

		if self.plotter is not None:
			for name, info in self.VM_Infos.iteritems():
				data = info.getData(self.fields)
				self.plotter.plot(data)


class VM_Info:

	def __init__(self, name):
		self.logger = logging.getLogger('mom.Policy.VM_Info')
		self.name = name
		self.attributes = {}
		self.keys = set(['Used', 'User', 'System', 'Nice', 'Idle', 'IOwait', 'Irq', 'Softirq', 'Total', 'Pagefault', 'Swapin', 'Swapout'])


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
		standard = self.getAttribute('Total') - self.getAttribute('Start-time')
		if standard > 0:
			speed = float(self.getAttribute('User')) / float(standard)
			self.setAttribute('Speed', speed)
			self.setAttribute('Rate', speed / self.getAttribute('Weight'))


	def initAttribute(self, guest):
		self.update(guest)


	def update(self, guest):
		self.guest = guest
		self.setAttribute('Used', guest.balloon_cur - guest.mem_unused)
		self.setAttribute('User', guest.user)
		self.setAttribute('System', guest.system)
		self.setAttribute('Nice', guest.nice)
		self.setAttribute('Idle', guest.idle)
		self.setAttribute('IOwait', guest.iowait)
		self.setAttribute('Irq', guest.irq)
		self.setAttribute('Softirq', guest.softirq)
		self.setAttribute('Total', guest.total)
		self.setAttribute('Pagefault', guest.major_fault)
		self.setAttribute('Swapin', guest.swap_in)
		self.setAttribute('Swapout', guest.swap_out)


	def getData(self, keys):
		data = {}
		for key in keys:
			data[key] = self.getAttribute(key)

		return data