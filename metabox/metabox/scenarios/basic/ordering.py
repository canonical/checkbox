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

from metabox.core.actions import (
    AssertPrinted,
    Start,
)
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("ordering")
class OrderingDepends(Scenario):
    steps = [
        Start("run 2021.com.canonical.certification::ordering_depends"),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : test_1_A\n"
            r".*job passed   : test_1_B\n"
            r".*job passed   : test_1_C"
        ),
    ]


@tag("ordering")
class OrderingBefore(Scenario):
    steps = [
        Start("run 2021.com.canonical.certification::ordering_before"),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : test_2_A\n"
            r".*job passed   : test_2_B\n"
            r".*job passed   : test_2_C"
        ),
    ]


@tag("ordering")
class OrderingMixed(Scenario):
    steps = [
        Start("run 2021.com.canonical.certification::ordering_mixed"),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : test_3_A\n"
            r".*job passed   : test_3_B\n"
            r".*job passed   : test_3_C"
        ),
    ]


@tag("ordering")
class OrderingResource(Scenario):
    steps = [
        Start("run 2021.com.canonical.certification::ordering_resource"),
        AssertPrinted(
            r"(?m).*job passed   : test_4_R\n.*job passed   : test_4_A"
        ),
    ]


@tag("ordering")
class OrderingDependsCycle(Scenario):
    steps = [
        Start("run 2021.com.canonical.certification::ordering_depends_cycle"),
        AssertPrinted(r"Dependency problem: dependency cycle detected"),
    ]


@tag("ordering")
class OrderingBeforeCycle(Scenario):
    steps = [
        Start("run 2021.com.canonical.certification::ordering_before_cycle"),
        AssertPrinted(r"Dependency problem: dependency cycle detected"),
    ]
