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

    # The outcome of a job is a one-word classification how how it ran.  There
    # are several values that were not used in the original implementation but
    # their existence helps to organize and implement plainbox. They are
    # discussed below to make their intended meaning more detailed than is
    # possible from the variable name alone.
    #
    # The None outcome - a job that basically did not run at all.
    OUTCOME_NONE = None
    # The pass and fail outcomes are the two most essential, and externally
    # visible, job outcomes. They can be provided by either automated or manual
    # "classifier" - a script or a person that clicks a "pass" or "fail"
    # button.
    OUTCOME_PASS = 'pass'
    OUTCOME_FAIL = 'fail'
    # The skip outcome is used when the operator selected a job but then
    # skipped it. This is typically used for a manual job that is tedious or
    # was selected by accident.
    OUTCOME_SKIP = 'skip'
    # The not supported outcome is used when a job was about to run but a
    # dependency or resource requirement prevent it from running.  XXX: perhaps
    # this should be called "not available", not supported has the "unsupported
    # code" feeling associated with it.
    OUTCOME_NOT_SUPPORTED = 'not-supported'
    # A temporary state that should be removed later on, used to indicate that
    # job runner is not implemented but the job "ran" so to speak.
    OUTCOME_NOT_IMPLEMENTED = 'not-implemented'

    # XXX: how to support attachments?

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
