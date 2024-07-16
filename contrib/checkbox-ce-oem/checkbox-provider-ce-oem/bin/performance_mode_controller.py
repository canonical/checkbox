#!/usr/bin/env python3
# Since there are lots of devices from different projects need to run case
# with Performance mode, therefore, this script aims to be an unified entry
# and can be called by other scripts. As for the detail of each device, we
# implement it in each different specific script.

# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib


@contextlib.contextmanager
def performance_mode(target: str = "", **kwrags):
    try:
        # Run performance mode if target string starts with "genio"
        if target.startswith("genio"):
            from genio_performance_mode import performance_mode
            with performance_mode(target):
                yield
        # Do nothing if no specific target
        else:
            yield
    finally:
        pass
