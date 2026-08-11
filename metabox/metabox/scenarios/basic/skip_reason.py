# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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

from metabox.core.scenario import Scenario
from metabox.core.actions import AssertPrinted, Start
from metabox.core.utils import tag


@tag("skip-reason", "basic")
class SkipReasonShownUI(Scenario):
    modes = ["remote"]

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::skipping_test_plan
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        [manifest]
        2021.com.canonical.certification::skipping_test_manifest=False
        """)
    steps = [
        Start(),
        AssertPrinted("Job cannot be started because of unmet resource:"),
        AssertPrinted(r'requires_skip\.missing == "missing value"'),
        AssertPrinted("Job cannot be started because of failed dependency:"),
        AssertPrinted("failing_job"),
        AssertPrinted("Job cannot be started because of unmet manifest:"),
        AssertPrinted("skipping_test_manifest"),
    ]
