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


@tag("xfail", "basic")
class XfailResults(Scenario):
    """
    Run the xfail_testplan and verify that xfail jobs report the
    correct outcomes:

    - xfailing_job_failing: used to test xfail in the unit on a passing test
    - xfailing_job_passing: used to test xfail in the unit
    - failing_job: used to test inline xfail override
    - basic-shell-failing: used to test xfail_overrides
    """

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::xfail_testplan
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        Start(),
        Expect("xfailing_job_failing"),
        Expect("passed unexpectedly"),
        Expect("xfailing_job_passing"),
        Expect("failed as expected"),
        Expect("failing_job"),
        Expect("failed as expected"),
        Expect("basic-shell-failing"),
        Expect("failed as expected"),
    ]
