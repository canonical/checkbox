# Copyright 2022 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Paolo Gentili <paolo.gentili@canonical.com>
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

from checkbox_support.scripts.zapper_proxy import (
    get_capabilities,
    zapper_run,
    main,
)


class ZapperProxyV1Tests(TestCase):
    """Unit tests for ZapperProxy module."""

    def setUp(self):
        self._rpyc_mock = Mock()
        self._mocked_conn = Mock()
        self._rpyc_mock.connect.return_value = self._mocked_conn

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_zapper_run_smoke(self, import_mock):
        """
        Check if zapper_run calls the appropriate function on the rpyc client.
        """
        import_mock.return_value = self._rpyc_mock
        self._mocked_conn.root.command.return_value = "test"

        args = ["a", "b"]
        kwargs = {"k1": "v1", "k2": "v2"}
        result = zapper_run("0.0.0.0", "command", *args, **kwargs)
        self._mocked_conn.root.command.assert_called_once_with(*args, **kwargs)
        assert result == "test"

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_zapper_run_wrong_cmd(self, import_mock):
        """
        Check if SystemExit is raised when an unavailable command is requested.
        """
        import_mock.return_value = self._rpyc_mock
        self._mocked_conn.root.command.side_effect = AttributeError()
        with self.assertRaises(SystemExit):
            zapper_run("0.0.0.0", "command")

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_zapper_run_missing_rpyc(self, import_mock):
        """
        Check if SystemExit is raised when RPyC cannot be imported.
        """
        import_mock.side_effect = ImportError
        with self.assertRaises(SystemExit):
            zapper_run("0.0.0.0", "command")

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_zapper_run_service_error(self, import_mock):
        """
        Check if SystemExit is raised when an error occurs on Zapper service.
        """
        import_mock.return_value = self._rpyc_mock

        class TestException(Exception):
            pass

        self._rpyc_mock.core.vinegar.GenericException = TestException
        self._mocked_conn.root.command.side_effect = TestException()

        with self.assertRaises(SystemExit):
            zapper_run("0.0.0.0", "command")

    @patch("time.sleep", Mock())
    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_zapper_run_connection_error(self, import_mock):
        """
        Check if SystemExit is raised when the connections cannot be established
        after two tentatives.
        """
        import_mock.return_value = self._rpyc_mock
        self._rpyc_mock.connect.side_effect = ConnectionRefusedError()

        with self.assertRaises(SystemExit):
            zapper_run("0.0.0.0", "command")
        assert self._rpyc_mock.connect.call_count == 2

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_get_capabilities_one_cap(self, import_mock):
        """
        Check if get_capabilities properly prints one record.

        The record should be in Checkbox resource syntax and should not be
        surrounded by any newlines.
        """
        import_mock.return_value = self._rpyc_mock

        ret_val = [{"foo": "bar"}]
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)

        with patch("builtins.print") as mocked_print:
            get_capabilities("0.0.0.0")
            mocked_print.assert_called_once_with("foo: bar\n\navailable: True")

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_get_capabilities_error(self, import_mock):
        """
        Check if get_capabilities prints nothing on error while
        fetching capabilities.
        """
        import_mock.return_value = self._rpyc_mock

        self._mocked_conn.root.get_capabilities.side_effect = AttributeError

        with patch("builtins.print") as mocked_print:
            get_capabilities("0.0.0.0")
            mocked_print.assert_called_once_with("available: False")

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_get_capabilities_empty(self, import_mock):
        """Check if get_capabilities prints nothing on no capabilities."""
        import_mock.return_value = self._rpyc_mock

        ret_val = []
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)
        with patch("builtins.print") as mocked_print:
            get_capabilities("0.0.0.0")
            mocked_print.assert_called_once_with("available: True")

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_get_capabilities_multiple_caps(self, import_mock):
        """
        Check if get_capabilities properly prints multiple records.

        The records should be in Checkbox resource syntax. Records should be
        separated by an empty line.
        """
        import_mock.return_value = self._rpyc_mock

        ret_val = [{"foo": "bar"}, {"baz": "biz"}]
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)

        with patch("builtins.print") as mocked_print:
            get_capabilities("0.0.0.0")
            mocked_print.assert_called_once_with(
                "foo: bar\n\nbaz: biz\n\navailable: True"
            )

    @patch("checkbox_support.scripts.zapper_proxy.import_module")
    def test_get_capabilities_one_cap_multi_rows(self, import_mock):
        """
        Check if get_capabilities properly prints a record with multiple caps.

        Each capability should be printed in a separate line.
        No additional newlines should be printed.
        """
        import_mock.return_value = self._rpyc_mock

        ret_val = [{"foo": "bar", "foo2": "bar2"}]
        self._mocked_conn.root.get_capabilities = Mock(return_value=ret_val)

        with patch("builtins.print") as mocked_print:
            get_capabilities("0.0.0.0")
            mocked_print.assert_called_once_with(
                "foo: bar\nfoo2: bar2\n\navailable: True"
            )

    @patch("checkbox_support.scripts.zapper_proxy.zapper_run")
    def test_main_run(self, mock_run):
        """
        Check if main calls zapper_run with proper parameters.
        """
        main(["command", "arg1", "arg2", "--host", "myhost"])
        mock_run.assert_called_once_with("myhost", "command", "arg1", "arg2")

    @patch("checkbox_support.scripts.zapper_proxy.get_capabilities")
    def test_main_capabilities(self, mock_cap):
        """
        Check if main calls get_capabilities with zapper host.
        """
        main(["get_capabilities", "arg1", "arg2", "--host", "myhost"])
        mock_cap.assert_called_once_with("myhost")
