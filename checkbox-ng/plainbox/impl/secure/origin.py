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
from plainbox.impl.symbol import SymbolDef


class OriginMode(SymbolDef):
    """
    A symbol definition (which will become an enumeration in the near future)
    that describes all the possible "modes" an :class:`Origin` can operate in.
    """
    # NOTE: this should be an enumeration
    whole_file = 'whole-file'
    single_line = 'single-line'
    line_range = 'line-range'


@functools.total_ordering
class Origin:
    """
    Simple class for tracking where something came from

    This class supports "pinpointing" something in a block of text. The block
    is described by the source attribute. The actual range is described by
    line_start (inclusive) and line_end (exclusive).

    :ivar source:
        Something that describes where the text came frome. Technically it
        should implement the :class:`~plainbox.abc.ITextSource` interface.

    :ivar line_start:
        The number of the line where the record begins. This can be None
        when the intent is to cover the whole file. This can also be equal
        to line_end (when not None) if the intent is to show a single line.

    :ivar line_end:
        The number of the line where the record ends
    """

    __slots__ = ['source', 'line_start', 'line_end']

    def __init__(self, source, line_start=None, line_end=None):
        self.source = source
        self.line_start = line_start
        self.line_end = line_end

    def mode(self):
        """
        Compute the "mode" of this origin instance.

        :returns:
            :attr:`OriginMode.whole_file`, :attr:`OriginMode.single_line`
            or :attr:`OriginMode.line_range`.

        The mode tells if this instance is describing the whole file,
        a range of lines or just a single line. It is mostly used internally
        by the implementation.
        """
        if self.line_start is None and self.line_end is None:
            return OriginMode.whole_file
        elif self.line_start == self.line_end:
            return OriginMode.single_line
        else:
            return OriginMode.line_range

    def __repr__(self):
        return "<{} source:{!r} line_start:{} line_end:{}>".format(
            self.__class__.__name__,
            self.source, self.line_start, self.line_end)

    def __str__(self):
        mode = self.mode()
        if mode is OriginMode.whole_file:
            return str(self.source)
        elif mode is OriginMode.single_line:
            return "{}:{}".format(self.source, self.line_start)
        elif mode is OriginMode.line_range:
            return "{}:{}-{}".format(
                self.source, self.line_start, self.line_end)
        else:
            raise NotImplementedError

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
        relative_source = self.source.relative_to(base_dir)
        if relative_source is not self.source:
            return Origin(relative_source, self.line_start, self.line_end)
        else:
            return self

    def with_offset(self, offset):
        """
        Create a new Origin by adding a offset of a specific number of lines

        :param offset:
            Number of lines to add (or substract)
        :returns:
            A new Origin object
        """
        mode = self.mode()
        if mode is OriginMode.whole_file:
            return self
        elif mode is OriginMode.single_line or mode is OriginMode.line_range:
            return Origin(self.source,
                          self.line_start + offset, self.line_end + offset)
        else:
            raise NotImplementedError

    def just_line(self):
        """
        Create a new Origin that points to the start line

        :returns:
            A new Origin with the end_line equal to start_line.
            This effectively makes the origin describe a single line.
        """
        return Origin(self.source, self.line_start, self.line_start)

    def just_file(self):
        """
        create a new Origin that points to the whole file

        :returns:
            A new Origin with line_end and line_start both set to None.
        """
        return Origin(self.source)

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

    def relative_to(self, path):
        return self


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
        Compute a FileTextSource with the filename being a relative path from
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
        return str(self.job.id)

    def __repr__(self):
        return "<{} job:{!r}>".format(self.__class__.__name__, self.job)

    def __eq__(self, other):
        if isinstance(other, JobOutputTextSource):
            return self.job == other.job
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, JobOutputTextSource):
            return self.job > other.job
        return NotImplemented

    def relative_to(self, base_path):
        return self


@functools.total_ordering
class CommandLineTextSource(ITextSource):
    """
    A :class:`ITextSource` describing text that originated arguments to main()

    :attr arg_name:
        The optional name of the argument that describes the arg_value
    :attr arg_value:
        The argument that was passed on command line (the actual text)
    """

    def __init__(self, arg_name, arg_value):
        self.arg_value = arg_value
        self.arg_name = arg_name

    def __str__(self):
        if self.arg_name is not None:
            return _("command line argument {}={!a}").format(
                self.arg_name, self.arg_value)
        else:
            return _("command line argument {!a}").format(self.arg_value)

    def __repr__(self):
        return "<{} arg_name:{!r} arg_value:{!r}>".format(
            self.__class__.__name__, self.arg_name, self.arg_value)

    def __eq__(self, other):
        if isinstance(other, CommandLineTextSource):
            return (self.arg_name == other.arg_name
                    and self.arg_value == other.arg_value)
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, CommandLineTextSource):
            if self.arg_name > other.arg_name:
                return True
            if self.arg_value > other.arg_value:
                return True
            return False
        return NotImplemented

    def relative_to(self, base_path):
        return self
