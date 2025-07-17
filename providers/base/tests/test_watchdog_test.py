import unittest
import shlex
import subprocess
import sys
from configparser import ConfigParser
from unittest.mock import patch, Mock, MagicMock, mock_open, call
from watchdog_test import (
    watchdog_argparse,
    probe_watchdog_module,
    collect_hardware_watchdogs,
    backup_systemd_config,
    restore_systemd_config,
    dump_watchdog_config,
    configure_watchdog_config,
    watchdog_test_timestamp,
    trigger_system_reset,
    watchdog_detection_test,
    watchdog_reset_test,
    post_check_test,
    main,
    WATCHDOG_CONFIG_FILE,
    WATCHDOG_LOG_FILE,
    WATCHDOG_DEV_PATTERN,
    WATCHDOG_TIMEOUT_PATTERN,
)


class TestWatchdogConfigTest(unittest.TestCase):

    def test_detection_argument(self):
        sys.argv = [
            "watchdog_test.py",
            "detect",
            "--module",
            "mod",
            "--identity",
            "watchdog",
        ]
        args = watchdog_argparse()

        self.assertEqual(args.method, "detect")
        self.assertEqual(args.module, "mod")
        self.assertEqual(args.identity, "watchdog")

    def test_system_reset_argument(self):
        sys.argv = [
            "watchdog_test.py",
            "trigger-reset",
            "--module",
            "mod",
            "--identity",
            "watchdog",
            "--log-dir",
            "tmpdir",
        ]
        args = watchdog_argparse()

        self.assertEqual(args.method, "trigger-reset")
        self.assertEqual(args.module, "mod")
        self.assertEqual(args.identity, "watchdog")
        self.assertEqual(args.log_dir, "tmpdir")

    def test_post_check_argument(self):
        sys.argv = ["watchdog_test.py", "post-check", "--log-dir", "tmpdir"]
        args = watchdog_argparse()

        self.assertEqual(args.method, "post-check")
        self.assertEqual(args.log_dir, "tmpdir")

    @patch("time.sleep")
    @patch("watchdog_test.subprocess.run")
    def test_probe_watchdog_module(self, mock_run, mock_sleep):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        with probe_watchdog_module("kernel"):
            pass
        calls = [
            call(["modprobe", "kernel"]),
            call(["modprobe", "-r", "kernel"]),
        ]
        mock_sleep.assert_called_with(2)
        mock_run.assert_has_calls(calls)

    @patch("builtins.print")
    @patch("watchdog_test.subprocess.run")
    def test_probe_watchdog_module_failed(self, mock_run, mock_print):

        mock_run.side_effect = Exception()
        with self.assertRaises(Exception):
            with probe_watchdog_module("kernel"):
                pass
        calls = [call(["modprobe", "kernel"])]

        mock_run.assert_has_calls(calls)

    @patch("watchdog_test.Path")
    @patch("glob.glob")
    def test_collect_hardware_watchdogs(self, mock_glob, mock_path):
        mock_node = Mock()
        mock_node.read_text.return_value = "identity"
        mock_path_node = Mock()
        mock_path_node.name = "watchdog0"
        mock_path_node.readlink.return_value = "link"
        mock_path_node.joinpath.return_value = mock_node
        mock_path.return_value = mock_path_node
        mock_glob.return_value = ["watchdog0"]

        watchdog_devs = collect_hardware_watchdogs("identity")
        mock_glob.assert_called_once_with("/sys/class/watchdog/watchdog*")
        mock_path.assert_called_once_with("watchdog0")
        mock_node.read_text.assert_called_once_with()

        self.assertEqual(watchdog_devs, {"watchdog0": "identity"})

    @patch("watchdog_test.Path")
    @patch("glob.glob")
    def test_collect_hardware_watchdogs_exclude_soft_watchdogs(
        self, mock_glob, mock_path
    ):
        mock_node = Mock()
        mock_node.read_text.return_value = "identity"
        mock_path_node = Mock()
        mock_path_node.name = "watchdog0"
        mock_path_node.readlink.return_value = (
            "../../devices/virtual/watchdog/watchdog0"
        )
        mock_path_node.joinpath.return_value = mock_node
        mock_path.return_value = mock_path_node
        mock_glob.return_value = ["watchdog0"]

        watchdog_devs = collect_hardware_watchdogs()
        mock_glob.assert_called_once_with("/sys/class/watchdog/watchdog*")
        mock_path.assert_called_once_with("watchdog0")
        mock_node.read_text.assert_called_once_with()

        self.assertEqual(watchdog_devs, {})

    @patch("watchdog_test.Path")
    @patch("glob.glob")
    def test_collect_hardware_watchdogs_failed(self, mock_glob, mock_path):

        mock_path_node = Mock()
        mock_path_node.name = "watchdog0"
        mock_path_node.readlink.side_effect = Exception()

        mock_path.return_value = mock_path_node
        mock_glob.return_value = ["watchdog0"]

        watchdog_devs = collect_hardware_watchdogs()
        mock_glob.assert_called_once_with("/sys/class/watchdog/watchdog*")
        mock_path.assert_called_once_with("watchdog0")

        self.assertEqual(watchdog_devs, {})

    @patch("watchdog_test.shutil.copy")
    def test_backup_systemd_config(self, mock_copy):
        backup_systemd_config("tmpdir")
        mock_copy.assert_called_with(WATCHDOG_CONFIG_FILE, "tmpdir")

    @patch("watchdog_test.Path")
    @patch("watchdog_test.shutil.copy")
    def test_restore_systemd_config(self, mock_copy, mock_path):
        mock_node = Mock()
        mock_node.joinpath.return_value = "mock_node"
        mock_path.return_value = mock_node

        restore_systemd_config("tmpdir")
        mock_copy.assert_called_with("mock_node", WATCHDOG_CONFIG_FILE)
        mock_path.assert_called_with("tmpdir")

    @patch("watchdog_test.print")
    @patch("watchdog_test.Path")
    def test_dump_watchdog_config(self, mock_path, mock_print):
        mock_node = Mock()
        mock_node.read_text.return_value = "mock_node"
        mock_path.return_value = mock_node

        dump_watchdog_config()

        calls = [
            call("# Dump systemd.conf"),
            call("mock_node"),
        ]
        mock_print.assert_has_calls(calls)

    @patch("builtins.open", new_callable=mock_open)
    @patch("configparser.ConfigParser.read")
    @patch("configparser.ConfigParser.set")
    @patch("configparser.ConfigParser.write")
    @patch("subprocess.run")
    @patch("watchdog_test.dump_watchdog_config")
    def test_configure_watchdog_config(
        self,
        mock_dump_config,
        mock_subprocess_run,
        mock_parser_write,
        mock_parser_set,
        mock_parser_read,
        mock_open_file,
    ):
        mock_parser_read.side_effect = lambda x: None

        mock_parser_instance = ConfigParser()
        mock_parser_instance.optionxform = lambda option: option
        mock_parser_instance.add_section("Manager")
        mock_parser_instance.set(
            "Manager", WATCHDOG_DEV_PATTERN, "/dev/old_watchdog"
        )
        mock_parser_instance.set("Manager", WATCHDOG_TIMEOUT_PATTERN, "10s")

        with patch(
            "watchdog_test.ConfigParser", return_value=mock_parser_instance
        ):
            configure_watchdog_config("watchdog0", "30s")

            mock_parser_set.assert_any_call(
                "Manager", WATCHDOG_DEV_PATTERN, "/dev/watchdog0"
            )
            mock_parser_set.assert_any_call(
                "Manager", WATCHDOG_TIMEOUT_PATTERN, "30s"
            )

            mock_open_file.assert_called_once_with(WATCHDOG_CONFIG_FILE, "w")
            mock_parser_write.assert_called_once_with(mock_open_file())

            mock_dump_config.assert_called_once_with()
            mock_subprocess_run.assert_called_once_with(
                shlex.split("systemctl daemon-reload"), check=True
            )

    @patch("time.time")
    @patch("watchdog_test.Path")
    def test_watchdog_test_timestamp(self, mock_path, mock_time):
        mock_node = Mock()
        mock_node.write_text.return_value = None
        mock_jpath = Mock()
        mock_jpath.joinpath.return_value = mock_node
        mock_path.return_value = mock_jpath
        mock_time.return_value = "time1"

        watchdog_test_timestamp("tmpdir")
        mock_path.assert_called_with("tmpdir")
        mock_jpath.joinpath.assert_called_with(WATCHDOG_LOG_FILE)
        mock_node.write_text.assert_called_with("time1")

    @patch("time.sleep")
    @patch("watchdog_test.Path")
    @patch("subprocess.run")
    @patch("watchdog_test.configure_watchdog_config")
    @patch("watchdog_test.backup_systemd_config")
    @patch("watchdog_test.watchdog_test_timestamp")
    @patch("builtins.print")
    def test_trigger_system_reset(
        self,
        mock_print,
        mock_wdt_timestamp,
        mock_backup_config,
        mock_wdt_config,
        mock_run,
        mock_path,
        mock_sleep,
    ):
        mock_node = Mock()
        mock_node.write_text.return_value = None
        mock_path.return_value = mock_node

        trigger_system_reset("tmpdir", "watchdog0", 30)

        self.assertEqual(mock_print.call_count, 1)
        mock_wdt_timestamp.assert_called_with("tmpdir")
        mock_backup_config.assert_called_with("tmpdir")
        mock_wdt_config.assert_called_with("watchdog0", "30")
        mock_run.assert_called_with(["sync"])
        mock_node.write_text.calls()
        mock_sleep.assert_called_with(10)

    @patch("watchdog_test.collect_hardware_watchdogs")
    @patch("watchdog_test.probe_watchdog_module", callable=mock_open)
    @patch("builtins.print")
    def test_watchdog_detection_test(
        self, mock_print, mock_probe_module, mock_collect_hardware
    ):
        mock_collect_hardware.return_value = True

        result = watchdog_detection_test("kernel_module", "watchdog0")

        self.assertEqual(mock_print.call_count, 2)
        mock_probe_module.assert_called_with("kernel_module")
        mock_collect_hardware.assert_called_with("watchdog0")
        self.assertEqual(result, None)

    @patch("watchdog_test.probe_watchdog_module")
    @patch("builtins.print")
    def test_watchdog_detection_test_probe_failed(
        self, mock_print, mock_probe_module
    ):
        mock_probe_module.side_effect = subprocess.CalledProcessError(
            returncode=100, cmd=""
        )

        with self.assertRaises(SystemExit):
            watchdog_detection_test("kernel_module", "watchdog0")

        self.assertEqual(mock_print.call_count, 2)
        mock_probe_module.assert_called_with("kernel_module")

    @patch("watchdog_test.collect_hardware_watchdogs")
    @patch("builtins.print")
    def test_watchdog_detection_test_detect_watchdog(
        self, mock_print, mock_collect_hardware
    ):
        mock_collect_hardware.return_value = True

        watchdog_detection_test("", "")

        self.assertEqual(mock_print.call_count, 2)
        mock_collect_hardware.assert_called_with("")

    @patch("watchdog_test.collect_hardware_watchdogs")
    @patch("builtins.print")
    def test_watchdog_detection_test_not_detect_watchdog(
        self, mock_print, mock_collect_hardware
    ):
        mock_collect_hardware.return_value = False
        with self.assertRaises(SystemExit):
            watchdog_detection_test("", "watchdog0")

        self.assertEqual(mock_print.call_count, 1)
        mock_collect_hardware.assert_called_with("watchdog0")

    @patch("watchdog_test.collect_hardware_watchdogs")
    @patch("watchdog_test.trigger_system_reset")
    @patch("watchdog_test.probe_watchdog_module")
    @patch("time.sleep", return_value=None)
    @patch("pathlib.Path.joinpath")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    @patch("builtins.print")
    def test_watchdog_reset_test_when_watchdog_available(
        self,
        mock_print,
        mock_subprocess_run,
        mock_write_text,
        mock_joinpath,
        mock_sleep,
        mock_probe_module,
        mock_trigger_reset,
        mock_collect_watchdogs,
    ):
        mock_path_instance = MagicMock()
        mock_joinpath.return_value = mock_path_instance
        mock_path_instance.write_text = mock_write_text
        mock_collect_watchdogs.return_value = {"/dev/watchdog0"}

        watchdog_reset_test("my_module", "my_identity", "/var/log", "30s")

        mock_collect_watchdogs.assert_called_once_with("my_identity")
        mock_trigger_reset.assert_called_once_with(
            "/var/log", "/dev/watchdog0", "30s"
        )
        mock_probe_module.assert_not_called()

        mock_sleep.assert_called_once_with(60)
        mock_joinpath.assert_called_once_with("watchdog_manual_reset.log")
        mock_write_text.assert_called_once_with("system reset by watchdog")
        mock_subprocess_run.assert_has_calls(
            [
                unittest.mock.call(["sync"]),
                unittest.mock.call(["systemctl", "reboot"]),
            ]
        )
        mock_print.assert_called_once_with("# Perform watchdog reset test")

    @patch("watchdog_test.collect_hardware_watchdogs")
    @patch("watchdog_test.trigger_system_reset")
    @patch("watchdog_test.probe_watchdog_module")
    @patch("time.sleep", return_value=None)
    @patch("pathlib.Path.joinpath")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    @patch("builtins.print")
    def test_watchdog_reset_test_when_watchdog_not_available(
        self,
        mock_print,
        mock_subprocess_run,
        mock_write_text,
        mock_joinpath,
        mock_sleep,
        mock_probe_module,
        mock_trigger_reset,
        mock_collect_watchdogs,
    ):
        mock_path_instance = MagicMock()
        mock_joinpath.return_value = mock_path_instance
        mock_path_instance.write_text = mock_write_text
        mock_collect_watchdogs.side_effect = [{}, {"/dev/watchdog0"}]

        watchdog_reset_test("my_module", "my_identity", "/var/log", "30s")

        mock_collect_watchdogs.assert_called_with("my_identity")
        self.assertEqual(mock_collect_watchdogs.call_count, 2)
        mock_trigger_reset.assert_called_once_with(
            "/var/log", "/dev/watchdog0", "30s"
        )
        mock_probe_module.assert_called_with("my_module")

        mock_sleep.assert_called_once_with(60)
        mock_joinpath.assert_called_once_with("watchdog_manual_reset.log")
        mock_write_text.assert_called_once_with("system reset by watchdog")
        mock_subprocess_run.assert_has_calls(
            [
                unittest.mock.call(["sync"]),
                unittest.mock.call(["systemctl", "reboot"]),
            ]
        )
        mock_print.assert_called_once_with("# Perform watchdog reset test")

    @patch("time.time")
    @patch("watchdog_test.Path.read_text")
    @patch("watchdog_test.Path.exists")
    @patch("watchdog_test.restore_systemd_config")
    @patch("builtins.print")
    def test_post_check_test(
        self,
        mock_print,
        mock_restore_config,
        mock_exists,
        mock_read,
        mock_time,
    ):
        mock_exists.return_value = False
        mock_read.side_effect = ["10.082", "20.082 235"]
        mock_time.return_value = 15.000
        post_check_test("tmpdir")

        mock_restore_config.assert_called_with("tmpdir")
        self.assertEqual(mock_print.call_count, 2)

    @patch("watchdog_test.Path.exists")
    @patch("watchdog_test.restore_systemd_config")
    @patch("builtins.print")
    def test_post_check_test_reset_by_scripts(
        self, mock_print, mock_restore_config, mock_exists
    ):
        mock_exists.return_value = True
        with self.assertRaises(SystemExit):
            post_check_test("tmpdir")

        mock_restore_config.assert_called_with("tmpdir")
        self.assertEqual(mock_print.call_count, 1)

    @patch("time.time")
    @patch("watchdog_test.Path.read_text")
    @patch("watchdog_test.Path.exists")
    @patch("watchdog_test.restore_systemd_config")
    @patch("builtins.print")
    def test_post_check_test_recover_after_long_period(
        self,
        mock_print,
        mock_restore_config,
        mock_exists,
        mock_read,
        mock_time,
    ):
        mock_exists.return_value = False
        mock_read.side_effect = ["10.082", "20.082 235"]
        mock_time.return_value = 500.000
        with self.assertRaises(SystemExit):
            post_check_test("tmpdir")

        mock_restore_config.assert_called_with("tmpdir")
        self.assertEqual(mock_print.call_count, 1)

    @patch("watchdog_test.watchdog_detection_test")
    @patch("watchdog_test.watchdog_argparse")
    def test_main_detection_test(self, mock_argparse, mock_test_func):
        mock_ins = Mock()
        mock_ins.method = "detect"
        mock_ins.module = "module"
        mock_ins.identity = "identity"
        mock_argparse.return_value = mock_ins

        main()
        mock_test_func.assert_called_with("module", "identity")

    @patch("watchdog_test.watchdog_reset_test")
    @patch("watchdog_test.watchdog_argparse")
    def test_main_reset_test(self, mock_argparse, mock_test_func):
        mock_ins = Mock()
        mock_ins.method = "trigger-reset"
        mock_ins.module = "module"
        mock_ins.identity = "identity"
        mock_ins.log_dir = "tmpdir"
        mock_ins.timeout = 300
        mock_argparse.return_value = mock_ins

        main()
        mock_test_func.assert_called_with("module", "identity", "tmpdir", 300)

    @patch("watchdog_test.post_check_test")
    @patch("watchdog_test.watchdog_argparse")
    def test_main_ok(self, mock_argparse, mock_test_func):
        mock_ins = Mock()
        mock_ins.method = "post-check"
        mock_ins.log_dir = "tmpdir"
        mock_argparse.return_value = mock_ins

        main()
        mock_test_func.assert_called_with("tmpdir")

    @patch("watchdog_test.watchdog_argparse")
    def test_main_failed(self, mock_argparse):
        mock_ins = Mock()
        mock_ins.method = "something else"
        mock_argparse.return_value = mock_ins

        with self.assertRaises(SystemExit):
            main()
