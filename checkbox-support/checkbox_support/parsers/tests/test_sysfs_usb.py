# This file is part of Checkbox.
#
# Copyright 2020 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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


"""Tests for the sysfs_usb module."""
import textwrap

from unittest import TestCase
from unittest.mock import mock_open, patch

from checkbox_support.parsers.sysfs_usb import ishex
from checkbox_support.parsers.sysfs_usb import UsbIds


class TestIsHex(TestCase):
    """Tests for the is_hex function."""
    def test_good(self):
        """Test actual hexes."""
        self.assertTrue(ishex('1'))
        self.assertTrue(ishex('a'))
        self.assertTrue(ishex('5b'))
        self.assertTrue(ishex('1234567890abcdef'))

    def test_empty(self):
        """Test empty string."""
        self.assertTrue(ishex(''))

    def test_failing(self):
        """Test non-hexes."""
        self.assertFalse(ishex('g'))
        self.assertFalse(ishex('5x'))

    def test_hex_literal(self):
        """Test hex literal. It uses non-hex char - 'x'."""
        self.assertFalse(ishex('0xff'))

    def test_bad_type(self):
        """Test non string arguments."""
        with self.assertRaises(TypeError):
            self.assertFalse(ishex(0xff))
        with self.assertRaises(TypeError):
            self.assertFalse(ishex(True))


class TestUsbIds(TestCase):
    """Test for the UsbIds class."""
    def test_empty(self):
        """Test empty database."""
        mopen = mock_open(read_data='')
        with patch('builtins.open', mopen):
            ids = UsbIds()
            with self.assertRaises(KeyError):
                ids.decode_product(42, 42)
            self.assertEqual(ids.decode_protocol(42, 42, 42), '')

    @patch('os.path.isfile')
    def test_full_product(self, m_isfile):
        """Test good entry."""
        m_isfile.return_value = True
        usb_ids_content = textwrap.dedent("""
            0042  ACME
            \t0042  Seafourium
        """)
        mopen = mock_open(read_data=usb_ids_content)
        with patch('builtins.open', mopen):
            ids = UsbIds()
            self.assertEqual(ids.decode_product(0x42, 0x42), 'ACME Seafourium')

    @patch('os.path.isfile')
    def test_vendor_only(self, m_isfile):
        """Test entry with vendor only."""
        m_isfile.return_value = True
        usb_ids_content = textwrap.dedent("""
            0042  ACME
        """)
        mopen = mock_open(read_data=usb_ids_content)
        with patch('builtins.open', mopen):
            ids = UsbIds()
            self.assertEqual(ids.decode_vendor(0x42), 'ACME')

    @patch('os.path.isfile')
    def test_full_protocol(self, m_isfile):
        """Test full protocol triplet."""
        m_isfile.return_value = True
        usb_ids_content = textwrap.dedent("""
            C 42  Explosives
            \t06  Bomb
            \t\t01  Boom
        """)
        mopen = mock_open(read_data=usb_ids_content)
        with patch('builtins.open', mopen):
            ids = UsbIds()
            self.assertEqual(ids.decode_protocol(0x42, 0x06, 0x01),
                             'Explosives:Bomb:Boom')

    @patch('os.path.isfile')
    def test_class_and_subclass_only(self, m_isfile):
        """Test fallback to cid and scid."""
        m_isfile.return_value = True
        usb_ids_content = textwrap.dedent("""
            C 42  Explosives
            \t06  Bomb
        """)
        mopen = mock_open(read_data=usb_ids_content)
        with patch('builtins.open', mopen):
            ids = UsbIds()
            self.assertEqual(ids.decode_protocol(0x42, 0x06, 0x01),
                             'Explosives:Bomb')

    @patch('os.path.isfile')
    def test_class_only(self, m_isfile):
        """Test fallback to cid."""
        m_isfile.return_value = True
        usb_ids_content = textwrap.dedent("""
            C 42  Explosives
        """)
        mopen = mock_open(read_data=usb_ids_content)
        with patch('builtins.open', mopen):
            ids = UsbIds()
            self.assertEqual(ids.decode_protocol(0x42, 0x06, 0x01),
                             'Explosives')
