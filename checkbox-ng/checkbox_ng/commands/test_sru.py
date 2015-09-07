# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
plainbox.impl.commands.test_sru
===============================

Test definitions for plainbox.impl.box module
"""

from inspect import cleandoc
from unittest import TestCase

from plainbox.testing_utils.io import TestIO

from checkbox_ng.main import main


class TestSru(TestCase):

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['sru', '--help'])
            self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: checkbox sru [-h] --secure_id SECURE-ID [-T TEST-PLAN-ID] [--staging]
                            [--check-config]

        optional arguments:
          -h, --help            show this help message and exit
          --secure_id SECURE-ID
                                Canonical hardware identifier
          -T TEST-PLAN-ID, --test-plan TEST-PLAN-ID
                                load the specified test plan
          --staging             Send the data to non-production test server
          --check-config        run check-config before starting
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
