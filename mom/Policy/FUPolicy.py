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

DEFAULT_POLICY_NAME = "50_main_"

class FUPolicy:
	def __init__(self):
		self.logger = logging.getLogger('mom.FUPolicy')
		self.policy_sem = threading.Semaphore()
		self.algorithm = Algorithm()
		self.allocated_mems = {}
		self.total_mem_alltime = 0
		self.first = True

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

	def set_policy(self, type, vm_threshold, host_threshold):
		self.type = type
		self.vmpres_threshold = vm_threshold
		self.hostpres_threshold = host_threshold

	def setBalloon(self, targets, vms):
		for name, vm in vms.iteritems():
			target = targets[name]
			vm.Control('balloon_target', target)
		

	def evaluate(self, host, guest_list):
		vms = {}
		weights = {}
		active_mems = {}
		config_mems = {}
		total_mem = host.mem_available * 0.7
		self.total_mem_alltime += total_mem
		swap_outs = {}
		all_statistics = {}
		total_weights = 0

		for guest in guest_list:
			name = guest.Prop('name')
			weight = guest.Prop('weight')
			free_mem = guest.mem_unused
			config_mem = guest.balloon_max
			swap_out = guest.swap_out
			if self.first is True:
				if name not in self.allocated_mems or self.allocated_mems[name] is None:
					self.allocated_mems[name] = 0
			else:
				if name not in self.allocated_mems or self.allocated_mems[name] is None:
					self.allocated_mems[name] = min(guest.balloon_cur, config_mem)
				else:
					self.allocated_mems[name] += min(guest.balloon_cur, config_mem)

			vms[name] = guest
			total_weights += weight
			weights[name] = weight
			active_mems[name] = config_mem - free_mem
			config_mems[name] = config_mem
			swap_outs[name] = swap_out
			all_statistics[name] = guest.statistics

		if self.first is True:
			self.first = False

		for name, weight in weights.iteritems():
			weights[name] = float(weight) / float(total_weights)

		self.logger.info("total memory all the time is %s", \
			self.total_mem_alltime)
		self.logger.info("allocated_mems is %s", \
			self.allocated_mems)

		f_allocated = self.algorithm.fairness(self.allocated_mems, \
		 	weights, self.total_mem_alltime)
		self.logger.info("f_allocated is %s", \
			f_allocated)

		predictors = self.algorithm.predictor(all_statistics)

		self.logger.info("predictors is %s", \
			predictors)

		u_allocated = self.algorithm.utilization(predictors, config_mems)
		self.logger.info("u_allocated is %s", \
			u_allocated)

		c_allocated = self.algorithm.combination(f_allocated, \
			u_allocated, total_mem, config_mems)

		self.logger.info("c_allocated is %s", \
			c_allocated)

		self.setBalloon(c_allocated, vms)



class Algorithm:
	def __init__(self):
		self.logger = logging.getLogger('mom.Algorithm')

	def fairness(self, allocated_mems, weights, total_mem):
		f_allocated = {}
		for name, mem in allocated_mems.iteritems():
			weight = weights[name]
			allocated_mem = total_mem * weight - mem
			f_allocated[name] = allocated_mem

		return f_allocated

	def predictor(self, all_statistics):
		predictors = {}
		if len(all_statistics) == 0:
			return None
		for name, statistics in all_statistics.iteritems():
			cur = statistics[-1]
			allocated_cur = cur.get('balloon_cur')
			free_cur = cur.get('mem_unused')
			swapout_cur = cur.get('swap_out')
			active_cur = allocated_cur - free_cur + swapout_cur
			self.logger.info("Cur: balloon is %s, mem_unused is %s, swap_out is %s", \
				allocated_cur, free_cur, swapout_cur)
			self.logger.info("active_cur is %s", \
				active_cur)

			active_prev = 0
			if len(statistics) > 1:
				prev = statistics[-2]
				allocated_prev = prev.get('balloon_cur')
				free_prev = prev.get('mem_unused')
				#swapout_prev = prev.get('swap_out')
				active_prev = allocated_prev - free_prev
				self.logger.info("prev: balloon is %s, mem_unused is %s", \
					allocated_prev, free_prev)
				self.logger.info("active_prev is %s", \
					active_prev)

			if active_prev >= active_cur:
				predictors[name] = active_cur
			else:
				predictors[name] = active_cur * 2 - active_prev

		return predictors

	def utilization(self, predictors, config_mems):
		u_allocated = {}
		for name, mem in predictors.iteritems():
			mem += 150000
			config = config_mems[name]
			if config < mem:
				u_allocated[name] = config
			else:
				u_allocated[name] = mem
		return u_allocated

	def combination(self, f_allocated, u_allocated, total_mem, config_mems):
		c_allocated = {}

		exceed = {}
		for name, f_mem in f_allocated.iteritems():
			u_mem = u_allocated[name]
			exceed[name] = u_mem - f_mem
		sorted_exceed = sorted(exceed.items(), key=operator.itemgetter(1))

		demands = 0
		for mem in u_allocated.itervalues():
			demands += mem

		if demands < total_mem:
			left_free = total_mem - demands
			n = 0
			while left_free > 0 and n < len(exceed):
				key = sorted_exceed[n][0]
				value = -sorted_exceed[n][1]

				config = config_mems[key]
				upper_bound = config - u_allocated[key]

				if upper_bound < value:
					value = upper_bound

				if left_free > value:
					u_allocated[key] += value
				else:
					u_allocated[key] += left_free
				left_free -= value
				n += 1


		else:
			left_demand = demands - total_mem
			n = len(exceed) - 1
			while left_demand > 0 and n >= 0:
				key = sorted_exceed[n][0]
				value = sorted_exceed[n][1]
				if left_demand > value:
					u_allocated[key] -= value
				else:
					u_allocated[key] -= left_demand
				left_demand -= value
				n -= 1

		c_allocated = u_allocated
		return c_allocated
