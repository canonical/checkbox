#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# All rights reserved.

"""Check PCM I/O across suspend without reopening the audio devices."""

import argparse
from contextlib import contextmanager, ExitStack
from ctypes import c_uint64
import errno
import itertools
import multiprocessing
import os
from pathlib import Path
import pwd
import struct
import subprocess
import sys
import time

import alsaaudio

from alsa_tests import PERIOD, RATE, sine
from suspend_stats import SuspendStats


def checked_frames(count, direction):
    if count == -errno.EPIPE:
        print(
            "{} xrun; retrying the existing PCM stream.".format(direction),
            flush=True,
        )
        return 0
    if count < 0:
        raise RuntimeError("{} PCM I/O failed: {}".format(direction, count))
    return count


def prepare_audio_session():
    if os.geteuid() != 0:
        return
    username = os.environ.get("NORMAL_USER")
    if username:
        try:
            user = pwd.getpwnam(username)
        except KeyError as error:
            raise RuntimeError(
                "Audio user {!r} does not exist".format(username)
            ) from error
    else:
        uid = os.environ.get("SUDO_UID") or os.environ.get("PKEXEC_UID")
        if not uid:
            raise RuntimeError(
                "NORMAL_USER, SUDO_UID or PKEXEC_UID is required when "
                "running as root to identify the desktop audio user"
            )
        try:
            user = pwd.getpwuid(int(uid))
        except (KeyError, ValueError, OverflowError) as error:
            raise RuntimeError(
                "Cannot resolve audio user from invoking UID {!r}".format(uid)
            ) from error
    os.initgroups(user.pw_name, user.pw_gid)
    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)
    runtime = "/run/user/{}".format(user.pw_uid)
    os.environ.update(
        {
            "HOME": user.pw_dir,
            "USER": user.pw_name,
            "LOGNAME": user.pw_name,
            "XDG_RUNTIME_DIR": runtime,
            "PIPEWIRE_RUNTIME_DIR": runtime,
            "PULSE_RUNTIME_PATH": runtime + "/pulse",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + runtime + "/bus",
        }
    )


def stream_audio(playback_device, capture_device, frames, stop):
    prepare_audio_session()
    with ExitStack() as stack:
        devices = []
        for direction, device in (
            (alsaaudio.PCM_PLAYBACK, playback_device),
            (alsaaudio.PCM_CAPTURE, capture_device),
        ):
            print(
                "Opening {} PCM {!r} as uid {} (XDG_RUNTIME_DIR={!r})".format(
                    (
                        "playback"
                        if direction == alsaaudio.PCM_PLAYBACK
                        else "capture"
                    ),
                    device,
                    os.geteuid(),
                    os.environ.get("XDG_RUNTIME_DIR"),
                ),
                flush=True,
            )
            pcm = alsaaudio.PCM(
                type=direction, mode=alsaaudio.PCM_NONBLOCK, device=device
            )
            stack.callback(pcm.close)
            pcm.setchannels(1)
            pcm.setrate(RATE)
            pcm.setformat(alsaaudio.PCM_FORMAT_FLOAT_LE)
            pcm.setperiodsize(PERIOD)
            devices.append(pcm)

        playback, capture = devices
        chunks = itertools.cycle(sine(440, RATE, PERIOD))
        pending = b""
        while not stop.is_set():
            if not pending:
                pending = struct.pack("<{}f".format(PERIOD), *next(chunks))
            try:
                written = playback.write(pending)
            except alsaaudio.ALSAAudioError:
                # Unlike read(), pyalsaaudio raises on a write underrun.
                if playback.state() != alsaaudio.PCM_STATE_XRUN:
                    raise
                written = -errno.EPIPE
            written = checked_frames(written, "Playback")
            pending = pending[written * 4 :]
            captured, _ = capture.read()
            captured = checked_frames(captured, "Capture")
            with frames.get_lock():
                frames[0] += written
                frames[1] += captured
            stop.wait(PERIOD / RATE / 2)


@contextmanager
def occupied_streams(playback_device, capture_device):
    frames = multiprocessing.Array(c_uint64, [0, 0])
    stop = multiprocessing.Event()
    process = multiprocessing.Process(
        target=stream_audio,
        args=(playback_device, capture_device, frames, stop),
    )
    process.start()
    try:
        yield process, frames
    finally:
        stop.set()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if process.is_alive():
            os.kill(process.pid, 9)
            process.join(timeout=2)
        if process.is_alive():
            raise RuntimeError("ALSA worker could not be stopped")
    if process.exitcode != 0:
        raise RuntimeError(
            "ALSA worker exited with code {}".format(process.exitcode)
        )


def monitor_streams(
    process, frames, duration, timeout=5, report_interval=None
):
    if report_interval is None:
        report_interval = duration
    start = time.monotonic()
    with frames.get_lock():
        initial = previous = frames[:]
    last_progress = [start, start]
    window_start = start
    next_report = start + report_interval
    window = 1
    while True:
        if not process.is_alive():
            raise RuntimeError(
                "ALSA worker exited with code {}".format(process.exitcode)
            )
        now = time.monotonic()
        with frames.get_lock():
            current = frames[:]
        for index, direction in enumerate(("Playback", "Capture")):
            if current[index] > previous[index]:
                last_progress[index] = now
            elif now - last_progress[index] >= timeout:
                raise RuntimeError(
                    "{} PCM made no progress for {} seconds".format(
                        direction, timeout
                    )
                )
        previous = current
        finished = now - start >= duration
        if finished or now >= next_report:
            if all(value > initial[i] for i, value in enumerate(current)):
                print(
                    "PCM progress: playback={} frames, "
                    "capture={} frames (window={}, elapsed={:.3f}s)".format(
                        current[0] - initial[0],
                        current[1] - initial[1],
                        window,
                        now - window_start,
                    ),
                    flush=True,
                )
                if finished:
                    return
                initial = current
                window_start = now
                next_report += report_interval
                window += 1
        time.sleep(0.1)


def suspend_system(seconds, rtc_device):
    before = int(SuspendStats().contents["success"])
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("suspend_trigger.py")),
            "--sleep-delay",
            str(seconds),
            "--check-delay",
            "1",
            "--rtc-device",
            rtc_device,
        ],
        check=True,
        timeout=120,
    )
    # systemctl may return before the queued suspend/resume has completed.
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if int(SuspendStats().contents["success"]) > before:
            return
        time.sleep(0.1)
    raise RuntimeError("No new successful suspend was recorded")


def positive_seconds(value):
    seconds = int(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("Duration must be greater than zero")
    return seconds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device", default=os.environ.get("ALSADEVICE", "default")
    )
    parser.add_argument("--capture-device", default="default")
    parser.add_argument("--before-suspend", type=positive_seconds, default=30)
    parser.add_argument("--suspend-time", type=positive_seconds, default=15)
    parser.add_argument("--after-resume", type=positive_seconds, default=60)
    parser.add_argument(
        "--rtc-device", default=os.environ.get("RTC_DEVICE_FILE", "/dev/rtc0")
    )
    args = parser.parse_args(argv)
    try:
        with occupied_streams(args.device, args.capture_device) as streams:
            print("Checking occupied PCM streams before suspend", flush=True)
            monitor_streams(*streams, duration=args.before_suspend)
            print("Suspending with both PCM streams open", flush=True)
            suspend_system(args.suspend_time, args.rtc_device)
            print(
                "Checking the same PCM streams after resume "
                "(reporting every {} seconds)".format(args.before_suspend),
                flush=True,
            )
            monitor_streams(
                *streams,
                duration=args.after_resume,
                report_interval=args.before_suspend,
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        print("FAIL: {}".format(error), file=sys.stderr)
        return 1
    print("PASS: PCM playback and capture continued after suspend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
