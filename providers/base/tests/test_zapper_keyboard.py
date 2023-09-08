"""This module provides test cases for the zapper_keyboard_test module."""
import os
import struct
import threading
import unittest
from unittest.mock import patch, Mock

from bin import zapper_keyboard_test


class ZapperKeyboardTests(unittest.TestCase):
    """This class provides test cases for the zapper_keyboard_test module."""

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

    @patch("os.access")
    def test_main_no_file_or_permission(self, mock_access):
        """Check main exits with failure if Zapper keyboard is missing."""
        mock_access.return_value = False
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1, 2])

    @patch("bin.zapper_keyboard_test.assert_type_string")
    @patch("bin.zapper_keyboard_test.assert_key_combo")
    @patch("bin.zapper_keyboard_test.KeyboardListener")
    @patch("os.access")
    def test_main(self, mock_access, mock_key, mock_combo, mock_type):
        """Check main exits with failure if any of the test fails."""

        mock_access.return_value = True

        mock_combo.side_effect = AssertionError
        mock_type.side_effect = None
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1, 2])
        mock_key.return_value.start.assert_called_once_with()
        mock_key.return_value.stop.assert_called_once_with()
        mock_key.return_value.join.assert_called_once_with()

        mock_combo.side_effect = None
        mock_type.side_effect = AssertionError
        with self.assertRaises(SystemExit):
            zapper_keyboard_test.main([1, 2])

        # Happy case
        mock_combo.side_effect = None
        mock_type.side_effect = None
        zapper_keyboard_test.main([1, 2])


class KeyboardListenerTests(unittest.TestCase):
    """This class provides test cases for the KeyboardListener class."""

    @patch("os.open")
    def test_init(self, mock_open):
        """Test init function open and event file with the right parameters."""
        event_file_path = "/dev/input/event0"
        listener = zapper_keyboard_test.KeyboardListener(event_file_path, None)

        assert listener._keep_running
        mock_open.assert_called_with(event_file_path, os.O_RDONLY | os.O_NONBLOCK)

    @patch("os.read")
    @patch("os.open")
    def test_read_keyboard_events(self, mock_open, mock_read):
        """Test the function unpack events and call the callback if needed."""

        callback = Mock()
        listener = zapper_keyboard_test.KeyboardListener(None, callback)

        value = zapper_keyboard_test.KeyEvent.DOWN
        code = 30
        mock_read.return_value = struct.pack(
            "llHHI",
            0,
            0,
            1,
            code,
            value.value,
        )

        listener._read_keyboard_events()

        mock_read.assert_called_with(mock_open.return_value, listener.EVENT_BIN_SIZE)
        callback.assert_called_with((value, code))

    @patch("os.open", Mock())
    @patch("os.read")
    def test_read_keyboard_events_not_ready(self, mock_read):
        """
        Test the function can handle a BlockingIOError and do not call
        the callback when that happens.
        """

        callback = Mock()
        listener = zapper_keyboard_test.KeyboardListener(None, callback)

        mock_read.side_effect = BlockingIOError

        listener._read_keyboard_events()
        callback.assert_not_called()

    @patch("os.open", Mock())
    @patch("os.read")
    def test_read_keyboard_events_not_kbd(self, mock_read):
        """Test the function doesn't call the callback for non-kbd events."""

        callback = Mock()
        listener = zapper_keyboard_test.KeyboardListener(None, callback)

        value = zapper_keyboard_test.KeyEvent.DOWN
        code = 30
        mock_read.return_value = struct.pack(
            "llHHI",
            0,
            0,
            2,
            code,
            value.value,
        )

        listener._read_keyboard_events()
        callback.assert_not_called()

    @patch("os.open", Mock())
    def test_run(self):
        """Test run function polls the event file until stopped."""

        listener = zapper_keyboard_test.KeyboardListener(None, None)
        called_event = threading.Event()
        listener._read_keyboard_events = called_event.set

        runner = threading.Thread(target=listener.run)
        runner.start()

        called_event.wait(1)
        if not called_event.is_set():
            raise AssertionError("Reader function not called")

        listener._keep_running = False
        runner.join(1)

        if runner.is_alive():
            raise AssertionError("Runner didn't stop.")

    @patch("os.close")
    @patch("os.open")
    def test_stop(self, mock_open, mock_close):
        """
        Test stop function stop the running loop and close the event files.
        """
        listener = zapper_keyboard_test.KeyboardListener(None, None)
        listener.stop()

        assert not listener._keep_running
        mock_close.assert_called_with(mock_open.return_value)
