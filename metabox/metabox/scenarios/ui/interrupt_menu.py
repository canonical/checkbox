# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.
import textwrap

import metabox.core.keys as keys
from metabox.core.actions import Expect, Send, Start, Signal
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("ui", "interact")
class CtrlCMenu(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::tired_test_plan
        forced = yes
        [test selection]
        forced = yes
        """)

    steps = [
        Start(),
        Expect("ID: 2021.com.canonical.certification::sleep_1000s"),
        Signal(keys.SIGINT),
        Expect("Interruption"),
        # Do nothing, go back to the test
        Expect("(X) Nothing"),
        Send(keys.KEY_ENTER),
        Expect(
            "In progress: 2021.com.canonical.certification::sleep_1000s (1/1)"
        ),
        Signal(keys.SIGINT),
        Expect("Interruption!"),
        Expect("Press <Enter> or <ESC> to continue"),
        # we are now disconnecting the controller
        Send(keys.KEY_DOWN),
        Send(keys.KEY_DOWN),
        Send(keys.KEY_SPACE),
        Expect("(X) Pause"),
        Send(keys.KEY_ENTER),
        Start(target="controller"),
        Expect(
            "In progress: 2021.com.canonical.certification::sleep_1000s (1/1)"
        ),
        Signal(keys.SIGINT),
        Expect("Interruption!"),
        Expect("Press <Enter> or <ESC> to continue"),
        # we are now crashing the test to continue the session
        Send(keys.KEY_DOWN),
        Send(keys.KEY_SPACE),
        Expect("(X) Stop the test case in progress"),
        Send(keys.KEY_ENTER),
        Expect("Crashed Jobs"),
    ]
