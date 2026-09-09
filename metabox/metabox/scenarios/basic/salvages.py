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


@tag("salvages", "basic")
class SalvagesSkipped(Scenario):
    modes = ["remote", "local"]

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::salvages_test_plan
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
        AssertPrinted("salvages_skipped_by_dependency"),
        AssertPrinted("Job cannot be started because of failed dependency:"),
        AssertPrinted("skipped_by_dependency"),
        AssertPrinted("salvages_skipped_by_requirement"),
        AssertPrinted("Job cannot be started because of failed dependency:"),
        AssertPrinted("simple_skipped"),
        AssertPrinted("salvages_skipped_by_manifest"),
        AssertPrinted("Job cannot be started because of failed dependency:"),
        AssertPrinted("skipped_by_manifest"),
    ]
