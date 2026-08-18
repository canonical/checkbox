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

from gst_utils import (
    GST_LAUNCH_BIN,
    BaseCodecProject,
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


def build_decoder_performance_command(
    gst_bin: str,
    golden_sample_path: str,
    decoder: str,
    sink: str,
    fpsdisplaysink_sync: str,
    platform: str,
) -> str:
    """
    Builds a GStreamer command to process the golden sample.

    :param gst_bin:
        The binary name of gstreamer. Default is "gst-launch-1.0"
        You can assign the snap name to GST_LAUNCH_BIN env variable if you
        want to using snap.
    :param golden_sample_path:
        The path to the golden sample file.
    :param decoder:
        The decoder to use for the video, e.g., "v4l2vp8dec", "v4l2vp9dec".
    :param sink:
        The desired sink option, e.g., "fakesink".
    :param fpsdisplaysink_sync:
        The property option of fpsdisplaysink."
        Ref: https://gstreamer.freedesktop.org/documentation/debugutilsbad/
        fpsdisplaysink.html?gi-language=python#fpsdisplaysink:sync
    :param platform:
        The platform (conf file name), unused on i.MX8M.

    :returns:
        The GStreamer command to execute.
    """
    if decoder == "v4l2h264dec":
        part_pipeline = "qtdemux ! h264parse ! {}".format(decoder)
        # qtdemux ! h264parse ! v4l2h264dec
    elif decoder == "v4l2h265dec":
        part_pipeline = "qtdemux ! h265parse ! {}".format(decoder)
        # qtdemux ! h264parse ! v4l2h264dec
    elif decoder in ["v4l2vp8dec", "v4l2vp9dec"]:
        part_pipeline = "matroskademux ! queue ! {}".format(decoder)
        # matroskademux ! queue ! v4l2vp9dec
    cmd = (
        "{} -v filesrc location={} ! {} ! queue ! videoconvert ! "
        "queue ! fpsdisplaysink video-sink='{}' text-overlay=false sync={}"
    ).format(
        gst_bin, golden_sample_path, part_pipeline, sink, fpsdisplaysink_sync
    )

    return cmd


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
