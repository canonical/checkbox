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
"""NVIDIA Carmel (Xavier) platform pipelines for the video-codec
scenarios."""

import argparse

from gst_utils import (
    GST_LAUNCH_BIN,
    PipelineInterface,
    GStreamerEncodePlugins,
    generate_artifact_name,
    get_test_file_path_by_params,
)


def create_encoder_psnr_project(args: argparse.Namespace):
    """Create the encoder-PSNR pipeline project for Carmel."""
    return CarmelProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
    )


class CarmelProject(PipelineInterface):
    """Carmel project pipeline handler and builder"""

    def __init__(
        self,
        platform: str,
        codec: str,
        width: int,
        height: int,
        framerate: int,
    ) -> None:
        self._platform = platform
        self._codec = codec
        self._width = width
        self._height = height
        self._framerate = framerate
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse",
            GStreamerEncodePlugins.V4L2H265ENC.value: "h265parse",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, "h264"
        )
        self._artifact_file = ""

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            self._artifact_file = generate_artifact_name()
        return self._artifact_file

    @property
    def psnr_reference_file(self) -> str:
        return self._golden_sample

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

    def build_pipeline(self) -> str:
        """
        Build the GStreamer commands based on the codec.

        Returns:
            str: A GStreamer command.
        """
        if self._codec in (
            GStreamerEncodePlugins.V4L2H264ENC.value,
            GStreamerEncodePlugins.V4L2H265ENC.value,
        ):
            return self._264_265_pipeline_builder()
        else:
            raise SystemExit(
                "Error: unknow encoder '{}' be used".format(self._codec)
            )
