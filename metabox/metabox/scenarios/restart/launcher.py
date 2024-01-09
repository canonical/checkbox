# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

from metabox.core.actions import AssertPrinted
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("reboot")
class Reboot(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::power-automated
        forced = yes
        [test selection]
        forced = yes
        exclude = .*cold.*
        [ui]
        type = silent
        """
    )
    steps = [
        AssertPrinted("Connection lost!"),
        AssertPrinted("job passed   : Warm reboot"),
    ]


@tag("system_information")
class SystemInfoPersistency(Scenario):
    """
    System Information should be persistent across reboots
    """

    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::power-automated
        forced = yes
        [test selection]
        forced = yes
        exclude = .*cold.*
        [ui]
        type = silent
        # Use json exporter to dump the submission.json file to the screen
        # so that we can read it with AssertPrinted
        [exporter:json]
        unit = com.canonical.plainbox::json
        [transport:out]
        type = stream
        stream = stdout
        [report:screen]
        exporter = json
        transport = out
        forced = yes
        """
    )
    steps = [
        AssertPrinted("Connection lost!"),
        AssertPrinted("job passed   : Warm reboot"),
        AssertPrinted('"system_information"'),
        AssertPrinted('"inxi"'),
    ]
