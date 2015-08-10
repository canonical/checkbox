# encoding: utf-8
# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
Implementation of job result (test result) classes.

:mod:`plainbox.impl.result` -- job result
=========================================

This module has two basic implementation of :class:`IJobResult`:
:class:`MemoryJobResult` and :class:`DiskJobResult`.
"""

import base64
import codecs
import gzip
import inspect
import io
import json
import logging
import re
from collections import namedtuple

from plainbox.abc import IJobResult
from plainbox.i18n import gettext as _
from plainbox.i18n import pgettext as C_
from plainbox.impl import pod
from plainbox.impl.decorators import raises

logger = logging.getLogger("plainbox.result")


# Regular expressions that match control characters, EXCEPT for the newline,
# carriage return, tab and vertical space
#
# According to http://unicode.org/glossary/#control_codes
# control codes are "The 65 characters in the ranges U+0000..U+001F and
# U+007F..U+009F. Also known as control characters."
#
# NOTE: we don't want to match certain control characters (newlines, carriage
# returns, tabs or vertical tabs as those are allowed by lxml and it would be
# silly to strip them.
CONTROL_CODE_RE_STR = re.compile(
    "(?![\n\r\t\v])[\u0000-\u001F]|[\u007F-\u009F]")


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


# Tuple representing meta-data associated with each possible value of "outcome"
#
# This tuple replaces various ad-hoc mapping that keyed off the outcome field
# to compute something. Currently the following fields are supported:
#
#   value - the actual constant like IJobResult.OUTCOME_NONE (for completeness)
#
#   unicode_sigil - a short string that renders to one character cell, useful
#   for representing this outcome in tabular renderings.
#
#   tr_outcome - a translatable, short string that describes the outcome. Those
#   strings are looked up with the context of "textual outcome" so that
#   translations can be more easily tuned without also affecting random parts
#   of the stack.
#
#   tr_label - a label suitable for displaying the type of the outcome. This is
#   different from tr_outcome as outcome but mostly in translations.
#
#   color_ansi - a string containing the ANSI escape sequence for colorizing
#   this outcome (or for representing it in general). This sequence is suitable
#   for various terminals.
#
#   color_hex - a string containing 7 character string like #RRGGBB that
#   encodes the hexadecimal representation of the color. This value is suitable
#   for graphical applications in the same way as color_ansi is useful for
#   console applications.
#
#   hexr_xml_mapping - a string that needs to be used in the XML report for the
#   Canonical HEXR application (also for the Canonical Certification web
#   application). Those values must be in sync with a piece of code in
#   checkbox_support that handles parsing of the XML report, for as long as the
#   report is to be maintained.
#
#   hexr_xml_allowed - a boolean indicating that this outcome may appear
#   in the XML document generated for the Canonical HEXR application. In
#   theory it can go away as we can now easily control both "sides"
#   (client and server) but it does exist today.
#
#   hexr_xml_order - an (optional) integer used for ordering allowed values.
#   This is used so that the XML output can have a fixed ordering regardless of
#   the actual order of entries in the dictionary.
OutcomeMetadata = namedtuple(
    "OutcomeMetadata", ("value unicode_sigil tr_outcome tr_label color_ansi"
                        " color_hex hexr_xml_mapping hexr_xml_allowed"
                        " hexr_xml_order"))

OUTCOME_METADATA_MAP = {
    IJobResult.OUTCOME_NONE: OutcomeMetadata(
        value=IJobResult.OUTCOME_NONE,
        unicode_sigil=' ',
        tr_outcome=C_("textual outcome", "job didn't run"),
        tr_label=C_("chart label", "not started"),
        color_ansi="",
        color_hex="#000000",
        hexr_xml_mapping="none",
        hexr_xml_allowed=True,
        hexr_xml_order=0,
    ),
    IJobResult.OUTCOME_PASS: OutcomeMetadata(
        value=IJobResult.OUTCOME_PASS,
        unicode_sigil='☑ ',
        tr_outcome=C_("textual outcome", "job passed"),
        tr_label=C_("chart label", "passed"),
        color_ansi="\033[32;1m",
        color_hex="#6AA84F",
        hexr_xml_mapping="pass",
        hexr_xml_allowed=True,
        hexr_xml_order=1,
    ),
    IJobResult.OUTCOME_FAIL: OutcomeMetadata(
        value=IJobResult.OUTCOME_FAIL,
        unicode_sigil='☒ ',
        tr_outcome=C_("textual outcome", "job failed"),
        tr_label=C_("chart label", "failed"),
        color_ansi="\033[31;1m",
        color_hex="#DC3912",
        hexr_xml_mapping="fail",
        hexr_xml_allowed=True,
        hexr_xml_order=2,
    ),
    IJobResult.OUTCOME_SKIP: OutcomeMetadata(
        value=IJobResult.OUTCOME_SKIP,
        unicode_sigil='☐ ',
        tr_outcome=C_("textual outcome", "job skipped"),
        tr_label=C_("chart label", "skipped"),
        color_ansi="\033[33;1m",
        color_hex="#FF9900",
        hexr_xml_mapping="skip",
        hexr_xml_allowed=True,
        hexr_xml_order=3,
    ),
    IJobResult.OUTCOME_NOT_SUPPORTED: OutcomeMetadata(
        value=IJobResult.OUTCOME_NOT_SUPPORTED,
        unicode_sigil='☐ ',
        tr_outcome=C_("textual outcome", "job cannot be started"),
        tr_label=C_("chart label", "not supported"),
        color_ansi="\033[33;1m",
        color_hex="#FF9900",
        hexr_xml_mapping="skip",
        hexr_xml_allowed=False,
        hexr_xml_order=None,
    ),
    IJobResult.OUTCOME_NOT_IMPLEMENTED: OutcomeMetadata(
        value=IJobResult.OUTCOME_NOT_IMPLEMENTED,
        unicode_sigil='-',
        tr_outcome=C_("textual outcome", "job is not implemented"),
        tr_label=C_("chart label", "not implemented"),
        color_ansi="\033[31;1m",
        color_hex="#DC3912",
        hexr_xml_mapping="skip",
        hexr_xml_allowed=False,
        hexr_xml_order=None,
    ),
    IJobResult.OUTCOME_UNDECIDED: OutcomeMetadata(
        value=IJobResult.OUTCOME_UNDECIDED,
        unicode_sigil='⁇ ',
        tr_outcome=C_("textual outcome", "job needs verification"),
        tr_label=C_("chart label", "undecided"),
        color_ansi="\033[35;1m",
        color_hex="#FF00FF",
        hexr_xml_mapping="skip",
        hexr_xml_allowed=False,
        hexr_xml_order=None,
    ),
    IJobResult.OUTCOME_CRASH: OutcomeMetadata(
        value=IJobResult.OUTCOME_CRASH,
        unicode_sigil='⚠ ',
        tr_outcome=C_("textual outcome", "job crashed"),
        tr_label=C_("chart label", "crashed"),
        color_ansi="\033[41;37;1m",
        color_hex="#FF0000",
        hexr_xml_mapping="fail",
        hexr_xml_allowed=False,
        hexr_xml_order=None,
    ),
}


def tr_outcome(outcome):
    """Get the translated value of ``OUTCOME_`` constant."""
    return OUTCOME_METADATA_MAP[outcome].tr_outcome


def outcome_color_hex(outcome):
    """Get the hexadecimal "#RRGGBB" color that represents this outcome."""
    return OUTCOME_METADATA_MAP[outcome].color_hex


def outcome_color_ansi(outcome):
    """Get an ANSI escape sequence that represents this outcome."""
    return OUTCOME_METADATA_MAP[outcome].color_ansi


def outcome_meta(outcome):
    """Get the OutcomeMetadata object associated with this outcome."""
    return OUTCOME_METADATA_MAP[outcome]


class JobResultBuilder(pod.POD):

    """A builder for job result objects."""

    outcome = pod.Field(
        'outcome of a test',
        str, pod.UNSET, assign_filter_list=[pod.unset_or_typed])
    execution_duration = pod.Field(
        'time of test execution',
        float, pod.UNSET, assign_filter_list=[pod.unset_or_typed])
    comments = pod.Field(
        'comments from the test operator',
        str, pod.UNSET, assign_filter_list=[pod.unset_or_typed])
    return_code = pod.Field(
        'return code from the (optional) test process',
        int, pod.UNSET, assign_filter_list=[pod.unset_or_typed])
    io_log = pod.Field(
        'history of the I/O log of the (optional) test process',
        list, pod.UNSET, assign_filter_list=[
            pod.unset_or_typed, pod.unset_or_typed.sequence(tuple)])
    io_log_filename = pod.Field(
        'path to a structured I/O log file of the (optional) test process',
        str, pod.UNSET, assign_filter_list=[pod.unset_or_typed])

    def add_comment(self, comment):
        """
        Add a new comment.

        The comment is safely combined with any prior comments.
        """
        if self.comments is pod.UNSET:
            self.comments = comment
        else:
            self.comments += '\n' + comment

    @raises(ValueError)
    def get_result(self):
        """
        Use the current state of the builder to create a new result.

        :returns:
            A new MemoryJobResult or DiskJobResult with all the data
        :raises ValueError:
            If both io_log and io_log_filename were used.
        """
        if not (self.io_log_filename is pod.UNSET or self.io_log is pod.UNSET):
            raise ValueError(
                "you can use only io_log or io_log_filename at a time")
        if self.io_log_filename is not pod.UNSET:
            cls = DiskJobResult
        else:
            cls = MemoryJobResult
        return cls(self.as_dict())


class _JobResultBase(IJobResult):

    """
    Base class for :`IJobResult` implementations.

    This class defines base properties common to all variants of `IJobResult`
    """

    def __init__(self, data):
        """
        Initialize a new result with the specified data.

        Data is a dictionary that can hold arbitrary values. At least some
        values are explicitly used, such as 'outcome', 'comments' and
        'return_code' but all of those are optional.
        """
        # Filter out boring items so that stuff that is rally identical,
        # behaves as if it was identical. This is especially important for
        # __eq__() below as various types of IJobResult are constructed and
        # compared with default entries that should not compare differently.
        self._data = {
            key: value for key, value in data.items()
            if value is not None and value != []}

    def get_builder(self, **kwargs):
        """Create a new job result builder from the data in this result."""
        builder = JobResultBuilder(**self._data)
        for key, value in kwargs.items():
            setattr(builder, key, value)
        return builder

    def __eq__(self, other):
        if not isinstance(other, _JobResultBase):
            return NotImplemented
        return self._data == other._data

    def __str__(self):
        return str(self.outcome)

    def __repr__(self):
        return "<{}>".format(
            ' '.join([self.__class__.__name__] + [
                "{}:{!r}".format(key, self._data[key])
                for key in sorted(self._data.keys())]))

    @property
    def outcome(self):
        """
        outcome of running this job.

        The outcome ultimately classifies jobs (tests) as failures or
        successes.  There are several other types of outcome that all basically
        mean that the job did not run for some particular reason.
        """
        return self._data.get('outcome', self.OUTCOME_NONE)

    def tr_outcome(self):
        """Get the translated value of the outcome."""
        return tr_outcome(self.outcome)

    def outcome_color_hex(self):
        """Get the hexadecimal "#RRGGBB" color that represents this outcome."""
        return outcome_color_hex(self.outcome)

    def outcome_color_rgb(self):
        h = outcome_meta(self.outcome).color_hex
        assert len(h) == 7, "expected format #RRGGBB"
        return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))

    def outcome_color_ansi(self):
        """Get an ANSI escape sequence that represents this outcome."""
        return outcome_color_ansi(self.outcome)

    def outcome_meta(self):
        """Get the OutcomeMetadata object associated with this outcome."""
        return outcome_meta(self.outcome)

    @property
    def execution_duration(self):
        """The amount of time in seconds it took to run this job."""
        return self._data.get('execution_duration')

    @property
    def comments(self):
        """Get the comments of the test operator."""
        return self._data.get('comments')

    @property
    def return_code(self):
        """return code of the command associated with the job, if any."""
        return self._data.get('return_code')

    @property
    def io_log(self):
        return tuple(self.get_io_log())

    @property
    def io_log_as_flat_text(self):
        """
        Perform a lossy conversion from the binary I/O log to text.

        Convert the I/O log to a text string, replacing non Unicode characters
        with U+FFFD, the REPLACEMENT CHARACTER.

        Both stdout and stderr streams are merged together into a single
        string. I/O log record are first decoded to UTF-8 and all control
        characters (EXCEPT for the newline, carriage return, tab and
        vertical space) are removed:

        >>> result = MemoryJobResult({'io_log': [
        ...            (0, 'stdout', b'foo\\n'),
        ...            (1, 'stderr', b'\u001Ebar\\n')]})
        >>> result.io_log_as_flat_text
        'foo\\nbar\\n'

        When the input bytes can’t be converted they are replaced by U+FFFD:

        >>> special_char = bytes([255,])
        >>> result = MemoryJobResult({'io_log': [(0, 'stdout', special_char)]})
        >>> result.io_log_as_flat_text
        '�'
        """
        return ''.join(
            CONTROL_CODE_RE_STR.sub('', text_chunk)
            for text_chunk in codecs.iterdecode(
                (record.data for record in self.get_io_log()),
                'UTF-8', 'replace'))

    @property
    def io_log_as_text_attachment(self):
        """
        Perform a conversion of the binary I/O log to text, if possible.

        Convert the I/O log to text attachment, if possible, otherwise return
        an empty string.

        This method is similar to
        :meth:`_JobResultBase.io_log_as_flat_text()` but only merge stdout
        records to recreate the original attachment file.

        :returns:
            stdout of the given job, converted to text (assuming UTF-8
            encoding) with Unicode control characters removed, if possible, or
            an empty string otherwise.
        """
        try:
            return ''.join(
                CONTROL_CODE_RE_STR.sub('', text_chunk)
                for text_chunk in codecs.iterdecode(
                    (record.data for record in self.get_io_log()
                        if record[1] == 'stdout'), 'UTF-8'))
        except UnicodeDecodeError:
            return ''

    @property
    def is_hollow(self):
        """
        flag that indicates if the result is hollow.

        Hollow results may have been created but hold no data at all.
        Hollow results are also tentatively deprecated, once we have some
        time to re-factor SessionState and specifically the job_state_map
        code we will remove the need to have hollow results.

        Hollow results are not saved, beginning with
        :class:`plainbox.impl.session.suspend.SessionSuspendHelper4`.
        """
        return not bool(self._data)


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
    Subclass of GzipFile that works around missing read1() on python3.2.

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
        """pathname of the file containing serialized IO log records."""
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
            # TRANSLATORS: please keep DiskJobResult.io_log untranslated
            _("Expensive DiskJobResult.io_log property access from %s:%d"),
            filename, lineno)
        return super(DiskJobResult, self).io_log


class IOLogRecordWriter:

    """Class for writing :class:`IOLogRecord` instances to a text stream."""

    def __init__(self, stream):
        self.stream = stream

    def close(self):
        self.stream.close()

    def write_record(self, record):
        """Write an :class:`IOLogRecord` to the stream."""
        text = json.dumps([
            record[0], record[1],
            base64.standard_b64encode(record[2]).decode("ASCII")],
            check_circular=False, ensure_ascii=True, indent=None,
            separators=(',', ':'))
        logger.debug(_("Encoded %r into string %r"), record, text)
        assert "\n" not in text
        self.stream.write(text)
        self.stream.write('\n')


class IOLogRecordReader:

    """Class for streaming :class`IOLogRecord` instances from a text stream."""

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
        Iterate over the entire stream generating subsequent records.

        This method generates subsequent :class:`IOLogRecord` entries.
        """
        while True:
            record = self.read_record()
            if record is None:
                break
            yield record
