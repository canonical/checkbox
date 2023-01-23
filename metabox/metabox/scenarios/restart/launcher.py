# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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


class Reboot(Scenario):

    modes = ['remote']
    launcher = textwrap.dedent("""
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
    """)
    steps = [
        AssertPrinted('Connection lost!'),
        AssertPrinted('Reconnecting...'),
        AssertPrinted('job passed   : Warm reboot'),
    ]
