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
plainbox.impl.result
====================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

import logging

from plainbox.abc import ITestResult

logger = logging.getLogger("plainbox.result")


class TestResult(ITestResult):

    @property
    def job(self):
        return self._data['job']

    @property
    def outcome(self):
        return self._data['outcome']

    @property
    def comments(self):
        return self._data['comments']

    @property
    def io_log(self):
        return self._data['io_log']

    @property
    def return_code(self):
        return self._data['return_code']

    def __init__(self, data):
        self._data = data

    def __str__(self):
        return "{}: {}".format(
            self.job.name, self.outcome)

    def __repr__(self):
        return "<TestResult job:{!r} outcome:{!r}>".format(
            self.job, self.outcome)
