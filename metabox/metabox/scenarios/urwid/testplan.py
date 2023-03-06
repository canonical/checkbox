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
import metabox.core.keys as keys
from metabox.core.actions import Expect
from metabox.core.actions import Send
from metabox.core.actions import SelectTestPlan
from metabox.core.scenario import Scenario


class UrwidTestPlanSelection(Scenario):

    modes = ['local']
    steps = [
        Expect('Select test plan'),
        SelectTestPlan('com.canonical.certification::stress-pm-graph'),
        SelectTestPlan(
            'com.canonical.certification::'
            'after-suspend-graphics-discrete-gpu-cert-automated'),
        SelectTestPlan(
            'com.canonical.certification::client-cert-desktop-18-04'),
        Send(keys.KEY_ENTER),
        Expect('Choose tests to run on your system:'),
        Send('d' + keys.KEY_ENTER),
        Expect('Choose tests to run on your system:'),
        Send(keys.KEY_DOWN * 18 + keys.KEY_SPACE + 't'),
        Expect('System Manifest:'),
        Send('y' * 11 + 't'),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Finish'),
        Send('f' + keys.KEY_ENTER),
    ]
