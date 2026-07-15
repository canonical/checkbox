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
"""Genio HDMI RX backend (``/dev/hdmirx``, magic 'H').

This is a pure-Python reimplementation of the ioctl surface of
MediaTek's ``mtk-hdmirx-tool`` C++ utility for the Genio platform --
written from the ABI spec (ioctl numbers, struct fields, decode
tables), not from its source. The kernel module is ``mtk_hdmirx``.
The reusable plumbing lives in ``hdmirx_utils``; this file declares
only the structs, the command table and the field mappers.

Struct sizes are natural-aligned (NO ``_pack_``) and verified:
``HDMIRX_VID_PARA`` = 40, ``HDMIRX_DEV_INFO`` = 12,
``HDMIRX_AUD_INFO`` = 28 (AUDIO_INFOFRAME_LEN = 10).
"""

import ctypes

from hdmirx_utils import (
    AudioInfo,
    Colorspace,
    DeviceInfo,
    Event,
    IoctlCharBackend,
    IoctlCmd,
    VideoInfo,
)


# --------------------------------------------------------------------------
# Video / device structs
# --------------------------------------------------------------------------
class HDMIRX_VID_PARA(ctypes.Structure):  # noqa: N801 (C struct name)
    _fields_ = [
        ("cs", ctypes.c_int),  # enum HDMIRX_CS
        ("dp", ctypes.c_int),  # enum HdmiRxDP
        ("htotal", ctypes.c_uint32),
        ("vtotal", ctypes.c_uint32),
        ("hactive", ctypes.c_uint32),
        ("vactive", ctypes.c_uint32),
        ("is_pscan", ctypes.c_uint32),
        ("hdmi_mode", ctypes.c_bool),
        ("frame_rate", ctypes.c_uint32),
        ("pixclk", ctypes.c_uint32),
    ]  # sizeof == 40


class HDMIRX_DEV_INFO(ctypes.Structure):  # noqa: N801 (C struct name)
    _fields_ = [
        ("hdmirx5v", ctypes.c_uint8),
        ("hpd", ctypes.c_bool),
        ("power_on", ctypes.c_uint32),
        ("vid_locked", ctypes.c_uint8),
        ("aud_locked", ctypes.c_uint8),
        ("hdcp_version", ctypes.c_uint8),
    ]  # sizeof == 12


# --------------------------------------------------------------------------
# Audio structs (AUDIO_INFOFRAME_LEN = 10 -> HDMIRX_AUD_INFO sizeof 28)
# All members are u8 / bitfields, so alignment is 1.
# --------------------------------------------------------------------------
class _AudInfoFrameInfo(ctypes.Structure):
    _fields_ = [
        ("Type", ctypes.c_uint8),
        ("Ver", ctypes.c_uint8),
        ("Len", ctypes.c_uint8),
        ("AudioChannelCount", ctypes.c_uint8, 3),
        ("RSVD1", ctypes.c_uint8, 1),
        ("AudioCodingType", ctypes.c_uint8, 4),
        ("SampleSize", ctypes.c_uint8, 2),
        ("SampleFreq", ctypes.c_uint8, 3),
        ("Rsvd2", ctypes.c_uint8, 3),
        ("FmtCoding", ctypes.c_uint8),
        ("SpeakerPlacement", ctypes.c_uint8),
        ("Rsvd3", ctypes.c_uint8, 3),
        ("LevelShiftValue", ctypes.c_uint8, 4),
        ("DM_INH", ctypes.c_uint8, 1),
    ]


class _AudInfoFramePkt(ctypes.Structure):
    _fields_ = [
        ("AUD_HB", ctypes.c_uint8 * 3),
        ("AUD_DB", ctypes.c_uint8 * 10),  # AUDIO_INFOFRAME_LEN
    ]


class _AudInfoFrame(ctypes.Union):
    _fields_ = [("info", _AudInfoFrameInfo), ("pktbyte", _AudInfoFramePkt)]


class _AudChSts(ctypes.Structure):
    _fields_ = [
        ("rev", ctypes.c_uint8, 1),
        ("IsLPCM", ctypes.c_uint8, 1),
        ("CopyRight", ctypes.c_uint8, 1),
        ("AdditionFormatInfo", ctypes.c_uint8, 3),
        ("ChannelStatusMode", ctypes.c_uint8, 2),
        ("CategoryCode", ctypes.c_uint8),
        ("SourceNumber", ctypes.c_uint8, 4),
        ("ChannelNumber", ctypes.c_uint8, 4),
        ("SamplingFreq", ctypes.c_uint8, 4),
        ("ClockAccuary", ctypes.c_uint8, 2),
        ("rev2", ctypes.c_uint8, 2),
        ("WordLen", ctypes.c_uint8, 4),
        ("OriginalSamplingFreq", ctypes.c_uint8, 4),
    ]


class _AudCaps(ctypes.Structure):
    _fields_ = [
        ("SampleFreq", ctypes.c_uint8),
        ("AudInf", _AudInfoFrame),
        ("CHStatusData", ctypes.c_uint8 * 5),
        ("AudChStat", _AudChSts),
    ]


class _AudExtraInfo(ctypes.Structure):
    _fields_ = [
        ("is_HBRAudio", ctypes.c_bool),
        ("is_DSDAudio", ctypes.c_bool),
        ("is_RawSDAudio", ctypes.c_bool),
        ("is_PCMMultiCh", ctypes.c_bool),
    ]


class HDMIRX_AUD_INFO(ctypes.Structure):  # noqa: N801 (C struct name)
    _fields_ = [("caps", _AudCaps), ("info", _AudExtraInfo)]  # sizeof == 28


# --------------------------------------------------------------------------
# Decode tables (verbatim from inc/hdmi_if.h + src/hdmirx_tool.cpp)
# --------------------------------------------------------------------------
_COLORSPACE = {
    0: Colorspace.RGB,
    1: Colorspace.YUV444,
    2: Colorspace.YUV422,
    3: Colorspace.YUV420,
}
_BIT_DEPTH = {0: 8, 1: 10, 2: 12, 3: 16}  # enum HdmiRxDP
_SAMPLE_FREQ_KHZ = {  # caps.SampleFreq code
    0x0: 44.1,
    0x2: 48.0,
    0x3: 32.0,
    0x8: 88.2,
    0xA: 96.0,
    0xC: 176.4,
    0xE: 192.0,
}


def _decode_word_len_bits(word_len):
    """Map the IEC 60958 WordLen nibble to a bit depth (0 = unknown).

    bit0 selects the max-word-length mode (0 -> base 16, 1 -> base 20)
    and bits 3:1 (1..5) add 0..4; anything else is 'not indicated'.
    """
    base = 20 if (word_len & 0x1) else 16
    index = (word_len & 0xE) >> 1
    if 1 <= index <= 5:
        return base + (index - 1)
    return 0


class GenioIoctlBackend(IoctlCharBackend):
    """Genio backend (``mtk_hdmirx`` kernel module)."""

    name = "genio"
    MAGIC = "H"
    DEVICE_PATH = "/dev/hdmirx"
    MODULE_NAME = "mtk_hdmirx"
    DEVPATH_FILTER = "hdmirx"
    EVENT_MAP = {
        0: Event.PWR_5V_CHANGE,
        1: Event.TIMING_LOCK,
        2: Event.TIMING_UNLOCK,
        3: Event.AUD_LOCK,
        4: Event.AUD_UNLOCK,
        11: Event.PLUG_IN,
        12: Event.PLUG_OUT,
    }
    COMMANDS = {
        "vid_info": IoctlCmd(1, "wr", HDMIRX_VID_PARA),
        "aud_info": IoctlCmd(2, "wr", HDMIRX_AUD_INFO),
        "enable": IoctlCmd(3, "w", ctypes.c_uint),
        "dev_info": IoctlCmd(4, "wr", HDMIRX_DEV_INFO),
    }
    EXPECTED_SIZES = {"vid_info": 40, "dev_info": 12, "aud_info": 28}

    def _map_device_info(self, raw):
        return DeviceInfo(
            connected=bool(raw.hpd and raw.hdmirx5v),
            power_5v=bool(raw.hdmirx5v),
            hpd=bool(raw.hpd),
            video_locked=bool(raw.vid_locked),
            audio_locked=bool(raw.aud_locked),
            hdcp_version=raw.hdcp_version,
        )

    def _map_video_info(self, raw):
        return VideoInfo(
            hactive=raw.hactive,
            vactive=raw.vactive,
            frame_rate=raw.frame_rate,
            colorspace=_COLORSPACE.get(raw.cs),
            bit_depth=_BIT_DEPTH.get(raw.dp),
            interlaced=not raw.is_pscan,
        )

    def _map_audio_info(self, raw):
        acc = raw.caps.AudInf.info.AudioChannelCount
        return AudioInfo(
            bit_depth=_decode_word_len_bits(raw.caps.AudChStat.WordLen),
            channels=(acc + 1) if acc else 0,
            sample_freq_khz=_SAMPLE_FREQ_KHZ.get(raw.caps.SampleFreq, 0.0),
        )
