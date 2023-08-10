# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hector Cao <hector.cao@canonical.com>
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

from metabox.core.actions import Start
from metabox.core.actions import Expect
from metabox.core.scenario import Scenario
from metabox.core.actions import AssertPrinted
from metabox.core.actions import AssertNotPrinted

from metabox.core.utils import _re

class TestDryRunOff(Scenario):
    """
    By default, dry run is disabled, jobs should be run and passed.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        auto_retry = no
        [environment]
        source = WET RUN
        """)
    steps = [
        Start(),
        AssertPrinted("source: WET RUN"),
        AssertPrinted("(☑|job passed).*config-environ-source"),
    ]

class TestDryRunOn(Scenario):
    """
    If --dry-run argument is present in the checkbox-cli, dry run mode is enabled and regular jobs
    (not attach, resource, ..) must be skipped.
    """
    cmd_args = '--dry-run'
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        auto_retry = no
        [environment]
        source = WET RUN
        """)
    steps = [
        Start(),
        AssertNotPrinted("source: WET RUN"),
        AssertPrinted("(☐|job skipped).*config-environ-source"),
    ]

