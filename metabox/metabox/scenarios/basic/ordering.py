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
class OrderingAfterSuspend(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::ordering_after_suspend
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
            r"(?s)"
            r".*ordering_7_A"
            r".*ordering_7_B"
            r".*suspend/suspend_advanced_auto"
            r".*after-suspend-ordering_7_B"
            r".*after-suspend-ordering_7_A"
        ),
    ]
