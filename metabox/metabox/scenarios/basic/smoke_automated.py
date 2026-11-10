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
    AssertNotPrinted,
    AssertPrinted,
    AssertRetCode,
)
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("smoke-automated")
class SmokeAutomatedPassing(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::smoke-automated-passing
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        # A run made only of passing, xfail and root jobs must succeed,
        # even though it is interrupted by a resume.
        AssertRetCode(0),
        # Setup and bootstrap jobs are reported by id only: neither their
        # summary nor their output is relayed, so their outcome is all we
        # can assert on. The root jobs guard on `id -u` to stay meaningful.
        AssertPrinted("smoke-automated-bootstrap-pass"),
        AssertPrinted("smoke-automated-bootstrap-fail"),
        AssertPrinted("smoke-automated-bootstrap-root"),
        AssertPrinted("smoke-automated-setup-pass"),
        AssertPrinted("smoke-automated-setup-fail"),
        AssertPrinted("smoke-automated-setup-root"),
        AssertPrinted("failed as expected"),
        AssertPrinted("Smoke automated normal pass"),
        AssertPrinted("SMOKE_NORMAL_PASS"),
        AssertPrinted("Smoke automated normal fail"),
        AssertPrinted("SMOKE_NORMAL_FAIL"),
        AssertPrinted("Smoke automated normal root"),
        AssertPrinted("SMOKE_NORMAL_ROOT"),
        # This job kills checkbox-cli, so racing to capture its output is
        # unreliable: only the resumed session report is guaranteed.
        AssertPrinted("Smoke automated normal resume pass"),
        AssertNotPrinted("job crashed"),
    ]


@tag("smoke-automated")
class SmokeAutomatedCrashing(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::smoke-automated-crashing
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        AssertRetCode(1),
        AssertPrinted("Smoke automated normal crash"),
        AssertPrinted("SMOKE_NORMAL_CRASH"),
        # This job kills checkbox-cli, so racing to capture its output is
        # unreliable: only the resumed session report is guaranteed.
        AssertPrinted("Smoke automated normal resume crash"),
        AssertPrinted("job crashed"),
    ]


@tag("smoke-automated")
class SmokeAutomated(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::smoke-automated
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """)
    steps = [
        # The nested plan inherits the crashing part, so it must fail.
        AssertRetCode(1),
        # Setup and bootstrap jobs are pulled in through the nested passing
        # part, and are reported by id only.
        AssertPrinted("smoke-automated-bootstrap-pass"),
        AssertPrinted("smoke-automated-bootstrap-fail"),
        AssertPrinted("smoke-automated-bootstrap-root"),
        AssertPrinted("smoke-automated-setup-pass"),
        AssertPrinted("smoke-automated-setup-fail"),
        AssertPrinted("smoke-automated-setup-root"),
        # xfail overrides have to survive nesting too.
        AssertPrinted("failed as expected"),
        AssertPrinted("Smoke automated normal pass"),
        AssertPrinted("SMOKE_NORMAL_PASS"),
        AssertPrinted("Smoke automated normal fail"),
        AssertPrinted("SMOKE_NORMAL_FAIL"),
        AssertPrinted("Smoke automated normal root"),
        AssertPrinted("SMOKE_NORMAL_ROOT"),
        AssertPrinted("Smoke automated normal resume pass"),
        AssertPrinted("Smoke automated normal crash"),
        AssertPrinted("SMOKE_NORMAL_CRASH"),
        AssertPrinted("Smoke automated normal resume crash"),
        AssertPrinted("job crashed"),
    ]
