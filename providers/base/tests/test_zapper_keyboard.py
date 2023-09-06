"""This module provides test cases for the zapper_keyboard_test module."""
import struct
import unittest
from unittest.mock import patch, Mock

from bin import zapper_keyboard_test


class ZapperKeyboardTests(unittest.TestCase):
    """This class provides test cases for the zapper_keyboard_test module."""

    @patch("builtins.open")
    def test_read_keyboard_events(self, mock_open):
        """
        Read from event file and launch the callback if the event is
        from a keyboard.
        """
        event_type = 1  # keyboard event
        code = 10
        value = zapper_keyboard_test.KeyEvent.UP.value
        callback = Mock()

        class MockData:
            """Mock binary file content."""

            def read(self, _):
                """Read mocked data."""
                return struct.pack(
                    zapper_keyboard_test.EVENT_BIN_FORMAT,
                    0,
                    0,
                    event_type,
                    code,
                    value,
                )

        mock_open.return_value.__enter__.return_value = MockData()

        zapper_keyboard_test.read_keyboard_events("", callback.fun1)
        callback.fun1.assert_called_with((zapper_keyboard_test.KeyEvent.UP, code))

    @patch("bin.zapper_keyboard_test.zapper_run")
    def test_assert_key_combo(self, mock_run):
        """
        Check if the function properly clear the events list and
        run the right zapper_run method for key combos.
        """
        events = [1, 2, 3]
        host = "127.0.0.1"

        with self.assertRaises(AssertionError):
            zapper_keyboard_test.assert_key_combo(host, events)

        assert events == []
        mock_run.assert_called_with(
            host,
            "robot_run",
            zapper_keyboard_test.ROBOT_TESTCASE_COMBO.encode(),
            {},
            {},
        )

    @patch("bin.zapper_keyboard_test.zapper_run")
    def test_assert_type_string(self, mock_run):
        """
        Check if the function properly clear the events list and
        run the right zapper_run method for string typing.
        """
        events = [1, 2, 3]
        host = "127.0.0.1"

        with self.assertRaises(AssertionError):
            zapper_keyboard_test.assert_type_string(host, events)

        assert events == []
        mock_run.assert_called_with(
            host,
            "robot_run",
            zapper_keyboard_test.ROBOT_TESTCASE_TYPE.encode(),
            {},
            {},
        )

    def test_main_no_args(self):
        """Check main exits with failure if input is missing."""
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1])

    @patch("os.path.realpath")
    def test_main_no_keyboard(self, mock_realpath):
        """Check main exits with failure if Zapper keyboard is missing."""
        mock_realpath.side_effect = FileNotFoundError
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1, 2])

    @patch("bin.zapper_keyboard_test.assert_type_string")
    @patch("bin.zapper_keyboard_test.assert_key_combo")
    @patch("threading.Thread", Mock())
    @patch("os.path.realpath", Mock())
    def test_main(self, mock_combo, mock_type):
        """Check main exits with failure if any of the test fails."""

        mock_combo.side_effect = AssertionError
        mock_type.side_effect = None
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1, 2])

        mock_combo.side_effect = None
        mock_type.side_effect = AssertionError
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1, 2])

        # Happy case
        mock_combo.side_effect = None
        mock_type.side_effect = None
        zapper_keyboard_test.main([1, 2])
