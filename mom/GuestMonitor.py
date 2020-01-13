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

import threading
import ConfigParser
from subprocess import *
import time
import re
import logging
from mom.Monitor import Monitor
from mom.Collectors import Collector


class GuestMonitor(Monitor):
    """
    A GuestMonitor thread collects and reports statistics about 1 running guest
    """
    def __init__(self, config, info, hypervisor_iface):
        self.config = config
        self.logger = logging.getLogger('mom.GuestMonitor')
        self.interval = self.config.getint('main', 'guest-monitor-interval')

        Monitor.__init__(self, config, info['name'])
        self.data_sem.acquire()
        self.properties.update(info)
        self.properties['hypervisor_iface'] = hypervisor_iface
        # Modified by DRG
        self.properties['userID'] = self.get_guest_userid(config, info['name'])
        self.properties['weight-user'] = self.get_user_weight(config, self.properties['userID'])
        self.properties['weight-vm'] = self.get_guest_weight(config, info['name'])
        self.properties['slope'] = self.get_guest_slope(config, info['name'])

        self.data_sem.release()

        collector_list = self.config.get('guest', 'collectors')
        self.collectors = Collector.get_collectors(collector_list,
                            self.properties, self.config)
        if self.collectors is None:
            self.logger.error("Guest Monitor initialization failed")

    def getGuestName(self):
        """
        Provide structured access to the guest name without calling hypervisor
        interface.
        """
        return self.properties.get('name')


    """
    Modified by DRG
    """
    def get_guest_userid(self, config, name):
        """
        There is no simple, standardized way to determine a guest's weight.
        We side-step the problem and make use of a helper program if specified.

        XXX: This is a security hole!  We are running a user-specified command!
        """
        try:
            prog = self.config.get('main', 'name-to-user')
        except KeyError:
            return 0
        try:
            output = Popen([prog, name], stdout=PIPE).communicate()[0]
            return output[:-1]
        except OSError, (errno, strerror):
            self.logger.warn("Cannot call name-to-user: %s", strerror)
            return None


    """
    Modified by DRG
    """
    def get_user_weight(self, config, name):
        """
        There is no simple, standardized way to determine a guest's weight.
        We side-step the problem and make use of a helper program if specified.

        XXX: This is a security hole!  We are running a user-specified command!
        """
        try:
            prog = self.config.get('main', 'name-to-user-weights')
        except KeyError:
            return 0
        try:
            output = Popen([prog, name], stdout=PIPE).communicate()[0]
        except OSError, (errno, strerror):
            self.logger.warn("Cannot call name-to-user-weights: %s", strerror)
            return None
        try:
            weight = int(output)
            if weight <= 0:
                self.logger.warn("Output from name-to-user-weights %s is not positive" \
                             "weight. (output = '%s')", name, output)
                return 0
            else:
                return weight
        except ValueError:
                self.logger.warn("Output from name-to-user-weights %s is not a number" \
                             "weight. (output = '%s')", name, output)
                return 0


    """
    Modified by DRG
    """
    def get_guest_weight(self, config, name):
        """
        There is no simple, standardized way to determine a guest's weight.
        We side-step the problem and make use of a helper program if specified.

        XXX: This is a security hole!  We are running a user-specified command!
        """
        try:
            prog = self.config.get('main', 'name-to-vm-weights')
        except KeyError:
            return 0
        try:
            output = Popen([prog, name], stdout=PIPE).communicate()[0]
        except OSError, (errno, strerror):
            self.logger.warn("Cannot call name-to-vm-weights: %s", strerror)
            return None
        try:
            weight = int(output)
            if weight <= 0:
                self.logger.warn("Output from name-to-vm-weights %s is not positive" \
                             "weight. (output = '%s')", name, output)
                return 0
            else:
                return weight
        except ValueError:
                self.logger.warn("Output from name-to-vm-weights %s is not a number" \
                             "weight. (output = '%s')", name, output)
                return 0

    """
    Modified by DRG
    """
    def get_guest_slope(self, config, name):
        """
        There is no simple, standardized way to determine a guest's weight.
        We side-step the problem and make use of a helper program if specified.

        XXX: This is a security hole!  We are running a user-specified command!
        """
        try:
            prog = self.config.get('main', 'name-to-slope')
        except KeyError:
            return 0
        try:
            output = Popen([prog, name], stdout=PIPE).communicate()[0]
        except OSError, (errno, strerror):
            self.logger.warn("Cannot call name-to-slope: %s", strerror)
            return None
        try:
            slope = float(output)
            if slope <= 0:
                self.logger.warn("Output from name-to-slope %s is not positive" \
                             "slope. (output = '%s')", name, output)
                return 0
            else:
                return slope
        except ValueError:
                self.logger.warn("Output from name-to-slope %s is not a number" \
                             "slope. (output = '%s')", name, output)
                return 0


class GuestMonitorThread(threading.Thread):
    def __init__(self, info, monitor):
        threading.Thread.__init__(self, name="guest:%s" % id)

        self.setName("GuestMonitor-%s" % info['name'])
        self.setDaemon(True)
        self.logger = logging.getLogger('mom.GuestMonitor.Thread')

        self._mon = monitor

    def run(self):
        try:
            self.logger.info("%s starting", self.getName())
            while self._mon.should_run():
                self._mon.collect()
                time.sleep(self._mon.interval)
        except Exception:
            self.logger.exception("%s crashed", self.getName())
        else:
            self.logger.info("%s ending", self.getName())
