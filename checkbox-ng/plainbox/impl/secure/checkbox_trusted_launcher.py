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
:mod:`plainbox.impl.secure.checkbox_trusted_launcher` -- command launcher
=========================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import argparse
import collections
import glob
import hashlib
import json
import os
import re
import subprocess
from inspect import cleandoc


class BaseJob:
    """
    Base Job definition class.
    """

    @property
    def plugin(self):
        return self.__getattr__('plugin')

    @property
    def command(self):
        try:
            return self.__getattr__('command')
        except AttributeError:
            return None

    @property
    def environ(self):
        try:
            return self.__getattr__('environ')
        except AttributeError:
            return None

    @property
    def user(self):
        try:
            return self.__getattr__('user')
        except AttributeError:
            return None

    def __init__(self, data):
        self._data = data

    def __getattr__(self, attr):
        if attr in self._data:
            return self._data[attr]
        raise AttributeError(attr)

    def get_checksum(self):
        """
        Compute a checksum of the job definition.

        This method can be used to compute the checksum of the canonical form
        of the job definition.  The canonical form is the UTF-8 encoded JSON
        serialization of the data that makes up the full definition of the job
        (all keys and values). The JSON serialization uses no indent and
        minimal separators.

        The checksum is defined as the SHA256 hash of the canonical form.
        """
        # Ideally we'd use simplejson.dumps() with sorted keys to get
        # predictable serialization but that's another dependency. To get
        # something simple that is equally reliable, just sort all the keys
        # manually and ask standard json to serialize that..
        sorted_data = collections.OrderedDict(sorted(self._data.items()))
        # Compute the canonical form which is arbitrarily defined as sorted
        # json text with default indent and separator settings.
        canonical_form = json.dumps(
            sorted_data, indent=None, separators=(',', ':'))
        # Compute the sha256 hash of the UTF-8 encoding of the canonical form
        # and return the hex digest as the checksum that can be displayed.
        return hashlib.sha256(canonical_form.encode('UTF-8')).hexdigest()

    def get_environ_settings(self):
        """
        Return a set of requested environment variables
        """
        if self.environ is not None:
            return {variable for variable in re.split('[\s,]+', self.environ)}
        else:
            return set()

    def modify_execution_environment(self, environ, packages):
        """
        Compute the environment the script will be executed in
        """
        # Get a proper environment
        env = dict(os.environ)
        # Use non-internationalized environment
        env['LANG'] = 'C.UTF-8'
        # Create CHECKBOX*_SHARE for every checkbox related packages
        # Add their respective script directory to the PATH variable
        # giving precedence to those located in /usr/lib/
        for path in packages:
            basename = os.path.basename(path)
            env[basename.upper().replace('-', '_') + '_SHARE'] = path
            # Update PATH so that scripts can be found
            env['PATH'] = os.pathsep.join([
                os.path.join('usr', 'lib', basename, 'bin'),
                os.path.join(path, 'scripts')]
                + env.get("PATH", "").split(os.pathsep))
        if 'CHECKBOX_DATA' in env:
            env['CHECKBOX_DATA'] = environ['CHECKBOX_DATA']
        # Add new environment variables only if they are defined in the
        # job environ property
        for key in self.get_environ_settings():
            if key in environ:
                env[key] = environ[key]
        return env


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


class Runner:
    """
    Runner for jobs

    Executes the command process and pipes back stdout/stderr
    """

    CHECKBOXES = "/usr/share/checkbox*"

    def __init__(self, builtin_jobs=[], packages=[]):
        # List of all available jobs in system-wide locations
        self.builtin_jobs = builtin_jobs
        # List of all checkbox variants, like checkbox-oem(-.*)?
        self.packages = packages

    def path_expand(self, path):
        for p in glob.glob(path):
            self.packages.append(p)
            for dirpath, dirs, filenames in os.walk(os.path.join(p, 'jobs')):
                for name in filenames:
                    if name.endswith(".txt"):
                        yield os.path.join(dirpath, name)

    def main(self, argv=None):
        parser = argparse.ArgumentParser(prog="checkbox-trusted-launcher")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--hash', metavar='HASH', help='job hash to match')
        group.add_argument(
            '--warmup',
            action='store_true',
            help='Return immediately, only useful when used with pkexec(1)')
        parser.add_argument(
            '--via',
            metavar='LOCAL-JOB-HASH',
            dest='via_hash',
            help='Local job hash to use to match the generated job')
        parser.add_argument(
            'ENV', metavar='NAME=VALUE', nargs='*',
            help='Set each NAME to VALUE in the string environment')
        args = parser.parse_args(argv)

        if args.warmup:
            return 0

        for filename in self.path_expand(self.CHECKBOXES):
            stream = open(filename, "r", encoding="utf-8")
            for message in load_rfc822_records(stream):
                self.builtin_jobs.append(BaseJob(message.data))
            stream.close()
        lookup_list = [j for j in self.builtin_jobs if j.user]

        if args.via_hash is not None:
            local_list = [j for j in self.builtin_jobs if j.plugin == 'local']
            desired_job_list = [j for j in local_list
                                if j.get_checksum() == args.via_hash]
            if desired_job_list:
                via_job = desired_job_list.pop()
                via_job_result = subprocess.Popen(
                    via_job.command,
                    shell=True,
                    universal_newlines=True,
                    stdout=subprocess.PIPE,
                    env=via_job.modify_execution_environment(
                        args.ENV,
                        self.packages)
                )
                try:
                    for message in load_rfc822_records(via_job_result.stdout):
                        message._data['via'] = args.via_hash
                        lookup_list.append(BaseJob(message.data))
                finally:
                    # Always call Popen.wait() in order to avoid zombies
                    via_job_result.stdout.close()
                    via_job_result.wait()

        try:
            target_job = [j for j in lookup_list
                          if j.get_checksum() == args.hash][0]
        except IndexError:
            return "Job not found"
        try:
            os.execve(
                '/bin/bash',
                ['bash', '-c', target_job.command],
                target_job.modify_execution_environment(
                    args.ENV,
                    self.packages)
            )
        # if execve doesn't fail, it never returns...
        except OSError:
            return "Fatal error"
        finally:
            return "Fatal error"


def main(argv=None):
    """
    Entry point for the checkbox trusted launcher
    """
    runner = Runner()
    raise SystemExit(runner.main(argv))
