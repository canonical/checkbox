# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_applogic
===========================

Test definitions for plainbox.impl.applogic module
"""

from unittest import TestCase

from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.applogic import get_matching_job_list
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.testing_utils import make_job


class FunctionTests(TestCase):

    def test_get_matching_job_list(self):
        job_list = [make_job('foo'), make_job('froz'), make_job('barg')]
        self.assertEqual(
            get_matching_job_list(job_list, RegExpJobQualifier('f.*')),
            [make_job('foo'), make_job('froz')])


class PlainBoxConfigTests(TestCase):

    def test_smoke(self):
        config = PlainBoxConfig()
        self.assertIs(config.secure_id, Unset)
        secure_id = "0123456789ABCDE"
        config.secure_id = secure_id
        self.assertEqual(config.secure_id, secure_id)
        with self.assertRaises(ValueError):
            config.secure_id = "bork"
        self.assertEqual(config.secure_id, secure_id)
        del config.secure_id
        self.assertIs(config.secure_id, Unset)
