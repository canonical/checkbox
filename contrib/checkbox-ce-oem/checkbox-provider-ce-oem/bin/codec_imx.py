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
"""NXP i.MX8M platform pipelines for the video-codec scenarios."""

import argparse

from codec_base import BaseCodecProject
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    generate_artifact_name,
    get_test_file_path_by_params,
)


def create_encoder_psnr_project(args: argparse.Namespace):
    """Create the encoder-PSNR pipeline project for i.MX8M."""
    return NxpIMX8mProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        color_space=args.color_space,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
    )


def create_decoder_performance_project(args: argparse.Namespace):
    """Create the decoder-performance pipeline project for i.MX8M."""
    return ImxDecoderPerformanceProject(args)


class ImxDecoderPerformanceProject(BaseCodecProject):
    """i.MX8M decoder-performance pipeline handler and builder."""

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
        self._demux_map = {
            "v4l2h264dec": "qtdemux ! h264parse ! {}",
            "v4l2h265dec": "qtdemux ! h265parse ! {}",
            "v4l2vp8dec": "matroskademux ! queue ! {}",
            "v4l2vp9dec": "matroskademux ! queue ! {}",
        }
        self._pipeline_builders = {
            decoder: self._performance_pipeline_builder
            for decoder in self._demux_map
        }

    def _performance_pipeline_builder(self) -> str:
        part_pipeline = self._demux_map[self._codec].format(self._codec)
        return (
            "{} -v filesrc location={} ! {} ! queue ! videoconvert ! "
            "queue ! fpsdisplaysink video-sink='{}' text-overlay=false"
            " sync={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            part_pipeline,
            self._sink,
            self._fpsdisplaysink_sync,
        )


class NxpIMX8mProject(BaseCodecProject):
    """NXP i.MX8M project pipeline handler and builder"""

    def __init__(
        self,
        platform: str,
        codec: str,
        color_space: str,
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
            color_space=color_space,
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._h264_pipeline_builder
            ),
            GStreamerEncodePlugins.V4L2H265ENC.value: (
                self._h265_pipeline_builder
            ),
            GStreamerEncodePlugins.V4L2VP8ENC.value: (
                self._vp8_pipeline_builder
            ),
        }

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            if self._codec == GStreamerEncodePlugins.V4L2VP8ENC.value:
                self._artifact_file = generate_artifact_name(extension="mkv")
            else:
                self._artifact_file = generate_artifact_name()
        return self._artifact_file

    def _h264_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 encoder
        """
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, "h264"
        )
        pipeline = (
            "{} filesrc location={} ! qtdemux ! decodebin !"
            " imxvideoconvert_g2d ! videoconvert ! video/x-raw,format={} !"
            " v4l2h264enc extra-controls="
            '"controls,h264_profile=1,video_bitrate=15000000;" !'
            " h264parse ! mp4mux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self.artifact_file,
        )

        return pipeline

    def _h265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 encoder
        """
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, "h265"
        )
        pipeline = (
            "{} filesrc location={} ! qtdemux ! decodebin !"
            " imxvideoconvert_g2d ! videoconvert ! video/x-raw,format={} !"
            " v4l2h265enc ! h265parse ! mp4mux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self.artifact_file,
        )

        return pipeline

    def _vp8_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 encoder
        """
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, "vp8"
        )
        pipeline = (
            "{} filesrc location={} ! matroskademux ! decodebin !"
            " imxvideoconvert_g2d ! videoconvert ! video/x-raw,format={} !"
            " v4l2vp8enc ! matroskamux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self.artifact_file,
        )

        return pipeline
