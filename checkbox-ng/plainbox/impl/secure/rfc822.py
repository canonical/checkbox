# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.secure.rfc822` -- RFC822 parser
===================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from inspect import cleandoc


class BaseRFC822Record:
    """
    Base class for tracking RFC822 records

    This is a simple container for the dictionary of data.
    """

    def __init__(self, data):
        self._data = data

    @property
    def data(self):
        """
        The data set (dictionary)
        """
        return self._data


class RFC822SyntaxError(SyntaxError):
    """
    SyntaxError subclass for RFC822 parsing functions
    """

    def __init__(self, filename, lineno, msg):
        self.filename = filename
        self.lineno = lineno
        self.msg = msg


def load_rfc822_records(stream, data_cls=dict):
    """
    Load a sequence of rfc822-like records from a text stream.

    Each record consists of any number of key-value pairs. Subsequent records
    are separated by one blank line. A record key may have a multi-line value
    if the line starts with whitespace character.

    Returns a list of subsequent values as instances BaseRFC822Record class. If
    the optional data_cls argument is collections.OrderedDict then the values
    retain their original ordering.
    """
    return list(gen_rfc822_records(stream, data_cls))


def gen_rfc822_records(stream, data_cls=dict):
    """
    Load a sequence of rfc822-like records from a text stream.

    Each record consists of any number of key-value pairs. Subsequent records
    are separated by one blank line. A record key may have a multi-line value
    if the line starts with whitespace character.

    Returns a list of subsequent values as instances BaseRFC822Record class. If
    the optional data_cls argument is collections.OrderedDict then the values
    retain their original ordering.
    """
    record = None
    data = None
    key = None
    value_list = None

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
        key = None
        value_list = None
        data = data_cls()
        record = BaseRFC822Record(data)

    def _commit_key_value_if_needed():
        """
        Finalize the most recently seen key: value pair
        """
        nonlocal key
        if key is not None:
            data[key] = cleandoc('\n'.join(value_list))
            key = None

    # Start with an empty record
    _new_record()
    # Iterate over subsequent lines of the stream
    for lineno, line in enumerate(stream, start=1):
        # Treat empty lines as record separators
        if line.strip() == "":
            # Commit the current record so that the multi-line value of the
            # last key, if any, is saved as a string
            _commit_key_value_if_needed()
            # If data is non-empty, yield the record, this allows us to safely
            # use newlines for formatting
            if data:
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
        # Treat lines with a colon as new key-value pairs
        elif ":" in line:
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
        # Treat all other lines as syntax errors
        else:
            raise _syntax_error("Unexpected non-empty line")
    # Make sure to commit the last key from the record
    _commit_key_value_if_needed()
    # Once we've seen the whole file return the last record, if any
    if data:
        yield record
