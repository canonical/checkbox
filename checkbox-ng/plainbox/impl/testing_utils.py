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

from functools import wraps
from gzip import GzipFile
from io import TextIOWrapper
from mock import Mock
from tempfile import NamedTemporaryFile
import warnings

from plainbox.impl.job import JobDefinition
from plainbox.impl.result import IOLogRecordWriter
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.rfc822 import Origin


def MockJobDefinition(name, *args, **kwargs):
    """
    Mock for JobDefinition class
    """
    job = Mock(*args, spec_set=JobDefinition, **kwargs)
    job.name = name
    return job


def make_io_log(io_log, io_log_dir):
    """
    Make the io logs serialization to json and return the saved file pathname
    WARNING: The caller has to remove the file once done with it!
    """
    with NamedTemporaryFile(
        delete=False, suffix='.record.gz', dir=io_log_dir) as byte_stream, \
            GzipFile(fileobj=byte_stream, mode='wb') as gzip_stream, \
            TextIOWrapper(gzip_stream, encoding='UTF-8') as text_stream:
        writer = IOLogRecordWriter(text_stream)
        for record in io_log:
            writer.write_record(record)
    return byte_stream.name


# Deprecated, use JobDefinition() directly
def make_job(name, plugin="dummy", requires=None, depends=None, **kwargs):
    """
    Make and return a dummy JobDefinition instance
    """
    data = {'name': name}
    if plugin is not None:
        data['plugin'] = plugin
    if requires is not None:
        data['requires'] = requires
    if depends is not None:
        data['depends'] = depends
    # Add any custom key-value properties
    data.update(kwargs)
    return JobDefinition(data, Origin.get_caller_origin())


def make_job_result(outcome="dummy"):
    """
    Make and return a dummy JobResult instance
    """
    return MemoryJobResult({
        'outcome': outcome
    })


def suppress_warnings(func):
    """
    Suppress all warnings from the decorated function
    """
    @wraps(func)
    def decorator(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return func(*args, **kwargs)
    return decorator
