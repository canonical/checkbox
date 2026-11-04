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
    calculate_encoder_bitrate,
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
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            width, height, framerate, codec
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

    @property
    def _colorimetry(self) -> str:
        """
        Our golden samples carry no explicit VUI/colorimetry metadata, so
        the decoder infers it from resolution using the standard
        convention (also used by GStreamer/FFmpeg): SD content (height
        <= 576) defaults to BT.601, HD content (height > 576) defaults to
        BT.709. `videoconvert` does not preserve this inferred value when
        it performs an actual pixel reformat (e.g. NV12 -> I420/NV21/YUY2),
        silently falling back to BT.601 and corrupting non-NV12 encodes.
        We re-derive and pin the correct colorimetry here so the caps
        filter matches what the source actually is, instead of hardcoding
        a single value that would be wrong for any future SD test sample.
        """
        return "bt601" if self._height <= 576 else "bt709"

    # Maps a GStreamer encoder plugin to the V4L2 fourcc name it reports
    # on its Capture queue, used to look up the actual encoder device and
    # its supported bitrate range.
    _V4L2_CODEC_FOURCC = {
        GStreamerEncodePlugins.V4L2H264ENC.value: "H264",
        GStreamerEncodePlugins.V4L2H265ENC.value: "HEVC",
        GStreamerEncodePlugins.V4L2VP8ENC.value: "VP80",
    }

    def _bitrate_for(self, codec: str) -> int:
        """
        Calculate the target bitrate for the given encoder plugin, scaled
        to the test's resolution/framerate and clamped to what the
        actual target VPU's 'video_bitrate' V4L2 control supports. This
        avoids a single hardcoded bitrate that could be over/under
        provisioned for a given resolution, or invalid on a VPU whose
        supported bitrate range differs from the one this was tuned on.
        """
        fourcc = self._V4L2_CODEC_FOURCC.get(codec)
        return calculate_encoder_bitrate(
            width=self._width,
            height=self._height,
            framerate=self._framerate,
            codec_fourcc=fourcc,
        )

    def _h264_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 encoder
        """
        pipeline = (
            "{} filesrc location={} ! qtdemux ! decodebin !"
            " videoconvert ! video/x-raw,format={},colorimetry={} !"
            " v4l2h264enc extra-controls="
            '"controls,h264_profile=1,video_bitrate={};" !'
            " h264parse ! mp4mux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._colorimetry,
            self._bitrate_for(GStreamerEncodePlugins.V4L2H264ENC.value),
            self.artifact_file,
        )

        return pipeline

    def _h265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 encoder
        """
        pipeline = (
            "{} filesrc location={} ! qtdemux ! decodebin !"
            " videoconvert ! video/x-raw,format={},colorimetry={} !"
            " v4l2h265enc extra-controls="
            '"controls,video_bitrate={};" !'
            " h265parse ! mp4mux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._colorimetry,
            self._bitrate_for(GStreamerEncodePlugins.V4L2H265ENC.value),
            self.artifact_file,
        )

        return pipeline

    def _vp8_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 encoder
        """
        pipeline = (
            "{} filesrc location={} ! matroskademux ! decodebin !"
            " videoconvert ! video/x-raw,format={},colorimetry={} !"
            " v4l2vp8enc extra-controls="
            '"controls,video_bitrate={};" !'
            " matroskamux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._colorimetry,
            self._bitrate_for(GStreamerEncodePlugins.V4L2VP8ENC.value),
            self.artifact_file,
        )

        return pipeline
