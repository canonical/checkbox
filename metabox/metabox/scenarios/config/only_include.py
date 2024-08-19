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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
import textwrap

from metabox.core.actions import (
    AssertPrinted,
    AssertNotPrinted,
    AssertRetCode,
    Start,
)
from metabox.core.utils import tag
from metabox.core.scenario import Scenario


@tag("test_selection", "only_include", "return_code")
class TestSelectionOnlyIncludeEmpty(Scenario):
    """
    Try to only_include a test that is not in the test plan, nothing should run
    """

    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::stress-only-include
        forced = yes
        [test selection]
        forced = yes
        only_include = .*storage-preinserted.*
        """
    )
    steps = [Start(), AssertRetCode(1)]


@tag("test_selection", "only_include", "return_code")
class TestSelectionOnlyIncludeNominal(Scenario):
    """
    only_include only pulls jobs and their direct/indirect dependencies +
    all bootstrap jobs. exclude has the precedence over only_include
    """

    launcher = textwrap.dedent(
        """
        #!/usr/bin/env checkbox-cli
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::stress_only_include
        forced = yes
        [test selection]
        forced = yes
        exclude = .*launcher_removed_target
        only_include = .*target
        """
    )
    steps = [
        Start(),
        AssertPrinted("include_direct_dependency"),
        AssertPrinted("include_indirect_dependency"),
        AssertNotPrinted("include_not_included"),
        AssertPrinted("include_target"),
        AssertNotPrinted("include_exclude_target"),
        AssertNotPrinted("include_launcher_removed_target"),
        AssertPrinted("include_generated_job_template_"),
        AssertPrinted("nested_indirect_resource"),
        AssertPrinted("nested_direct_dependency"),
        AssertPrinted("nested_indirect_dependency"),
        AssertNotPrinted("nested_not_included"),
        AssertPrinted("nested_target"),
        AssertPrinted("nested_generated_job_template_"),
        AssertNotPrinted("nested_exclude_target"),
        AssertRetCode(0),
    ]
