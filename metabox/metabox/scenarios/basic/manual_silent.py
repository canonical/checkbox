# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

from metabox.core.actions import Expect, Start
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("manual", "silent", "basic")
class SilentManualJobsAreSkipped(Scenario):
    modes = ["local", "remote"]

    launcher = textwrap.dedent("""
        [ui]
        type = silent
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::basic-manual-one-per-kind
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect("2021.com.canonical.certification::basic/manual"),
        Expect("Outcome: job manually skipped"),
        Expect("2021.com.canonical.certification::basic/user-interact-verify"),
        Expect("Outcome: job manually skipped"),
    ]
