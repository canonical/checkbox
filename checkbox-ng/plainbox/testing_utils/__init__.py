# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
:mod:`plainbox.testing_utils` - generic testing utilities
=========================================================
"""

import collections
import json

from pkg_resources import resource_string


def resource_json(package, pathname, exact=False):
    """
    Like resource_string, but loaded as JSON.

    :param package: name of the python package
    :param pathame: pathname of a file inside that package
    :param exact: if True, uses OrderedDict to preserve ordering

    :returns: deserialized json object
    """
    return json.loads(
        resource_string(package, pathname).decode("UTF-8"),
        object_pairs_hook=collections.OrderedDict if exact else None)
