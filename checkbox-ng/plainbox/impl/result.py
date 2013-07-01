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

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from collections import namedtuple
import base64
import json
import logging
import os

from plainbox.abc import IJobResult

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


class JobResult(IJobResult):
    """
    Result of running a JobDefinition.
    """


    def __init__(self, data):
        """
        Initialize a new result with the specified data
        """
        # XXX: consider moving job to a dedicated field as we want to serialize
        # results without putting the job reference in there (a job name would
        # be a fine substitute). It would also make the 'job is required'
        # requirement spelled out below explicit)
        #
        # TODO: Do some basic validation, at least 'job' must be set.
        self._data = data

    def __str__(self):
        return "{}: {}".format(
            self.job.name, self.outcome)

    def __repr__(self):
        return "<{} job:{!r} outcome:{!r}>".format(
            self.__class__.__name__, self.job, self.outcome)

    @property
    def job(self):
        return self._data['job']

    @property
    def outcome(self):
        return self._data.get('outcome', self.OUTCOME_NONE)

    @property
    def comments(self):
        return self._data.get('comments')

    @property
    def io_log(self):
        if os.path.exists(self._data.get('io_log', '')):
            with open(self._data.get('io_log')) as f:
                return json.load(f, cls=IoLogDecoder)
        else:
            return ()

    @property
    def return_code(self):
        return self._data.get('return_code')

    def _get_persistance_subset(self):
        state = {}
        state['data'] = {}
        for key, value in self._data.items():
            state['data'][key] = value
        return state

    @classmethod
    def from_json_record(cls, record):
        """
        Create a JobResult instance from JSON record
        """
        return cls(record['data'])


class IoLogEncoder(json.JSONEncoder):
    """
    JSON Serialize helper to encode binary io logs
    """

    def default(self, obj):
        return base64.standard_b64encode(obj).decode('ASCII')


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
