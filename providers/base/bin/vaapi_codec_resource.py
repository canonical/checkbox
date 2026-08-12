#! /usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
Resource job that reports the VA-API profile/entrypoint combinations the
DRM render node actually supports.

It parses the "Supported profile and entrypoints" table printed by vainfo
and emits one resource record per (profile, entrypoint) pair, e.g.::

    profile: VAProfileH264High
    profile_id: 7
    entrypoint: VAEntrypointVLD
    entrypoint_id: 1

The numeric ids match the VAProfile/VAEntrypoint enum values from libva's
va/va.h, so the ffmpeg codec jobs can gate on the same --profile and
--entrypoint numbers they already pass to ffmpeg_hw_codec_test.py. This lets
a job skip (unmet resource) instead of failing when the platform cannot
handle that codec.

If vainfo is missing or cannot initialise VA-API, no records are printed and
every gated job is skipped rather than failing.
"""

import os
import subprocess as sp
import sys

# VAProfile enum values, from libva va/va.h. Only the profiles referenced by
# the ffmpeg codec jobs need to match a number; unknown profiles are still
# emitted (with an empty profile_id) so the resource stays informative.
VA_PROFILE_IDS = {
    "VAProfileMPEG2Simple": 0,
    "VAProfileMPEG2Main": 1,
    "VAProfileH264Main": 6,
    "VAProfileH264High": 7,
    "VAProfileVC1Simple": 8,
    "VAProfileJPEGBaseline": 12,
    "VAProfileH264ConstrainedBaseline": 13,
    "VAProfileVP8Version0_3": 14,
    "VAProfileHEVCMain": 17,
    "VAProfileHEVCMain10": 18,
    "VAProfileVP9Profile0": 19,
    "VAProfileVP9Profile1": 20,
    "VAProfileVP9Profile2": 21,
    "VAProfileVP9Profile3": 22,
    "VAProfileHEVCMain12": 23,
    "VAProfileHEVCMain422_10": 24,
    "VAProfileHEVCMain422_12": 25,
    "VAProfileHEVCMain444": 26,
    "VAProfileHEVCMain444_10": 27,
    "VAProfileHEVCMain444_12": 28,
    "VAProfileHEVCSccMain": 29,
    "VAProfileHEVCSccMain10": 30,
    "VAProfileHEVCSccMain444": 31,
    "VAProfileAV1Profile0": 32,
    "VAProfileAV1Profile1": 33,
    "VAProfileHEVCSccMain444_10": 34,
    "VAProfileH264High10": 36,
    "VAProfileAV1Profile2": 39,
    "VAProfileH264High422": 40,
}

# VAEntrypoint enum values, from libva va/va.h.
VA_ENTRYPOINT_IDS = {
    "VAEntrypointVLD": 1,
    "VAEntrypointIZZ": 2,
    "VAEntrypointIDCT": 3,
    "VAEntrypointMoComp": 4,
    "VAEntrypointDeblocking": 5,
    "VAEntrypointEncSlice": 6,
    "VAEntrypointEncPicture": 7,
    "VAEntrypointEncSliceLP": 8,
    "VAEntrypointVideoProc": 10,
    "VAEntrypointFEI": 11,
    "VAEntrypointStats": 12,
    "VAEntrypointProtectedTEEComm": 13,
    "VAEntrypointProtectedContent": 14,
}


def parse_vainfo(text):
    """
    Parse vainfo output and yield one record dict per supported
    profile/entrypoint pair.

    The relevant lines look like::

          VAProfileH264High               :	VAEntrypointVLD

    so we keep lines that split on ':' into a "VAProfile..." name and a
    "VAEntrypoint..." name and ignore everything else (headers, the
    VAProfileNone/VideoProc line, libva log noise, etc).

    :param text: the combined stdout/stderr of vainfo.
    :returns: an iterator of dicts with profile, profile_id, entrypoint and
        entrypoint_id keys.
    """
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) != 2:
            continue
        profile = parts[0].strip()
        entrypoint = parts[1].strip()
        if not profile.startswith("VAProfile"):
            continue
        if not entrypoint.startswith("VAEntrypoint"):
            continue
        yield {
            "profile": profile,
            "profile_id": VA_PROFILE_IDS.get(profile, ""),
            "entrypoint": entrypoint,
            "entrypoint_id": VA_ENTRYPOINT_IDS.get(entrypoint, ""),
        }


def get_vainfo_output(device):
    """
    Run vainfo against the given DRM render node and return its combined
    output, or None if vainfo is unavailable or fails to initialise VA-API.
    """
    try:
        result = sp.run(
            ["vainfo", "--display", "drm", "--device", device],
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            universal_newlines=True,
        )
    except OSError as exc:
        print("vainfo could not be executed: {}".format(exc), file=sys.stderr)
        return None
    if result.returncode != 0:
        print(
            "vainfo failed on {} (exit {}):\n{}".format(
                device, result.returncode, result.stdout
            ),
            file=sys.stderr,
        )
        return None
    return result.stdout


def main():
    device = os.environ.get("VAAPI_DEVICE", "/dev/dri/renderD128")
    output = get_vainfo_output(device)
    if output is None:
        return
    for record in parse_vainfo(output):
        print("profile: {}".format(record["profile"]))
        print("profile_id: {}".format(record["profile_id"]))
        print("entrypoint: {}".format(record["entrypoint"]))
        print("entrypoint_id: {}".format(record["entrypoint_id"]))
        print()


if __name__ == "__main__":
    main()
