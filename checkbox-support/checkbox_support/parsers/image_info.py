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

"""
Parsers for OEM image information.

There are 3 possible attachments containing data relevant to OEM images::

    * /etc/buildstamp
    * recovery_info_attachment
    * dell_bto_xml_attachment

A class is provided to parse each of these.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io


class ImageInfoResult():

    """
    A simple class to hold image information results.

    It has methods for all the parser classes in this module so it can be
    easily reused.

    """

    def __init__(self):
        self.image_info = {}

    def addBuildstampInfo(self, data):
        """Add the given buildstamp."""
        self.image_info['buildstamp'] = data


class BuildstampParser():

    """
    Parser for the info/buildstamp attachment.

    Buildstamp is quite unstructured, so the parser is very simple, it will
    just verify that the attachment contains exactly 2 lines and call the
    addBuildstamp method of the resutl class with the entire content of the
    second line.
    """

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """Parse stream and set the buildstamp in the result."""
        buildstamp = ""
        for index, line in enumerate(self.stream):
            if index == 1:
                buildstamp = line
            if index >= 2 and line.strip() != '':
                # It contains more than 2 non-blank
                # lines, so exit right now,
                # this attachment looks bogus.
                return
        if buildstamp.strip():
            result.addBuildstampInfo(buildstamp.strip())


def parse_buildstamp_attachment_output(output):
    """Parse info/buildstamp attachment output."""
    stream = io.StringIO(output)
    parser = BuildstampParser(stream)
    result = ImageInfoResult()
    parser.run(result)
    return result.image_info['buildstamp']
