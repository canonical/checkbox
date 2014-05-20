#
# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

import json
import logging


class LshwJsonParser(object):

    def __init__(self, stream_or_string):
        self.stream_or_string = stream_or_string

    def _parse_lshw(self, lshw, result):
        if 'children' in lshw.keys():
            for child in lshw['children']:
                self._parse_lshw(child, result)
            del lshw['children']

        result.addHardware(lshw)

    def run(self, result):
        try:
            lshw = json.loads(self.stream_or_string)
        except ValueError as exc:
            logging.error("Unable to parse JSON: %s", exc)

        self._parse_lshw(lshw, result)
