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
"""The basic codec project class every codec_<family>.py inherits."""

from gst_utils import PipelineInterface, generate_artifact_name


class BaseCodecProject(PipelineInterface):
    """
    The basic encoder-PSNR project every platform project inherits,
    like the camera platform classes inherit their base camera class.

    It carries the shared fields and default behaviors; a platform
    project overrides only what differs:
      - fill self._pipeline_builders with its codec -> builder mapping
        (build_pipeline dispatches through it)
      - override artifact_file / psnr_reference_file when the default
        does not fit
    """

    def __init__(
        self,
        platform: str,
        codec: str,
        width: int,
        height: int,
        framerate: int,
        color_space: str = "",
        mux: str = "",
    ) -> None:
        self._platform = platform
        self._codec = codec
        self._width = width
        self._height = height
        self._framerate = framerate
        self._color_space = color_space
        self._mux = mux
        self._golden_sample = ""
        self._artifact_file = ""
        # codec value -> bound pipeline builder, filled by the platform
        self._pipeline_builders = {}

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            self._artifact_file = generate_artifact_name()
        return self._artifact_file

    @property
    def psnr_reference_file(self) -> str:
        return self._golden_sample

    def build_pipeline(self) -> str:
        """
        Build the GStreamer command via the platform's builder mapping.
        """
        builder = self._pipeline_builders.get(self._codec)
        if builder is None:
            raise SystemExit(
                "Error: unknow encoder '{}' be used".format(self._codec)
            )
        return builder()
