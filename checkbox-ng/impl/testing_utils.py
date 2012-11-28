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
plainbox.impl.testing_utils
===========================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

from plainbox.impl.job import JobDefinition
from plainbox.impl.result import JobResult


def make_job(name, plugin="dummy", requires=None, depends=None):
    """
    Make and return a dummy JobDefinition instance
    """
    return JobDefinition({
        'name': name,
        'plugin': plugin,
        'requires': requires,
        'depends': depends
    })


def make_job_result(job, outcome="dummy"):
    """
    Make and return a dummy JobResult instance
    """
    return JobResult({
        'job': job,
        'outcome': outcome
    })
