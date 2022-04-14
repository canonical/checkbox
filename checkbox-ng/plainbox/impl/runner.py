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
Definition of JobRunner class.

:mod:`plainbox.impl.runner` -- job runner
=========================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import collections
import contextlib
import datetime
import getpass
import gzip
import io
import logging
import os
import select
import string
import subprocess
import sys
import tempfile
import threading
import time


from plainbox.abc import IJobResult, IJobRunner
from plainbox.i18n import gettext as _
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import IOLogRecordWriter
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.secure.config import Unset
from plainbox.vendor import extcmd
from plainbox.vendor import morris


logger = logging.getLogger("plainbox.runner")


def slugify(_string):
    """Transform any string to one that can be used in filenames."""
    valid_chars = frozenset(
        "-_.{}{}".format(string.ascii_letters, string.digits))
    return ''.join(c if c in valid_chars else '_' for c in _string)


class IOLogRecordGenerator(extcmd.DelegateBase):

    """Delegate for extcmd that generates io_log entries."""

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command is being invoked.

        Begins tracking time (relative time entries)
        """
        self.last_msg = datetime.datetime.utcnow()

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase.

        Creates a new IOLogRecord and passes it to :meth:`on_new_record()`.
        Maintains a timestamp of the last message so that approximate delay
        between each piece of output can be recorded as well.
        """
        now = datetime.datetime.utcnow()
        delay = now - self.last_msg
        self.last_msg = now
        record = IOLogRecord(delay.total_seconds(), stream_name, line)
        self.on_new_record(record)

    @morris.signal
    def on_new_record(self, record):
        """
        Internal signal method of :class:`IOLogRecordGenerator`.

        Called when a new record is generated and needs to be processed.
        """
        # TRANSLATORS: io means input-output
        logger.debug(_("io log generated %r"), record)


class CommandOutputWriter(extcmd.DelegateBase):

    """
    Delegate for extcmd that writes output to a file on disk.

    The file itself is only opened once on_begin() gets called by extcmd. This
    makes it safe to instantiate this without worrying about dangling
    resources.
    """

    def __init__(self, stdout_path, stderr_path):
        """
        Initialize new writer.

        Just records output paths.
        """
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command is being invoked
        """
        self.stdout = open(self.stdout_path, "wb")
        self.stderr = open(self.stderr_path, "wb")

    def on_end(self, returncode):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command finishes running
        """
        self.stdout.close()
        self.stderr.close()

    def on_abnormal_end(self, signal_num):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command abnormally finishes running
        """
        self.stdout.close()
        self.stderr.close()

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase.

        Called for each line of output.
        """
        if stream_name == 'stdout':
            self.stdout.write(line)
        elif stream_name == 'stderr':
            self.stderr.write(line)


class FallbackCommandOutputPrinter(extcmd.DelegateBase):

    """
    Delegate for extcmd that prints all output to stdout.

    This delegate is only used as a fallback when no delegate was explicitly
    provided to a JobRunner instance.
    """

    def __init__(self, prompt):
        """Initialize a new fallback command output printer."""
        self._prompt = prompt
        self._lineno = collections.defaultdict(int)
        self._abort = False

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase.

        Called for each line of output. Normally each line is just printed
        (assuming UTF-8 encoding) If decoding fails for any reason that and all
        subsequent lines are ignored.
        """
        if self._abort:
            return
        self._lineno[stream_name] += 1
        try:
            print("(job {}, <{}:{:05}>) {}".format(
                self._prompt, stream_name, self._lineno[stream_name],
                line.decode('UTF-8').rstrip()))
        except UnicodeDecodeError:
            self._abort = True


class JobRunnerUIDelegate(extcmd.DelegateBase):

    """
    Delegate for extcmd that delegates extcmd events to IJobRunnerUI.

    The file itself is only opened once on_begin() gets called by extcmd. This
    makes it safe to instantiate this without worrying about dangling
    resources.

    The instance attribute 'ui' can be changed at any time. It can also be set
    to None to silence all notifications from execution progress of external
    programs.
    """

    def __init__(self, ui=None):
        """
        Initialize the JobRunnerUIDelegate.

        :param ui:
            (optional) an instance of IJobRunnerUI to delegate events to
        """
        self.ui = ui

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command is being invoked
        """
        if self.ui is not None:
            self.ui.about_to_execute_program(args, kwargs)

    def on_end(self, returncode):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command finishes running
        """
        if self.ui is not None:
            self.ui.finished_executing_program(returncode)

    def on_abnormal_end(self, signal_num):
        """
        Internal method of extcmd.DelegateBase.

        Called when a command abnormally finishes running

        The negated signal number is used as the exit code of the program and
        fed into the UI (if any)
        """
        if self.ui is not None:
            self.ui.finished_executing_program(-signal_num)

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase.

        Called for each line of output.
        """
        if self.ui is not None:
            self.ui.got_program_output(stream_name, line)

    def on_chunk(self, stream_name, chunk):
        """
        Internal method of extcmd.DelegateBase.

        Called for each chunk of output.
        """
        if self.ui is not None:
            self.ui.got_program_output(stream_name, chunk)
