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

class Old_RPPolicy:
	def __init__(self):
		self.logger = logging.getLogger('mom.RPPolicy')
		self.policy_sem = threading.Semaphore()
		self.algorithm = Algorithm()
		self.fields = set(['VM', 'User', 'Balloon', 'Swap_usage', 'Active_Mem', 'Working_Set', 'Allocated', 'Congestion', 'Predict', 'T_workset', 'T_used'])
		self.start = True

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

	def set_policy(self, type, total_mem, plot_dir):
		self.type = type
		self.total_mem_ratio = total_mem
		name = 'Policy'
		if plot_dir != '':
			self.plotter = Plotter(plot_dir, name)
			self.plotter.setFields(self.fields)
		else:
			self.plotter = None



	def setBalloon(self, targets, vms, datas, flag):
		for name, vm in vms.iteritems():
			target = targets[name]
			vm.Control('balloon_target', target)
			datas[name]['Allocated'] = target
			datas[name]['Congestion'] = flag

	def initAllocate(self, vms, total_mem, datas, flag):
		share = total_mem / len(vms)
		for name, vm in vms.iteritems():
			vm.Control('balloon_target', share)
			datas[name]['Allocated'] = share
			datas[name]['Congestion'] = flag


	def evaluate(self, host, guest_list):
		datas = {}

		vms = {}
		weights_user = {}
		weights_vms = {}

		active_mems = {}
		config_mems = {}
		swap_usages = {}
		worksets = {}
		low_limit = {}

		config_mems_user = {}
		low_limit_user = {}

		balloons = {}
		all_statistics = {}

		total_mem = host.mem_available * float(self.total_mem_ratio)

		for guest in guest_list:
			name = guest.Prop('name')
			weight_user = guest.Prop('weight-user')
			weight_vm = guest.Prop('weight-vm')
			user = guest.Prop('userID')
			self.algorithm.vm_user[name] = user
			free_mem = guest.mem_unused
			config_mem = guest.balloon_max
			balloon_cur = guest.balloon_cur
			swap_usage = guest.swap_usage
			all_statistics[name] = guest.statistics

			vms[name] = guest

			weights_vms[name] = weight_vm
			weights_user[user] = weight_user
			active_mems[name] = balloon_cur - free_mem + 150000
			config_mems[name] = config_mem
			swap_usages[name] = swap_usage
			worksets[name] = swap_usage + active_mems[name]
			low_limit[name] = 400000
			balloons[name] = balloon_cur


			datas[name] = {}
			datas[name]['VM'] = name
			datas[name]['User'] = user
			datas[name]['Balloon'] = config_mem - balloon_cur
			datas[name]['Swap_usage'] = swap_usage
			datas[name]['Active_Mem'] = active_mems[name]
			datas[name]['Working_Set'] = worksets[name]

			self.logger.info("basic info: (%s) free_memory: %s, swap size: %s, workset: %s", \
				name, free_mem, swap_usages[name], worksets[name])

			if user not in config_mems_user or config_mems_user[user] is None:
				config_mems_user[user] = config_mem
			else:
				config_mems_user[user] += config_mem

			if user not in low_limit_user or low_limit_user[user] is None:
				low_limit_user[user] = low_limit[name]
			else:
				low_limit_user[user] += low_limit[name]


		total_predict, predict_user = self.algorithm.predictor(worksets, datas)
		# self.logger.info("predictors is %s", \
		# 	predict_user)

		if total_predict > total_mem:
			#self.logger.info("Congestion !!!")
			# user_allocate = self.algorithm.user_fairness(weights_user, predict_user, low_limit_user, config_mems_user, total_mem)
			# self.logger.info("user_allocate is %s", \
			# 	user_allocate)

			# vm_allocate = self.algorithm.vm_fairness(user_allocate, weights_vms, low_limit, config_mems)
			vm_allocate = self.algorithm.perf_diff(weights_vms, low_limit, config_mems, all_statistics, total_mem)
			self.logger.info("vm_allocate is %s", \
				vm_allocate)

			self.setBalloon(vm_allocate, vms, datas, 1)

			self.algorithm.update(vm_allocate, worksets, active_mems, datas)

			self.algorithm.check(weights_user, weights_vms)

		else:
			if self.start:
				self.initAllocate(vms, total_mem, datas, 0)
				self.start = False

			elif self.algorithm.check_adjust(balloons):
				vm_allocate = self.algorithm.meanByWork(total_predict, total_mem)

				self.setBalloon(vm_allocate, vms, datas, 0)
			else:
				for name, allocated in balloons.iteritems():
					datas[name]['Allocated'] = allocated
					datas[name]['Congestion'] = 0

		if self.plotter is not None:
			for name, data in datas.iteritems():
				self.plotter.plot(data)


class Algorithm:
	def __init__(self):
		self.logger = logging.getLogger('mom.Algorithm')
		self.used_mems_vm = {}
		self.allocated_mems = {}
		self.allocated_mems_user = {}
		self.total_mem_alltime = 0
		self.predict = {}
		self.workset_history = {}
		self.vm_user = {}
		self.total_progress = {}


	def predictor(self, worksets, datas):
		lever = 0.125
		total_predict = 0
		predict_user = {}
		if len(worksets) == 0:
			return 0, None
		for name, workset in worksets.iteritems():

			if name not in self.predict or self.predict[name] is None:
				self.predict[name] = workset
				total_predict += workset 
			else:
				prev_predict = self.predict[name]
				self.predict[name] = prev_predict * lever + (1 - lever)*workset
				total_predict += self.predict[name]

			datas[name]['Predict'] = self.predict[name]
			user = self.vm_user[name]
			if user not in predict_user or predict_user[user] is None:
				predict_user[user] = self.predict[name]
			else:
				predict_user[user] += self.predict[name]


		self.logger.info("pridictor is %s", \
			self.predict)
		return total_predict, predict_user


	def user_fairness(self, weights, predicts, low_limit, config_mems, total_mem):
		allocates = {}
		M = total_mem
		T = self.total_mem_alltime
		users = list(predicts.keys())
		users_temp = list(users)
		for name in users_temp:
			if predicts[name] <= low_limit[name]:
				allocates[name] = low_limit[name]
				M -= low_limit[name]
				if name in self.allocated_mems_user:
					T -= self.allocated_mems_user[name]
				users.remove(name)
		while M > 0 and len(users) > 0:
			total_weights = 0
			for name in users:
				weight = weights[name]
				total_weights += weight
			deserved = {}
			for name in users:
				pre_allocation = 0
				if name in self.allocated_mems_user:
					pre_allocation = self.allocated_mems_user[name]

				weight = weights[name]
				deserved[name] = weight * (M + T) / total_weights - pre_allocation
			flag = 0
			users_temp = list(users)
			for name in users_temp:
				if predicts[name] < deserved[name]:
					flag = 1
					allocation = predicts[name]
					if allocation > config_mems[name]:
						allocation = config_mems[name]
					allocates[name] = allocation
					M -= allocation
					if name in self.allocated_mems_user:
						T -= self.allocated_mems_user[name]
					users.remove(name)
			if flag == 0:
				users_temp = list(users)
				for name in users_temp:
					allocation = deserved[name]
					if allocation < low_limit[name]:
						allocation = low_limit[name]
					elif allocation > config_mems[name]:
						allocation = config_mems[name]
					allocates[name] = allocation
					M -= allocation
					if name in self.allocated_mems_user:
						T -= self.allocated_mems_user[name]
					users.remove(name)

		return allocates


	def vm_fairness(self, user_allocate, weights, low_limit, config_mems):
		allocates = {}
		user_info = {}
		for vm, user in self.vm_user.iteritems():
			if user not in user_info or user_info[user] is None:
				user_info[user] = [vm]
			else:
				user_info[user].append(vm)

		for user, vms in user_info.iteritems():
			total_mem = user_allocate[user]
			prev_allo_user = 0
			if user in self.allocated_mems_user:
				prev_allo_user = self.allocated_mems_user[user]

			while len(vms) > 0 and total_mem > 0:
				denominator = 0
				new_weights = {}
				deserved = {}
				flag = 0
				for vm in vms:
					prev_workset = 0
					if vm in self.workset_history:
						prev_workset = self.workset_history[vm]

					weight = weights[vm]
					new_weight = (prev_workset + self.predict[vm]) * weight
					new_weights[vm] = new_weight
					denominator += new_weight

				vm_temp = list(vms)
				for vm in vm_temp:
					prev_allocated = 0
					if vm in self.allocated_mems:
						prev_allocated = self.allocated_mems[vm]
					# self.logger.info("VM: %s, prev_allo_user: %s, prev_allocated: %s, new_weights: %s, denominator: %s, total mem: %s", \
					# 	vm, prev_allo_user, prev_allocated, new_weights[vm], denominator, total_mem)
					allocation = (total_mem + prev_allo_user) * new_weights[vm] / denominator - prev_allocated
					# self.logger.info("vm is %s, prev_allocated is %s, prev_allo_user is %s", \
					# 	vm, prev_allocated, prev_allo_user)
					deserved[vm] = allocation

				for vm, allocation in deserved.iteritems():
					prev_allocated = 0
					if vm in self.allocated_mems:
						prev_allocated = self.allocated_mems[vm]
					if allocation < low_limit[vm]:
						allocates[vm] = low_limit[vm]
						flag = 1
						total_mem -= low_limit[vm]
						prev_allo_user -= prev_allocated
						vms.remove(vm)
					elif allocation > config_mems[vm]:
						allocates[vm] = config_mems[vm]
						flag = 1
						total_mem -= config_mems[vm]
						prev_allo_user -= prev_allocated
						vms.remove(vm)

				if flag == 0:
					for vm, allocation in deserved.iteritems():
						allocates[vm] = allocation
					break


		return allocates


	def update(self, final_allocate, worksets, used_mems, datas):
		for name, allocation in final_allocate.iteritems():
			if name not in self.allocated_mems or self.allocated_mems[name] is None:
					self.allocated_mems[name] = allocation
			else:
				self.allocated_mems[name] += allocation

			user = self.vm_user[name]
			if user not in self.allocated_mems_user or self.allocated_mems_user[user] is None:
					self.allocated_mems_user[user] = allocation
			else:
				self.allocated_mems_user[user] += allocation

			self.total_mem_alltime += allocation

		for name, workset in worksets.iteritems():
			if name not in self.workset_history or self.workset_history[name] is None:
				self.workset_history[name] = workset
			else:
				self.workset_history[name] += workset
			datas[name]['T_workset'] = self.workset_history[name]

		for name, used in used_mems.iteritems():
			if name not in self.used_mems_vm or self.used_mems_vm[name] is None:
				self.used_mems_vm[name] = used
			else:
				self.used_mems_vm[name] += used
			datas[name]['T_used'] = self.used_mems_vm[name]


		# self.logger.info("update info: \ntotal allocated per vm: %s, \ntotal allocated per user: %s, \ntotal workset: %s", \
		# 	self.allocated_mems, self.allocated_mems_user, self.workset_history)


	def check(self, weights_user, weights_vms):
		share_user = {}
		for user, allocation in self.allocated_mems_user.iteritems():
			share_user[user] = allocation / weights_user[user]
		#print(share_user)
		share_vms = {}
		for vm, allocation in self.allocated_mems.iteritems():
			share_vms[vm] = weights_vms[vm] * self.workset_history[vm] / allocation
		# print(weights_vms)
		# print(share_vms)


	def mean(self, total_predict, total_m):
		allocate = {}
		rest = (total_m - total_predict) / len(self.predict)
		for user, pred in self.predict.iteritems():
			allocate[user] = pred + rest
		return allocate


	def meanByWork(self, total_predict, total_m):
		allocate = {}
		denominator = 0
		for user, pred in self.predict.iteritems():
			denominator += pred

		for user, pred in self.predict.iteritems():
			allocate[user] = total_m * pred / denominator
		return allocate


	def check_adjust(self, balloons):
		for vm, balloon in balloons.iteritems():
			if self.predict[vm] > balloon:
				return True

		return False




	def progress_func(self, ratio):
		if ratio <= 0: 
			return 0
		return max(1.2*math.log(ratio)+1, 0)
		#return max(1.594296596*ratio - 0.60503133, 0)


	def perf_diff(self, weights_vms, low_limit, config_mems, all_statistics, total_mem):

		priorities = {}
		allocates = {}
		for vm, statistics in all_statistics.iteritems():
			for i in range(-1, -9, -1):
				if len(statistics) < -i:
					break
				cur = statistics[i]
				allocated = cur.get('balloon_cur')
				free = cur.get('mem_unused')
				swapusage = cur.get('swap_usage')
				used_mem = allocated - free
				workset = used_mem + swapusage

				progress = self.progress_func(float(used_mem)/float(workset))
				print(vm + " progress: " + str(progress) + " ration: " + str(float(used_mem)/float(workset)))
				if vm not in self.total_progress or self.total_progress[vm] is None:
					self.total_progress[vm] = progress
				else:
					self.total_progress[vm] += progress
			priorities[vm] = self.total_progress[vm] / weights_vms[vm]

		print(self.total_progress)

		for vm, low in low_limit.iteritems():
			allocates[vm] = low
			total_mem -= low

		sorted_x = sorted(priorities.items(), key=operator.itemgetter(1))
		for n in range(0, len(sorted_x)):
			vm = sorted_x[n][0]
			workset = self.predict[vm]
			if workset <= total_mem:
				allocates[vm] += workset
				total_mem -= workset
			else:
				allocates[vm] += total_mem
				break

		return allocates