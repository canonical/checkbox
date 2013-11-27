# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.secure.rfc822` -- RFC822 parser
===================================================

Implementation of rfc822 serializer and deserializer.

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from functools import total_ordering
from inspect import cleandoc
import inspect
import logging

from plainbox.abc import ITextSource

logger = logging.getLogger("plainbox.secure.rfc822")


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
        return "???"

    def __repr__(self):
        return "<{}>".format(self.__class__.__name__)

    def __eq__(self, other):
        if isinstance(other, UnknownTextSource):
            return True
        else:
            return False

    def __gt__(self, other):
        return NotImplemented


@total_ordering
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
        return "<{} filename:{!r}>".format(
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


class PythonFileTextSource(FileTextSource):
    """
    A :class:`FileTextSource` subclass indicating the file was a python file.

    It implements no differences but in some context it might be helpful to
    differentiate on the type of the source field in the origin of a job
    definition record.

    :ivar filename:
        name of the python filename that something comes from
    """


@total_ordering
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


class RFC822Record:
    """
    Class for tracking RFC822 records

    This is a simple container for the dictionary of data.
    Each instance also holds the origin of the data
    """

    def __init__(self, data, origin=None):
        """
        Initialize a new record.

        :param data:
            A dictionary with record data
        :param origin:
            A :class:`Origin` instance that describes where the data came from
        """
        if origin is None:
            origin = Origin.get_caller_origin()
        self._data = data
        self._origin = origin

    def __repr__(self):
        return "<{} data:{!r} origin:{!r}>".format(
            self.__class__.__name__, self._data, self._origin)

    def __eq__(self, other):
        if isinstance(other, RFC822Record):
            return (self._data, self._origin) == (other._data, other._origin)
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, RFC822Record):
            return (self._data, self._origin) != (other._data, other._origin)
        return NotImplemented

    @property
    def data(self):
        """
        The data set (dictionary)
        """
        return self._data

    @property
    def origin(self):
        """
        The origin of the record.
        """
        return self._origin

    def dump(self, stream):
        """
        Dump this record to a stream
        """
        def _dump_part(stream, key, values):
            stream.write("%s:\n" % key)
            for value in values:
                if not value:
                    stream.write(" .\n")
                elif value == ".":
                    stream.write(" ..\n")
                else:
                    stream.write(" %s\n" % value)
        for key, value in self._data.items():
            if isinstance(value, (list, tuple)):
                _dump_part(stream, key, value)
            elif isinstance(value, str) and "\n" in value:
                values = value.split("\n")
                if not values[-1]:
                    values = values[:-1]
                _dump_part(stream, key, values)
            else:
                stream.write("%s: %s\n" % (key, value))
        stream.write("\n")


class RFC822SyntaxError(SyntaxError):
    """
    SyntaxError subclass for RFC822 parsing functions
    """

    def __init__(self, filename, lineno, msg):
        self.filename = filename
        self.lineno = lineno
        self.msg = msg

    def __eq__(self, other):
        if isinstance(other, RFC822SyntaxError):
            return ((self.filename, self.lineno, self.msg)
                    == (other.filename, other.lineno, other.msg))
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, RFC822SyntaxError):
            return ((self.filename, self.lineno, self.msg)
                    != (other.filename, other.lineno, other.msg))
        return NotImplemented


def load_rfc822_records(stream, data_cls=dict, source=None):
    """
    Load a sequence of rfc822-like records from a text stream.

    :param stream:
        A file-like object from which to load the rfc822 data
    :param data_cls:
        The class of the dictionary-like type to hold the results. This is
        mainly there so that callers may pass collections.OrderedDict.
    :param source:
        A :class:`plainbox.abc.ITextSource` subclass instance that describes
        where stream data is coming from. If None, it will be inferred from the
        stream (if possible). Specialized callers should provider a custom
        source object to allow developers to accurately keep track of where
        (possibly problematic) RFC822 data is coming from. If this is None and
        inferring fails then all of the loaded records will have a None origin.

    Each record consists of any number of key-value pairs. Subsequent records
    are separated by one blank line. A record key may have a multi-line value
    if the line starts with whitespace character.

    Returns a list of subsequent values as instances RFC822Record class.  If
    the optional data_cls argument is collections.OrderedDict then the values
    retain their original ordering.
    """
    return list(gen_rfc822_records(stream, data_cls, source))


def gen_rfc822_records(stream, data_cls=dict, source=None):
    """
    Load a sequence of rfc822-like records from a text stream.

    :param stream:
        A file-like object from which to load the rfc822 data
    :param data_cls:
        The class of the dictionary-like type to hold the results. This is
        mainly there so that callers may pass collections.OrderedDict.
    :param source:
        A :class:`plainbox.abc.ITextSource` subclass instance that describes
        where stream data is coming from. If None, it will be inferred from the
        stream (if possible). Specialized callers should provider a custom
        source object to allow developers to accurately keep track of where
        (possibly problematic) RFC822 data is coming from. If this is None and
        inferring fails then all of the loaded records will have a None origin.

    Each record consists of any number of key-value pairs. Subsequent records
    are separated by one blank line. A record key may have a multi-line value
    if the line starts with whitespace character.

    Returns a list of subsequent values as instances RFC822Record class. If
    the optional data_cls argument is collections.OrderedDict then the values
    retain their original ordering.
    """
    record = None
    data = None
    key = None
    value_list = None
    origin = None
    # If the source was not provided then try constructing a FileTextSource
    # from the name of the stream. If that fails, keep using None.
    if source is None:
        try:
            source = FileTextSource(stream.name)
        except AttributeError:
            source = UnknownTextSource()

    def _syntax_error(msg):
        """
        Report a syntax error in the current line
        """
        try:
            filename = stream.name
        except AttributeError:
            filename = None
        return RFC822SyntaxError(filename, lineno, msg)

    def _new_record():
        """
        Reset local state to track new record
        """
        nonlocal key
        nonlocal value_list
        nonlocal record
        nonlocal data
        nonlocal origin
        key = None
        value_list = None
        data = None
        if source is not None:
            origin = Origin(source, None, None)
        data = data_cls()
        record = RFC822Record(data, origin)

    def _commit_key_value_if_needed():
        """
        Finalize the most recently seen key: value pair
        """
        nonlocal key
        if key is not None:
            data[key] = cleandoc('\n'.join(value_list))
            logger.debug("Committed key/value %r=%r", key, data[key])
            key = None

    def _set_start_lineno_if_needed():
        """
        Remember the line number of the record start unless already set
        """
        if origin and record.origin.line_start is None:
            record.origin.line_start = lineno

    def _update_end_lineno():
        """
        Update the line number of the record tail
        """
        if origin:
            record.origin.line_end = lineno

    # Start with an empty record
    _new_record()
    # Iterate over subsequent lines of the stream
    for lineno, line in enumerate(stream, start=1):
        logger.debug("Looking at line %d:%r", lineno, line)
        # Treat empty lines as record separators
        if line.strip() == "":
            # Commit the current record so that the multi-line value of the
            # last key, if any, is saved as a string
            _commit_key_value_if_needed()
            # If data is non-empty, yield the record, this allows us to safely
            # use newlines for formatting
            if data:
                logger.debug("yielding record: %r", record)
                yield record
            # Reset local state so that we can build a new record
            _new_record()
        # Treat lines staring with whitespace as multi-line continuation of the
        # most recently seen key-value
        elif line.startswith(" "):
            if key is None:
                # If we have not seen any keys yet then this is a syntax error
                raise _syntax_error("Unexpected multi-line value")
            # Append the current line to the list of values of the most recent
            # key. This prevents quadratic complexity of string concatenation
            if line == " .\n":
                value_list.append(" ")
            elif line == " ..\n":
                value_list.append(" .")
            else:
                value_list.append(line.rstrip())
            # Update the end line location of this record
            _update_end_lineno()
        # Treat lines with a colon as new key-value pairs
        elif ":" in line:
            # Since this is actual data let's try to remember where it came
            # from. This may be a no-operation if there were any preceding
            # key-value pairs.
            _set_start_lineno_if_needed()
            # Since we have a new, key-value pair we need to commit any
            # previous key that we may have (regardless of multi-line or
            # single-line values).
            _commit_key_value_if_needed()
            # Parse the line by splitting on the colon, get rid of additional
            # whitespace from both key and the value
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            # Check if the key already exist in this message
            if key in record.data:
                raise _syntax_error((
                    "Job has a duplicate key {!r} "
                    "with old value {!r} and new value {!r}").format(
                        key, record.data[key], value))
            # Construct initial value list out of the (only) value that we have
            # so far. Additional multi-line values will just append to
            # value_list
            value_list = [value]
            # Update the end-line location
            _update_end_lineno()
        # Treat all other lines as syntax errors
        else:
            raise _syntax_error("Unexpected non-empty line")
    # Make sure to commit the last key from the record
    _commit_key_value_if_needed()
    # Once we've seen the whole file return the last record, if any
    if data:
        logger.debug("yielding record: %r", record)
        yield record
