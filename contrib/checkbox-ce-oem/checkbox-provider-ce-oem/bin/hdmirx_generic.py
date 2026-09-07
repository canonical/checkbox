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
"""Generic mainline V4L2 HDMI RX backend.

For any platform whose HDMI RX exposes a mainline V4L2 sub-device
(e.g. the Synopsys DesignWare ``snps-hdmirx`` driver) this backend
reads the received resolution/refresh through the *stable* V4L2 UAPI
``VIDIOC_QUERY_DV_TIMINGS`` -- no vendor shim, no fragile private ABI.

Scope note: video and device presence are implemented and unit
tested against recorded ``v4l2_dv_timings`` buffers. Audio, RX
enable/disable and source-change events need a real V4L2 HDMI-RX
target to validate, so they raise ``NotImplementedError`` with the
exact UAPI to wire up, rather than ship unverified ctypes. The Genio
target uses ``hdmirx_genio`` and is unaffected.
"""

import ctypes
import fcntl
import glob
import os

from hdmirx_utils import (
    DeviceInfo,
    HdmiRxBackend,
    VideoInfo,
    _IOR,
)

# Driver ``name`` substrings that identify an HDMI RX capture node.
_HDMIRX_DRIVER_HINTS = ("hdmirx", "hdmi-rx", "hdmi rx")


class v4l2_fract(ctypes.Structure):  # noqa: N801 (UAPI struct name)
    _pack_ = 1
    _fields_ = [
        ("numerator", ctypes.c_uint32),
        ("denominator", ctypes.c_uint32),
    ]


class v4l2_bt_timings(ctypes.Structure):  # noqa: N801 (UAPI struct name)
    _pack_ = 1
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("interlaced", ctypes.c_uint32),
        ("polarities", ctypes.c_uint32),
        ("pixelclock", ctypes.c_uint64),
        ("hfrontporch", ctypes.c_uint32),
        ("hsync", ctypes.c_uint32),
        ("hbackporch", ctypes.c_uint32),
        ("vfrontporch", ctypes.c_uint32),
        ("vsync", ctypes.c_uint32),
        ("vbackporch", ctypes.c_uint32),
        ("il_vfrontporch", ctypes.c_uint32),
        ("il_vsync", ctypes.c_uint32),
        ("il_vbackporch", ctypes.c_uint32),
        ("standards", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("picture_aspect", v4l2_fract),
        ("cea861_vic", ctypes.c_uint8),
        ("hdmi_vic", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8 * 46),
    ]  # sizeof == 124 (packed)


class _v4l2_dv_union(ctypes.Union):  # noqa: N801 (UAPI struct name)
    _pack_ = 1
    _fields_ = [("bt", v4l2_bt_timings), ("reserved", ctypes.c_uint32 * 32)]


class v4l2_dv_timings(ctypes.Structure):  # noqa: N801 (UAPI struct name)
    _pack_ = 1
    _fields_ = [("type", ctypes.c_uint32), ("u", _v4l2_dv_union)]
    # union deliberately kept named ('u') rather than anonymous


# VIDIOC_QUERY_DV_TIMINGS = _IOR('V', 63, struct v4l2_dv_timings)
def _vidioc_query_dv_timings():
    return _IOR("V", 63, ctypes.sizeof(v4l2_dv_timings))


def _frame_rate_hz(bt):
    """Compute the refresh rate (rounded Hz) from BT timings."""
    htotal = bt.width + bt.hfrontporch + bt.hsync + bt.hbackporch
    vtotal = bt.height + bt.vfrontporch + bt.vsync + bt.vbackporch
    if bt.interlaced:
        vtotal += bt.il_vfrontporch + bt.il_vsync + bt.il_vbackporch
    denom = htotal * vtotal
    if denom == 0:
        return 0
    return int(round(bt.pixelclock / float(denom)))


def _find_hdmirx_video_node():
    """Return the /dev/videoN of the first HDMI RX node, or None."""
    for name_path in sorted(glob.glob("/sys/class/video4linux/video*/name")):
        try:
            with open(name_path) as handle:
                name = handle.read().strip().lower()
        except OSError:
            continue
        if any(hint in name for hint in _HDMIRX_DRIVER_HINTS):
            node = os.path.join(
                "/dev", os.path.basename(os.path.dirname(name_path))
            )
            if os.path.exists(node):
                return node
    return None


class V4L2Backend(HdmiRxBackend):
    """Mainline V4L2 HDMI RX backend (video + presence)."""

    name = "v4l2"

    def __init__(self, device_path=None):
        self._device_path = device_path or _find_hdmirx_video_node()

    def is_available(self):
        return bool(self._device_path) and os.path.exists(self._device_path)

    def module_present(self):
        return self.is_available()

    def _query_timings(self):
        timings = v4l2_dv_timings()
        fd = os.open(self._device_path, os.O_RDWR)
        try:
            ctypes.memset(ctypes.byref(timings), 0, ctypes.sizeof(timings))
            fcntl.ioctl(fd, _vidioc_query_dv_timings(), timings)
        finally:
            os.close(fd)
        return timings

    def get_video_info(self):
        bt = self._query_timings().u.bt
        return VideoInfo(
            hactive=bt.width,
            vactive=bt.height,
            frame_rate=_frame_rate_hz(bt),
            interlaced=bool(bt.interlaced),
        )

    def get_device_info(self):
        # A successful timings query with a non-zero width means the
        # RX is locked to an incoming signal (i.e. a cable is present).
        try:
            locked = self._query_timings().u.bt.width > 0
        except OSError:
            locked = False
        return DeviceInfo(
            connected=locked,
            power_5v=locked,
            hpd=locked,
            video_locked=locked,
            audio_locked=locked,
            hdcp_version=0,
        )

    def get_audio_info(self):
        raise NotImplementedError(
            "audio not available via the V4L2 video node; wire up the "
            "paired ALSA capture card (snd HDMI-RX) when a V4L2 target "
            "is available to validate"
        )

    def set_enabled(self, on):
        raise NotImplementedError(
            "enable/disable has no V4L2 equivalent for HDMI RX; add "
            "VIDIOC_STREAMON/OFF semantics only if a target requires it"
        )

    def wait_for_events(self, kind, timeout):
        raise NotImplementedError(
            "V4L2 source-change events (VIDIOC_SUBSCRIBE_EVENT + "
            "V4L2_EVENT_SOURCE_CHANGE + VIDIOC_DQEVENT) are not yet "
            "implemented; needs a V4L2 HDMI-RX target to validate"
        )
