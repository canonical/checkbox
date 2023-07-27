# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

from metabox.core.scenario import Scenario
from metabox.core.actions import AssertRetCode, Start


class ExporterSettingOptions(Scenario):
    """
    Check that setting exporter parameters does not crash
    checkbox
    """

    launcher = textwrap.dedent(
        """
        [launcher]
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::basic-automated-passing
        forced = yes
        [test selection]
        forced = yes
        [exporter:text]
        options=squash-io-log
        """
    )
    steps = [Start(), AssertRetCode(0)]
