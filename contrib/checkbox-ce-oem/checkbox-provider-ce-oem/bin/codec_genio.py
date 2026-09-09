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
"""MediaTek Genio platform pipelines for the video-codec scenarios."""

import argparse
import logging
import os

from codec_base import BaseCodecProject
from gst_utils import (
    VIDEO_CODEC_TESTING_DATA,
    GST_LAUNCH_BIN,
    GStreamerMuxerType,
    GStreamerEncodePlugins,
    file_name_placeholder,
    generate_artifact_name,
    get_test_file_path_by_params,
)

logger = logging.getLogger(__name__)


def create_encoder_psnr_project(args: argparse.Namespace):
    """Create the encoder-PSNR pipeline project for Genio."""
    return GenioProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        color_space=args.color_space,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
        mux=args.mux,
    )


class GenioProject(BaseCodecProject):
    """
    Genio project manages platforms and codecs, and handles
    building.

    Spec: https://download.mediatek.com/aiot/download/release-note/v24.0/v24.0_IoT_Yocto_Feature_Table_v1.0.pdf     # noqa: E501
    """

    def __init__(
        self,
        platform: str,
        codec: str,
        color_space: str,
        width: int,
        height: int,
        framerate: int,
        mux: str,
    ) -> None:
        super().__init__(
            platform=platform,
            codec=codec,
            width=width,
            height=height,
            framerate=framerate,
            color_space=color_space,
            mux=mux,
        )
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse",
            GStreamerEncodePlugins.V4L2H265ENC.value: "h265parse",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        file_name = get_test_file_path_by_params(
            width, height, framerate, codec
        )
        # For v4l2jpegenc / v4l2jpegdec, using the MJPEG sample video.
        # https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/app-dev/image/image-common.html#motion-jpeg-video
        if codec == GStreamerEncodePlugins.V4L2JPEGENC.value:
            file_name = os.path.join(
                VIDEO_CODEC_TESTING_DATA,
                file_name_placeholder(
                    width=width,
                    height=height,
                    framerate=framerate,
                    codec_short_name="mjpeg",
                    ext="mov",
                ),
            )

        self._golden_sample = file_name

        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._264_265_pipeline_builder
            ),
            GStreamerEncodePlugins.V4L2H265ENC.value: (
                self._264_265_pipeline_builder
            ),
            GStreamerEncodePlugins.V4L2JPEGENC.value: (
                self._v4l2jpegenc_pipeline_builder
            ),
        }

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            self._artifact_file = generate_artifact_name(
                extension=GStreamerMuxerType.get_extension(
                    mux_type=self._mux.upper()
                )
            )
        return self._artifact_file

    def _264_265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 and H265 encoder
        """
        logger.info("Building H264/H265 pipeline for codec: %s", self._codec)
        base_pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert !"
            " video/x-raw,format={} ! {}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._codec,
        )

        if self._mux.upper() in (
            GStreamerMuxerType.MP4MUX.name,
            GStreamerMuxerType.MATROSKAMUX.name,
        ):
            encode_parser = self._codec_parser_map.get(self._codec)
            final_pipeline = "{} ! {} ! {} ! filesink location={}".format(
                base_pipeline,
                encode_parser,
                self._mux,
                self.artifact_file,
            )
        elif self._mux.upper() == GStreamerMuxerType.AVIMUX.name:
            final_pipeline = "{} ! {} ! filesink location={}".format(
                base_pipeline, self._mux, self.artifact_file
            )
        else:
            raise SystemExit(
                "Error: Pipeline for '{}' mux not implemented.".format(
                    self._mux
                )
            )

        logger.info("Final Pipeline: %s", final_pipeline)

        return final_pipeline

    def _v4l2jpegenc_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for JPEG encoder.
        https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/app-dev/image/image-common.html#image-codec
        """
        logger.info("Building JPEG pipeline for codec: %s", self._codec)
        if "350" in self._platform:
            raise SystemExit(
                "Genio 350 platform doesn't support v4l2jpegenc codec"
            )
        final_pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert ! "
            "video/x-raw,format={},width={},height={},framerate={}/1"
            " ! {} ! qtmux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._width,
            self._height,
            self._framerate,
            self._codec,
            self.artifact_file,
        )
        logger.info("Final Pipeline: %s", final_pipeline)
        return final_pipeline
