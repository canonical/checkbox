# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.session.jobs` -- jobs state handling
========================================================

This module contains a helper class for associating job state within a
particular session. The :class:`JobState` class holds references to a
:class:`JobDefinition` and :class:`JobResult` as well as a list of inhibitors
that prevent the job from being runnable in a particular session.
"""

import logging

from plainbox.abc import IJobResult
from plainbox.i18n import gettext as _
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.signal import Signal

logger = logging.getLogger("plainbox.session.jobs")


class JobReadinessInhibitor:
    """
    Class representing the cause of a job not being ready to execute.

    It is intended to be consumed by UI layers and to provide them with enough
    information to render informative error messages or other visual feedback
    that will aid the user in understanding why a job cannot be started.

    There are four possible not ready causes:

        UNDESIRED:
            This job was not selected to run in this session

        PENDING_DEP:
           This job depends on another job which was not started yet

        FAILED_DEP:
            This job depends on another job which was started and failed

        PENDING_RESOURCE:
            This job has a resource requirement expression that uses a resource
            produced by another job which was not started yet

        FAILED_RESOURCE:
            This job has a resource requirement that evaluated to a false value

    All causes apart from UNDESIRED use the related_job property to encode a
    job that is related to the problem. The PENDING_RESOURCE and
    FAILED_RESOURCE causes also store related_expression that describes the
    relevant requirement expression.

    There are three attributes that can be accessed:

        cause:
            Encodes the reason why a job is not ready, see above.

        related_job:
            Provides additional context for the problem. This is not the job
            that is affected, rather, the job that is causing the problem.

        related_expression:
            Provides additional context for the problem caused by a failing
            resource expression.
    """
    # XXX: PENDING_RESOURCE is not strict, there are multiple states that are
    # clumped here which is something I don't like. A resource may be still
    # "pending" as in PENDING_DEP (it has not ran yet) or it could have ran but
    # failed to produce any data, it could also be prevented from running
    # because it has unmet dependencies. In essence it tells us nothing about
    # if related_job.can_start() is true or not.
    #
    # XXX: FAILED_RESOURCE is "correct" but somehow misleading, FAILED_RESOURCE
    # is used to represent a resource expression that evaluated to a non-True
    # value

    UNDESIRED, PENDING_DEP, FAILED_DEP, PENDING_RESOURCE, FAILED_RESOURCE \
        = range(5)

    _cause_display = {
        UNDESIRED: "UNDESIRED",
        PENDING_DEP: "PENDING_DEP",
        FAILED_DEP: "FAILED_DEP",
        PENDING_RESOURCE: "PENDING_RESOURCE",
        FAILED_RESOURCE: "FAILED_RESOURCE"
    }

    def __init__(self, cause, related_job=None, related_expression=None):
        """
        Initialize a new inhibitor with the specified cause.

        If cause is other than UNDESIRED a related_job is necessary. If cause
        is either PENDING_RESOURCE or FAILED_RESOURCE related_expression is
        necessary as well. A ValueError is raised when this is violated.
        """
        if cause not in self._cause_display:
            raise ValueError(_("unsupported value for cause"))
        if cause != self.UNDESIRED and related_job is None:
            raise ValueError(
                # TRANSLATORS: please don't translate related_job and None
                _("related_job must not be None when cause is {}").format(
                    self._cause_display[cause]))
        if cause in (self.PENDING_RESOURCE, self.FAILED_RESOURCE) \
                and related_expression is None:
            raise ValueError(_(
                # TRANSLATORS: please don't translate related_expression and
                # None
                "related_expression must not be None when cause is {}"
            ).format(self._cause_display[cause]))
        self.cause = cause
        self.related_job = related_job
        self.related_expression = related_expression

    def __eq__(self, other):
        if isinstance(other, JobReadinessInhibitor):
            return ((self.cause, self.related_job, self.related_expression)
                    == (self.cause, self.related_job, self.related_expression))
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, JobReadinessInhibitor):
            return ((self.cause, self.related_job, self.related_expression)
                    != (self.cause, self.related_job, self.related_expression))
        return NotImplemented

    @property
    def cause_name(self):
        return self._cause_display[self.cause]

    def __repr__(self):
        return "<{} cause:{} related_job:{!r} related_expression:{!r}>".format(
            self.__class__.__name__, self._cause_display[self.cause],
            self.related_job, self.related_expression)

    def __str__(self):
        if self.cause == self.UNDESIRED:
            return _("undesired")
        elif self.cause == self.PENDING_DEP:
            return _("required dependency {!r} did not run yet").format(
                self.related_job.id)
        elif self.cause == self.FAILED_DEP:
            return _("required dependency {!r} has failed").format(
                self.related_job.id)
        elif self.cause == self.PENDING_RESOURCE:
            return _(
                "resource expression {!r} could not be evaluated because"
                " the resource it depends on did not run yet"
            ).format(self.related_expression.text)
        else:
            assert self.cause == self.FAILED_RESOURCE
            return _("resource expression {!r} evaluates to false").format(
                self.related_expression.text)


# A global instance of :class:`JobReadinessInhibitor` with the UNDESIRED cause.
# This is used a lot and it makes no sense to instantiate all the time.
UndesiredJobReadinessInhibitor = JobReadinessInhibitor(
    JobReadinessInhibitor.UNDESIRED)


class JobState:
    """
    Class representing the state of a job in a session.

    Contains two basic properties of each job:

        * the readiness_inhibitor_list that prevent the job form starting
        * the result (outcome) of the run (IJobResult)

    For convenience (to SessionState implementation) it also has a reference to
    the job itself.  This class is a pure state holder an will typically
    collaborate with the SessionState class and the UI layer.
    """

    def __init__(self, job):
        """
        Initialize a new job state object.

        The job will be inhibited by a single UNDESIRED inhibitor and will have
        a result with OUTCOME_NONE that basically says it did not run yet.
        """
        self._job = job
        self._readiness_inhibitor_list = [UndesiredJobReadinessInhibitor]
        self._result = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_NONE
        })

    def __repr__(self):
        fmt = ("<{} job:{!r} readiness_inhibitor_list:{!r} result:{!r}>")
        return fmt.format(self.__class__.__name__, self._job,
                          self._readiness_inhibitor_list, self._result)

    @property
    def job(self):
        """
        the job associated with this state
        """
        return self._job

    @job.setter
    def job(self, job):
        """
        Changes the job associated with this state
        """
        #FIXME: This setter should not exist. job attribute should be
        #read-only. This is a temporary kludge to get session restoring
        #over DBus working. Once a solution that doesn't involve setting
        #a JobState's job attribute is implemented, please remove this
        #awful method.
        self._job = job

    def _readiness_inhibitor_list():

        doc = "the list of readiness inhibitors of the associated job"

        def fget(self):
            return self._readiness_inhibitor_list

        def fset(self, value):
            self._readiness_inhibitor_list = value

        return (fget, fset, None, doc)

    readiness_inhibitor_list = property(*_readiness_inhibitor_list())

    def _result():
        doc = "the result of running the associated job"

        def fget(self):
            return self._result

        def fset(self, new):
            old = self._result
            if old != new:
                self._result = new
                self.on_result_changed(old, new)

        return (fget, fset, None, doc)

    result = property(*_result())

    @Signal.define
    def on_result_changed(self, old, new):
        """
        Event fired when the result associated with this job state changes
        """
        logger.info(
            "<%s %s>.on_result_changed(%r, %r)",
            self.__class__.__name__, id(self), old, new)

    def can_start(self):
        """
        Quickly check if the associated job can run right now.
        """
        return len(self._readiness_inhibitor_list) == 0

    def get_readiness_description(self):
        """
        Get a human readable description of the current readiness state
        """
        if self._readiness_inhibitor_list:
            return _("job cannot be started: {}").format(
                ", ".join((str(inhibitor)
                           for inhibitor in self._readiness_inhibitor_list)))
        else:
            return "job can be started"

    def _get_persistance_subset(self):
        # Don't save resource job results, fresh data are required
        # so we can't reuse the old ones
        # The inhibitor list needs to be recomputed as well, don't save it.
        state = {}
        state['_job'] = self._job
        if self._job.plugin == 'resource':
            state['_result'] = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NONE
            })
        else:
            state['_result'] = self._result
        return state

    @classmethod
    def from_json_record(cls, record):
        """
        Create a JobState instance from JSON record
        """
        obj = cls(record['_job'])
        obj._readiness_inhibitor_list = [UndesiredJobReadinessInhibitor]
        obj._result = record['_result']
        return obj
