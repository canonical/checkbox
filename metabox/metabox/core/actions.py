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
This module defines the Actions classes.

"""

__all__ = [
    "Start", "Expect", "Send", "SelectTestPlan",
    "AssertPrinted", "AssertNotPrinted", "AssertRetCode",
    "AssertServiceActive", "Sleep", "RunCmd", "Signal", "Reboot",
    "NetUp", "NetDown", "Put"
]


class ActionBase:
    handler = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, scn):
        assert(self.handler is not None)
        getattr(scn, self.handler)(*self.args, **self.kwargs)


class Start(ActionBase):
    handler = 'start'


class Expect(ActionBase):
    handler = 'expect'


class Send(ActionBase):
    handler = 'send'


class SelectTestPlan(ActionBase):
    handler = 'select_test_plan'


class AssertPrinted(ActionBase):
    handler = 'assert_printed'


class AssertNotPrinted(ActionBase):
    handler = 'assert_not_printed'


class AssertRetCode(ActionBase):
    handler = 'assert_ret_code'


class AssertServiceActive(ActionBase):
    handler = 'is_service_active'


class Sleep(ActionBase):
    handler = 'sleep'


class RunCmd(ActionBase):
    handler = 'run_cmd'


class Signal(ActionBase):
    handler = 'signal'


class Reboot(ActionBase):
    handler = 'reboot'


class NetUp(ActionBase):
    handler = 'switch_on_networking'


class NetDown(ActionBase):
    handler = 'switch_off_networking'


class Put(ActionBase):
    handler = 'put'
