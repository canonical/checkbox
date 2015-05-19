# This file is part of Checkbox.
#
# Copyright 2011-2015 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io


class ModinfoResult():

    """
    A simple class to hold results for the MultipleModinfoParser.

    It has a dict keyed by module name, the data is another dict keyed by field
    with the contents of that field. Some fields can only appear once and the
    content will be a string. Some fields can appear multiple times so their
    key will contain a list of all the arguments they appeared with. So for
    each module, the value is exactly the dict that ModinfoParser.get_all will
    return.
    """

    def __init__(self):
        self.mod_data = {}

    def addModuleInfo(self, module, data):
        """Add the data dict as the value under the module's key."""
        self.mod_data[module] = data


class MultipleModinfoParser():

    """
    Parser for the modinfo_attachment.

    The modinfo_attachment contains records separated by newlines.
    Each record contains the module's name in the name: field (which
    should be the first one) and the rest of the record is, verbatim,
    the output of modinfo $MODULE_NAME.

    The modinfo data for each module can be parsed with ModinfoParser,
    while this parser takes care of splitting the records, running
    ModinfoParser with what it expects, and calling the addModuleInfo
    method for the result instance we were passed at run() time.
    """

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """
        Parse stream and add information for each module to the result.

        For each module found in the stream, its data will be parsed using
        ModinfoParser, and the result's addModuleInfo method will be called
        with the module name and a dict with all the data items parsed from
        it.
        """
        record = []
        mod_name = None
        for line in self.stream:
            # First line, extract module name from this
            # and don't add to the record
            if line.startswith("name:"):
                split_data = line.split(":")
                if len(split_data) == 2:
                    mod_name = split_data[1].strip()
                else:
                    mod_name = None
            else:
                if line.strip() == "" and record:
                    self._parse_record(record, result, mod_name)
                    # Reset the record and mod_name
                    record = []
                    mod_name = None
                else:
                    record.append(line)
        if record:
            # Process last record
            self._parse_record(record, result, mod_name)

    def _parse_record(self, record, result, module):
        """
        Parse the record and maybe add it to the result.

        The records parsed from "record" will be added to "result"
        as the data entry for "module".

        If module is empty or None, it means we couldn't get a module
        name, so don't really do the parsing as a name is strictly required.
        """
        if not module:
            return
        not_a_stream = "".join(record)
        parser = ModinfoParser(not_a_stream)
        data = parser.get_all()
        if any(data.values()):
            result.addModuleInfo(module, data)


class ModinfoParser(object):

    """
    Parser for modinfo information.

    This will take the stdout for modinfo output and return a dict populated
    with each field.

    Basic usage in your script:
    try:
        output = subprocess.check_output('/sbin/modinfo e1000e',
                                         stderr=subprocess.STDOUT,
                                         universal_newlines=True)
    except CalledProcessError as err:
        print("Error while running modinfo")
        print(err.output)
        return err.returncode

    parser = ModinfoParser(output)
    all_fields = parser.get_all()
    one_field = parser.get_field(field)
    """

    def __init__(self, stream):
        """
        Initialize the parser with the given stream.

        The stream should be a string.
        """
        self._modinfo = {'alias': [],
                         'author': '',
                         'depends': [],
                         'description': '',
                         'filename': '',
                         'firmware': [],
                         'intree': '',
                         'license': '',
                         'parm': [],
                         'srcversion': '',
                         'vermagic': '',
                         'version': ''}
        self._get_info(stream)

    def _get_info(self, stream):
        for line in stream.splitlines():
            # At this point, stream should be the stdout from the modinfo
            # command, in a list.
            try:
                key, data = line.split(':', 1)
            except ValueError:
                # Most likely this will be caused by a blank line in the
                # stream, so we just ignore it and move on.
                continue
            else:
                key = key.strip()
                data = data.strip()
                # First, we need to handle alias, parm, firmware, and depends
                # because there can be multiple lines of output for these.
                if key in ('alias', 'depend', 'firmware', 'parm',):
                    self._modinfo[key].append(data)
                else:
                    self._modinfo[key] = data

    def get_all(self):
        """
        Return all the module data as a dictionary.

        If there's no module data (i.e. all elements of the dict
        are empty), return an empty dict instead, which makes it
        easier for callers to verify emptiness while still returning
        a consistent data type.
        """
        if any(self._modinfo.values()):
            return self._modinfo
        else:
            return {}

    def get_field(self, field):
        """Return a specific field from the module data dictionary."""
        if field not in self._modinfo.keys():
            raise Exception("Key not found: %s" % field)
        else:
            return self._modinfo[field]


def parse_modinfo_attachment_output(output):
    r"""
    Parse modinfo_attachment-style output.

    The modinfo_attachment does this (which can also be used for testing)::

        for mod in $(lsmod | cut -f 1 -d " ")
        do
            printf "%-16s%s\n" "name:" "$mod"
            modinfo $mod
            echo
        done

    :returns: a dict with {'module': {'field': 'value', ...}} for each
    module listed. Note that the value can be either a string or a list of
    strings.
    """
    stream = io.StringIO(output)
    modparser = MultipleModinfoParser(stream)
    result = ModinfoResult()
    modparser.run(result)
    return result.mod_data
