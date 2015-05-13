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


class PciSubsystemIdResult():

    """Simple class to hold PCI Subsystem ID parsing results."""

    def __init__(self):
        self.pci_subsystem_id = None

    def setPciSubsystemId(self, pci_subsys_id):
        self.pci_subsystem_id = pci_subsys_id


class PciSubsystemIdParser():

    """
    Parser for lspci subsystem ID for devices.

    This takes the output from lspci -x (which shows the standard part of
    configuration space) and parses only the subsystem ID (4 hex digits)
    for the first device.
    """

    bdf_re = re.compile(r'[0-9a-fA-F]{2}:[0-9a-fA-F]{2}.[0-0a-fA-F] .*$')
    config_re = re.compile(r'([0-9a-fA-F]{2}): (([0-9a-fA-F]{2} ).+)$')

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """
        Parse the initialized lspci output.

        Returns nothing, but will call the result object's
        setPciSubsystemId method once with the susbystem ID for the
        first device found.
        """
        for line_no, line in enumerate(self.stream):
            if not line:
                return None
            line = line.strip()
            if line_no == 0:
                # This should be the BDF and device type and name
                if not re.match(self.bdf_re, line):
                    return None
            if line_no == 3:
                # The fourth line should contain the value we want
                matches = re.match(self.config_re, line)
                if matches:
                    # The first group marks the offset which we expect
                    # to be 20 for the fourth line (first line is the
                    # BDF, second and third lines are offsets 00 and 10
                    # respectively but we don't care about them).
                    if matches.group(1) != "20":
                        return None
                    octets = matches.group(2).split(" ")
                    # After the offset marker, we expect exactly 16
                    # hex octets of data.
                    if not len(octets) == 16:
                        return None
                    # The ID we want consists of the last and next-to-last
                    # octets (in that order, hence the index reversal).
                    result.setPciSubsystemId(octets[-1] + octets[-2])
                    break
                else:
                    return None


def parse_pci_subsys_id(output):
    """
    Parse output of `lspci -x`.

    :returns: an instance of PciSubsystemIdResult which will
    have a pci_subsystem_id attribute. This can either contain the
    actual subsystem ID, or None, if no valid subsystem ID could
    be extracted.
    """
    parser = PciSubsystemIdParser(io.StringIO(output))
    result = PciSubsystemIdResult()
    parser.run(result)
    return result
