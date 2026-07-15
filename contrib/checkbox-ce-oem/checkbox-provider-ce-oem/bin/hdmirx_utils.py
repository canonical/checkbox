#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.
"""Shared core for the pure-Python HDMI RX (input) test.

This module carries everything that is platform independent:

* the data models (`DeviceInfo`, `VideoInfo`, `AudioInfo`) and the
  `Event` enum used by the checkbox jobs;
* the `HdmiRxBackend` contract every platform backend implements;
* the Linux `_IOC` ioctl-number helpers;
* `IoctlCharBackend`, a reusable base for any driver that is a custom
  ioctl character device (a new vendor is data + mappers only);
* `uevent_wait`, a stdlib netlink KOBJECT_UEVENT listener; and
* the `verify_*` helpers that turn readings into pass/fail reasons.

Syntax is kept Python 3.5-safe because the provider tox gate still
runs py35/py36 (namedtuples instead of dataclasses, ``.format()``
instead of f-strings, no variable annotations).
"""

import collections
import ctypes
import fcntl
import os
import select
import socket
import time
from abc import ABC, abstractmethod
from enum import Enum


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class Colorspace(Enum):
    RGB = "RGB"
    YUV444 = "YUV444"
    YUV422 = "YUV422"
    YUV420 = "YUV420"


class Event(Enum):
    """HDMI RX notifications.

    The *value* is the ``HDMI_RX_*`` string the checkbox job text
    asserts on. The numeric driver code is NOT implied by member
    order -- each backend declares its own mapping in ``EVENT_MAP``.
    """

    PWR_5V_CHANGE = "HDMI_RX_PWR_5V_CHANGE"
    TIMING_LOCK = "HDMI_RX_TIMING_LOCK"
    TIMING_UNLOCK = "HDMI_RX_TIMING_UNLOCK"
    AUD_LOCK = "HDMI_RX_AUD_LOCK"
    AUD_UNLOCK = "HDMI_RX_AUD_UNLOCK"
    PLUG_IN = "HDMI_RX_PLUG_IN"
    PLUG_OUT = "HDMI_RX_PLUG_OUT"


DeviceInfo = collections.namedtuple(
    "DeviceInfo",
    [
        "connected",
        "power_5v",
        "hpd",
        "video_locked",
        "audio_locked",
        "hdcp_version",
    ],
)

VideoInfo = collections.namedtuple(
    "VideoInfo",
    [
        "hactive",
        "vactive",
        "frame_rate",
        "colorspace",
        "bit_depth",
        "interlaced",
    ],
)
VideoInfo.__new__.__defaults__ = (None, None, None)  # last 3 optional

AudioInfo = collections.namedtuple(
    "AudioInfo", ["bit_depth", "channels", "sample_freq_khz"]
)

# One custom-ioctl command. direction is 'wr' | 'w' | 'r'; ctype is a
# ctypes.Structure subclass (or a ctypes scalar such as c_uint).
IoctlCmd = collections.namedtuple("IoctlCmd", ["nr", "direction", "ctype"])


class HdmiRxBackend(ABC):
    """Contract every platform backend implements.

    Concrete backends are registered in ``hdmirx_tool`` and selected
    by auto-detection (or ``--backend``).
    """

    name = ""  # short id shown by --backend and used by the registry

    @abstractmethod
    def is_available(self):
        """True when this platform's RX device is present."""

    @abstractmethod
    def module_present(self):
        """True when the kernel driver is loaded (module-detect)."""

    @abstractmethod
    def get_device_info(self):
        """Return a DeviceInfo."""

    @abstractmethod
    def get_video_info(self):
        """Return a VideoInfo."""

    @abstractmethod
    def get_audio_info(self):
        """Return an AudioInfo."""

    @abstractmethod
    def set_enabled(self, on):
        """Enable (True) or disable (False) the RX path."""

    @abstractmethod
    def wait_for_events(self, kind, timeout):
        """kind in {'plug','unplug'}; return the set of Event seen."""


# --------------------------------------------------------------------------
# Linux ioctl number helpers (asm-generic encoding)
# --------------------------------------------------------------------------
_IOC_TYPESHIFT = 8
_IOC_SIZESHIFT = 16
_IOC_DIRSHIFT = 30
_IOC_WRITE = 1
_IOC_READ = 2


def _IOC(direction, magic, nr, size):
    return (
        (direction << _IOC_DIRSHIFT)
        | (ord(magic) << _IOC_TYPESHIFT)
        | nr
        | (size << _IOC_SIZESHIFT)
    )


def _IOW(magic, nr, size):
    return _IOC(_IOC_WRITE, magic, nr, size)


def _IOR(magic, nr, size):
    return _IOC(_IOC_READ, magic, nr, size)


def _IOWR(magic, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, magic, nr, size)


# --------------------------------------------------------------------------
# Netlink uevent listener (pure stdlib, no ABI surface)
# --------------------------------------------------------------------------
NETLINK_KOBJECT_UEVENT = 15


def uevent_wait(key, event_map, timeout, devpath_filter=None):
    """Collect Events from kernel uevents for up to ``timeout`` seconds.

    key: the payload key to read, e.g. ``"SWITCH_NOTIFY"``.
    event_map: {driver code (int): Event}.
    devpath_filter: optional substring a datagram must contain (e.g.
        ``"hdmirx"``) so unrelated subsystems are ignored.

    Returns the set of Event seen before the deadline (possibly empty).
    """
    sock = socket.socket(
        socket.AF_NETLINK,
        socket.SOCK_DGRAM | socket.SOCK_CLOEXEC,
        NETLINK_KOBJECT_UEVENT,
    )
    got = set()
    try:
        sock.bind((0, 1))  # nl_pid=0 (kernel assigns), group 1 = uevents
        poller = select.poll()
        poller.register(sock, select.POLLIN)
        prefix = key.encode() + b"="
        prefix_len = len(prefix)
        needle = devpath_filter.encode() if devpath_filter else None
        deadline = time.monotonic() + timeout
        while True:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0 or not poller.poll(remaining_ms):
                break
            fields = sock.recv(8192).split(b"\0")
            if needle is not None and not any(needle in f for f in fields):
                continue
            for field in fields:
                if field.startswith(prefix):
                    got.add(_decode_event(field[prefix_len:], event_map))
        got.discard(None)
    finally:
        sock.close()
    return got


def _decode_event(raw_value, event_map):
    try:
        return event_map.get(int(raw_value))
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------
# Reusable ioctl-char-device backend base
# --------------------------------------------------------------------------
class IoctlError(OSError):
    """An ioctl call failed; carries the command key and device path."""


class AbiMismatch(RuntimeError):
    """A ctypes struct size differs from the expected kernel size."""


class IoctlCharBackend(HdmiRxBackend):
    """Base for a driver exposed as a custom ioctl character device.

    A platform supplies DATA only: ``MAGIC``, ``DEVICE_PATH``,
    ``MODULE_NAME``, ``DEVPATH_FILTER``, ``COMMANDS`` (keys
    ``dev_info`` / ``vid_info`` / ``aud_info`` / ``enable``),
    ``UEVENT_KEY``, ``EVENT_MAP``, ``EXPECTED_SIZES`` -- plus the
    three pure ``_map_*`` methods. The open/ioctl/errno/``_IOC``/
    self-check/uevent plumbing lives here once.
    """

    MAGIC = ""
    DEVICE_PATH = ""
    MODULE_NAME = None
    DEVPATH_FILTER = None
    COMMANDS = {}
    UEVENT_KEY = "SWITCH_NOTIFY"
    EVENT_MAP = {}
    EXPECTED_SIZES = {}

    def is_available(self):
        return bool(self.DEVICE_PATH) and os.path.exists(self.DEVICE_PATH)

    def module_present(self):
        if not self.MODULE_NAME:
            return self.is_available()
        return os.path.isdir("/sys/module/{}".format(self.MODULE_NAME))

    def _request(self, cmd_key):
        cmd = self.COMMANDS[cmd_key]
        encode = {"wr": _IOWR, "w": _IOW, "r": _IOR}[cmd.direction]
        return encode(self.MAGIC, cmd.nr, ctypes.sizeof(cmd.ctype))

    def _ioctl(self, cmd_key, arg):
        fd = os.open(self.DEVICE_PATH, os.O_RDWR)
        try:
            fcntl.ioctl(fd, self._request(cmd_key), arg)
        except OSError as exc:
            raise IoctlError(
                "ioctl {} on {} failed: {}".format(
                    cmd_key, self.DEVICE_PATH, exc
                )
            )
        finally:
            os.close(fd)
        return arg

    def abi_selfcheck(self):
        """Raise AbiMismatch if any struct size differs from the ABI."""
        for cmd_key, want in sorted(self.EXPECTED_SIZES.items()):
            got = ctypes.sizeof(self.COMMANDS[cmd_key].ctype)
            if got != want:
                raise AbiMismatch(
                    "{}: ctypes sizeof {} != expected kernel size {} "
                    "-- regenerate structs".format(cmd_key, got, want)
                )

    def set_enabled(self, on):
        self._ioctl("enable", ctypes.c_uint(1 if on else 0))

    def get_device_info(self):
        raw = self._ioctl("dev_info", self.COMMANDS["dev_info"].ctype())
        return self._map_device_info(raw)

    def get_video_info(self):
        raw = self._ioctl("vid_info", self.COMMANDS["vid_info"].ctype())
        return self._map_video_info(raw)

    def get_audio_info(self):
        raw = self._ioctl("aud_info", self.COMMANDS["aud_info"].ctype())
        return self._map_audio_info(raw)

    def wait_for_events(self, kind, timeout):
        return uevent_wait(
            self.UEVENT_KEY,
            self.EVENT_MAP,
            timeout,
            devpath_filter=self.DEVPATH_FILTER,
        )

    @abstractmethod
    def _map_device_info(self, raw):
        """Map a raw ctypes struct to a DeviceInfo."""

    @abstractmethod
    def _map_video_info(self, raw):
        """Map a raw ctypes struct to a VideoInfo."""

    @abstractmethod
    def _map_audio_info(self, raw):
        """Map a raw ctypes struct to an AudioInfo."""


# --------------------------------------------------------------------------
# Verification helpers (expected vs actual -> list of reason strings)
# --------------------------------------------------------------------------
_PLUG_EVENTS = frozenset(
    [Event.PWR_5V_CHANGE, Event.PLUG_IN, Event.TIMING_LOCK, Event.AUD_LOCK]
)
_UNPLUG_EVENTS = frozenset(
    [
        Event.AUD_UNLOCK,
        Event.TIMING_UNLOCK,
        Event.PWR_5V_CHANGE,
        Event.PLUG_OUT,
    ]
)
# With a zapper the cable stays physically connected, so the physical
# hot-plug events never fire -- only the signal lock/unlock ones do.
_ZAPPER_DISCARD = frozenset(
    [Event.PWR_5V_CHANGE, Event.PLUG_IN, Event.PLUG_OUT]
)


def expected_event_set(kind, with_zapper=False):
    """Return the set of Event a plug/unplug action should produce."""
    if kind == "plug":
        expected = set(_PLUG_EVENTS)
    elif kind == "unplug":
        expected = set(_UNPLUG_EVENTS)
    else:
        raise ValueError("kind must be 'plug' or 'unplug', got %r" % kind)
    if with_zapper:
        expected -= _ZAPPER_DISCARD
    return expected


def verify_events(got, kind, with_zapper=False):
    """Return reasons the observed events do not match expectations."""
    expected = expected_event_set(kind, with_zapper)
    missing = expected - set(got)
    if not missing:
        return []
    names = ", ".join(sorted(e.value for e in missing))
    return ["missing {} event(s): {}".format(kind, names)]


def verify_video(actual, exp_h, exp_v, exp_rate):
    """Return reasons the video reading differs from expectations."""
    reasons = []
    checks = (
        ("hactive", actual.hactive, int(exp_h)),
        ("vactive", actual.vactive, int(exp_v)),
        ("frame_rate", actual.frame_rate, int(exp_rate)),
    )
    for field, got, want in checks:
        if got != want:
            reasons.append("{} {} != expected {}".format(field, got, want))
    return reasons


def verify_audio(actual, exp_bits, exp_channels, exp_freq_khz):
    """Return reasons the audio reading differs from expectations."""
    reasons = []
    if actual.bit_depth != int(exp_bits):
        reasons.append(
            "bit_depth {} != expected {}".format(
                actual.bit_depth, int(exp_bits)
            )
        )
    if actual.channels != int(exp_channels):
        reasons.append(
            "channels {} != expected {}".format(
                actual.channels, int(exp_channels)
            )
        )
    if abs(actual.sample_freq_khz - float(exp_freq_khz)) > 0.01:
        reasons.append(
            "sample_freq_khz {} != expected {}".format(
                actual.sample_freq_khz, float(exp_freq_khz)
            )
        )
    return reasons
