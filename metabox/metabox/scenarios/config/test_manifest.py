# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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

from metabox.core.actions import AssertPrinted, AssertNotPrinted, Expect,\
        Start, Put, Send
from metabox.core.scenario import Scenario


class ManifestLauncherAuto(Scenario):
    """
    When provided with a manifest in the launcher
    checkbox reads it correctly regardless if 
    tests selection was skipped or not
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        unit = com.canonical.certification::manifest_test_support
        forced = yes
        [test selection]
        forced = yes
        [manifest]
        com.canonical.certification::manifest_location = 0
    """)
    steps = [
        AssertPrinted(".*Outcome: job passed.*")
    ]


