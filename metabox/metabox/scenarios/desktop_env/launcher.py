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
import textwrap

import metabox.core.keys as keys
from metabox.core.actions import AssertNotPrinted
from metabox.core.actions import Expect
from metabox.core.actions import RunCmd
from metabox.core.actions import Send
from metabox.core.scenario import Scenario
from metabox.core.utils import _re


class GlxGears(Scenario):

    launcher = textwrap.dedent("""
    [launcher]
    launcher_version = 1
    stock_reports = text
    [test plan]
    unit = 2021.com.canonical.certification::display-manual
    forced = yes
    [test selection]
    forced = yes
    """)
    steps = [
        Expect('Pick an action'),
        Send(keys.KEY_ENTER),
        Expect('FPS'),
        RunCmd('pkill -2 glxgears'),
        Expect('Pick an action'),
        Send('p' + keys.KEY_ENTER),
        Expect(_re('(☑|job passed).*Test that glxgears works')),
    ]


class AudioPlayback(Scenario):

    launcher = textwrap.dedent("""
    [launcher]
    launcher_version = 1
    stock_reports = text
    [test plan]
    unit = 2021.com.canonical.certification::audio-manual
    forced = yes
    [test selection]
    forced = yes
    """)
    steps = [
        Expect('Pick an action'),
        Send(keys.KEY_ENTER),
        Expect('Pipeline initialized, now starting playback.'),
        Expect('Pick an action', timeout=10),
        Send('p' + keys.KEY_ENTER),
        AssertNotPrinted('Connection failure: Connection refused'),
        Expect(_re('(☑|job passed).*audio/playback_auto'), timeout=10),
    ]
