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
NVIDIA Jetson (Orin / Thor) platform pipelines for the video-codec
scenarios.

All hardware codecs are reached through NVIDIA's L4T gstreamer plugins:
the single nvv4l2decoder element decodes every codec, and the
nvv4l2{h264,h265,av1}enc elements encode. The decoder emits NVMM buffers
which the encoders consume directly.
"""

import argparse

from codec_base import BaseCodecProject
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    generate_artifact_name,
    get_test_file_path_by_params,
)


def create_encoder_psnr_project(args: argparse.Namespace):
    """Create the encoder-PSNR pipeline project for Jetson."""
    return JetsonProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
    )


def create_decoder_performance_project(args: argparse.Namespace):
    """Create the decoder-performance pipeline project for Jetson."""
    return JetsonDecoderPerformanceProject(args)


class JetsonDecoderPerformanceProject(BaseCodecProject):
    """
    Jetson decoder-performance pipeline handler and builder.

    The single nvv4l2decoder element emits NVMM buffers; nvvidconv brings
    them back to system memory for the sink. parsebin picks the
    demuxer/parser for any container.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(
            platform=args.platform,
            codec=args.decoder_plugin,
            width=0,
            height=0,
            framerate=0,
        )
        self._golden_sample = args.golden_sample_path
        self._sink = args.sink
        self._fpsdisplaysink_sync = args.fpsdisplaysink_sync
        self._pipeline_builders = {
            args.decoder_plugin: self._performance_pipeline_builder,
        }

    def _performance_pipeline_builder(self) -> str:
        return (
            "{} -v filesrc location={} ! parsebin ! queue ! {} ! queue ! "
            "nvvidconv ! video/x-raw,format=NV12 ! "
            'queue ! fpsdisplaysink video-sink="{}"'
            " text-overlay=false sync={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._codec,
            self._sink,
            self._fpsdisplaysink_sync,
        )


class JetsonProject(BaseCodecProject):
    """Jetson project pipeline handler and builder."""

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
            GStreamerEncodePlugins.NVV4L2H264ENC.value: "h264parse",
            GStreamerEncodePlugins.NVV4L2H265ENC.value: "h265parse",
            GStreamerEncodePlugins.NVV4L2AV1ENC.value: "av1parse",
        }
        # Bitrates follow the legacy Jetson transcode jobs; the AV1
        # encoder keeps its default.
        self._codec_bitrate_map = {
            GStreamerEncodePlugins.NVV4L2H264ENC.value: " bitrate=20000000",
            GStreamerEncodePlugins.NVV4L2H265ENC.value: " bitrate=8000000",
            GStreamerEncodePlugins.NVV4L2AV1ENC.value: "",
        }
        # This sample video file will be consumed by any gstreamer pipeline
        # as input video. Keyed by the encoder plugin so it matches the file
        # that main()'s manage_test_file_by_params downloads (h265 input for
        # the h265 encoder, h264 otherwise); nvv4l2decoder decodes both.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, self._codec
        )
        self._input_parser = (
            "h265parse"
            if self._codec == GStreamerEncodePlugins.NVV4L2H265ENC.value
            else "h264parse"
        )
        # Every supported encoder shares the one decode-then-encode
        # pipeline.
        self._pipeline_builders = {
            codec: self._encode_pipeline_builder
            for codec in self._codec_parser_map
        }

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            # AV1-in-mp4 support is inconsistent in gstreamer 1.20, so the
            # AV1 artifact goes into a matroska container instead.
            if self._codec == GStreamerEncodePlugins.NVV4L2AV1ENC.value:
                self._artifact_file = generate_artifact_name(extension="mkv")
            else:
                self._artifact_file = generate_artifact_name()
        return self._artifact_file

    def _encode_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline: decode the golden sample with
        nvv4l2decoder, re-encode it with the codec under test.
        """
        if self._codec == GStreamerEncodePlugins.NVV4L2AV1ENC.value:
            mux = "matroskamux"
        else:
            mux = "mp4mux"
        pipeline = (
            "{} -e filesrc location={} ! qtdemux ! queue ! {} !"
            " nvv4l2decoder ! queue ! {}{} ! {} ! {} ! queue !"
            " filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._input_parser,
            self._codec,
            self._codec_bitrate_map[self._codec],
            self._codec_parser_map[self._codec],
            mux,
            self.artifact_file,
        )

        return pipeline
