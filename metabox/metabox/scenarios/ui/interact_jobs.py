# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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
from metabox.core.actions import (
    Expect,
    Send,
    Start,
    ExpectNot
)
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("manual", "interact")
class ManualInteractQuit(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-manual-resume
        forced = yes
        [test selection]
        forced = yes
        """
    )

    steps = [
        Start(),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("save the session and quit"),
        Send("q" + keys.KEY_ENTER),
        # if q is pressed, checkbox should exit instead of going ahead printing
        # results
        ExpectNot("Results")
    ]
