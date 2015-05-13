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

from io import StringIO
from unittest import TestCase

from checkbox_support.parsers.pci_config import (PciSubsystemIdParser,
                                                 PciSubsystemIdResult)

INPUT1 = """\
00:00.0 Host bridge: Intel Corporation Haswell-ULT DRAM Controller (rev 09)
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
10: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
20: 00 00 00 00 00 00 00 00 00 00 00 00 28 10 0a 06
30: 00 00 00 00 e0 00 00 00 00 00 00 00 00 00 00 00

00:02.0 VGA compatible controller: Intel Corporation Haswell-ULT Integrated Graphics Controller (rev 09)
00: 86 80 16 0a 07 04 90 00 09 00 00 03 00 00 00 00
10: 04 00 00 f0 00 00 00 00 0c 00 00 e0 00 00 00 00
20: 01 30 00 00 00 00 00 00 00 00 00 00 28 10 0a 06
30: 00 00 00 00 90 00 00 00 00 00 00 00 0b 01 00 00
"""

INPUT2 = """\
00:00.0 Host bridge: Intel Corporation Haswell-ULT DRAM Controller (rev 09)
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
10: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
20: 00 00 00 00 00 00 00 00 00 00 00 00 28 10 0a 06
30: 00 00 00 00 e0 00 00 00 00 00 00 00 00 00 00 00
00:02.0 VGA compatible controller: Intel Corporation Haswell-ULT Integrated Graphics Controller (rev 09)
00: 86 80 16 0a 07 04 90 00 09 00 00 03 00 00 00 00
20: 01 30 00 00 00 00 00 00 00 00 00 00 28 10 0a 07
30: 00 00 00 00 90 00 00 00 00 00 00 00 0b 01 00 00
"""

INPUT3 = """\
Lorem ipsum dolor sit amet, consectetur adipiscing
elit, sed do eiusmod tempor incididunt ut labore et
dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in
voluptate velit esse cillum dolore eu fugiat nulla pariatur.

Excepteur sint occaecat cupidatat non proident, sunt
in culpa qui officia deserunt mollit anim id est laborum
"""

INPUT4 = """\
the first line is bogus in this input
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
10: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
20: 00 00 00 00 00 00 00 00 00 00 00 00 28 10 0a 06
30: 00 00 00 00 e0 00 00 00 00 00 00 00 00 00 00 00
"""

INPUT5 = """\
00:00.0 Host bridge: Intel Corporation Haswell-ULT DRAM Controller (rev 09)
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
10: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
20: someone really borked this line with crap 0a 06
30: 00 00 00 00 e0 00 00 00 00 00 00 00 00 00 00 00
"""

INPUT6 = """\
00:00.0 Host bridge: Intel Corporation Haswell-ULT DRAM Controller (rev 09)
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
10: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
50: 00 00 00 00 00 00 00 00 00 00 00 00 28 10 0a 06
30: 00 00 00 00 e0 00 00 00 00 00 00 00 00 00 00 00
"""

INPUT7 = """\
00:00.0 Host bridge: Intel Corporation Haswell-ULT DRAM Controller (rev 09)
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
10: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
20: 00 00 00 00 00 00 00 00 00 00 28 10 0a 06
30: 00 00 00 00 e0 00 00 00 00 00 00 00 00 00 00 00
"""

INPUT8 = """\
00:00.0 Host bridge: Intel Corporation Haswell-ULT DRAM Controller (rev 09)
00: 86 80 04 0a 06 00 90 20 09 00 00 06 00 00 00 00
"""


class TestPciSubsystemIdParser(TestCase):

    """Tests for the PCI subsystem ID parser."""

    def _parse_helper(self, input_stream):
        """
        Take an input string, wrap it in StringIO and run it
        through the parser, returning the result object
        """

        parser = PciSubsystemIdParser(StringIO(input_stream))
        result = PciSubsystemIdResult()
        parser.run(result)
        return result

    def test_good_input(self):
        """
        Test that a good input produces a nice output value.

        This is a test with no traps or tricks.
        """

        result = self._parse_helper(INPUT1)
        self.assertEqual(result.pci_subsystem_id, "060a")

    def test_badly_delimited_input(self):
        """
        Test a weird input where records are not separated by blank lines.

        Should still return a good system ID.
        """

        result = self._parse_helper(INPUT2)
        self.assertEqual(result.pci_subsystem_id, "060a")

    def test_lorem_ipsum(self):
        """
        Test someone trying to feed lorem ipsum into the parser.

        Should return an empty dict.
        """

        result = self._parse_helper(INPUT3)
        self.assertEqual(result.pci_subsystem_id, None)

    def test_bad_first_line(self):
        """
        Test a lspci stanza with a bad first line.

        The parser will check that the first line begins with a PCI
        BDF triplet. If not, the input is considered bogus.

        Should return an empty dict.
        """

        result = self._parse_helper(INPUT4)
        self.assertEqual(result.pci_subsystem_id, None)

    def test_bad_fourth_line(self):
        """
        Test a lspci stanza with a bad fourth line.

        The information we want is in the fourth line. This borked input
        even has the desired information in the correct position but the
        rest of the line is borked. Since it doesn't consist of hex
        octets it should be considered bogus.

        Should return an empty dict.
        """

        result = self._parse_helper(INPUT5)
        self.assertEqual(result.pci_subsystem_id, None)

    def test_bad_fourth_line_start_address(self):
        """
        Test a lspci stanza with a bad fourth line start address.

        The fourth line looks OK but the starting marker (which should
        be 20) is bad in this example.

        Should return an empty dict.
        """

        result = self._parse_helper(INPUT6)
        self.assertEqual(result.pci_subsystem_id, None)

    def test_short_fourth_line(self):
        """
        Test a lspci stanza with a short fourth line.

        Each line should contain exactly 16 octets. The data used in this
        test is short/truncated.

        Should return an empty dict.
        """

        result = self._parse_helper(INPUT7)
        self.assertEqual(result.pci_subsystem_id, None)

    def test_short_input(self):
        """
        Test a short lspci stanza.

        Should return an empty dict and not get stuck in an endless loop.
        """

        result = self._parse_helper(INPUT8)
        self.assertEqual(result.pci_subsystem_id, None)
