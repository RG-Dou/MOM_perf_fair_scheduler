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
from sklearn.linear_model import LinearRegression
import numpy as np

DEFAULT_POLICY_NAME = "50_main_"
Max_free = 200000
Min_share = 40000
Epoch = 100

AVE_LEN = 40
WINDOW = 40

# RPPolicy_1.0.1
class RPPolicy:
	def __init__(self):
		self.logger = logging.getLogger('mom.RPPolicy')
		self.policy_sem = threading.Semaphore()
		self.start = True
		self.fields = set(['VM', 'Used', 'Swap', 'Worksize', 
							'Balloon', 'User', 'Start-time', 
							'IOwait', 'Softirq', 'System',
							'Total', 'Speed', 'Rate', 'Allocated', 
							'Pagefault'])
		self.fit_fields = set(['users', 'standard_users', 'ave_users',
							'pfs', 'ave_pfs', 'ins_speed'])
		self.VM_Infos = {}
		self.count = 0
		self.givers = {}
		self.takers = {}


	def set_policy(self, type, total_mem, plot_dir, alpha, beta):
		self.type = type
		self.total_mem_ratio = total_mem
		self.alpha = alpha
		self.beta = beta
		name = 'Policy'
		if plot_dir != '':
			self.plotter = Plotter(plot_dir, name)
			self.plotter.setFields(self.fields.union(self.fit_fields))
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
			if rate > 0:
				ranks[info] = rate

		rank_l = sorted(ranks.items(), lambda x, y: cmp(x[1], y[1]))

		N = len(rank_l)
		if N < 2:
			return
		index_g = N-1

		giver = rank_l[index_g][0]
		giver_blk = giver.dist2low()
		while giver_blk <= 0 and index_g > 0:
			index_g -= 1
			giver = rank_l[index_g][0]
			giver_blk = giver.dist2low()

		taker = rank_l[0][0]
		taker_blk = taker.dist2high()

		if index_g > 0:
			final_blk = min(giver_blk, taker_blk, Min_share)

			self.givers[giver] = -final_blk
			self.takers[taker] = final_blk


	def meanByFree(self):
		total_free = 0
		frees = {}
		for name, info in self.VM_Infos.iteritems():
			if info.getAttribute('Used') < info.getAttribute('Min'):
				frees[name] = info.getAttribute('Allocated') - info.getAttribute('Min')
			else:
				frees[name] = info.getAttribute('Free')

			total_free += frees[name]

		target = total_free/len(self.VM_Infos)
		for name, info in self.VM_Infos.iteritems():
			free = frees[name]
			blk = target - free
			if blk < 0:
				self.givers[info] = blk
			else:
				self.takers[info] = blk

	def seperate(self):
		busy, idle = [], []
		for name, info in self.VM_Infos.iteritems():
			if info.getAttribute('Free') < Max_free:
				busy.append(info)
			else:
				idle.append(info)
		return busy,idle


	def trigger_balloon(self, maps):
		for info, blk in maps.iteritems():
			info.addAttribute('Allocated', blk)
			info.setBalloon()


	def check(self, total_mem):
		total = 0
		for name, info in self.VM_Infos.iteritems():
			total += info.getAttribute('Allocated')

		self.logger.info("Total Allocated: %s, Distance : %s", total, total - total_mem)


	def evaluate(self, host, guest_list):

		self.givers, self.takers = {},{}

		total_mem = host.mem_available * float(self.total_mem_ratio)

		for guest in guest_list:
			name = guest.Prop('name')
			if name not in self.VM_Infos or self.VM_Infos[name] is None:
				info = VM_Info(name, self.alpha, self.beta)
				info.initAttribute(guest)
				self.VM_Infos[name] = info
			else:
				info = self.VM_Infos[name]
				info.update(guest)


		if self.start:
			self.count += 1
			self.firstTime(total_mem)
			if self.count >= AVE_LEN:
				self.start = False
			return

		busy_vm, idle_vm = self.seperate()

		if len(idle_vm) == 0:
			self.dynamic_allocate()
		elif len(busy_vm) > 0:
			self.meanByFree()

		self.check(total_mem)

		self.trigger_balloon(self.givers)
		self.trigger_balloon(self.takers)


		if self.plotter is not None:
			for name, info in self.VM_Infos.iteritems():
				data = info.getData(self.fields, self.fit_fields)
				self.plotter.plot(data)


class VM_Info:

	def __init__(self, name, alpha, beta):
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
		self.fitting = Fitting(name, alpha, beta)


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
		#standard = (self.getAttribute('Total') - self.getAttribute('Start-time'))*self.getAttribute('Slope')
		speed = self.fitting.getSpeed()

		if speed is not None:
			self.setAttribute('Speed', speed)
			self.setAttribute('Rate', speed / self.getAttribute('Weight'))


	def initAttribute(self, guest):
		self.setAttribute('Min', 900000)
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

		growUser = guest.user - self.getAttribute('User')
		growPf = guest.major_fault - self.getAttribute('Pagefault')
		self.setAttribute('User', guest.user)
		self.setAttribute('Pagefault', guest.major_fault)
		if guest.user == self.getAttribute('Start-user'):
			self.setAttribute('Start-time', guest.total)
		else:
			self.fitting.update(growUser, growPf, guest.total)

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


	def getData(self, keys, fit_keys):
		data = {}
		for key in keys:
			data[key] = self.getAttribute(key)
		for key in fit_keys:
			data[key] = self.fitting.getAttribute(key)

		return data


class Fitting:
	def __init__(self, name, alpha, beta):
		self.logger = logging.getLogger('mom.Policy.Fitting')
		self.name = name
		self.keys = set(['users', 'standard_users', 'ave_users',
							'pfs', 'ave_pfs', 'ins_speed', 'time'])
		self.attributes = {}
		for key in self.keys:
			self.attributes[key] = np.arange(0)
		self.alpha = alpha
		self.beta = beta
		self.status = 1


	def getAttribute(self, key):
		if key in self.keys:
			if len(self.attributes[key]) > 0:
				return self.attributes[key][-1]
			else:
				return None
		else:
			self.logger.error("invalid attribute: %s", key)


	def mean_value(self, key):
		mean = 0
		if key == 'user' and len(self.attributes['users']) >= AVE_LEN:
			mean = np.sum(self.attributes['users'][-1-AVE_LEN:-1])/AVE_LEN
		elif key == 'pf' and len(self.attributes['pfs']) >= AVE_LEN:
			mean = np.sum(self.attributes['pfs'][-1-AVE_LEN:-1])/AVE_LEN
		else:
			return None

		return mean


	def update(self, value1, value2, value3):
		self.attributes['users'] = np.append(self.attributes['users'], [value1])
		mean = self.mean_value('user')
		if mean is not None:
			self.attributes['ave_users'] = np.append(self.attributes['ave_users'], [mean])

		self.attributes['pfs'] = np.append(self.attributes['pfs'], [value2])
		mean = self.mean_value('pf')
		if mean is not None:
			self.attributes['ave_pfs'] = np.append(self.attributes['ave_pfs'], [mean])

		self.attributes['time'] = np.append(self.attributes['time'], [value3/100])


	def getSpeed(self):
		# self.logger.info("users:%s", self.attributes['users'])
		# self.logger.info("standard users:%s", self.attributes['standard_users'])
		# self.logger.info("average users:%s", self.attributes['ave_users'])
		# self.logger.info("page fault:%s", self.attributes['pfs'])
		# self.logger.info("average page fault:%s", self.attributes['ave_pfs'])
		# self.logger.info("instant speed:%s", self.attributes['ins_speed'])
		if len(self.attributes['ave_users']) < WINDOW:
			return None
		else:
			standard = self.estimated()

			if self.status == 1:
				for i in range(0, len(self.attributes['users'])):
					self.appendStandard(standard, i)
				self.status = 2
			self.appendStandard(standard, -1)

			speed = np.mean(self.attributes['ins_speed'])
			return speed


	def getWeight(self, dist, age):
		weights = np.arange(0)
		for i in range(0, len(dist)):
			weight = math.pow(self.beta, dist[i]) * math.pow(self.alpha, age[i])
			weights = np.append(weights, [weight])
		return weights


	def estimated(self):
		if len(self.attributes['ave_users']) >= WINDOW:
			x = self.attributes['ave_pfs'].reshape(-1,1)
			y = self.attributes['ave_users']
			age = self.attributes['time'][-1] - self.attributes['time']
			weights = self.getWeight(self.attributes['ave_pfs'], age)
			if np.sum(weights) == 0:
				weights = weights + 1
			reg = LinearRegression().fit(x, y, sample_weight = weights)
			return reg.intercept_
		else:
			return None


	def appendStandard(self, standard, index):
		if standard < self.attributes['users'][index]:
			standard = self.attributes['users'][index]
		# elif self.attributes['pfs'][index] < 100:
		# 	standard = self.attributes['users'][index]
		if standard > Epoch:
			standard = Epoch

		self.attributes['standard_users'] = np.append(self.attributes['standard_users'], [standard])
		speed = 1
		if self.attributes['standard_users'][index] != 0:
			speed = float(self.attributes['users'][index])/float(self.attributes['standard_users'][index])
		self.attributes['ins_speed'] = np.append(self.attributes['ins_speed'], [speed])