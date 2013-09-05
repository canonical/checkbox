# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.impl.providers.stubbox` -- stub job provider
===========================================================

The stubbox provider is useful for various kinds of testing where you don't
want to pull in a volume of data, just a bit of each kind of jobs that we need
to support.
"""

import os

from plainbox.impl import get_plainbox_dir
from plainbox.impl.providers.v1 import Provider1


class StubBoxProvider(Provider1):
    """
    A provider for stub, dummy and otherwise non-production jobs.
    """

    def __init__(self):
        super(StubBoxProvider, self).__init__(
            os.path.join(get_plainbox_dir(), "stubbox"),
            "stubbox", "StubBox (dummy data for development)")
