from unittest.mock import patch, MagicMock, mock_open
import webgl_conformance_test as wct
import unittest
import json


class MockFileWatcher:
    """A mock class for the FileWatcher."""

    def __init__(self):
        self.watch_directory_called = False
        self.stop_watch_called = False
        self.read_events_called = False
        self.events_to_return = []
        self.events_read_count = 0

    def watch_directory(self, directory, event_type):
        self.watch_directory_called = True
        return 1  # Return a mock file descriptor

    def read_events(self, buffer_size):
        self.read_events_called = True
        if self.events_read_count < len(self.events_to_return):
            event = self.events_to_return[self.events_read_count]
            self.events_read_count += 1
            return [event]
        return []

    def stop_watch(self, fd):
        self.stop_watch_called = True


class MockEvent:
    """A mock class for the FileWatcher event."""

    def __init__(self, event_type, name):
        self.event_type = event_type
        self.name = name

    def __repr__(self):
        return "MockEvent(event_type='{}', name='{}')".format(
            self.event_type, self.name
        )


class TestWebGLConformance(unittest.TestCase):
    """Unit tests for webgl_conformance_test.py."""

    @patch("os.path.isdir")
    @patch("webgl_conformance_test.FileWatcher", new=MockFileWatcher)
    def test_watch_test_result_success(self, mock_isdir):
        """Test watch_test_result for success."""
        mock_isdir.return_value = True
        fw = MockFileWatcher()
        fw.events_to_return.append(
            MockEvent(event_type="create", name="test_results.json")
        )
        with patch("webgl_conformance_test.FileWatcher", return_value=fw):
            result = wct.watch_test_result("/tmp", "test_results.json")
            self.assertTrue(result)
            self.assertTrue(fw.watch_directory_called)
            self.assertTrue(fw.read_events_called)
            self.assertTrue(fw.stop_watch_called)

    @patch("os.path.isdir")
    def test_watch_test_result_directory_not_found(self, mock_isdir):
        """Test watch_test_result when directory does not exist."""
        mock_isdir.return_value = False
        with self.assertRaises(SystemExit) as cm:
            wct.watch_test_result("/nonexistent", "results.json")
        self.assertEqual(
            cm.exception.code, "Directory [/nonexistent] does not exist"
        )

    @patch("os.path.isdir", return_value=True)
    @patch("webgl_conformance_test.FileWatcher")
    def test_watch_test_result_inotify_fail(self, mock_fw, mock_isdir):
        """Test watch_test_result when inotify fails."""
        mock_fw_instance = MagicMock()
        mock_fw_instance.watch_directory.return_value = -1
        mock_fw.return_value = mock_fw_instance
        with self.assertRaises(SystemExit) as cm:
            wct.watch_test_result("/tmp", "results.json")
        self.assertEqual(cm.exception.code, "Failed to add inotify watch")

    @patch("requests.get")
    def test_is_webgl_conformance_url_reachable_success(self, mock_get):
        """Test URL reachability success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        self.assertTrue(
            wct.is_webgl_conformance_url_reachable("http://test.url")
        )
        mock_get.assert_called_once_with("http://test.url", timeout=5)

    @patch("requests.get")
    def test_is_webgl_conformance_url_reachable_failure(self, mock_get):
        """Test URL reachability failure."""
        mock_get.side_effect = Exception("Connection error")
        with self.assertRaises(Exception) as cm:
            self.assertFalse(
                wct.is_webgl_conformance_url_reachable("http://test.url")
            )
        mock_get.assert_called_once_with("http://test.url", timeout=5)
        self.assertEqual(str(cm.exception), "Connection error")

    @patch("os.path.exists")
    @patch("os.remove")
    def test_remove_duplicate_file(self, mock_remove, mock_exists):
        """Test file removal when it exists."""
        mock_exists.return_value = True
        wct.remove_duplicate_file("/tmp/file.txt")
        mock_exists.assert_called_once_with("/tmp/file.txt")
        mock_remove.assert_called_once_with("/tmp/file.txt")

    @patch("os.path.exists")
    @patch("os.remove")
    def test_remove_duplicate_file_not_exist(self, mock_remove, mock_exists):
        """Test file removal when it doesn't exist."""
        mock_exists.return_value = False
        wct.remove_duplicate_file("/tmp/file.txt")
        mock_exists.assert_called_once_with("/tmp/file.txt")
        mock_remove.assert_not_called()

    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_success(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Test result validation with a successful outcome."""
        mock_getsize.return_value = 100
        mock_file.return_value.read.return_value = json.dumps(
            {
                "failures": [],
                "timeouts": [],
                "testinfo": {
                    "WebGL RENDERER": "NVIDIA",
                    "Unmasked RENDERER": "NVIDIA",
                },
            }
        )
        wct.validate_result("/tmp/results.json")
        mock_remove.assert_called_once_with("/tmp/results.json")

    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_empty_file(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Test result validation with an empty file."""
        mock_getsize.return_value = 0
        with self.assertRaises(SystemExit) as cm:
            wct.validate_result("/tmp/results.json")
        self.assertEqual(
            cm.exception.code, "WebGL conformance tests result is empty"
        )
        mock_remove.assert_not_called()

    @patch("os.remove")
    @patch("os.path.getsize", return_value=100)
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_json_parse_fail(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Test result validation with a JSON parsing error."""
        mock_file.return_value.read.return_value = "invalid json"
        with self.assertRaises(SystemExit) as cm:
            wct.validate_result("/tmp/results.json")
        self.assertIn(
            "Failed to parse test result file", str(cm.exception.code)
        )
        mock_remove.assert_not_called()

    @patch("os.remove")
    @patch("os.path.getsize", return_value=100)
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_software_renderer_llvm(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Validation when software rendering is detected (LLVM)."""
        mock_file.return_value.read.return_value = json.dumps(
            {
                "failures": [],
                "timeouts": [],
                "testinfo": {
                    "WebGL RENDERER": "llvmpipe",
                    "Unmasked RENDERER": "NVIDIA",
                },
            }
        )
        with self.assertRaises(SystemExit) as cm:
            wct.validate_result("/tmp/results.json")
        self.assertEqual(
            cm.exception.code, "Test is not running on hardware renderer"
        )
        mock_remove.assert_called_once_with("/tmp/results.json")

    @patch("os.remove")
    @patch("os.path.getsize", return_value=100)
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_software_renderer_swiftshader(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Validation when software rendering is detected (SwiftShader)."""
        mock_file.return_value.read.return_value = json.dumps(
            {
                "failures": [],
                "timeouts": [],
                "testinfo": {
                    "WebGL RENDERER": "NVIDIA",
                    "Unmasked RENDERER": "SwiftShader",
                },
            }
        )
        with self.assertRaises(SystemExit) as cm:
            wct.validate_result("/tmp/results.json")
        self.assertEqual(
            cm.exception.code, "Test is not running on hardware renderer"
        )
        mock_remove.assert_called_once_with("/tmp/results.json")

    @patch("os.remove")
    @patch("os.path.getsize", return_value=100)
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_failures(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Test result validation with test failures."""
        mock_file.return_value.read.return_value = json.dumps(
            {
                "failures": ["test_case_1"],
                "timeouts": [],
                "testinfo": {
                    "WebGL RENDERER": "NVIDIA",
                    "Unmasked RENDERER": "NVIDIA",
                },
            }
        )
        with self.assertRaises(SystemExit) as cm:
            wct.validate_result("/tmp/results.json")
        self.assertEqual(
            cm.exception.code, "Not all WebGL conformance tests are passed"
        )
        mock_remove.assert_called_once_with("/tmp/results.json")

    @patch("os.remove")
    @patch("os.path.getsize", return_value=100)
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_result_timeouts(
        self, mock_file, mock_getsize, mock_remove
    ):
        """Test result validation with test timeouts."""
        mock_file.return_value.read.return_value = json.dumps(
            {
                "failures": [],
                "timeouts": ["test_case_2"],
                "testinfo": {
                    "WebGL RENDERER": "NVIDIA",
                    "Unmasked RENDERER": "NVIDIA",
                },
            }
        )
        with self.assertRaises(SystemExit) as cm:
            wct.validate_result("/tmp/results.json")
        self.assertEqual(
            cm.exception.code, "Not all WebGL conformance tests are passed"
        )
        mock_remove.assert_called_once_with("/tmp/results.json")

    @patch("time.sleep", return_value=None)
    @patch(
        "webgl_conformance_test.is_webgl_conformance_url_reachable",
        return_value=False,
    )
    def test_execute_webgl_test_url_not_reachable(
        self, mock_is_reachable, mock_sleep
    ):
        """Test execute_webgl_test when URL is not reachable."""
        exception = (
            "Test URL is not reachable: http://localhost:8000/local-tests.html"
        )
        with self.assertRaises(SystemExit) as cm:
            wct.execute_webgl_test("firefox", "", "results.json", False)
        self.assertEqual(
            cm.exception.code,
            exception,
        )

    @patch("time.sleep", return_value=None)
    @patch("subprocess.Popen")
    @patch(
        "webgl_conformance_test.is_webgl_conformance_url_reachable",
        return_value=True,
    )
    @patch("webgl_conformance_test.remove_duplicate_file")
    @patch("webgl_conformance_test.watch_test_result", return_value=True)
    @patch("webgl_conformance_test.validate_result")
    @patch("webgl_conformance_test.Path")
    def test_execute_webgl_test_firefox(
        self,
        mock_path,
        mock_validate,
        mock_watch,
        mock_remove,
        mock_is_reachable,
        mock_popen,
        mock_sleep,
    ):
        """Test execute_webgl_test for firefox."""
        mock_path.home.return_value = "/home/user"
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        wct.execute_webgl_test("firefox", "", "results.json", False)
        mock_popen.assert_called_once_with(
            [
                "firefox",
                "--new-instance",
                "--private-window",
                "http://localhost:8000/local-tests.html?run=1",
            ]
        )
        unittest.TestCase().assertEqual(mock_process.terminate.call_count, 1)
        unittest.TestCase().assertEqual(mock_process.wait.call_count, 1)
        unittest.TestCase().assertEqual(mock_validate.call_count, 1)

    @patch("time.sleep", return_value=None)
    @patch("subprocess.Popen")
    @patch(
        "webgl_conformance_test.is_webgl_conformance_url_reachable",
        return_value=True,
    )
    @patch("webgl_conformance_test.remove_duplicate_file")
    @patch("webgl_conformance_test.watch_test_result", return_value=True)
    @patch("webgl_conformance_test.validate_result")
    @patch("webgl_conformance_test.Path")
    def test_execute_webgl_test_chromium_native(
        self,
        mock_path,
        mock_validate,
        mock_watch,
        mock_remove,
        mock_is_reachable,
        mock_popen,
        mock_sleep,
    ):
        """Test execute_webgl_test for chromium with native flag."""
        mock_path.home.return_value = "/home/user"
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        wct.execute_webgl_test("chromium", "", "results.json", True)
        mock_popen.assert_called_once_with(
            [
                "chromium",
                "--new-window",
                "--use-gl=desktop",
                "http://localhost:8000/local-tests.html?run=1",
            ]
        )
        unittest.TestCase().assertEqual(mock_process.terminate.call_count, 1)
        unittest.TestCase().assertEqual(mock_process.wait.call_count, 1)
        unittest.TestCase().assertEqual(mock_validate.call_count, 1)

    @patch("time.sleep", return_value=None)
    @patch("subprocess.Popen")
    @patch(
        "webgl_conformance_test.is_webgl_conformance_url_reachable",
        return_value=True,
    )
    @patch("webgl_conformance_test.remove_duplicate_file")
    @patch("webgl_conformance_test.watch_test_result", return_value=True)
    @patch("webgl_conformance_test.validate_result")
    @patch("webgl_conformance_test.Path")
    def test_execute_webgl_test_chrome_skip(
        self,
        mock_path,
        mock_validate,
        mock_watch,
        mock_remove,
        mock_is_reachable,
        mock_popen,
        mock_sleep,
    ):
        """Test execute_webgl_test for google-chrome with skip flag."""
        mock_path.home.return_value = "/home/user"
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        wct.execute_webgl_test(
            "google-chrome", "test1,test2", "results.json", False
        )

        url = "http://localhost:8000/local-tests.html?run=1&skip=test1,test2"
        mock_popen.assert_called_once_with(
            [
                "google-chrome",
                "--new-window",
                "--no-first-run",
                "--disable-fre",
                "--password-store=basic",
                url,
            ]
        )
        unittest.TestCase().assertEqual(mock_process.terminate.call_count, 1)
        unittest.TestCase().assertEqual(mock_process.wait.call_count, 1)
        unittest.TestCase().assertEqual(mock_validate.call_count, 1)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
