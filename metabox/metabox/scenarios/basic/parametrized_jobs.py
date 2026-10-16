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

from metabox.core.actions import (
    AssertPrinted,
    AssertRetCode,
    Put,
    RunManage,
    Start,
)
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("parametrized-job", "basic")
class ParametrizedSingle(Scenario):
    """Instantiate jobs using one parameter."""

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::parametrized_single
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : parametrized_1_A\n"
            r".*job passed   : parametrized_1_B"
        ),
        AssertRetCode(0),
    ]


@tag("parametrized-job", "basic")
class ParametrizedMultiple(Scenario):
    """Instantiate jobs using multiple parameters."""

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::parametrized_multiple
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : parametrized_2_A_1\n"
            r".*job passed   : parametrized_2_B_2"
        ),
        AssertRetCode(0),
    ]


@tag("parametrized-job", "ordering")
class ParametrizedDepends(Scenario):
    """Resolve dependencies between ordinary and generated jobs."""

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::parametrized_depends
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : parametrized_3_A\n"
            r".*job passed   : parametrized_3_B\n"
            r".*job passed   : parametrized_3_C\n"
            r".*job passed   : parametrized_3_D"
        ),
        AssertRetCode(0),
    ]


@tag("parametrized-job", "suspend")
class ParametrizedSuspend(Scenario):
    """Run a generated sibling after the existing suspend mock."""

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::parametrized_suspend
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        Start(),
        AssertPrinted(
            r"(?m)"
            r".*job passed   : parametrized_4_A\n"
            r".*job passed   : suspend/suspend_advanced_auto\n"
            r".*job passed   : after-suspend-parametrized_4_A"
        ),
        AssertRetCode(0),
    ]


@tag("parametrized-job", "validation")
class ParametrizedDuplicate(Scenario):
    """Reject a generated job ID that already belongs to an ordinary job."""

    modes = ["local"]
    origins = ["source"]

    def run(self):
        self.start_session = False
        super().run()

    steps = [
        RunManage("validate"),
        # Validation resolves references against the installed provider.
        Put(
            "/usr/local/lib/plainbox-providers-1/"
            "2021.com.canonical.certification:metabox/"
            "units/parametrized-duplicate.yaml",
            textwrap.dedent("""\
                unit: parametrized-job
                template-id: parametrized_5
                parameters:
                  - value: A
                id: parametrized_3_{value}
                flags: [simple]
                command: 'true'
                """),
        ),
        RunManage("validate", expect_failure=True),
        AssertRetCode(1),
        AssertPrinted(
            r"job 'parametrized_3_A', field 'id'.*clashes with 1 other unit"
        ),
    ]
