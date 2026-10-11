#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
import configparser
import os
import platform
import subprocess

ENCODER_MAP = {
    "h264": "vah264enc",
    "h265": "vah265enc",
    "vp8": "vavp8enc",
    "vp9": "vavp9enc",
    "av1": "vaav1enc",
    "jpeg": "jpegenc",
    "mpeg4": "vampl4enc",
}

DECODER_MAP = {
    "av1-profile0": "has_av1_profile0_decoder_vaapi",
    "av1-profile1": "has_av1_profile1_decoder_vaapi",
    "av1-profile2": "has_av1_profile2_decoder_vaapi",
    "h264-constrained_baseline": (
        "has_h264_constrained_baseline_decoder_vaapi"
    ),
    "h264-main": "has_h264_main_decoder_vaapi",
    "h264-high": "has_h264_high_decoder_vaapi",
    "h264-high10": "has_h264_high10_decoder_vaapi",
    "h264-high422": "has_h264_high422_decoder_vaapi",
    "h264-high444": "has_h264_high444_decoder_vaapi",
    "h265-main": "has_h265_main_decoder_vaapi",
    "h265-main10": "has_h265_main10_decoder_vaapi",
    "h265-main12": "has_h265_main12_decoder_vaapi",
    "h265-main422_10": "has_h265_main422_10_decoder_vaapi",
    "h265-main444": "has_h265_main444_decoder_vaapi",
    "h265-main444_10": "has_h265_main444_10_decoder_vaapi",
    "h265-main444_12": "has_h265_main444_12_decoder_vaapi",
    "jpeg-baseline": "has_jpeg_baseline_decoder_vaapi",
    "mpeg2-simple": "has_mpeg2_simple_decoder_vaapi",
    "mpeg2-main": "has_mpeg2_main_decoder_vaapi",
    "mpeg4-simple": "has_mpeg4_simple_decoder_vaapi",
    "mpeg4-advanced_simple": ("has_mpeg4_advanced_simple_decoder_vaapi"),
    "mpeg4-main": "has_mpeg4_main_decoder_vaapi",
    "vc1-simple": "has_vc1_simple_decoder_vaapi",
    "vc1-main": "has_vc1_main_decoder_vaapi",
    "vc1-advanced": "has_vc1_advanced_decoder_vaapi",
    "vp8-version0_3": "has_vp8_version0_3_decoder_vaapi",
    "vp9-profile0": "has_vp9_profile0_decoder_vaapi",
    "vp9-profile1": "has_vp9_profile1_decoder_vaapi",
    "vp9-profile2": "has_vp9_profile2_decoder_vaapi",
    "vp9-profile3": "has_vp9_profile3_decoder_vaapi",
}

VA_ENCODER_NAMES = {
    "h264": "H264",
    "h265": "H265",
    "vp8": "VP8",
    "vp9": "VP9",
    "av1": "AV1",
    "jpeg": "JPEG",
    "mpeg4": "MPEG4",
}

VA_DECODER_NAMES = {
    "av1": "AV1",
    "h264": "H264",
    "h265": "H265",
    "jpeg": "JPEG",
    "mpeg2": "MPEG2",
    "mpeg4": "MPEG4",
    "vc1": "VC1",
    "vp8": "VP8",
    "vp9": "VP9",
}

DECODER_PROFILES = {
    "av1": ["profile0", "profile1", "profile2"],
    "h264": [
        "constrained_baseline",
        "main",
        "high",
        "high10",
        "high422",
        "high444",
    ],
    "h265": [
        "main",
        "main10",
        "main12",
        "main422_10",
        "main444",
        "main444_10",
        "main444_12",
    ],
    "jpeg": ["baseline"],
    "mpeg2": ["simple", "main"],
    "mpeg4": ["simple", "advanced_simple", "main"],
    "vc1": ["simple", "main", "advanced"],
    "vp8": ["version0_3"],
    "vp9": ["profile0", "profile1", "profile2", "profile3"],
}


def run_vainfo():
    try:
        result = subprocess.run(
            ["vainfo"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return ""
        return result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def detect_vaapi_encoders():
    output = run_vainfo()
    if not output:
        return {}
    available = {}
    for codec, va_name in VA_ENCODER_NAMES.items():
        if "VAProfile{}".format(va_name) in output:
            available[codec] = True
    return available


def detect_vaapi_decoders():
    output = run_vainfo()
    if not output:
        return {}
    available = {}
    for codec, va_name in VA_DECODER_NAMES.items():
        if "VAProfile{}".format(va_name) in output:
            profiles = DECODER_PROFILES.get(codec, [])
            for profile in profiles:
                key = "{}-{}".format(codec, profile)
                available[key] = True
    return available


def read_config_file(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    resources = {}

    if config.has_section("platform"):
        for key, value in config["platform"].items():
            resources[key] = value

    if config.has_section("encoder"):
        for codec, enabled in config["encoder"].items():
            resources["encoder_{}".format(codec)] = enabled

    if config.has_section("decoder"):
        for decoder, enabled in config["decoder"].items():
            resources["decoder_{}".format(decoder)] = enabled

    return resources


def detect_gpu_vendor(output):
    for vendor in ["intel", "amd", "nvidia", "mesa"]:
        if vendor in output.lower():
            return vendor
    return "unknown"


def emit_resources(resources):
    for key, value in sorted(resources.items()):
        print("{}: {}".format(key, value))


def main():
    resources = {}
    config_path = os.environ.get("PLATFORM_CONFIG")

    resources["arch"] = platform.machine()
    resources["gpu_vendor"] = "unknown"

    if config_path and os.path.exists(config_path):
        config_resources = read_config_file(config_path)
        resources.update(config_resources)
    else:
        vainfo_output = run_vainfo()
        if vainfo_output:
            available_encoders = detect_vaapi_encoders()
            available_decoders = detect_vaapi_decoders()

            for codec in ENCODER_MAP:
                resources["encoder_{}".format(codec)] = str(
                    available_encoders.get(codec, False)
                )

            for profile in DECODER_MAP:
                resources["decoder_{}".format(profile)] = str(
                    available_decoders.get(profile, False)
                )

            resources["gpu_vendor"] = detect_gpu_vendor(vainfo_output)

    emit_resources(resources)


if __name__ == "__main__":
    main()
