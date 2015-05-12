# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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
import re
from collections import defaultdict


class ModprobeResult():

    """
    A simple class to hold results for the ModprobeParser.

    It simply stores the options in a dict, keyed by module name.
    """

    def __init__(self):
        self.mod_options = {}

    def addModprobeInfo(self, module, options):
        self.mod_options[module] = options


class ModprobeParser(object):

    """Parser for module configuration from /etc/modprobe.d."""

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """
        Parse stream and return sets of modules and option_strings.

        All the "option" statements for each module are collected into
        a set, and at the end the result's addModprobeInfo method is called
        for each set of  of module, option_string parameters.
        """
        mod_options = defaultdict(set)
        optregex = re.compile(r'^options\s+(?P<module>.+?)\s+(?P<options>.+)$')
        for line in self.stream.readlines():
            opt_matches = re.match(optregex, line)
            if opt_matches:
                module = opt_matches.group('module')
                options = opt_matches.group('options')
                for option in options.split():
                    mod_options[module].add(option)
        for module, options in mod_options.items():
            result.addModprobeInfo(module, " ".join(options))


def parse_modprobe_d_output(output):
    """
    Parse output of `cat /etc/modprobe.d/*`.

    :returns: a dict with {'module': 'options'} information sets.
    """
    stream = io.StringIO(output)
    modparser = ModprobeParser(stream)
    result = ModprobeResult()
    modparser.run(result)
    return result.mod_options
