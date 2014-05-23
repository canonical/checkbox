# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.unit.test_init
============================

Test definitions for plainbox.impl.unit (package init file)
"""

from unittest import TestCase

from plainbox.impl.unit import Unit 
from plainbox.testing_utils.testcases import TestCaseWithParameters


class TestUnitDefinition(TestCase):

    def test_get_raw_record_value(self):
        """
        Ensure that get_raw_record_value() works okay
        """
        unit1 = Unit({'key': 'value'}, {'key': 'raw-value'})
        unit2 = Unit({'_key': 'value'}, {'_key': 'raw-value'})
        self.assertEqual(unit1.get_raw_record_value('key'), 'raw-value')
        self.assertEqual(unit2.get_raw_record_value('key'), 'raw-value')

    def test_get_record_value(self):
        """
        Ensure that get_record_value() works okay
        """
        unit1 = Unit({'key': 'value'}, {'key': 'raw-value'})
        unit2 = Unit({'_key': 'value'}, {'_key': 'raw-value'})
        self.assertEqual(unit1.get_record_value('key'), 'value')
        self.assertEqual(unit2.get_record_value('key'), 'value')

    def test_validate(self):
        unit = Unit({})
        unit.validate()

