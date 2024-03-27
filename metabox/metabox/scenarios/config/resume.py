# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

from metabox.core import keys
from metabox.core.scenario import Scenario
from metabox.core.actions import Expect, Start, Signal


class ConfigLoadedAlsoAfterResume(Scenario):
    """
    Check that configs are loaded also after resume
    """

    modes = ["local"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-slow-automated
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        [environment]
        var1=a
        var2=b
        var3=c
        case=case
        Case=Case
        CASE=CASE
        source=source
        """
    )
    steps = [
        Start(),
        Expect("source: source"),
        Expect("starting to sleep"),
        Signal(keys.SIGKILL),
        Start(),
        # autoresume
        Expect("Case CASE case"),
    ]
