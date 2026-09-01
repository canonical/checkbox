"""Tests for backlight_panel.py resource and test subcommands."""

import io
import unittest
from unittest.mock import call, mock_open, patch

from backlight_panel import (
    BacklightPanelResource,
    BrightnessTest,
    cmd_resource,
    cmd_test,
    parse_args,
)

# -------------------------------------------------------------------
# BacklightPanelResource
# -------------------------------------------------------------------


class TestNormalizeAlias(unittest.TestCase):
    """Tests for BacklightPanelResource.normalize_alias."""

    def test_lowercase(self):
        """Uppercase letters are lowered."""
        self.assertEqual(
            BacklightPanelResource.normalize_alias("DSI"),
            "dsi",
        )

    def test_special_chars_replaced(self):
        """Non-alphanumeric characters become hyphens."""
        self.assertEqual(
            BacklightPanelResource.normalize_alias("a.b_c"),
            "a-b-c",
        )

    def test_collapse_repeated(self):
        """Consecutive special chars collapse to one hyphen."""
        self.assertEqual(
            BacklightPanelResource.normalize_alias("a---b"),
            "a-b",
        )

    def test_strip_leading_trailing(self):
        """Leading/trailing hyphens are stripped."""
        self.assertEqual(
            BacklightPanelResource.normalize_alias("-foo-"),
            "foo",
        )

    def test_empty_string(self):
        """Empty input returns empty string."""
        self.assertEqual(BacklightPanelResource.normalize_alias(""), "")

    def test_already_clean(self):
        """Clean input passes through unchanged."""
        self.assertEqual(
            BacklightPanelResource.normalize_alias("backlight-lcd0"),
            "backlight-lcd0",
        )


class TestDeduplicateAlias(unittest.TestCase):
    """Tests for BacklightPanelResource.deduplicate_alias."""

    def _dedup(self, alias, seen):
        """Shortcut to call the static method directly."""
        return BacklightPanelResource.deduplicate_alias(alias, seen)

    def test_first_occurrence(self):
        """First alias is returned unchanged."""
        seen = {}
        self.assertEqual(self._dedup("dsi", seen), "dsi")
        self.assertEqual(seen, {"dsi": 1})

    def test_second_occurrence(self):
        """Second alias gets -2 suffix."""
        seen = {"dsi": 1}
        self.assertEqual(self._dedup("dsi", seen), "dsi-2")

    def test_third_occurrence(self):
        """Third alias gets -3 suffix."""
        seen = {"dsi": 2}
        self.assertEqual(self._dedup("dsi", seen), "dsi-3")


class TestParseMapping(unittest.TestCase):
    """Tests for BacklightPanelResource._parse_mapping."""

    @staticmethod
    def _parse(raw):
        """Shortcut: instantiate with a non-existent sysfs path."""
        with patch(
            "backlight_panel.os.path.isdir",
            return_value=False,
        ):
            r = BacklightPanelResource(panel_mapping=raw, sysfs_path="/absent")
        return r.mapping_pairs

    def test_valid_single(self):
        """Single valid pair is returned."""
        self.assertEqual(
            self._parse("dsi:backlight-lcd0"),
            [("dsi", "backlight-lcd0")],
        )

    def test_valid_multiple(self):
        """Multiple comma-separated pairs are returned."""
        result = self._parse("dsi:backlight-lcd0,edp:backlight-lcd1")
        self.assertEqual(
            result,
            [
                ("dsi", "backlight-lcd0"),
                ("edp", "backlight-lcd1"),
            ],
        )

    def test_empty_string(self):
        """Empty string returns empty list."""
        self.assertEqual(self._parse(""), [])

    def test_whitespace_only(self):
        """Whitespace-only string returns empty list."""
        self.assertEqual(self._parse("   "), [])

    def test_malformed_no_colon(self):
        """Token without colon is warned and skipped."""
        with patch("sys.stderr", new_callable=io.StringIO) as err:
            result = self._parse("dsi")
            self.assertEqual(result, [])
            self.assertIn("malformed", err.getvalue())

    def test_malformed_empty_alias(self):
        """Token with empty alias is warned and skipped."""
        with patch("sys.stderr", new_callable=io.StringIO) as err:
            result = self._parse(":backlight-lcd0")
            self.assertEqual(result, [])
            self.assertIn("malformed", err.getvalue())

    def test_malformed_empty_device(self):
        """Token with empty device is warned and skipped."""
        with patch("sys.stderr", new_callable=io.StringIO) as err:
            result = self._parse("dsi:")
            self.assertEqual(result, [])
            self.assertIn("malformed", err.getvalue())

    def test_whitespace_around_tokens(self):
        """Whitespace around tokens and parts is stripped."""
        result = self._parse(" dsi : lcd0 , edp : lcd1 ")
        self.assertEqual(result, [("dsi", "lcd0"), ("edp", "lcd1")])

    def test_trailing_comma(self):
        """Trailing comma does not produce an extra entry."""
        result = self._parse("dsi:lcd0,")
        self.assertEqual(result, [("dsi", "lcd0")])


class TestEnumerateDevices(unittest.TestCase):
    """Tests for BacklightPanelResource device enumeration."""

    @patch("backlight_panel.os.path.isdir")
    @patch("backlight_panel.os.listdir")
    def test_normal(self, mock_listdir, mock_isdir):
        """Directories are returned sorted."""
        mock_isdir.return_value = True
        mock_listdir.return_value = ["lcd1", "lcd0"]
        r = BacklightPanelResource(sysfs_path="/fake")
        self.assertEqual(r.devices, ["lcd0", "lcd1"])

    @patch(
        "backlight_panel.os.path.isdir",
        return_value=False,
    )
    def test_missing_path(self, _mock):
        """Missing sysfs directory returns empty list."""
        r = BacklightPanelResource(sysfs_path="/missing")
        self.assertEqual(r.devices, [])

    @patch("backlight_panel.os.path.isdir")
    @patch("backlight_panel.os.listdir", return_value=[])
    def test_empty_dir(self, _mock_ls, mock_isdir):
        """Empty sysfs directory returns empty list."""
        mock_isdir.return_value = True
        r = BacklightPanelResource(sysfs_path="/fake")
        self.assertEqual(r.devices, [])


class TestBuildRecords(unittest.TestCase):
    """Tests for BacklightPanelResource.build_records."""

    def _make_resource(self, devices, mapping=""):
        """Create a resource with patched device list."""
        with patch(
            "backlight_panel.os.path.isdir",
            return_value=False,
        ):
            r = BacklightPanelResource(
                panel_mapping=mapping,
                sysfs_path="/absent",
            )
        r.devices = devices
        return r

    def test_with_mapping(self):
        """Mapped devices get their alias; others fall back."""
        r = self._make_resource(
            ["backlight-lcd0", "backlight-lcd1"],
            "dsi:backlight-lcd0",
        )
        self.assertEqual(
            r.build_records(),
            [
                ("backlight-lcd0", "dsi"),
                ("backlight-lcd1", "backlight-lcd1"),
            ],
        )

    def test_without_mapping(self):
        """No mapping means all devices use their basename."""
        r = self._make_resource(["backlight-lcd0", "backlight-lcd1"])
        self.assertEqual(
            r.build_records(),
            [
                ("backlight-lcd0", "backlight-lcd0"),
                ("backlight-lcd1", "backlight-lcd1"),
            ],
        )

    def test_unknown_mapped_device(self):
        """Mapped device not in list is warned and skipped."""
        r = self._make_resource(["backlight-lcd0"], "edp:nonexistent")
        with patch("sys.stderr", new_callable=io.StringIO) as err:
            result = r.build_records()
            self.assertIn("not found", err.getvalue())
        self.assertEqual(result, [("backlight-lcd0", "backlight-lcd0")])

    def test_duplicate_alias_suffixed(self):
        """Duplicate aliases get numeric suffix."""
        r = self._make_resource(["a", "b"], "dsi:a,DSI:b")
        self.assertEqual(
            r.build_records(),
            [("a", "dsi"), ("b", "dsi-2")],
        )


class TestPrintRecords(unittest.TestCase):
    """Tests for BacklightPanelResource.print_records."""

    @patch(
        "backlight_panel.os.path.isdir",
        return_value=False,
    )
    def test_no_devices(self, _mock):
        """No devices produces no output and returns 0."""
        r = BacklightPanelResource(sysfs_path="/absent")
        with patch("builtins.print") as mock_print:
            rc = r.print_records()
        self.assertEqual(rc, 0)
        mock_print.assert_not_called()

    def test_with_devices_and_mapping(self):
        """Devices with mapping produce correct records."""
        with patch(
            "backlight_panel.os.path.isdir",
            return_value=False,
        ):
            r = BacklightPanelResource(
                panel_mapping=("dsi:backlight-lcd0," "edp:backlight-lcd1"),
                sysfs_path="/absent",
            )
        r.devices = ["backlight-lcd0", "backlight-lcd1"]
        with patch("builtins.print") as mock_print:
            rc = r.print_records()
        self.assertEqual(rc, 0)
        mock_print.assert_has_calls(
            [
                call("device: backlight-lcd0"),
                call("panel_alias: dsi"),
                call(),
                call("device: backlight-lcd1"),
                call("panel_alias: edp"),
                call(),
            ]
        )

    def test_without_mapping_fallback(self):
        """No mapping means panel_alias equals basename."""
        with patch(
            "backlight_panel.os.path.isdir",
            return_value=False,
        ):
            r = BacklightPanelResource(sysfs_path="/absent")
        r.devices = ["backlight-lcd0"]
        with patch("builtins.print") as mock_print:
            rc = r.print_records()
        self.assertEqual(rc, 0)
        mock_print.assert_has_calls(
            [
                call("device: backlight-lcd0"),
                call("panel_alias: backlight-lcd0"),
                call(),
            ]
        )


# -------------------------------------------------------------------
# BrightnessTest
# -------------------------------------------------------------------


class TestReadWriteValue(unittest.TestCase):
    """Tests for BrightnessTest.read_value / write_value."""

    def test_read_value(self):
        """read_value returns stripped integer."""
        m = mock_open(read_data="  42 \n")
        with patch("builtins.open", m):
            result = BrightnessTest.read_value("/fake/brightness")
        self.assertEqual(result, 42)

    def test_write_value(self):
        """write_value writes stringified integer."""
        m = mock_open()
        with patch("builtins.open", m):
            BrightnessTest.write_value(100, "/fake/brightness")
        m().write.assert_called_once_with("100")


class TestWasBrightnessApplied(unittest.TestCase):
    """Tests for BrightnessTest.was_brightness_applied."""

    def _make_bt(self):
        """Create a BrightnessTest without real sysfs."""
        return BrightnessTest("fake-dev", sysfs_path="/fake", settle=0)

    @patch.object(BrightnessTest, "read_value")
    def test_exact_match(self, mock_read):
        """Returns True when actual == last_set."""
        mock_read.side_effect = [50, 50]
        bt = self._make_bt()
        self.assertTrue(bt.was_brightness_applied())

    @patch.object(BrightnessTest, "read_value")
    def test_within_tolerance(self, mock_read):
        """Returns True when difference is exactly 1."""
        mock_read.side_effect = [51, 50]
        bt = self._make_bt()
        self.assertTrue(bt.was_brightness_applied())

    @patch.object(BrightnessTest, "read_value")
    def test_outside_tolerance(self, mock_read):
        """Returns False when difference exceeds 1."""
        mock_read.side_effect = [53, 50]
        bt = self._make_bt()
        self.assertFalse(bt.was_brightness_applied())


class TestBrightnessRun(unittest.TestCase):
    """Tests for BrightnessTest.run."""

    def _make_bt(self):
        """Create a BrightnessTest without real sysfs."""
        return BrightnessTest("fake-dev", sysfs_path="/fake", settle=0)

    @patch.object(BrightnessTest, "was_brightness_applied")
    @patch.object(BrightnessTest, "write_value")
    @patch.object(BrightnessTest, "read_value")
    @patch("backlight_panel.time.sleep")
    def test_success(self, _sleep, mock_read, mock_write, mock_app):
        """All levels pass returns 0 failures."""
        mock_read.side_effect = [80, 200]
        mock_app.return_value = True
        bt = self._make_bt()
        with patch("builtins.print"):
            failures = bt.run()
        self.assertEqual(failures, 0)
        last_wr = mock_write.call_args_list[-1]
        self.assertEqual(
            last_wr,
            call(80, "/fake/fake-dev/brightness"),
        )

    @patch.object(BrightnessTest, "was_brightness_applied")
    @patch.object(BrightnessTest, "write_value")
    @patch.object(BrightnessTest, "read_value")
    @patch("backlight_panel.time.sleep")
    def test_all_fail(self, _sleep, mock_read, _write, mock_app):
        """All levels fail returns 5 failures."""
        mock_read.side_effect = [80, 200]
        mock_app.return_value = False
        bt = self._make_bt()
        with patch("builtins.print"):
            failures = bt.run()
        self.assertEqual(failures, 5)

    @patch.object(BrightnessTest, "was_brightness_applied")
    @patch.object(BrightnessTest, "write_value")
    @patch.object(BrightnessTest, "read_value")
    @patch("backlight_panel.time.sleep")
    def test_restore_on_error(self, _sleep, mock_read, mock_write, mock_app):
        """Original brightness is restored on exception."""
        mock_read.side_effect = [80, 200]
        mock_app.side_effect = RuntimeError("boom")
        bt = self._make_bt()
        with patch("builtins.print"):
            with self.assertRaises(RuntimeError):
                bt.run()
        last_wr = mock_write.call_args_list[-1]
        self.assertEqual(
            last_wr,
            call(80, "/fake/fake-dev/brightness"),
        )


# -------------------------------------------------------------------
# Subcommand handlers + argument parsing
# -------------------------------------------------------------------


class TestCmdResource(unittest.TestCase):
    """Tests for the cmd_resource handler."""

    @patch(
        "backlight_panel.BacklightPanelResource." "print_records",
        return_value=0,
    )
    @patch(
        "backlight_panel.BacklightPanelResource." "_enumerate_devices",
        return_value=[],
    )
    def test_returns_zero(self, _enum, mock_print):
        """cmd_resource delegates to print_records."""
        args = parse_args(["resource", "--panel-mapping", ""])
        rc = cmd_resource(args)
        self.assertEqual(rc, 0)


class TestCmdTest(unittest.TestCase):
    """Tests for the cmd_test handler."""

    @patch("backlight_panel.os.geteuid", return_value=1000)
    def test_non_root(self, _mock):
        """Non-root user gets error return."""
        args = parse_args(["test", "-d", "backlight-lcd0"])
        with patch("sys.stderr", new_callable=io.StringIO):
            rc = cmd_test(args)
        self.assertEqual(rc, 1)

    @patch(
        "backlight_panel.os.path.isdir",
        return_value=False,
    )
    @patch("backlight_panel.os.geteuid", return_value=0)
    def test_missing_device(self, _root, _isdir):
        """Missing device directory gets error return."""
        args = parse_args(["test", "-d", "nonexistent"])
        with patch("sys.stderr", new_callable=io.StringIO):
            rc = cmd_test(args)
        self.assertEqual(rc, 1)

    @patch.object(BrightnessTest, "run", return_value=0)
    @patch(
        "backlight_panel.os.path.isdir",
        return_value=True,
    )
    @patch("backlight_panel.os.geteuid", return_value=0)
    def test_success(self, _root, _isdir, mock_run):
        """Successful test returns 0."""
        args = parse_args(["test", "-d", "backlight-lcd0"])
        with patch("builtins.print"):
            rc = cmd_test(args)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once()


class TestParseArgs(unittest.TestCase):
    """Tests for argument parsing."""

    def test_resource_defaults(self):
        """Resource subcommand defaults panel-mapping to empty."""
        args = parse_args(["resource"])
        self.assertEqual(args.command, "resource")
        self.assertEqual(args.panel_mapping, "")

    def test_resource_with_mapping(self):
        """Resource subcommand accepts --panel-mapping."""
        args = parse_args(["resource", "--panel-mapping", "dsi:lcd0"])
        self.assertEqual(args.panel_mapping, "dsi:lcd0")

    def test_test_device_required(self):
        """Test subcommand requires -d/--device."""
        with self.assertRaises(SystemExit):
            parse_args(["test"])

    def test_test_settle_default(self):
        """Test subcommand defaults settle to SETTLE_SECONDS."""
        args = parse_args(["test", "-d", "lcd0"])
        self.assertEqual(args.settle, 2)

    def test_test_settle_custom(self):
        """Test subcommand accepts custom --settle."""
        args = parse_args(["test", "-d", "lcd0", "--settle", "5"])
        self.assertEqual(args.settle, 5)


if __name__ == "__main__":
    unittest.main()
