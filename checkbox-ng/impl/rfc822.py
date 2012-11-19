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
plainbox.impl.rfc822
====================

Implementation of rfc822 serializer and deserializer.

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""


from inspect import cleandoc


class RFC822SyntaxError(SyntaxError):
    """
    SyntaxError subclass for RFC822 parsing functions
    """

    def __init__(self, filename, lineno, msg):
        self.filename = filename
        self.lineno = lineno
        self.msg = msg


def load_rfc822_records(stream, record_cls=dict):
    """
    Load a sequence of rtf822-like records from a text stream.

    Each record consists of any number of key-value pairs. Subsequent records
    are separated by one blank line. A record key may have a multi-line value
    if the line starts with whitespace character.

    Returns a list of subsequent values as instances of record_cls. If the
    optional record_cls argument is collections.OrderedDict then the values
    retain their original ordering.
    """
    return list(gen_rfc822_records(stream, record_cls))


def gen_rfc822_records(stream, record_cls=dict):
    """
    Load a sequence of rtf822-like records from a text stream.

    Each record consists of any number of key-value pairs. Subsequent records
    are separated by one blank line. A record key may have a multi-line value
    if the line starts with whitespace character.

    Generates subsequent values as instances of record_cls. If the optional
    record_cls argument is collections.OrderedDict then the values retain their
    original ordering.
    """
    record = None
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
        key = None
        value_list = None
        record = record_cls()

    def _commit_record():
        """
        Finalize the most recently seen key: value pair
        """
        nonlocal key
        if key is not None:
            record[key] = cleandoc('\n'.join(value_list))
            key = None
    # Start with an empty record
    _new_record()
    # Iterate over subsequent lines of the stream
    for lineno, line in enumerate(stream, start=1):
        # Treat empty lines as record separators
        if line.strip() == "":
            # Commit the current record so that the multi-line value of the
            # last key, if any, is saved as a string
            _commit_record()
            # If the record is non-empty, yield it, this allows us to safely
            # use newlines for formatting
            if record:
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
            value_list.append(line.rstrip())
        # Treat lines with a colon as new key-value pairs
        elif ":" in line:
            # Since we have a new, key-value pair we need to commit any
            # previous key that we may have (regardless of multi-line or
            # single-line values).
            _commit_record()
            # Parse the line by splitting on the colon, get rid of additional
            # whitespace from both key and the value
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            # Construct initial value list out of the (only) value that we have
            # so far. Additional multi-line values will just append to
            # value_list
            value_list = [value]
        # Treat all other lines as syntax errors
        else:
            raise _syntax_error("Unexpected non-empty line")
    # Once we've seen the whole file return the last record, if any
    _commit_record()
    if record:
        yield record
