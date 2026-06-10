#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Checkbox Contributors
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

"""
Generate hardware video acceleration resource records from C3 manifest
environment variables.

Reads per-API environment variables that declare codec:profile capabilities
in the format ``CODEC:Profile1,Profile2;CODEC2:Profile3``.  Cross-references
with fluster-decoder-map.json to produce RFC2822 resource records used by
template-based test jobs.

The data file is the single source of truth for decoder names, test suites,
and encoder mappings.  No encoder or profile mappings are hardcoded here.
"""

import argparse
import json
import os
import re
import sys

MANIFEST_ENV_MAP = {
    "vaapi_decode": "HW_VIDEO_ACCEL_VAAPI_DECODE",
    "vaapi_encode": "HW_VIDEO_ACCEL_VAAPI_ENCODE",
    "vdpau_decode": "HW_VIDEO_ACCEL_VDPAU_DECODE",
    "vulkan_decode": "HW_VIDEO_ACCEL_VULKAN_DECODE",
    "nvdec_decode": "HW_VIDEO_ACCEL_NVDEC_DECODE",
    "nvenc_encode": "HW_VIDEO_ACCEL_NVENC_ENCODE",
}

API_JSON_KEY = {
    "vaapi_decode": "va-api",
    "vaapi_encode": "va-api",
    "vdpau_decode": "vdpau",
    "vulkan_decode": "vulkan-video",
    "nvdec_decode": "nvdec",
    "nvenc_encode": "nvenc",
}

DECODE_APIS = [
    "vaapi_decode",
    "vdpau_decode",
    "vulkan_decode",
    "nvdec_decode",
]

ENCODE_APIS = [
    "vaapi_encode",
    "nvenc_encode",
]

FLUSTER_DECODER_MAP_FILE = "fluster-decoder-map.json"

PROFILE_OPTS_MAP = {
    ("h264", "baseline"): "-profile:v baseline",
    ("h264", "main"): "-profile:v main",
    ("h264", "high"): "-profile:v high",
    ("hevc", "main"): "-profile:v main",
    ("hevc", "main 10"): "-profile:v main10",
    ("av1", "main"): "-profile:v main",
    ("av1", "high"): "-profile:v high",
    ("vp8", "default"): "",
    ("vp9", "profile 0"): "-profile:v 0",
    ("vp9", "profile 1"): "-profile:v 1",
    ("vp9", "profile 2"): "-profile:v 2",
    ("vp9", "profile 3"): "-profile:v 3",
}


def parse_profiles(raw_value):
    """Parse ``CODEC:Profile1,Profile2;CODEC2:Profile3`` into a list."""
    if not raw_value:
        return []
    results = []
    for codec_entry in raw_value.split(";"):
        codec_entry = codec_entry.strip()
        if not codec_entry:
            continue
        parts = codec_entry.split(":", 1)
        if len(parts) != 2:
            continue
        codec = parts[0].strip()
        profiles = [p.strip() for p in parts[1].split(",") if p.strip()]
        if codec and profiles:
            results.append((codec, profiles))
    return results


def slugify(text):
    """Convert a profile name to a filesystem-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def load_decoder_map(provider_data):
    """Load the fluster decoder map from the provider data directory."""
    path = os.path.join(provider_data, FLUSTER_DECODER_MAP_FILE)
    if not os.path.isfile(path):
        print(
            "WARNING: {} not found".format(path),
            file=sys.stderr,
        )
        return {}
    with open(path, "r") as fh:
        return json.load(fh)


def generate_decode_resources(env, decoder_map, backends):
    """Generate resource records for Fluster decode scenarios."""
    records = []
    fluster_decoders = decoder_map.get("fluster_decoders", {})
    test_suites = decoder_map.get("test_suites", {})
    for api in DECODE_APIS:
        env_var = MANIFEST_ENV_MAP.get(api, "")
        raw_value = env.get(env_var, "")
        if not raw_value:
            continue
        json_key = API_JSON_KEY.get(api, "")
        api_decoders = fluster_decoders.get(json_key, {})
        for codec, profiles in parse_profiles(raw_value):
            codec_suites = test_suites.get(codec, {})
            for profile in profiles:
                profile_s = slugify(profile)
                suite_names = codec_suites.get(profile, [])
                if not suite_names:
                    continue
                for backend in backends:
                    backend_decoders = api_decoders.get(backend, {})
                    decoder_name = backend_decoders.get(codec, "")
                    if not decoder_name:
                        continue
                    for suite in suite_names:
                        records.append(
                            {
                                "scenario": "fluster-decode",
                                "decoder": decoder_name,
                                "profile_slug": profile_s,
                                "test_suite": suite,
                                "codec": codec,
                                "profile": profile,
                            }
                        )
    return records


def generate_encode_resources(env, decoder_map):
    """Generate resource records for hardware encode scenarios."""
    records = []
    encode_profiles = decoder_map.get("encode_profiles", {})
    for api in ENCODE_APIS:
        env_var = MANIFEST_ENV_MAP.get(api, "")
        raw_value = env.get(env_var, "")
        if not raw_value:
            continue
        json_key = API_JSON_KEY.get(api, "")
        api_encoders = encode_profiles.get(json_key, {})
        declared = parse_profiles(raw_value)
        for codec, profiles in declared:
            for encoder_key, encoder_info in api_encoders.items():
                if encoder_info.get("codec") != codec:
                    continue
                encoder_profiles = encoder_info.get("profiles", [])
                for profile in profiles:
                    if profile not in encoder_profiles:
                        continue
                    profile_s = slugify(profile)
                    profile_key = (
                        encoder_key.split("_")[0],
                        profile.lower(),
                    )
                    profile_opts = PROFILE_OPTS_MAP.get(profile_key, "")
                    records.append(
                        {
                            "scenario": "encode",
                            "encoder": encoder_key,
                            "ffmpeg_encoder": encoder_key,
                            "ffmpeg_profile_opts": profile_opts,
                            "profile_slug": profile_s,
                            "codec": codec,
                            "profile": profile,
                        }
                    )
    return records


def _format_rfc2822(record):
    """Format a dict as an RFC2822-style record block."""
    lines = []
    for key in record:
        lines.append("{}: {}".format(key, record[key]))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate HW video accel resource records"
    )
    parser.add_argument(
        "--backends",
        default="ffmpeg,gstreamer",
        help="Comma-separated backends (default: ffmpeg,gstreamer)",
    )
    args = parser.parse_args()
    backends = [b.strip() for b in args.backends.split(",")]
    env = os.environ
    provider_data = env.get("PLAINBOX_PROVIDER_DATA", "")
    decoder_map = load_decoder_map(provider_data) if provider_data else {}
    records = generate_decode_resources(env, decoder_map, backends)
    records.extend(generate_encode_resources(env, decoder_map))
    blocks = []
    for record in records:
        blocks.append(_format_rfc2822(record))
    output = "\n\n".join(blocks)
    if output:
        print(output)


if __name__ == "__main__":
    main()
