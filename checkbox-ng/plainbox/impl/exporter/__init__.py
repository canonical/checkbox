# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
:mod:`plainbox.impl.exporter` -- shared code for session state exporters
========================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from io import RawIOBase
from logging import getLogger
import base64

import pkg_resources

from plainbox.i18n import gettext as _

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
    OPTION_WITH_JOB_VIA = 'with-job-via'
    OPTION_WITH_JOB_HASH = 'with-job-hash'

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
        OPTION_WITH_JOB_VIA,
        OPTION_WITH_JOB_HASH,
    )

    def __init__(self, option_list=None):
        if option_list is None:
            option_list = []
        for option in option_list:
            if option not in self.supported_option_list:
                raise ValueError("Unsupported option: {}".format(option))
        self._my_option_list = option_list

    @property
    def _option_list(self):
        return self._my_option_list

    @_option_list.setter
    def _option_list(self, value):
        """
        Sets the option list to exactly what is sent as the parameter.
        Note that this will obliterate any prior settings in the list.
        """
        self._my_option_list = value

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

        Must return a collection that can be handled by :meth:`dump()`.
        Special care must be taken when processing io_log (and in the future,
        attachments) as those can be arbitrarily large.
        """
        data = {
            'result_map': {}
        }
        if self.OPTION_WITH_JOB_LIST in self._option_list:
            data['job_list'] = [job.id for job in session.job_list]
        if self.OPTION_WITH_RUN_LIST in self._option_list:
            data['run_list'] = [job.id for job in session.run_list]
        if self.OPTION_WITH_DESIRED_JOB_LIST in self._option_list:
            data['desired_job_list'] = [job.id
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
        for job_id, job_state in session.job_state_map.items():
            if job_state.result.outcome is None:
                continue
            data['result_map'][job_id] = OrderedDict()
            data['result_map'][job_id]['outcome'] = job_state.result.outcome
            if job_state.result.execution_duration:
                data['result_map'][job_id]['execution_duration'] = \
                    job_state.result.execution_duration
            if self.OPTION_WITH_COMMENTS in self._option_list:
                data['result_map'][job_id]['comments'] = \
                    job_state.result.comments

            # Add Parent hash if requested
            if self.OPTION_WITH_JOB_VIA in self._option_list:
                data['result_map'][job_id]['via'] = job_state.job.via

            # Add Job hash if requested
            if self.OPTION_WITH_JOB_HASH in self._option_list:
                data['result_map'][job_id]['hash'] = job_state.job.checksum

            # Add Job definitions if requested
            if self.OPTION_WITH_JOB_DEFS in self._option_list:
                for prop in ('plugin',
                             'requires',
                             'depends',
                             'command',
                             'description',
                             ):
                    if not getattr(job_state.job, prop):
                        continue
                    data['result_map'][job_id][prop] = getattr(
                        job_state.job, prop)

            # Add Attachments if requested
            if job_state.job.plugin == 'attachment':
                if self.OPTION_WITH_ATTACHMENTS in self._option_list:
                    raw_bytes = b''.join(
                        (record[2] for record in
                         job_state.result.get_io_log()
                         if record[1] == 'stdout'))
                    data['attachment_map'][job_id] = \
                        base64.standard_b64encode(raw_bytes).decode('ASCII')
                continue  # Don't add attachments IO logs to the result_map

            # Add IO log if requested
            if self.OPTION_WITH_IO_LOG in self._option_list:
                # If requested, squash the IO log so that only textual data is
                # saved, discarding stream name and the relative timestamp.
                if self.OPTION_SQUASH_IO_LOG in self._option_list:
                    io_log_data = self._squash_io_log(
                        job_state.result.get_io_log())
                elif self.OPTION_FLATTEN_IO_LOG in self._option_list:
                    io_log_data = self._flatten_io_log(
                        job_state.result.get_io_log())
                else:
                    io_log_data = self._io_log(job_state.result.get_io_log())
                data['result_map'][job_id]['io_log'] = io_log_data
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


class ByteStringStreamTranslator(RawIOBase):
    """
    This is a sort of "impedance matcher" that bridges the gap between
    something that expects to write strings to a stream and a stream
    that expects to receive bytes. Instead of using, for instance, an
    intermediate in-memory IO object, this decodes on the fly and
    has the same interface as a writable stream, so it can be initialized
    with the destination string stream and then passed to something
    (usually a dump-style function) that writes bytes.
    """

    def __init__(self, dest_stream, encoding):
        """
        Create a stream that will take bytes, decode them into strings
        according to the specified encoding, and then write them
        as bytes into the destination stream.

        :param dest_stream:
            the destination string stream.

        :param encoding:
            Encoding with which bytes data is encoded. It will be decoded
            using the same encoding to obtain the string to be written.

        """
        self.dest_stream = dest_stream
        self.encoding = encoding

    def write(self, data):
        """ Writes to the stream, takes bytes and decodes them per the
            object's specified encoding prior to writing.
            :param data: the chunk of data to write.
        """
        return self.dest_stream.write(data.decode(self.encoding))


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
        except pkg_resources.DistributionNotFound as exc:
            logger.info(_("Unable to load %s: %s"), entry_point, exc)
        except ImportError as exc:
            logger.exception(_("Unable to import %s: %s"), entry_point, exc)
        else:
            exporter_map[entry_point.name] = exporter_cls
    return exporter_map
