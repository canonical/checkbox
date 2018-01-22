# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.testing_utils` - generic testing utilities
=========================================================
"""

import collections
import json
import os

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


class XLongTextCompare:
    """
    A helper that allows to debug failing text comparison on x-large text
    To use, put it before TestCase in class inheritance list.

    To get a chance to observe each failure, define
    XLONGTEXTCOMPARE='interactive' and run your tests. Once you get to a
    failing test pdb will be started. Then you can inspect two files
    ``/tmp/actual`` and ``/tmp/expected`` for example, with vimdiff.
    """

    def assertEqual(self, actual, expected):
        try:
            return super(XLongTextCompare, self).assertEqual(actual, expected)
        except AssertionError:
            if os.getenv("XLONGTEXTCOMPARE") != "interactive":
                raise
            if not isinstance(actual, str) or not isinstance(expected, str):
                raise
            with open('/tmp/actual', 'wt', encoding='UTF-8') as stream:
                stream.write(actual)
            with open('/tmp/expected', 'wt', encoding='UTF-8') as stream:
                stream.write(expected)
            import pdb
            pdb.set_trace()
            raise
