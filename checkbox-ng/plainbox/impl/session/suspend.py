# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.session.suspend` -- session suspend support
===============================================================

This module contains classes that can suspend an instance of
:class:`~plainbox.impl.session.state.SessionState`. The general idea is that
:class:`~plainbox.impl.session.resume.SessionSuspendHelper` knows how to
describe the session and
:class:`~plainbox.impl.session.resume.SessionResumeHelper` knows how to
recreate the session from that description.

Both of the helper classes are only used by
:class:`~plainbox.impl.session.manager.SessionManager` and in the
the legacy suspend/resume code paths of
:class:`~plainbox.impl.session.state._LegacySessionState`.
Applications should use one of those APIs to work with session snapshots.

The design of the on-disk format is not like typical pickle or raw dump of all
of the objects. Instead it is designed to create a smart representation of a
subset of the data and explicitly support migrations, so that some future
version of PlainBox can change the format and still read old sessions (to the
extent that it makes sense) or at least reject them with an intelligent
message.

One important consideration of the format is that we suspend very often and
resume very infrequently so everything is optimized around saving big
chunks of data incrementally (all the big job results and their log files)
and to keep most of the data we save over and over small.

The key limitation in how the suspend code works is that we cannot really
serialize jobs at all. There are two reasons for that, one very obvious
and one which is more of a design decision.

The basic reason for why we cannot serialize jobs is that we cannot really,
meaningfully serialize the code that runs inside a job. That may the shell
command or a call into python module. Without this limitation we would
be basically pretending that we are running the same job as before while the
job definition has transparently changed and the results would not be
sensible anymore.

The design decision is to allow abstract, opaque Providers to offer various
types of JobDefinitions (that may be radically different to what current
CheckBox jobs look like). This is why the resume interface requires one to
provide a full list of job definitions to resume. This is also why the
get_checksum() method can be implemented differently in non-CheckBox jobs.

As an exception to this rule we _do_ serialize generated jobs. Those are a
compromise between ease-of-use of the framework and the external
considerations mentioned above. Generated jobs are re-created from whatever
results that created them. The framework has special support code for knowing
how to resume in light of the fact that some jobs might be generated during
the resume process itself.

Serialization format versions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
1) The initial version
"""

import gzip
import json
import logging
import base64

from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import MemoryJobResult

logger = logging.getLogger("plainbox.session.suspend")


class SessionSuspendHelper1:
    """
    Helper class for computing binary representation of a session.

    The helper only creates a bytes object to save. Actual saving should
    be performed using some other means, preferably using
    :class:`~plainbox.impl.session.storage.SessionStorage`.
    """

    def suspend(self, session):
        """
        Compute the data that is saved by :class:`SessionStorage` as a
        part of :meth:`SessionStorage.save_checkpoint()`.

        :returns bytes: the serialized data
        """
        json_repr = self._json_repr(session)
        data = json.dumps(
            json_repr,
            ensure_ascii=False,
            sort_keys=True,
            indent=None,
            separators=(',', ':')
        ).encode("UTF-8")
        # NOTE: gzip.compress is not deterministic on python3.2
        return gzip.compress(data)

    def _json_repr(self, session):
        """
        Compute the representation of all of the data that needs to be saved.

        :returns:
            JSON-friendly representation
        :rtype:
            dict

        The dictionary has the following keys:

            ``version``
                A integral number describing the version of the representation.
                See the version table for details.

            ``session``
                Representation of the session as computed by
                :meth:`_repr_SessionState()`
        """
        return {
            "version": 1,
            "session": self._repr_SessionState(session),
        }

    def _repr_SessionState(self, obj):
        """
        Compute the representation of :class:`SessionState`

        :returns:
            JSON-friendly representation
        :rtype:
            dict

        The result is a dictionary with the following items:

            ``jobs``:
                Dictionary mapping job name to job checksum.
                The checksum is computed with
                :meth:`~plainbox.impl.job.JobDefinition.get_checksum()`

            ``results``
                Dictionary mapping job name to a list of results.
                Each result is represented by data computed by
                :meth:`_repr_JobResult()`

            ``desired_job_list``:
                List of (names) of jobs that are desired (to be executed)

            ``metadata``:
                The representation of meta-data associated with the session
                state object. This is encoded as a dictionary
                with the following items:

                    ``title``:
                        Title of the session. Arbitrary text provided by
                        the application.

                    ``flags``:
                        List of strings that enumerate the flags the session
                        is in. There are some well-known flags but this list
                        can have any items it it.

                    ``running_job_name``:
                        Name of the job that was about to be executed before
                        snapshotting took place. Can be None.
        """
        return {
            "jobs": {
                state.job.name: state.job.get_checksum()
                for state in obj.job_state_map.values()
            },
            "results": {
                # Currently we store only one result but we may store
                # more than that in a later version.
                state.job.name: [self._repr_JobResult(state.result)]
                for state in obj.job_state_map.values()
            },
            "desired_job_list": [
                job.name for job in obj.desired_job_list
            ],
            "metadata": self._repr_SessionMetaData(obj.metadata),
        }

    def _repr_SessionMetaData(self, obj):
        """
        Compute the representation of :class:`SessionMetaData`.

        :returns:
            JSON-friendly representation.
        :rtype:
            dict
        """
        return {
            "title": obj.title,
            "flags": list(sorted(obj.flags)),
            "running_job_name": obj.running_job_name
        }

    def _repr_JobResult(self, obj):
        """
        Compute the representation of one of IJobResult subclasses
        """
        if isinstance(obj, DiskJobResult):
            return self._repr_DiskJobResult(obj)
        elif isinstance(obj, MemoryJobResult):
            return self._repr_MemoryJobResult(obj)
        else:
            raise TypeError(
                "_repr_JobResult() supports DiskJobResult or MemoryJobResult")

    def _repr_JobResultBase(self, obj):
        """
        Compute the representation of :class:`plainbox.impl.job._JobResultBase`

        :returns:
            JSON-friendly representation
        :rtype:
            dict

        The dictionary has the following keys:

            ``outcome``
                The outcome of the test

            ``execution_duration``
                Time it took to execute the test command in seconds

            ``comments``
                Tester-supplied comments

            ``return_code``
                The exit code of the application.

        .. note::
            return_code can have unexpected values when the process was killed
            by a signal
        """
        return {
            "outcome": obj.outcome,
            "execution_duration": obj.execution_duration,
            "comments": obj.comments,
            "return_code": obj.return_code,
        }

    def _repr_MemoryJobResult(self, obj):
        """
        Compute the representation of
        :class:`plainbox.impl.job.MemoryJobResult`

        :returns:
            JSON-friendly representation
        :rtype:
            dict

        The dictionary has the following keys *in addition to* what is
        produced by :meth:`_repr_JobResultBase()`:

            ``io_log``
                Representation of the list of IO Log records
        """
        assert isinstance(obj, MemoryJobResult)
        result = self._repr_JobResultBase(obj)
        result.update({
            "io_log": [self._repr_IOLogRecord(record)
                       for record in obj.io_log],
        })
        return result

    def _repr_DiskJobResult(self, obj):
        """
        Compute the representation of :class:`plainbox.impl.job.DiskJobResult`

        :returns:
            JSON-friendly representation
        :rtype:
            dict

        The dictionary has the following keys *in addition to* what is
        produced by :meth:`_repr_JobResultBase()`:

            ``io_log_filename``
                The name of the file that keeps the serialized IO log
        """
        assert isinstance(obj, DiskJobResult)
        result = self._repr_JobResultBase(obj)
        result.update({
            "io_log_filename": obj.io_log_filename,
        })
        return result

    def _repr_IOLogRecord(self, obj):
        """
        Compute the representation of
        :class:`plainbox.impl.result.IOLogRecord`

        :returns:
            JSON-friendly representation
        :rtype:
            list

        The list has three elements:

        * delay, copied from :attr:`~plainbox.impl.result.IOLogRecord.delay`
        * stream name, copied from
          :attr:`~plainbox.impl.result.IOLogRecord.stream_name`
        * data, base64 encoded ASCII string, computed from
          :attr:`~plainbox.impl.result.IOLogRecord.data`
        """
        return [obj[0], obj[1],
                base64.standard_b64encode(obj[2]).decode("ASCII")]


# Alias for the most recent version
SessionSuspendHelper = SessionSuspendHelper1
