# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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
from metabox.core.actions import AssertRetCode, Start, AssertPrinted
from metabox.core.utils import tag


@tag("template", "basic")
class InvalidUnitErrorUserVisible(Scenario):
    """
    Check that when Checkbox expands a template it correctly detects
    if some of the expanded units are invalid and reports it to the user
    """

    launcher = textwrap.dedent(
        """
        #!/usr/bin/env checkbox-cli
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::crash_invalid_template_id
        forced = yes
        [test selection]
        forced=yes
        """
    )
    steps = [
        Start(),
        AssertPrinted(
            "2021.com.canonical.certification::template_validation_testing_somename"
        ),
        AssertPrinted("Outcome: job passed"),
        AssertPrinted("Validation failed with message:"),
        AssertPrinted("Outcome: job failed"),
        AssertRetCode(1),
    ]
