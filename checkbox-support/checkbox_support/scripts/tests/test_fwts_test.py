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

import unittest

from tempfile import NamedTemporaryFile
import os
from io import StringIO

from checkbox_support.scripts.fwts_test import print_log
from unittest.mock import patch


class LogPrinterTest(unittest.TestCase):
    def setUp(self):
        self.logfile = NamedTemporaryFile(delete=False)

    @patch("sys.stdout", new_callable=StringIO)
    def test_logfile_with_encoding_error(self, mock_stdout):
        with open(self.logfile.name, "wb") as f:
            f.write(b"Cannot read PCI config for device 0000:00:\xa1")
            f.write(b"<85>)PNP0B00:00\n")
            f.write(b"SKIPPED: Test 2, Could not guess cache type.\n")
        print_log(self.logfile.name)
        self.assertEqual(
            mock_stdout.getvalue(),
            "WARNING: Found bad char in " + self.logfile.name + "\n",
        )
        os.unlink(self.logfile.name)

    def tearDown(self):
        try:
            os.unlink(self.logfile.name)
        except OSError:
            pass
