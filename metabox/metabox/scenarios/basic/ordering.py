# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
    AssertRetCode,
    Start,
)
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("ordering")
class OrderingDepends(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_depends
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """
    )
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : ordering_1_A\n"
            r".*job passed   : ordering_1_B\n"
            r".*job passed   : ordering_1_C"
        ),
    ]


@tag("ordering")
class OrderingBefore(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_before
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """
    )
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : ordering_2_A\n"
            r".*job passed   : ordering_2_B\n"
            r".*job passed   : ordering_2_C"
        ),
    ]


@tag("ordering")
class OrderingMixed(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_mixed
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
"""
    )
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : ordering_3_A\n"
            r".*job passed   : ordering_3_B\n"
            r".*job passed   : ordering_3_C"
        ),
    ]


@tag("ordering")
class OrderingResource(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_resource
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """
    )
    steps = [
        Start(),
        AssertPrinted(
            r"(?m).*job passed   : ordering_4_R\n.*job passed   : ordering_4_A"
        ),
    ]


@tag("ordering")
class OrderingDependsCycle(Scenario):
    modes = ["local"]
    steps = [
        Start("run 2021.com.canonical.certification::ordering_before_cycle"),
        AssertPrinted(r"Dependency problem: dependency cycle detected"),
    ]


@tag("ordering")
class OrderingBeforeCycle(Scenario):
    modes = ["local"]
    steps = [
        Start("run 2021.com.canonical.certification::ordering_before_cycle"),
        AssertPrinted(r"Dependency problem: dependency cycle detected"),
    ]


@tag("ordering")
class OrderingGroups(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_groups
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """
    )
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*groups_1_A\n"
            r".*groups_1_g1\n"
            r".*groups_1_g2\n"
            r".*groups_1_B\n"
            r".*groups_1_C\n"
        ),
    ]


@tag("ordering")
class OrderingGroupsCycle(Scenario):
    modes = ["local"]
    steps = [
        Start("run 2021.com.canonical.certification::ordering_groups_cycle"),
        AssertPrinted(r"Dependency problem: dependency cycle detected"),
    ]


@tag("ordering")
class OrderingGroupsTemplate(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_groups_template
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """
    )
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*setup_order_1\n"
            r".*test_feature_order_A_1\n"
            r".*test_feature_order_B_1\n"
            r".*teardown_order_1\n"
            r".*setup_order_2\n"
            r".*test_feature_order_A_2\n"
            r".*test_feature_order_B_2\n"
            r".*teardown_order_2\n"
        ),
    ]
