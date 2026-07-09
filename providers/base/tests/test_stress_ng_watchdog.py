import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stress_ng_watchdog


class WatchdogTestBase(unittest.TestCase):
    def setUp(self):
        self.session_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.session_dir.cleanup)
        self.dropin_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dropin_dir.cleanup)
        self.dropin = Path(self.dropin_dir.name) / "99-watchdog.conf"
        patches = [
            patch.dict(
                "os.environ",
                {"PLAINBOX_SESSION_SHARE": self.session_dir.name},
            ),
            patch.object(stress_ng_watchdog, "DROPIN_PATH", self.dropin),
            patch.object(stress_ng_watchdog, "reload_systemd"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def state_path(self):
        return Path(self.session_dir.name) / (
            stress_ng_watchdog.STATE_FILE_NAME
        )


class TestDisable(WatchdogTestBase):
    @patch.object(stress_ng_watchdog, "get_watchdog_usec", return_value="0")
    def test_already_disabled_changes_nothing(self, _usec):
        self.assertEqual(stress_ng_watchdog.disable(), 0)
        self.assertEqual(self.state_path().read_text(), "0")
        self.assertFalse(self.dropin.exists())

    @patch.object(stress_ng_watchdog, "get_watchdog_usec", return_value="")
    def test_unset_value_treated_as_disabled(self, _usec):
        self.assertEqual(stress_ng_watchdog.disable(), 0)
        self.assertFalse(self.dropin.exists())

    @patch.object(
        stress_ng_watchdog,
        "get_watchdog_usec",
        side_effect=["30s", "0"],
    )
    def test_enabled_watchdog_is_disabled(self, _usec):
        self.assertEqual(stress_ng_watchdog.disable(), 0)
        self.assertEqual(self.state_path().read_text(), "30s")
        self.assertEqual(
            self.dropin.read_text(), stress_ng_watchdog.DROPIN_CONTENT
        )

    @patch.object(
        stress_ng_watchdog,
        "get_watchdog_usec",
        side_effect=["30s", "30s"],
    )
    def test_failed_disable_returns_error(self, _usec):
        self.assertEqual(stress_ng_watchdog.disable(), 1)


class TestRestore(WatchdogTestBase):
    def test_missing_state_returns_error(self):
        self.assertEqual(stress_ng_watchdog.restore(), 1)

    @patch.object(stress_ng_watchdog, "get_watchdog_usec")
    def test_no_dropin_means_nothing_to_restore(self, usec_mock):
        self.state_path().write_text("0")
        self.assertEqual(stress_ng_watchdog.restore(), 0)
        usec_mock.assert_not_called()

    @patch.object(stress_ng_watchdog, "get_watchdog_usec", return_value="30s")
    def test_restore_removes_dropin_and_verifies(self, _usec):
        self.state_path().write_text("30s")
        self.dropin.write_text(stress_ng_watchdog.DROPIN_CONTENT)
        self.assertEqual(stress_ng_watchdog.restore(), 0)
        self.assertFalse(self.dropin.exists())

    @patch.object(stress_ng_watchdog, "get_watchdog_usec", return_value="1min")
    def test_restore_mismatch_returns_error(self, _usec):
        self.state_path().write_text("30s")
        self.dropin.write_text(stress_ng_watchdog.DROPIN_CONTENT)
        self.assertEqual(stress_ng_watchdog.restore(), 1)


class TestMain(WatchdogTestBase):
    @patch.object(stress_ng_watchdog, "disable", return_value=0)
    def test_main_dispatches_disable(self, disable_mock):
        with patch("sys.argv", ["stress_ng_watchdog.py", "disable"]):
            self.assertEqual(stress_ng_watchdog.main(), 0)
        # call_count instead of assert_called_once(): the latter only
        # exists from Python 3.6 and this provider is tox-tested on 3.5.
        self.assertEqual(disable_mock.call_count, 1)

    @patch.object(stress_ng_watchdog, "restore", return_value=0)
    def test_main_dispatches_restore(self, restore_mock):
        with patch("sys.argv", ["stress_ng_watchdog.py", "restore"]):
            self.assertEqual(stress_ng_watchdog.main(), 0)
        self.assertEqual(restore_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
