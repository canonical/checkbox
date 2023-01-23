# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
"""
This module defines the Scenario class.

See Scenario class properties and the assert_* functions, as they serve as
the interface to a Scenario.
"""
import re
import time

from metabox.core.actions import Start, Expect, Send, SelectTestPlan
from metabox.core.aggregator import aggregator


class Scenario:
    """Definition of how to run a Checkbox session."""
    config_override = {}
    environment = {}
    launcher = None
    LAUNCHER_PATH = '/home/ubuntu/launcher.checkbox'

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = '{}.{}'.format(cls.__module__, cls.__name__)
        # If a scenario does not declare the modes it should run in,
        # assume it will run in both local and remote modes.
        if not hasattr(cls, "modes"):
            cls.modes = ["local", "remote"]
        # If a scenario does not include what version of Checkbox it should run
        # in, assume it will run in every possible ones, as defined in
        # configuration._decl_has_a_valid_origin().
        # TODO: don't hardcode it here, use shared values
        if not hasattr(cls, "origins"):
            cls.origins = ["source", "ppa", "classic-snap", "snap"]
        aggregator.add_scenario(cls)

    def __init__(self, mode, *releases):
        self.mode = mode
        self.releases = releases
        # machines set up by Runner.run()
        self.local_machine = None
        self.remote_machine = None
        self.service_machine = None
        self._checks = []
        self._ret_code = None
        self._stdout = ''
        self._stderr = ''
        self._pts = None

    def has_passed(self):
        """Check whether all the assertions passed."""
        return all(self._checks)

    def run(self):
        # Simple scenarios don't need to specify a START step
        if not any([isinstance(s, Start) for s in self.steps]):
            self.steps.insert(0, Start())
        for i, step in enumerate(self.steps):
            # Check how to start checkbox, interactively or not
            if isinstance(step, Start):
                interactive = False
                # CHECK if any EXPECT/SEND command follows
                # w/o a new call to START before it
                for next_step in self.steps[i + 1:]:
                    if isinstance(next_step, Start):
                        break
                    if isinstance(next_step, (Expect, Send, SelectTestPlan)):
                        interactive = True
                        break
                step.kwargs['interactive'] = interactive
            try:
                step(self)
            except TimeoutError:
                self._checks.append(False)
                break
        if self._pts:
            self._stdout = self._pts.stdout_data_full
            # Mute the PTS since we're about to stop the machine to avoid
            # getting empty log trace events
            self._pts.verbose = False

    def _assign_outcome(self, ret_code, stdout, stderr):
        """Store remnants of a machine that run the scenario."""
        self._ret_code = ret_code
        self._stdout = stdout
        self._stderr = stderr

    # TODO: add storing of what actually failed in the assert methods
    def assert_printed(self, pattern):
        """
        Check if during Checkbox execution a line produced that matches the
        pattern.
        :param patter: regular expresion to check against the lines.
        """
        regex = re.compile(pattern)
        self._checks.append(bool(regex.search(self._stdout)))

    def assert_not_printed(self, pattern):
        """
        Check if during Checkbox execution a line did not produced that matches
        the pattern.
        :param pattern: regular expression to check against the lines.
        """
        regex = re.compile(pattern)
        if self._pts:
            self._checks.append(
                bool(not regex.search(self._pts.stdout_data_full.decode(
                    'utf-8', errors='ignore'))))
        else:
            self._checks.append(bool(not regex.search(self._stdout)))

    def assert_ret_code(self, code):
        """Check if Checkbox returned given code."""
        self._checks.append(code == self._ret_code)

    def assertIn(self, member, container):
        self._checks.append(member in container)

    def assertEqual(self, first, second):
        self._checks.append(first == second)

    def assertNotEqual(self, first, second):
        self._checks.append(first != second)

    def start(self, cmd='', interactive=False, timeout=0):
        if self.mode == 'remote':
            outcome = self.start_all(interactive=interactive, timeout=timeout)
            if interactive:
                self._pts = outcome
            else:
                self._assign_outcome(*outcome)
        else:
            if self.launcher:
                cmd = self.LAUNCHER_PATH
            outcome = self.local_machine.start(
                cmd=cmd, env=self.environment,
                interactive=interactive, timeout=timeout)
            if interactive:
                self._pts = outcome
            else:
                self._assign_outcome(*outcome)

    def start_all(self, interactive=False, timeout=0):
        self.start_service()
        outcome = self.start_remote(interactive, timeout)
        if interactive:
            self._pts = outcome
        else:
            self._assign_outcome(*outcome)
        return outcome

    def start_remote(self, interactive=False, timeout=0):
        outcome = self.remote_machine.start_remote(
            self.service_machine.address, self.LAUNCHER_PATH, interactive,
            timeout=timeout)
        if interactive:
            self._pts = outcome
        else:
            self._assign_outcome(*outcome)
        return outcome

    def start_service(self, force=False):
        return self.service_machine.start_service(force)

    def expect(self, data, timeout=60):
        assert(self._pts is not None)
        outcome = self._pts.expect(data, timeout)
        self._checks.append(outcome)

    def send(self, data):
        assert(self._pts is not None)
        self._pts.send(data.encode('utf-8'), binary=True)

    def sleep(self, secs):
        time.sleep(secs)

    def signal(self, signal):
        assert(self._pts is not None)
        self._pts.send_signal(signal)

    def select_test_plan(self, testplan_id, timeout=60):
        assert(self._pts is not None)
        outcome = self._pts.select_test_plan(testplan_id, timeout)
        self._checks.append(outcome)

    def run_cmd(self, cmd, env={}, interactive=False, timeout=0, target='all'):
        if self.mode == 'remote':
            if target == 'remote':
                self.remote_machine.run_cmd(cmd, env, interactive, timeout)
            elif target == 'service':
                self.service_machine.run_cmd(cmd, env, interactive, timeout)
            else:
                self.remote_machine.run_cmd(cmd, env, interactive, timeout)
                self.service_machine.run_cmd(cmd, env, interactive, timeout)
        else:
            self.local_machine.run_cmd(cmd, env, interactive, timeout)

    def reboot(self, timeout=0, target='all'):
        if self.mode == 'remote':
            if target == 'remote':
                self.remote_machine.reboot(timeout)
            elif target == 'service':
                self.service_machine.reboot(timeout)
            else:
                self.remote_machine.reboot(timeout)
                self.service_machine.reboot(timeout)
        else:
            self.local_machine.reboot(timeout)

    def put(self, filepath, data, mode=None, uid=1000, gid=1000, target='all'):
        if self.mode == 'remote':
            if target == 'remote':
                self.remote_machine.put(filepath, data, mode, uid, gid)
            elif target == 'service':
                self.service_machine.put(filepath, data, mode, uid, gid)
            else:
                self.remote_machine.put(filepath, data, mode, uid, gid)
                self.service_machine.put(filepath, data, mode, uid, gid)
        else:
            self.local_machine.put(filepath, data, mode, uid, gid)

    def switch_on_networking(self, target='all'):
        if self.mode == 'remote':
            if target == 'remote':
                self.remote_machine.switch_on_networking()
            elif target == 'service':
                self.service_machine.switch_on_networking()
            else:
                self.remote_machine.switch_on_networking()
                self.service_machine.switch_on_networking()
        else:
            self.local_machine.switch_on_networking()

    def switch_off_networking(self, target='all'):
        if self.mode == 'remote':
            if target == 'remote':
                self.remote_machine.switch_off_networking()
            elif target == 'service':
                self.service_machine.switch_off_networking()
            else:
                self.remote_machine.switch_off_networking()
                self.service_machine.switch_off_networking()
        else:
            self.local_machine.switch_off_networking()

    def stop_service(self):
        return self.service_machine.stop_service()

    def reboot_service(self):
        return self.service_machine.reboot_service()

    def is_service_active(self):
        return self.service_machine.is_service_active()
