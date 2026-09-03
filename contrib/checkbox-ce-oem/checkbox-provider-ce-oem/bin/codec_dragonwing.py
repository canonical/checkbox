#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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
"""Qualcomm Dragonwing platform pipelines for the video-codec
scenarios."""

import argparse

from codec_base import BaseCodecProject
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    get_test_file_path_by_params,
)


def create_encoder_psnr_project(args: argparse.Namespace):
    """Create the encoder-PSNR pipeline project for Dragonwing."""
    return DragonwingProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
    )


class DragonwingProject(BaseCodecProject):
    """Dragonwing project pipeline handler and builder"""

    def __init__(
        self,
        platform: str,
        codec: str,
        width: int,
        height: int,
        framerate: int,
    ) -> None:
        super().__init__(
            platform=platform,
            codec=codec,
            width=width,
            height=height,
            framerate=framerate,
        )
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse",
            GStreamerEncodePlugins.V4L2H265ENC.value: "h265parse",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, codec
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._264_265_pipeline_builder
            ),
            GStreamerEncodePlugins.V4L2H265ENC.value: (
                self._264_265_pipeline_builder
            ),
        }

    def _264_265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 and H265 encoder
        """
        # always use h264 file as golden sample
        encode_parser = self._codec_parser_map.get(self._codec)
        pipeline = (
            "{} -e filesrc location={} ! qtdemux ! queue ! h264parse !"
            " v4l2h264dec capture-io-mode=5 output-io-mode=5 !"
            " {} capture-io-mode=5 output-io-mode=5 !"
            " queue ! {} ! mp4mux ! queue !"
            " filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._codec,
            encode_parser,
            self.artifact_file,
        )

        return pipeline
