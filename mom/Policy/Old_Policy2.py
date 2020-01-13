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

class RPPolicy:
	def __init__(self):
		self.logger = logging.getLogger('mom.RPPolicy')
		self.policy_sem = threading.Semaphore()
		self.algorithm = Algorithm()
		self.start = 0

		self.firsts = {}
		self.lasts = {}
		self.totals = {}

		self.start = time.time()
		self.time = []
		self.time2user = []
		self.time2nice = []
		self.time2sys = []
		self.time2idle = []
		self.time2iowait = []
		self.time2irq = []
		self.time2softirq = []
		self.time2total = []
		self.time2pf = []



	def set_policy(self, type, total_mem, plot_dir):
		self.type = type
		self.total_mem_ratio = total_mem


	def setBalloon(self, targets, vms):
		for name, vm in vms.iteritems():
			target = targets[name]
			vm.Control('balloon_target', target)

	def initAllocate(self, vms, total_mem):
		share = total_mem / len(vms)
		for name, vm in vms.iteritems():
			vm.Control('balloon_target', share)


	def evaluate(self, host, guest_list):
		vms = {}
		weights_vms = {}
		low_limit = {}
		pagefaults = {}
		coefficients = {}
		last_balloons = {}

		total_mem = host.mem_available * float(self.total_mem_ratio)

		for guest in guest_list:

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

			if name not in self.lasts or self.lasts[name] is None:
				self.totals[name] = {}
				self.totals[name]['user'] = 0
				self.totals[name]['nice'] = 0
				self.totals[name]['system'] = 0
				self.totals[name]['idle'] = 0
				self.totals[name]['iowait'] = 0
				self.totals[name]['irq'] = 0
				self.totals[name]['softirq'] = 0
				self.totals[name]['steal'] = 0

				self.firsts[name] = {}
				self.firsts[name]['user'] = user
				self.firsts[name]['nice'] = nice
				self.firsts[name]['system'] = system
				self.firsts[name]['idle'] = idle
				self.firsts[name]['iowait'] = iowait
				self.firsts[name]['irq'] = irq
				self.firsts[name]['softirq'] = softirq
				self.firsts[name]['steal'] = steal

				self.lasts[name] = {}
				self.lasts[name]['pf'] = pf
				self.lasts[name]['user'] = 0
				self.lasts[name]['nice'] = 0
				self.lasts[name]['system'] = 0
				self.lasts[name]['idle'] = 0
				self.lasts[name]['iowait'] = 0
				self.lasts[name]['irq'] = 0
				self.lasts[name]['softirq'] = 0
				self.lasts[name]['steal'] = 0
				return


			user -= self.firsts[name]['user']
			nice -= self.firsts[name]['nice']
			system -= self.firsts[name]['system']
			idle -= self.firsts[name]['idle']
			iowait -= self.firsts[name]['iowait']
			irq -= self.firsts[name]['irq']
			softirq -= self.firsts[name]['softirq']
			steal -= self.firsts[name]['steal']



			currtime = int(time.time() - self.start)
			self.time.append(currtime)
			self.time2user.append(user - self.lasts[name]['user'])
			self.time2nice.append(nice - self.lasts[name]['nice'])
			self.time2sys.append(system - self.lasts[name]['system'])
			self.time2idle.append(idle -  self.lasts[name]['idle'])
			self.time2iowait.append(iowait - self.lasts[name]['iowait'])
			self.time2irq.append(irq - self.lasts[name]['irq'])
			self.time2softirq.append(softirq - self.lasts[name]['softirq'])
			self.time2pf.append(pf - self.lasts[name]['pf'])
			self.time2total.append(self.time2user[-1] + self.time2nice[-1] + self.time2sys[-1] + self.time2idle[-1] + \
										self.time2iowait[-1] + self.time2irq[-1] + self.time2softirq[-1])


			if pf != self.lasts[name]['pf']:
				self.totals[name]['user'] += user - self.lasts[name]['user']
				self.totals[name]['nice'] += nice - self.lasts[name]['nice']
				self.totals[name]['system'] += system - self.lasts[name]['system']
				self.totals[name]['idle'] += idle - self.lasts[name]['idle']
				self.totals[name]['iowait'] += iowait - self.lasts[name]['iowait']
				self.totals[name]['irq'] += irq - self.lasts[name]['irq']
				self.totals[name]['softirq'] += softirq - self.lasts[name]['softirq']
				self.totals[name]['steal'] += steal - self.lasts[name]['steal']
				#self.total_delay[name] = self.total_iowait[name] + self.total_irq[name] + self.total_softirq[name]

			#self.logger.info("raw   iowait:%s, irq:%s, softirq:%s, total:%s", iowait, irq, softirq, iowait+softirq)
			#self.logger.info("after iowait:%s, user:%s, softirq:%s, total:%s", self.total_iowait[name], user-self.first_user[name], self.total_softirq[name], self.total_delay[name])

			self.lasts[name]['pf'] = pf
			self.lasts[name]['user'] = user
			self.lasts[name]['nice'] = nice
			self.lasts[name]['system'] = system
			self.lasts[name]['idle'] = idle
			self.lasts[name]['iowait'] = iowait
			self.lasts[name]['irq'] = irq
			self.lasts[name]['softirq'] = softirq
			self.lasts[name]['steal'] = steal

			# self.logger.info("raw  :%s", self.lasts[name])
			# self.logger.info("after:%s", self.totals[name])

		self.logger.info("time = %s", self.time)
		self.logger.info("user = %s", self.time2user)
		self.logger.info("nice = %s", self.time2nice)
		self.logger.info("system = %s", self.time2sys)
		self.logger.info("idle = %s", self.time2idle)
		self.logger.info("iowait = %s", self.time2iowait)
		self.logger.info("irq = %s", self.time2irq)
		self.logger.info("softirq = %s", self.time2softirq)
		self.logger.info("total = %s", self.time2total)
		self.logger.info("pf = %s", self.time2pf)

		# 	name = guest.Prop('name')
		# 	weight_vm = guest.Prop('weight-vm')
		# 	vms[name] = guest
		# 	weights_vms[name] = weight_vm
		# 	low_limit[name] = 400000
		# 	last_balloons[name] = guest.balloon_cur
		# 	if name not in self.fisrt_pf or self.fisrt_pf[name] is None:
		# 		self.fisrt_pf[name] = guest.major_fault

		# 	pagefaults[name] = guest.major_fault - self.fisrt_pf[name]
		# 	coefficients[name] = guest.Prop('coefficient')

		# if self.start <= 3:
		# 	self.initAllocate(vms, total_mem)
		# 	self.start += 1
		# 	return


		# rich_vm, poor_vm = self.algorithm.pf_func(pagefaults, weights_vms, coefficients)
		# rest_mem = self.algorithm.rest(rich_vm, poor_vm, last_balloons, total_mem)
		# targets = self.algorithm.target(rich_vm, poor_vm, low_limit, last_balloons, rest_mem)
		# if targets is not None:
		# 	self.setBalloon(targets, vms)



class Algorithm:
	def __init__(self):
		self.logger = logging.getLogger('mom.Algorithm')


	def pf_func(self, pagefaults, weights_vms, coefficients):
		shares = {}
		for name, weight in weights_vms.iteritems():
			pagefault = pagefaults[name]
			coefficient = coefficients[name]
			share = (coefficient * pagefault) * weight
			shares[name] = share

		sorted_x = sorted(shares.items(), key=operator.itemgetter(1))
		self.logger.info("page fault: %s", pagefaults)
		self.logger.info("shares: %s", sorted_x)

		return sorted_x[0][0], sorted_x[-1][0]


	def rest(self, rich_vm, poor_vm, last_balloons, total_mem):
		rest = total_mem
		for name, balloon in last_balloons.iteritems():
			if name is not rich_vm and name is not poor_vm:
				rest -= balloon
		return rest


	def target(self, rich_vm, poor_vm, low_limit, last_balloons, rest_mem):
		last_rich = last_balloons[rich_vm]
		low_rich = low_limit[rich_vm]
		last_poor = last_balloons[poor_vm]
		Bucks = 50000
		targets = {}
		if last_rich == low_rich:
			return None
		elif last_rich - Bucks < low_rich:
			remain = last_rich - low_rich
			targets[rich_vm] = low_rich
			targets[poor_vm] = rest_mem - low_rich
		else:
			targets[rich_vm] = last_rich - Bucks
			targets[poor_vm] = rest_mem - targets[rich_vm]

		return targets