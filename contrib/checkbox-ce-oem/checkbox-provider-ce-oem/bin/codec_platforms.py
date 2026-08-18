#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Isaac Yang    <isaac.yang@canonical.com>
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
"""
The single place that knows which video-codec platforms exist.

The naming rule: every conf file in data/video-codec-test-confs/ starts
with its family name (genio-1200.json, imx-8mp.json, rzg2l.json,
jetson-orin-agx.json, ...), the family's pipelines live in
codec_<family>.py, and the family key in PLATFORM_FAMILIES is that
shared prefix.

Adding a new project means adding one PlatformFamily entry here, one
conf file named <family>[-<board>].json, and - only when the platform
needs its own gstreamer pipelines - a codec_<family>.py module.
"""

import importlib

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class PlatformFamily:
    """
    Declarative description of one platform family.

    Attributes:
        id_prefix: family prefix carried by the job ids ("" = none).
        encoder_id_suffix_fields: optional fields the encoder job id
            appends, in order. These define the family's id shape - do
            not change them for existing families.
        perf_id_includes_sample: True when one decoder element serves
            several codecs, so the decoder-performance job id needs the
            golden-sample name to stay unique per codec.
    """

    id_prefix: str = ""
    encoder_id_suffix_fields: Tuple[str, ...] = field(default_factory=tuple)
    perf_id_includes_sample: bool = False


PLATFORM_FAMILIES = {
    "genio": PlatformFamily(
        id_prefix="genio",
        encoder_id_suffix_fields=("color_space", "mux"),
    ),
    "dragonwing": PlatformFamily(
        id_prefix="dragonwing",
    ),
    "imx": PlatformFamily(
        id_prefix="imx8",
        encoder_id_suffix_fields=("color_space",),
    ),
    "rz": PlatformFamily(
        id_prefix="renesas",
        encoder_id_suffix_fields=("color_space",),
    ),
}


def get_platform_family(conf_name: str) -> str:
    """
    Map a conf file name (which doubles as the platform) to its family in
    PLATFORM_FAMILIES: conf files are named after their family, so the
    family key is the conf-name prefix. Returns "" for unknown platforms.
    """
    for family in PLATFORM_FAMILIES:
        if conf_name.startswith(family):
            return family
    return ""


def codec_factory(platform: str):
    """
    Return the family's codec_<family>.py module for the platform, like
    camera_factory() does for the camera framework. Returns None when the
    platform is unknown or the family ships no module (platforms that only
    use the generic pipelines).
    """
    family = get_platform_family(platform)
    if not family:
        return None
    try:
        return importlib.import_module("codec_{}".format(family))
    except ImportError:
        return None
