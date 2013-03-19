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
:mod:`plainbox.impl.exporter` -- shared code for session state exporters
========================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from logging import getLogger
import base64

import pkg_resources


logger = getLogger("plainbox.exporter")


class classproperty:
    """
    Class property.
    """
    # I wish it was in the standard library or that the composition worked

    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        # If we were being pedantic we could throw a TypeError if instance is
        # None but this is not really something we care about in the code below
        return self.func(owner)


class SessionStateExporterBase(metaclass=ABCMeta):
    """
    Base class for "exporter" that write out the state of the session after all
    jobs have finished running, in a user-selected format. The intent is not to
    preserve everything that the session may hold but instead to present it to
    the user in the best format possible.

    Each exporter can support a set of options (currently boolean flags) that
    can alter the way it operates. It's best to keep the list of exporter
    options under control to keep the user interface from becoming annoying.
    """

    OPTION_WITH_IO_LOG = 'with-io-log'
    OPTION_SQUASH_IO_LOG = 'squash-io-log'
    OPTION_FLATTEN_IO_LOG = 'flatten-io-log'
    OPTION_WITH_RUN_LIST = 'with-run-list'
    OPTION_WITH_JOB_LIST = 'with-job-list'
    OPTION_WITH_DESIRED_JOB_LIST = 'with-job-list'
    OPTION_WITH_RESOURCE_MAP = 'with-resource-map'
    OPTION_WITH_JOB_DEFS = 'with-job-defs'
    OPTION_WITH_ATTACHMENTS = 'with-attachments'
    OPTION_WITH_COMMENTS = 'with-comments'

    SUPPORTED_OPTION_LIST = (
        OPTION_WITH_IO_LOG,
        OPTION_SQUASH_IO_LOG,
        OPTION_FLATTEN_IO_LOG,
        OPTION_WITH_RUN_LIST,
        OPTION_WITH_JOB_LIST,
        OPTION_WITH_RESOURCE_MAP,
        OPTION_WITH_JOB_DEFS,
        OPTION_WITH_ATTACHMENTS,
        OPTION_WITH_COMMENTS,
    )

    def __init__(self, option_list=None):
        if option_list is None:
            option_list = []
        for option in option_list:
            if option not in self.supported_option_list:
                raise ValueError("Unsupported option: {}".format(option))
        self._option_list = option_list

    @classproperty
    def supported_option_list(cls):
        """
        Return the list of supported options
        """
        return cls.SUPPORTED_OPTION_LIST

    def get_session_data_subset(self, session):
        """
        Compute a subset of session data.

        The subset of the data that should be saved may depend on a particular
        saver class and options selected by the user.

        Must return a collection that can be handled by save_data().  Special
        care must be taken when processing io_log (and in the future,
        attachments) as those can be arbitrarily large.
        """
        data = {
            'result_map': {}
        }
        if self.OPTION_WITH_JOB_LIST in self._option_list:
            data['job_list'] = [job.name for job in session.job_list]
        if self.OPTION_WITH_RUN_LIST in self._option_list:
            data['run_list'] = [job.name for job in session.run_list]
        if self.OPTION_WITH_DESIRED_JOB_LIST in self._option_list:
            data['desired_job_list'] = [job.name
                                        for job in session.desired_job_list]
        if self.OPTION_WITH_RESOURCE_MAP in self._option_list:
            data['resource_map'] = {
                # TODO: there is no method to get all data from a Resource
                # instance and there probably should be. Or just let there be
                # a way to promote _data to a less hidden-but-non-conflicting
                # property.
                resource_name: [
                    object.__getattribute__(resource, "_data")
                    for resource in resource_list]
                # TODO: turn session._resource_map to a public property
                for resource_name, resource_list
                in session._resource_map.items()
            }
        if self.OPTION_WITH_ATTACHMENTS in self._option_list:
            data['attachment_map'] = {}
        for job_name, job_state in session.job_state_map.items():
            if job_state.result.outcome is None:
                continue
            data['result_map'][job_name] = OrderedDict()
            data['result_map'][job_name]['outcome'] = job_state.result.outcome
            if self.OPTION_WITH_COMMENTS in self._option_list:
                data['result_map'][job_name]['comments'] = \
                    job_state.result.comments

            # Add Job definitions if requested
            if self.OPTION_WITH_JOB_DEFS in self._option_list:
                for prop in ('plugin',
                             'requires',
                             'depends',
                             'command',
                             'description',
                             ):
                    if not getattr(job_state.result.job, prop):
                        continue
                    data['result_map'][job_name][prop] = getattr(
                        job_state.result.job, prop)

            # Add Attachments if requested
            if job_state.result.job.plugin == 'attachment':
                if self.OPTION_WITH_ATTACHMENTS in self._option_list:
                    raw_bytes = b''.join(
                        (record[2] for record in
                         job_state.result.io_log if record[1] == 'stdout'))
                    data['attachment_map'][job_name] = \
                        base64.standard_b64encode(raw_bytes).decode('ASCII')
                continue  # Don't add attachments IO logs to the result_map

            # Add IO log if requested
            if self.OPTION_WITH_IO_LOG in self._option_list:
                # If requested, squash the IO log so that only textual data is
                # saved, discarding stream name and the relative timestamp.
                if self.OPTION_SQUASH_IO_LOG in self._option_list:
                    io_log_data = self._squash_io_log(
                        job_state.result.io_log)
                elif self.OPTION_FLATTEN_IO_LOG in self._option_list:
                    io_log_data = self._flatten_io_log(
                        job_state.result.io_log)
                else:
                    io_log_data = self._io_log(job_state.result.io_log)
                data['result_map'][job_name]['io_log'] = io_log_data
        return data

    @classmethod
    def _squash_io_log(cls, io_log):
        # Squash the IO log by discarding everything except for the 'data'
        # portion. The actual data is escaped with base64.
        return [
            base64.standard_b64encode(record.data).decode('ASCII')
            for record in io_log]

    @classmethod
    def _flatten_io_log(cls, io_log):
        # Similar to squash but also coalesce all records into one big base64
        # string (there are no arrays / lists anymore)
        return base64.standard_b64encode(
            b''.join([record.data for record in io_log])
        ).decode('ASCII')

    @classmethod
    def _io_log(cls, io_log):
        # Return the raw io log, but escape the data portion with base64
        return [(record.delay, record.stream_name,
                 base64.standard_b64encode(record.data).decode('ASCII'))
                for record in io_log]

    @abstractmethod
    def dump(self, data, stream):
        """
        Dump data to stream.

        This method operates on data that was returned by
        get_session_data_subset(). It may not really process bytes or simple
        collections. Instead, for efficiency, anything is required.

        As in get_session_data_subset() it's essential to safely save
        arbitrarily large data sets (or actually, only where it matters the
        most, like in io_log).

        Data is a text stream suitable for writing.
        """
        # TODO: Add a way for the stream to be binary as well.


def get_all_exporters():
    """
    Discover and load all exporter classes.

    Returns a map of exporters (mapping from name to exporter class)
    """
    exporter_map = OrderedDict()
    iterator = pkg_resources.iter_entry_points('plainbox.exporter')
    for entry_point in sorted(iterator, key=lambda ep: ep.name):
        try:
            exporter_cls = entry_point.load()
        except ImportError as exc:
            logger.exception("Unable to import {}: {}", entry_point, exc)
        else:
            exporter_map[entry_point.name] = exporter_cls
    return exporter_map
