#
# This file is part of Checkbox.
#
# Copyright 2011 Canonical Ltd.
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
                # Now handle unknown keys
                elif key not in self._modinfo.keys():
                    self._modinfo[key] = ("WARNING: Unknown Key %s providing "
                                     "data: %s") % (key, data)
                # And finally known keys
                else:
                    self._modinfo[key] = data

    def get_all(self):
        return self._modinfo

    def get_field(self, field):
        if field not in self._modinfo.keys():
            raise Exception("Key not found: %s" % field)
        else:
            return self._modinfo[field]
