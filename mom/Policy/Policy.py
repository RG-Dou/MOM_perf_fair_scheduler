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
from Parser import Evaluator
from Parser import get_code
from Parser import PolicyError

DEFAULT_POLICY_NAME = "50_main_"

class Policy:
    def __init__(self):
        self.logger = logging.getLogger('mom.Policy')
        self.policy_sem = threading.Semaphore()
        self.evaluator = Evaluator()
        self.clear_policy()

    def get_strings(self, name=None):
        with self.policy_sem:
            if name is None:
                return self.policy_strings.copy()
            else:
                return self.policy_strings.get(name)

    def get_string(self):
        with self.policy_sem:
            return self._cat_policies() or '0'

    def _cat_policies(self):
        keys = sorted(self.policy_strings.iterkeys())
        return '\n'.join(self.policy_strings[k] for k in keys)

    def set_policy(self, name, policyStr):
        if name is None:
            name = DEFAULT_POLICY_NAME
        with self.policy_sem:
            oldStr = self.policy_strings.get(name)
            if policyStr is None:
                try:
                    del self.policy_strings[name]
                except KeyError:
                    pass
            else:
                self.policy_strings[name] = policyStr
            try:
                self.code = get_code(self.evaluator, self._cat_policies())
            except PolicyError, e:
                self.logger.warn("Unable to load policy: %s" % e)
                if oldStr is None:
                    del self.policy_strings[name]
                else:
                    self.policy_strings[name] = oldStr
                return False
            return True

    def clear_policy(self):
        with self.policy_sem:
            self.policy_strings = {}
            self.code = []

    def evaluate(self, host, guest_list):
        results = []
        self.evaluator.stack.set('Host', host, alloc=True)
        self.evaluator.stack.set('Guests', guest_list, alloc=True)

        with self.policy_sem:
            try:
                for expr in self.code:
                    results.append(self.evaluator.eval(expr))
                self.logger.debug("Results: %s" % results)
            except PolicyError as e:
                self.logger.error("Policy error: %s" % e)
                return False
            except Exception as e:
                self.logger.error("Unexpected error when evaluating policy: %s" % e)
                return False
        return True
