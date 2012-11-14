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
plainbox.impl.utils
===================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

from plainbox.impl.testdef import TestDefinition
from plainbox.impl.rfc822 import load_rfc822_records


def get_builtin_test_definitions():
    raise NotImplementedError()


def save(something, somewhere):
    raise NotImplementedError()


def load(somewhere):
    if isinstance(somewhere, str):
        # Load data from a file with the given name
        with open(somewhere, 'rt', encoding='utf-8') as stream:
            records = load_rfc822_records(stream)
        return [TestDefinition.from_rfc822_record(record)
                for record in records]
    else:
        raise TypeError("Unsupported type of 'somewhere'")


def run(*args, **kwargs):
    print("I ran!")
