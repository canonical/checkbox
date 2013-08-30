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
:mod:`plainbox.impl.result` -- job result
=========================================

This module has two basic implementation of :class:`IJobResult`:
:class:`MemoryJobResult` and :class:`DiskJobResult`.
"""

from collections import namedtuple
import base64
import gzip
import io
import json
import logging
import inspect

from plainbox.abc import IJobResult
from plainbox.impl.signal import Signal

logger = logging.getLogger("plainbox.result")


# Tuple representing entries in the JobResult.io_log
# Each entry has three fields:
#
#   delay - time elapsed since the previous record was created (in seconds,
#   floating point unit represent fractional parts)
#
#   stream_name - name of the stream the IO was observed on, currently
#   'stdout' and 'stderr' are supported.
#
#   data - the actual IO seen (bytes)
IOLogRecord = namedtuple("IOLogRecord", "delay stream_name data".split())


class _JobResultBase(IJobResult):
    """
    Base class for :`IJobResult` implementations.

    This class defines base properties common to all variants of `IJobResult`
    """

    def __init__(self, data):
        """
        Initialize a new result with the specified data

        Data is a dictionary that can hold arbitrary values. At least some
        values are explicitly used, such as 'outcome', 'comments' and
        'return_code' but all of those are optional.
        """
        self._data = data

    def __str__(self):
        return str(self.outcome)

    def __repr__(self):
        return "<{} outcome:{!r}>".format(
            self.__class__.__name__, self.outcome)

    @property
    def outcome(self):
        """
        outcome of running this job.

        The outcome ultimately classifies jobs (tests) as failures or
        successes.  There are several other types of outcome that all basically
        mean that the job did not run for some particular reason.
        """
        return self._data.get('outcome', self.OUTCOME_NONE)

    @outcome.setter
    def outcome(self, new):
        old = self.outcome
        if old != new:
            self._data['outcome'] = new

    @property
    def execution_duration(self):
        """
        The amount of time in seconds it took to run this
        jobs command.
        """
        return self._data.get('execution_duration')

    @property
    def comments(self):
        """
        comments of the test operator
        """
        return self._data.get('comments')

    @comments.setter
    def comments(self, new):
        old = self.comments
        if old != new:
            self._data['comments'] = new
            self.on_comments_changed(old, new)

    @Signal.define
    def on_comments_changed(self, old, new):
        """
        Signal sent when ``comments`` property value is changed
        """

    @property
    def return_code(self):
        """
        return code of the command associated with the job, if any
        """
        return self._data.get('return_code')

    # deprecated
    def _get_persistance_subset(self):
        return {
            "data": dict(self._data)
        }

    # deprecated
    @classmethod
    def from_json_record(cls, record):
        """
        Create a specific IJobResult instance from JSON record
        """
        return cls(record['data'])

    @property
    def io_log(self):
        return tuple(self.get_io_log())


class MemoryJobResult(_JobResultBase):
    """
    A :class:`IJobResult` that keeps IO logs in memory.

    This type of JobResult is indented for writing unit tests where the hassle
    of going through the filesystem would make them needlessly complicated.
    """

    def get_io_log(self):
        io_log_data = self._data.get('io_log', ())
        for entry in io_log_data:
            if isinstance(entry, IOLogRecord):
                yield entry
            elif isinstance(entry, tuple):
                yield IOLogRecord(*entry)
            else:
                raise TypeError(
                    "each item in io_log must be either a tuple"
                    " or special the IOLogRecord tuple")


class GzipFile(gzip.GzipFile):
    """
    Subclass of GzipFile that works around missing read1() on python3.2

    See: http://bugs.python.org/issue10791
    """

    def read1(self, n):
        return self.read(n)


class DiskJobResult(_JobResultBase):
    """
    A :class:`IJobResult` that keeps IO logs on disk.

    This type of JobResult is intended for working with most results. It does
    not store IO logs in memory so it is scalable to arbitrary IO log sizes.
    Each instance just knows where the log file is located (using the
    'io_log_filename' attribute for that) and offers streaming API for
    accessing particular parts of the log.
    """

    @property
    def io_log_filename(self):
        """
        pathname of the file containing serialized IO log records
        """
        return self._data.get("io_log_filename")

    def get_io_log(self):
        record_path = self.io_log_filename
        if record_path:
            with GzipFile(record_path, mode='rb') as gzip_stream, \
                    io.TextIOWrapper(gzip_stream, encoding='UTF-8') as stream:
                for record in IOLogRecordReader(stream):
                    yield record

    @property
    def io_log(self):
        caller_frame, filename, lineno = inspect.stack(0)[1][:3]
        logger.warning(
            "Expensive DiskJobResult.io_log property access from %s:%d",
            filename, lineno)
        return super(DiskJobResult, self).io_log


# Deprecated
class IoLogEncoder(json.JSONEncoder):
    """
    JSON Serialize helper to encode binary io logs
    """

    def default(self, obj):
        return base64.standard_b64encode(obj).decode('ASCII')


# Deprecated
class IoLogDecoder(json.JSONDecoder):
    """
    JSON Decoder helper for io logs objects
    """

    def decode(self, obj):
        return tuple([IOLogRecord(
            # io logs namedtuple are recorded as list in json, using _asdict()
            # would require too much space for little benefit.
            # IOLogRecord are re created using the list ordering
            log[0], log[1], base64.standard_b64decode(log[2].encode('ASCII')))
            for log in super().decode(obj)])


class IOLogRecordWriter:
    """
    Class for writing :class:`IOLogRecord` instances to a text stream
    """

    def __init__(self, stream):
        self.stream = stream

    def close(self):
        self.stream.close()

    def write_record(self, record):
        """
        Write an :class:`IOLogRecord` to the stream.
        """
        text = json.dumps([
            record[0], record[1],
            base64.standard_b64encode(record[2]).decode("ASCII")],
            check_circular=False, ensure_ascii=True, indent=None,
            separators=(',', ':'))
        logger.debug("Encoded %r into string %r", record, text)
        assert "\n" not in text
        self.stream.write(text)
        self.stream.write('\n')


class IOLogRecordReader:
    """
    Class for streaming :class`IOLogRecord` instances from a text stream
    """

    def __init__(self, stream):
        self.stream = stream

    def close(self):
        self.stream.close()

    def read_record(self):
        """
        Read the next record from the stream.

        :returns: None if the stream is empty
        :returns: next :class:`IOLogRecord` as found in the stream.
        """
        text = self.stream.readline()
        if len(text) == 0:
            return
        data = json.loads(text)
        return IOLogRecord(
            data[0], data[1],
            base64.standard_b64decode(data[2].encode("ASCII")))

    def __iter__(self):
        """
        Iterate over the entire stream generating subsequent
        :class:`IOLogRecord` entries.
        """
        while True:
            record = self.read_record()
            if record is None:
                break
            yield record
