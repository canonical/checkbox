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
from metabox.core.actions import AssertPrinted
from metabox.core.actions import AssertRetCode
from metabox.core.actions import Expect
from metabox.core.actions import Send
from metabox.core.actions import Start
from metabox.core.scenario import Scenario


class RunTestplan(Scenario):

    modes = ['local']
    config_override = {'local': {'releases': ['bionic']}}
    steps = [
        Start('run 2021.com.canonical.certification::'
              'basic-automated-passing', timeout=30),
        AssertRetCode(0)
    ]


class RunFailingTestplan(Scenario):

    modes = ['local']
    steps = [
        Start('run 2021.com.canonical.certification::'
              'basic-automated-failing', timeout=30),
        AssertRetCode(0)
    ]


class RunTestplanWithEnvvar(Scenario):

    modes = ['local']
    environment = {'foo': 42}
    steps = [
        Start('run 2021.com.canonical.certification::basic-automated',
              timeout=30),
        AssertPrinted("foo: 42"),
    ]


class RunManualplan(Scenario):

    modes = ['local']
    steps = [
        Start('run 2021.com.canonical.certification::basic-manual'),
        Expect('Pick an action'),
        Send(keys.KEY_ENTER),
        Expect('Pick an action', timeout=30),
        Send('p' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send(keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('p' + keys.KEY_ENTER),
        Expect(' [32;1m☑ [0m: '
               'A simple user interaction and verification job'),
    ]
