from checkbox_support.helpers.file_watcher import FileWatcher, InotifyEvent
from unittest.mock import MagicMock, patch
import unittest


class TestInotifyEvent(unittest.TestCase):
    """
    Test the InotifyEvent data class.
    """

    def test_inotify_event_creation(self):
        event = InotifyEvent(
            wd=1, event_type="modify", cookie=0, name="test_file.txt"
        )
        self.assertEqual(event.wd, 1)
        self.assertEqual(event.event_type, "modify")
        self.assertEqual(event.cookie, 0)
        self.assertEqual(event.name, "test_file.txt")


class TestFileWatcher(unittest.TestCase):
    """
    Test the FileWatcher class by mocking system-level calls.
    """

    @patch.object(FileWatcher, "libc")
    def test_initialization_success(self, mock_libc):
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()
        self.assertEqual(watcher.fd, 123)

    @patch.object(FileWatcher, "libc")
    def test_initialization_failure(self, mock_libc):
        mock_libc.inotify_init.return_value = -1
        with self.assertRaises(SystemExit) as cm:
            FileWatcher()
        self.assertEqual(cm.exception.code, "Failed to initialize inotify")

    @patch.object(FileWatcher, "libc")
    def test_watch_directory_with_single_event(self, mock_libc):
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()

        test_path = "/tmp/test_dir"
        mock_watch_desc = 456
        mock_libc.inotify_add_watch.return_value = mock_watch_desc

        wd = watcher.watch_directory(test_path, "m")
        mock_libc.inotify_add_watch.assert_called_with(
            123, test_path.encode("utf-8"), 0x00000002
        )
        self.assertEqual(wd, mock_watch_desc)

    @patch.object(FileWatcher, "libc")
    def test_watch_directory_with_multiple_events(self, mock_libc):
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()

        test_path = "/tmp/test_dir"
        mock_watch_desc = 789
        mock_libc.inotify_add_watch.return_value = mock_watch_desc

        wd = watcher.watch_directory(test_path, "dmc")
        expected_mask = 0x00000200 | 0x00000002 | 0x00000100
        mock_libc.inotify_add_watch.assert_called_with(
            123, test_path.encode("utf-8"), expected_mask
        )
        self.assertEqual(wd, mock_watch_desc)

    @patch.object(FileWatcher, "libc")
    def test_stop_watch(self, mock_libc):
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()

        mock_watch_desc = 1011
        watcher.stop_watch(mock_watch_desc)
        mock_libc.inotify_rm_watch.assert_called_with(123, mock_watch_desc)

    def test_mask2event(self):
        watcher = FileWatcher()
        self.assertEqual(watcher._mask2event(0x00000002), "modify")
        self.assertEqual(watcher._mask2event(0x00000100), "create")
        self.assertEqual(watcher._mask2event(0x00000200), "delete")
        self.assertEqual(watcher._mask2event(0x0000FFFF), "unknown")

    @patch("checkbox_support.helpers.file_watcher.os.read")
    @patch("checkbox_support.helpers.file_watcher.InotifyEvent")
    @patch.object(FileWatcher, "libc")
    def test_read_events_single_event(
        self, mock_libc, mock_inotify_event, mock_os_read
    ):
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()

        mock_os_read.return_value = b"\x01\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x09\x00\x00\x00filename\x00"

        mock_event_instance = MagicMock()
        mock_inotify_event.return_value = mock_event_instance

        events = watcher.read_events(1024)

        mock_os_read.assert_called_with(watcher.fd, 1024)

        self.assertEqual(len(events), 1)

        mock_inotify_event.assert_called_with(1, "modify", 0, "filename")

        self.assertEqual(events[0], mock_event_instance)

    @patch("checkbox_support.helpers.file_watcher.os.read")
    @patch("checkbox_support.helpers.file_watcher.InotifyEvent")
    @patch.object(FileWatcher, "libc")
    def test_read_events_multiple_events(
        self, mock_libc, mock_inotify_event, mock_os_read
    ):
        # Mock multiple events in a single read
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()

        # Mock data for two events
        mock_os_read.return_value = (
            b"\x01\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x09\x00\x00\x00file_one\x00"
            + b"\x02\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x09\x00\x00\x00file_two\x00"
        )

        events = watcher.read_events(1024)

        self.assertEqual(len(events), 2)
        mock_inotify_event.assert_any_call(1, "modify", 0, "file_one")
        mock_inotify_event.assert_any_call(2, "delete", 0, "file_two")

    @patch(
        "checkbox_support.helpers.file_watcher.os.read",
        side_effect=KeyboardInterrupt,
    )
    @patch.object(FileWatcher, "stop_watch")
    @patch.object(FileWatcher, "libc")
    def test_read_events_keyboard_interrupt(
        self, mock_libc, mock_stop_watch, mock_os_read
    ):
        mock_libc.inotify_init.return_value = 123
        watcher = FileWatcher()

        watcher.read_events(1024)
        mock_stop_watch.assert_called_with(watcher.fd)


if __name__ == "__main__":
    unittest.main()
