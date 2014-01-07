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
#
from tempfile import NamedTemporaryFile
import os
import unittest

from checkbox.scripts.gputest_benchmark import check_log
from checkbox.vendor.mock import patch


class LogParserTest(unittest.TestCase):

    def setUp(self):
        self.logfile = NamedTemporaryFile(delete=False)
        self.devnull = open(os.devnull, 'w')

    def test_logfile_not_found(self):
        os.unlink(self.logfile.name)
        with self.assertRaises(SystemExit) as cm:
            check_log(self.logfile.name)
        self.assertEqual(
            "[Errno 2] No such file or directory: "
            "'{}'".format(self.logfile.name),
            str(cm.exception))

    def test_logfile_with_score(self):
        with open(self.logfile.name, 'wt') as f:
            f.write('FurMark : init OK.\n')
            f.write('[Benchmark_Score] - module: FurMark - Score: 8 points'
                    '(800x600 windowed, duration:2000 ms).')
        with patch('sys.stdout', self.devnull):
            self.assertFalse(check_log(self.logfile.name))
        os.unlink(self.logfile.name)

    def test_logfile_without_score(self):
        with open(self.logfile.name, 'wt') as f:
            f.write('FurMark : init OK.\n')
            f.write('[No_Score] - module: FurMark - Score: _ points'
                    '(800x600 windowed, duration:2000 ms).')
        with patch('sys.stdout', self.devnull):
            with self.assertRaises(SystemExit) as cm:
                check_log(self.logfile.name)
            self.assertEqual(
                'Benchmark score not found, check the log for errors',
                str(cm.exception))
        os.unlink(self.logfile.name)

    def test_logfile_with_encoding_error(self):
        with open(self.logfile.name, 'wb') as f:
            f.write(b'\x80abc\n')
            f.write(b'FurMark : init OK.\n')
            f.write(b'[Benchmark_Score] - module: FurMark - Score: 116 points'
                    b'(800x600 windowed, duration:2000 ms).')
        with patch('sys.stdout', self.devnull):
            self.assertFalse(check_log(self.logfile.name))
        os.unlink(self.logfile.name)

    def tearDown(self):
        try:
            os.unlink(self.logfile.name)
        except OSError:
            pass
