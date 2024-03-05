# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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

"""
:mod:`plainbox.impl.configuration` -- Configuration variables
=============================================================
"""


class Suspend:
    AUTO_JOB_ID = "com.canonical.certification::suspend/suspend_advanced_auto"
    MANUAL_JOB_ID = "com.canonical.certification::suspend/suspend_advanced"
    AUTO_FLAG = "also-after-suspend"
    MANUAL_FLAG = "also-after-suspend-manual"
