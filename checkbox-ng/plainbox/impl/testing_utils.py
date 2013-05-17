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
:mod:`plainbox.impl.testing_utils` -- plainbox specific test tools
==================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import inspect
from tempfile import NamedTemporaryFile

from plainbox.impl.job import JobDefinition
from plainbox.impl.result import JobResult
from plainbox.impl.rfc822 import Origin
from plainbox.impl.runner import io_log_write


def make_io_log(io_log, io_log_dir):
    """
    Make the io logs serialization to json and return the saved file pathname
    WARNING: The caller has to remove the file once done with it!
    """
    with NamedTemporaryFile(mode='w+t', delete=False) as stream:
        io_log_write(io_log, stream)
        return stream.name


def make_job(name, plugin="dummy", requires=None, depends=None, **kwargs):
    """
    Make and return a dummy JobDefinition instance
    """
    # Jobs are usually loaded from RFC822 records and use the
    # origin tracking to understand which file they came from.
    #
    # Here we can create a Origin instance that pinpoints the
    # place that called make_job(). This aids in debugging as
    # the origin field is printed by JobDefinition repr
    caller_frame, filename, lineno = inspect.stack(0)[1][:3]
    try:
        # XXX: maybe create special origin subclass for such things?
        origin = Origin(filename, lineno, lineno)
    finally:
        # Explicitly delete the frame object, this breaks the
        # reference cycle and makes this part of the code deterministic
        # with regards to the CPython garbage collector.
        #
        # As recommended by the python documentation:
        # http://docs.python.org/3/library/inspect.html#the-interpreter-stack
        del caller_frame
    settings = {
        'name': name,
        'plugin': plugin,
        'requires': requires,
        'depends': depends
    }
    settings.update(kwargs)
    return JobDefinition(settings, origin)


def make_job_result(job, outcome="dummy"):
    """
    Make and return a dummy JobResult instance
    """
    return JobResult({
        'job': job,
        'outcome': outcome
    })
