# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.secure.origin` -- origin objects
====================================================
"""

import functools
import inspect
import os

from plainbox.abc import ITextSource
from plainbox.i18n import gettext as _


@functools.total_ordering
class Origin:
    """
    Simple class for tracking where something came from

    :ivar source:
        something that describes where the text came frome, technically it
        should be a :class:`~plainbox.abc.ITextSource` subclass but that
        interface defines just the intent, not any concrete API.

    :ivar line_start:
        the number of the line where the record begins

    :ivar line_end:
        the number of the line where the record ends
    """

    __slots__ = ['source', 'line_start', 'line_end']

    def __init__(self, source, line_start, line_end):
        self.source = source
        self.line_start = line_start
        self.line_end = line_end

    def __repr__(self):
        return "<{} source:{!r} line_start:{} line_end:{}>".format(
            self.__class__.__name__,
            self.source, self.line_start, self.line_end)

    def __str__(self):
        return "{}:{}-{}".format(
            self.source, self.line_start, self.line_end)

    def relative_to(self, base_dir):
        """
        Create a Origin with source relative to the specified base directory.

        :param base_dir:
            A base directory name
        :returns:
            A new Origin with source replaced by the result of calling
            relative_to(base_dir) on the current source *iff* the current
            source has that method, self otherwise.

        This method is useful for obtaining user friendly Origin objects that
        have short, understandable filenames.
        """
        if hasattr(self.source, 'relative_to'):
            return Origin(
                self.source.relative_to(base_dir),
                self.line_start, self.line_end)
        else:
            return self

    def __eq__(self, other):
        if isinstance(other, Origin):
            return ((self.source, self.line_start, self.line_end) ==
                    (other.source, other.line_start, other.line_end))
        else:
            return NotImplemented

    def __gt__(self, other):
        if isinstance(other, Origin):
            return ((self.source, self.line_start, self.line_end) >
                    (other.source, other.line_start, other.line_end))
        else:
            return NotImplemented

    @classmethod
    def get_caller_origin(cls, back=0):
        """
        Create an Origin instance pointing at the call site of this method.
        """
        # Create an Origin instance that pinpoints the place that called
        # get_caller_origin().
        caller_frame, filename, lineno = inspect.stack(0)[2 + back][:3]
        try:
            source = PythonFileTextSource(filename)
            origin = Origin(source, lineno, lineno)
        finally:
            # Explicitly delete the frame object, this breaks the
            # reference cycle and makes this part of the code deterministic
            # with regards to the CPython garbage collector.
            #
            # As recommended by the python documentation:
            # http://docs.python.org/3/library/inspect.html#the-interpreter-stack
            del caller_frame
        return origin


@functools.total_ordering
class UnknownTextSource(ITextSource):
    """
    A :class:`ITextSource` subclass indicating that the source of text is
    unknown.

    This instances of this class are constructed by gen_rfc822_records() when
    no explicit source is provided and the stream has no name. The serve as
    non-None values to prevent constructing :class:`PythonFileTextSource` with
    origin computed from :meth:`Origin.get_caller_origin()`
    """

    def __str__(self):
        return _("???")

    def __repr__(self):
        return "{}()".format(self.__class__.__name__)

    def __eq__(self, other):
        if isinstance(other, UnknownTextSource):
            return True
        else:
            return False

    def __gt__(self, other):
        if isinstance(other, UnknownTextSource):
            return False
        else:
            return NotImplemented


@functools.total_ordering
class FileTextSource(ITextSource):
    """
    A :class:`ITextSource` subclass indicating that text came from a file.

    :ivar filename:
        name of the file something comes from
    """

    def __init__(self, filename):
        self.filename = filename

    def __str__(self):
        return self.filename

    def __repr__(self):
        return "{}({!r})".format(
            self.__class__.__name__, self.filename)

    def __eq__(self, other):
        if isinstance(other, FileTextSource):
            return self.filename == other.filename
        else:
            return False

    def __gt__(self, other):
        if isinstance(other, FileTextSource):
            return self.filename > other.filename
        else:
            return NotImplemented

    def relative_to(self, base_dir):
        """
        Compute a FileTextSource with the filename being a realtive path from
        the specified base directory.

        :param base_dir:
            A base directory name
        :returns:
            A new FileTextSource with filename relative to that base_dir
        """
        return self.__class__(os.path.relpath(self.filename, base_dir))


class PythonFileTextSource(FileTextSource):
    """
    A :class:`FileTextSource` subclass indicating the file was a python file.

    It implements no differences but in some context it might be helpful to
    differentiate on the type of the source field in the origin of a job
    definition record.

    :ivar filename:
        name of the python filename that something comes from
    """


@functools.total_ordering
class JobOutputTextSource(ITextSource):
    """
    A :class:`ITextSource` subclass indicating that text came from job output.

    This class is used by
    :meth:`SessionState._gen_rfc822_records_from_io_log()` to allow such
    (generated) jobs to be traced back to the job that generated them.

    :ivar job:
        :class:`plainbox.impl.job.JobDefinition` instance that generated the
        text
    """

    def __init__(self, job):
        self.job = job

    def __str__(self):
        return str(self.job)

    def __repr__(self):
        return "<{} job:{!r}".format(self.__class__.__name__, self.job)

    def __eq__(self, other):
        if isinstance(other, JobOutputTextSource):
            return self.job == other.job
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, JobOutputTextSource):
            return self.job > other.job
        return NotImplemented
