#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# All rights reserved.

import errno
import multiprocessing
import re
import subprocess
import sys
import unittest
from ctypes import c_uint64
from types import SimpleNamespace
from unittest.mock import Mock, call, patch


class FakeALSAAudioError(Exception):
    pass


with patch.dict(
    sys.modules, {"alsaaudio": Mock(ALSAAudioError=FakeALSAAudioError)}
):
    import audio_occupied


class TestAudioWorker(unittest.TestCase):
    def setUp(self):
        uid_patch = patch.object(
            audio_occupied.os, "geteuid", return_value=1000
        )
        self.euid = uid_patch.start()
        self.addCleanup(uid_patch.stop)
        self.frames = multiprocessing.Array(c_uint64, [0, 0])
        self.stop = Mock()
        self.stop.is_set.side_effect = [False, False, True]
        self.playback = Mock()
        self.capture = Mock()
        self.playback.write.return_value = audio_occupied.PERIOD
        self.capture.read.return_value = (3, b"\0" * 12)
        patcher = patch.object(
            audio_occupied.alsaaudio,
            "PCM",
            side_effect=[self.playback, self.capture],
        )
        self.pcm = patcher.start()
        self.addCleanup(patcher.stop)

    def run_worker(self):
        audio_occupied.stream_audio("output", "input", self.frames, self.stop)

    @patch.object(audio_occupied.os, "setuid")
    @patch.object(audio_occupied.os, "setgid")
    @patch.object(audio_occupied.os, "initgroups")
    @patch.object(audio_occupied.pwd, "getpwnam")
    def test_root_worker_enters_normal_session_before_opening_pcm(
        self, getpwnam, initgroups, setgid, setuid
    ):
        self.euid.return_value = 0
        getpwnam.return_value = SimpleNamespace(
            pw_name="tester", pw_uid=1000, pw_gid=1001, pw_dir="/home/tester"
        )
        credentials = Mock()
        credentials.attach_mock(initgroups, "initgroups")
        credentials.attach_mock(setgid, "setgid")
        credentials.attach_mock(setuid, "setuid")
        devices = iter((self.playback, self.capture))

        def drop_uid(uid):
            self.euid.return_value = uid

        def open_pcm(**kwargs):
            self.assertEqual(self.euid(), 1000)
            self.assertEqual(
                credentials.mock_calls,
                [
                    call.initgroups("tester", 1001),
                    call.setgid(1001),
                    call.setuid(1000),
                ],
            )
            for name, value in {
                "HOME": "/home/tester",
                "USER": "tester",
                "LOGNAME": "tester",
                "XDG_RUNTIME_DIR": "/run/user/1000",
                "PIPEWIRE_RUNTIME_DIR": "/run/user/1000",
                "PULSE_RUNTIME_PATH": "/run/user/1000/pulse",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            }.items():
                self.assertEqual(audio_occupied.os.environ[name], value)
            return next(devices)

        setuid.side_effect = drop_uid
        self.pcm.side_effect = open_pcm
        with patch.dict(
            audio_occupied.os.environ,
            {
                "NORMAL_USER": "tester",
                "SUDO_UID": "0",
                "HOME": "/root",
                "XDG_RUNTIME_DIR": "/run/user/0",
                "PIPEWIRE_RUNTIME_DIR": "/run/user/0",
                "PULSE_RUNTIME_PATH": "/run/user/0/pulse",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/0/bus",
            },
            clear=True,
        ):
            self.run_worker()

    @patch.object(audio_occupied.os, "setuid")
    @patch.object(audio_occupied.os, "setgid")
    @patch.object(audio_occupied.os, "initgroups")
    @patch.object(audio_occupied.pwd, "getpwuid")
    def test_root_worker_uses_the_sudo_or_polkit_invoking_uid(
        self, getpwuid, initgroups, setgid, setuid
    ):
        getpwuid.return_value = SimpleNamespace(
            pw_name="tester", pw_uid=1000, pw_gid=1001, pw_dir="/home/tester"
        )
        for environment in (
            {"SUDO_UID": "1000"},
            {"PKEXEC_UID": "1000"},
            {"SUDO_UID": "1000", "PKEXEC_UID": "2000"},
        ):
            with self.subTest(environment=environment):
                self.euid.return_value = 0
                self.stop.is_set.side_effect = [False, False, True]
                self.pcm.side_effect = [self.playback, self.capture]
                with patch.dict(
                    audio_occupied.os.environ, environment, clear=True
                ):
                    self.run_worker()
                    self.assertEqual(
                        audio_occupied.os.environ["HOME"], "/home/tester"
                    )
                    self.assertEqual(
                        audio_occupied.os.environ["XDG_RUNTIME_DIR"],
                        "/run/user/1000",
                    )
                getpwuid.assert_called_with(1000)
                initgroups.assert_called_with("tester", 1001)
                setgid.assert_called_with(1001)
                setuid.assert_called_with(1000)

    @patch.object(
        audio_occupied.pwd, "getpwuid", side_effect=KeyError("missing")
    )
    def test_invalid_invoking_uid_fails_before_opening_pcm(self, getpwuid):
        self.euid.return_value = 0
        for uid in ("not-a-number", "999999"):
            with self.subTest(uid=uid), patch.dict(
                audio_occupied.os.environ, {"SUDO_UID": uid}, clear=True
            ):
                with self.assertRaisesRegex(RuntimeError, "invoking UID"):
                    self.run_worker()
        self.pcm.assert_not_called()

    def test_root_without_invoking_user_fails_before_opening_pcm(self):
        self.euid.return_value = 0
        with patch.dict(audio_occupied.os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "NORMAL_USER"):
                self.run_worker()
        self.pcm.assert_not_called()

    @patch.object(
        audio_occupied.pwd, "getpwnam", side_effect=KeyError("missing")
    )
    def test_unknown_normal_user_fails_before_opening_pcm(self, getpwnam):
        self.euid.return_value = 0
        with patch.dict(
            audio_occupied.os.environ, {"NORMAL_USER": "missing"}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "Audio user.*missing"):
                self.run_worker()
        self.pcm.assert_not_called()

    @patch.object(audio_occupied.os, "setuid")
    def test_unprivileged_worker_keeps_its_existing_session(self, setuid):
        with patch.dict(
            audio_occupied.os.environ,
            {"XDG_RUNTIME_DIR": "/custom/runtime", "NORMAL_USER": "another"},
            clear=True,
        ):
            self.run_worker()
            self.assertEqual(
                audio_occupied.os.environ["XDG_RUNTIME_DIR"], "/custom/runtime"
            )
        setuid.assert_not_called()

    def test_partial_writes_keep_same_stream_and_unwritten_samples(self):
        self.playback.write.side_effect = [2, audio_occupied.PERIOD - 2]

        self.run_worker()

        self.assertEqual(self.pcm.call_count, 2)
        self.assertEqual(list(self.frames), [audio_occupied.PERIOD, 6])
        first, second = [
            args[0][0] for args in self.playback.write.call_args_list
        ]
        self.assertEqual(second, first[8:])
        for pcm in (self.playback, self.capture):
            pcm.setrate.assert_called_once_with(audio_occupied.RATE)
            pcm.close.assert_called_once_with()

    def test_write_failure_closes_both_devices(self):
        self.playback.write.return_value = -errno.EIO

        with self.assertRaisesRegex(RuntimeError, "Playback"):
            self.run_worker()

        self.playback.close.assert_called_once_with()
        self.capture.close.assert_called_once_with()

    def test_capture_failure_is_not_counted_as_progress(self):
        self.capture.read.return_value = (-errno.EIO, b"")

        with self.assertRaisesRegex(RuntimeError, "Capture"):
            self.run_worker()

        self.assertEqual(self.frames[1], 0)

    @patch("builtins.print")
    def test_write_xrun_exception_retries_without_reopening_pcm(self, output):
        self.playback.write.side_effect = [
            FakeALSAAudioError("Broken pipe"),
            audio_occupied.PERIOD,
        ]
        self.playback.state.return_value = (
            audio_occupied.alsaaudio.PCM_STATE_XRUN
        )

        self.run_worker()

        self.assertEqual(self.pcm.call_count, 2)
        self.assertEqual(list(self.frames), [audio_occupied.PERIOD, 6])
        first, second = [
            args[0][0] for args in self.playback.write.call_args_list
        ]
        self.assertEqual(first, second)
        output.assert_any_call(
            "Playback xrun; retrying the existing PCM stream.", flush=True
        )

    def test_non_xrun_write_exception_is_not_hidden(self):
        self.playback.write.side_effect = FakeALSAAudioError("Host is down")
        self.playback.state.return_value = (
            audio_occupied.alsaaudio.PCM_STATE_DISCONNECTED
        )

        with self.assertRaisesRegex(FakeALSAAudioError, "Host is down"):
            self.run_worker()

        self.assertEqual(self.frames[0], 0)
        self.playback.close.assert_called_once_with()
        self.capture.close.assert_called_once_with()

    @patch("builtins.print")
    def test_xruns_are_reported_and_require_subsequent_progress(self, output):
        self.playback.write.side_effect = [-errno.EPIPE, audio_occupied.PERIOD]
        self.capture.read.side_effect = [
            (-errno.EPIPE, b""),
            (3, b"\0" * 12),
        ]

        self.run_worker()

        self.assertEqual(list(self.frames), [audio_occupied.PERIOD, 3])
        for direction in ("Playback", "Capture"):
            output.assert_any_call(
                "{} xrun; retrying the existing PCM stream.".format(direction),
                flush=True,
            )


class TestMonitoring(unittest.TestCase):
    def setUp(self):
        self.frames = multiprocessing.Array(c_uint64, [100, 200])
        self.process = Mock()
        self.process.is_alive.return_value = True
        self.clock = 0
        self.advancing = (True, True)
        clock_patch = patch.object(
            audio_occupied.time, "monotonic", side_effect=lambda: self.clock
        )
        sleep_patch = patch.object(
            audio_occupied.time, "sleep", side_effect=self.advance
        )
        clock_patch.start()
        sleep_patch.start()
        self.addCleanup(clock_patch.stop)
        self.addCleanup(sleep_patch.stop)

    def advance(self, seconds):
        self.clock = round(self.clock + seconds, 6)
        for index, advancing in enumerate(self.advancing):
            if advancing:
                self.frames[index] += 441

    def test_both_streams_must_advance_during_the_current_phase(self):
        audio_occupied.monitor_streams(
            self.process, self.frames, duration=1, timeout=0.3
        )
        self.assertGreater(self.frames[0], 100)
        self.assertGreater(self.frames[1], 200)

    @patch("builtins.print")
    @patch.object(audio_occupied, "suspend_system")
    @patch.object(audio_occupied, "occupied_streams")
    def test_main_reports_equal_windows_without_shortening_resume(
        self, streams, suspend, output
    ):
        streams.return_value.__enter__.return_value = (
            self.process,
            self.frames,
        )

        result = audio_occupied.main(
            [
                "--device",
                "output",
                "--capture-device",
                "input",
                "--before-suspend",
                "1",
                "--suspend-time",
                "1",
                "--after-resume",
                "2",
            ]
        )

        self.assertEqual(result, 0)
        reports = [
            args[0][0]
            for args in output.call_args_list
            if args[0][0].startswith("PCM progress:")
        ]
        self.assertEqual(len(reports), 3)
        counts = [
            tuple(
                map(
                    int,
                    re.search(
                        r"playback=(\d+) frames, capture=(\d+) frames", report
                    ).groups(),
                )
            )
            for report in reports
        ]
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(counts[0], counts[2])
        self.assertEqual(
            sum(playback for playback, _ in counts), self.frames[0] - 100
        )
        self.assertEqual(
            sum(capture for _, capture in counts), self.frames[1] - 200
        )
        self.assertAlmostEqual(self.clock, 3)
        streams.assert_called_once_with("output", "input")

    @patch("builtins.print")
    def test_last_partial_window_reports_its_actual_duration(self, output):
        audio_occupied.monitor_streams(
            self.process, self.frames, duration=1.5, report_interval=1
        )

        reports = [args[0][0] for args in output.call_args_list]
        self.assertEqual(len(reports), 2)
        self.assertIn("window=1, elapsed=1.000s", reports[0])
        self.assertIn("window=2, elapsed=0.500s", reports[1])

    @patch("builtins.print")
    def test_reporting_boundary_does_not_reset_stall_timeout(self, output):
        def advance_until_stalled(seconds):
            self.advance(seconds)
            if self.clock >= 0.9:
                self.advancing = (False, True)

        with patch.object(
            audio_occupied.time, "sleep", side_effect=advance_until_stalled
        ):
            with self.assertRaisesRegex(RuntimeError, "Playback.*progress"):
                audio_occupied.monitor_streams(
                    self.process,
                    self.frames,
                    duration=2,
                    timeout=0.25,
                    report_interval=1,
                )

        self.assertAlmostEqual(self.clock, 1.2)

    def test_stalled_capture_fails_even_when_playback_advances(self):
        self.advancing = (True, False)

        with self.assertRaisesRegex(RuntimeError, "Capture.*progress"):
            audio_occupied.monitor_streams(
                self.process, self.frames, duration=1, timeout=0.3
            )

    def test_pre_suspend_progress_cannot_pass_post_resume_monitoring(self):
        self.advancing = (False, False)

        with self.assertRaisesRegex(RuntimeError, "Playback.*progress"):
            audio_occupied.monitor_streams(
                self.process, self.frames, duration=1, timeout=0.3
            )

    def test_worker_exit_is_a_failure(self):
        self.process.is_alive.return_value = False
        self.process.exitcode = 1

        with self.assertRaisesRegex(RuntimeError, "worker.*1"):
            audio_occupied.monitor_streams(
                self.process, self.frames, duration=1
            )


class TestSuspendCycle(unittest.TestCase):
    @patch.object(audio_occupied.subprocess, "run")
    @patch.object(audio_occupied, "SuspendStats")
    def test_requires_a_new_successful_suspend(self, stats, run):
        stats.side_effect = [
            SimpleNamespace(contents={"success": "4"}),
            SimpleNamespace(contents={"success": "5"}),
        ]

        audio_occupied.suspend_system(15, "/dev/rtc1")

        command = run.call_args[0][0]
        self.assertTrue(command[1].endswith("/suspend_trigger.py"))
        self.assertEqual(
            command[2:],
            [
                "--sleep-delay",
                "15",
                "--check-delay",
                "1",
                "--rtc-device",
                "/dev/rtc1",
            ],
        )
        self.assertTrue(run.call_args[1]["check"])
        self.assertGreater(run.call_args[1]["timeout"], 0)

    @patch.object(audio_occupied.time, "sleep")
    @patch.object(audio_occupied.time, "monotonic", side_effect=[0, 0, 121])
    @patch.object(audio_occupied.subprocess, "run")
    @patch.object(audio_occupied, "SuspendStats")
    def test_successful_command_without_suspend_fails(
        self, stats, run, clock, sleep
    ):
        stats.return_value.contents = {"success": "4"}

        with self.assertRaisesRegex(RuntimeError, "successful suspend"):
            audio_occupied.suspend_system(15, "/dev/rtc0")

    @patch.object(
        audio_occupied.subprocess,
        "run",
        side_effect=subprocess.CalledProcessError(1, "suspend_trigger.py"),
    )
    @patch.object(audio_occupied, "SuspendStats")
    def test_suspend_command_failure_is_propagated(self, stats, run):
        stats.return_value.contents = {"success": "4"}

        with self.assertRaises(subprocess.CalledProcessError):
            audio_occupied.suspend_system(15, "/dev/rtc0")


class TestWorkerCleanup(unittest.TestCase):
    @patch.object(audio_occupied.multiprocessing, "Process")
    @patch.object(audio_occupied.multiprocessing, "Event")
    def test_failure_terminates_a_blocked_worker(
        self, event_type, process_type
    ):
        process = process_type.return_value
        process.is_alive.side_effect = [True, False, False]

        with self.assertRaisesRegex(RuntimeError, "suspend failed"):
            with audio_occupied.occupied_streams("output", "input"):
                raise RuntimeError("suspend failed")

        event_type.return_value.set.assert_called_once_with()
        process.terminate.assert_called_once_with()
        self.assertEqual(process.join.call_count, 2)

    @patch.object(audio_occupied.multiprocessing, "Process")
    def test_worker_failure_during_shutdown_cannot_pass(self, process_type):
        process = process_type.return_value
        process.is_alive.return_value = False
        process.exitcode = 1

        with self.assertRaisesRegex(RuntimeError, "worker.*1"):
            with audio_occupied.occupied_streams("output", "input"):
                pass


class TestArguments(unittest.TestCase):
    def test_zero_duration_cannot_skip_a_test_phase(self):
        with patch("sys.stderr"), self.assertRaises(SystemExit) as error:
            audio_occupied.main(["--after-resume", "0"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
