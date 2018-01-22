# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <roadmr@ubuntu.com>
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
plainbox.impl.transport.test_init
=================================

Test definitions for plainbox.impl.transport module
"""

from unittest import TestCase

from plainbox.impl.transport import TransportBase


class TransportBaseTests(TestCase):

    class TestTransport(TransportBase):

        def send(self, data):
            """
            Dummy implementation of a method required by the base class.
            """

    def test_parameter_parsing(self):
        test_url = "http://test.com"
        test_opt_string = "secure_id=abcdefg000123,arbitrary_param=whatever"
        transport = self.TestTransport(test_url, test_opt_string)

        self.assertEqual(test_url, transport.url)
        self.assertEqual(sorted(['secure_id', 'arbitrary_param']),
                         sorted(transport.options.keys()))
        self.assertEqual("abcdefg000123", transport.options['secure_id'])
        self.assertEqual("whatever", transport.options['arbitrary_param'])

    def test_invalid_option_string_behavior(self):
        test_opt_string = "Something nonsensical"
        with self.assertRaises(ValueError):
            transport = self.TestTransport("", test_opt_string)
            self.assertIsInstance(TransportBase, transport)

    def test_empty_option_string_behavior(self):
        test_opt_string = ""
        transport = self.TestTransport("", test_opt_string)
        self.assertEqual([], list(transport.options.keys()))

    def test_double_equals_behavior(self):
        test_opt_string = "this=contains=equal"
        transport = self.TestTransport("", test_opt_string)
        self.assertEqual(['this'], list(transport.options.keys()))
        self.assertEqual("contains=equal", transport.options['this'])
