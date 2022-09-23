# Copyright 2022 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for zapper_proxy module."""

from unittest import TestCase
from unittest.mock import Mock, patch

from checkbox_support.scripts.zapper_proxy import ZapperControlV1


class ZapperProxyV1Tests(TestCase):
    """Unit tests for ZapperProxyV1 class."""

    def setUp(self):
        self._mocked_conn = Mock()
        self._mocked_conn.root = Mock()

    def test_usb_get_state_smoke(self):
        """
        Check if usb_get_state calls appropriate function on the rpyc client.

        Current implementation on the service side uses mutable arguments for
        returning values (C-style stuff that should be removed) this is why we
        need the stateful side_effect below
        """
        def side_effect_fn(_, ret):
            ret.append('ON')
            return True
        self._mocked_conn.root.zombiemux_get_state = Mock(
            side_effect=side_effect_fn)
        zapctl = ZapperControlV1(self._mocked_conn)

        with patch('builtins.print') as mocked_print:
            zapctl.usb_get_state(0)
            mocked_print.assert_called_once_with(
                'State for address 0 is ON')

    def test_usb_get_state_fails(self):
        """Check if usb_get_state quits with a proper message on failure."""
        self._mocked_conn.root.zombiemux_get_state = Mock(return_value=False)
        zapctl = ZapperControlV1(self._mocked_conn)
        with self.assertRaises(SystemExit) as context:
            zapctl.usb_get_state(0)
        self.assertEqual(
            context.exception.code, 'Failed to get state for address 0.')

    def test_usb_set_state_smoke(self):
        """
        Check if usb_set_state calls appropriate functions on the rpyc client.
        """
        self._mocked_conn.root.zombiemux_set_state = Mock(return_value=True)
        zapctl = ZapperControlV1(self._mocked_conn)
        with patch('builtins.print') as mocked_print:
            zapctl.usb_set_state(0, 'ON')
            mocked_print.assert_called_once_with(
                "State 'ON' set for the address 0.")

    def test_usb_set_state_fails(self):
        """Check if usb_set_state quits with a proper message on failure."""
        self._mocked_conn.root.zombiemux_set_state = Mock(return_value=False)
        zapctl = ZapperControlV1(self._mocked_conn)
        with self.assertRaises(SystemExit) as context:
            zapctl.usb_set_state(0, 'ON')
        self.assertEqual(
            context.exception.code, "Failed to set 'ON' state for address 0.")

    def test_get_capabilities_one_cap(self):
        """
        Check if get_capabilities properly prints one record.

        The record should be in Checkbox resource syntax and should not be
        surrounded by any newlines.
        """
        ret_val = [{'foo': 'bar'}]
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)
        zapctl = ZapperControlV1(self._mocked_conn)
        with patch('builtins.print') as mocked_print:
            zapctl.get_capabilities()
            mocked_print.assert_called_once_with('foo: bar')

    def test_get_capabilities_empty(self):
        """Check if get_capabilities prints nothing on no capabilities."""
        ret_val = []
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)
        zapctl = ZapperControlV1(self._mocked_conn)
        with patch('builtins.print') as mocked_print:
            zapctl.get_capabilities()
            mocked_print.assert_called_once_with('')

    def test_get_capabilities_multiple_caps(self):
        """
        Check if get_capabilities properly prints multiple records.

        The records should be in Checkbox resource syntax. Records should be
        separated by an empty line.
        """
        ret_val = [{'foo': 'bar'}, {'baz': 'biz'}]
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)
        zapctl = ZapperControlV1(self._mocked_conn)
        with patch('builtins.print') as mocked_print:
            zapctl.get_capabilities()
            mocked_print.assert_called_once_with('foo: bar\n\nbaz: biz')

    def test_get_capabilities_one_cap_multi_rows(self):
        """
        Check if get_capabilities properly prints a record with multiple caps.

        Each capability should be printed in a separate line.
        No additional newlines should be printed.
        """
        ret_val = [{'foo': 'bar', 'foo2': 'bar2'}]
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)
        zapctl = ZapperControlV1(self._mocked_conn)
        with patch('builtins.print') as mocked_print:
            zapctl.get_capabilities()
            mocked_print.assert_called_once_with('foo: bar\nfoo2: bar2')
