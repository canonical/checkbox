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
import os

from codec_base import BaseCodecProject
from gst_utils import (
    VIDEO_CODEC_TESTING_DATA,
    SAMPLE_2_FOLDER,
    GST_LAUNCH_BIN,
    GStreamerMuxerType,
    GStreamerEncodePlugins,
    GStreamerTransformActions,
    generate_artifact_name,
    get_big_bug_bunny_golden_sample,
    get_test_file_path_by_params,
)


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


def create_transform_rotate_and_flip_project(args: argparse.Namespace):
    """Create the rotate/flip transform project for Genio."""
    return GenioTransformRotateAndFlipProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        action=args.action,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
    )


def create_transform_resize_project(args: argparse.Namespace):
    """Create the resize transform project for Genio."""
    return GenioTransformResizeProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        width_from=args.width_from,
        height_from=args.height_from,
        width_to=args.width_to,
        height_to=args.height_to,
        framerate=args.framerate,
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
        # input video. Genio always encodes from the h264 sample, like the
        # other platforms that decode then re-encode.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, "h264"
        )
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
            if self._codec == GStreamerEncodePlugins.V4L2JPEGENC.value:
                self._artifact_file = generate_artifact_name(extension="jpg")
            else:
                self._artifact_file = generate_artifact_name(
                    extension=GStreamerMuxerType.get_extension(
                        mux_type=self._mux.upper()
                    )
                )
        return self._artifact_file

    @property
    def psnr_reference_file(self) -> str:
        if self._codec == GStreamerEncodePlugins.V4L2JPEGENC.value:
            return os.path.join(
                VIDEO_CODEC_TESTING_DATA,
                SAMPLE_2_FOLDER,
                "big_bug_bunny_{}x{}.jpg".format(self._width, self._height),
            )
        else:
            return self._golden_sample

    def _264_265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 and H265 encoder
        """
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

        return final_pipeline

    def _v4l2jpegenc_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for JPEG encoder
        """
        if self._platform == "genio-350":
            raise SystemExit(
                "Genio 350 platform doesn't support v4l2jpegenc codec"
            )
        # Capture the first frame and save it as jpg file
        final_pipeline = (
            "{} filesrc location={} ! decodebin ! videorate !"
            " video/x-raw,framerate=1/1 ! videoconvert ! "
            "video/x-raw,format={} ! {} ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._codec,
            self.artifact_file,
        )
        return final_pipeline


class GenioTransformRotateAndFlipProject(BaseCodecProject):
    """Genio rotate/flip transform pipeline handler and builder."""

    def __init__(
        self,
        platform: str,
        codec: str,
        action: GStreamerTransformActions,
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
        self._action = action
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse"
        }
        self._actions_map = {
            GStreamerTransformActions.ROTATE_90: "rotate=90",
            GStreamerTransformActions.ROTATE_180: "rotate=180",
            GStreamerTransformActions.ROTATE_270: "rotate=270",
            GStreamerTransformActions.HORIZONTAL_FLIP: "horizontal_flip=1",
            GStreamerTransformActions.VERTICAL_FLIP: "vertical_flip=1",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_big_bug_bunny_golden_sample(
            width=self._width, height=self._height, framerate=self._framerate
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._transform_pipeline_builder
            ),
        }

    @property
    def psnr_reference_file(self) -> str:
        """
        A golden reference which has been transformed in advance. It's used to
        be the compared reference file for PSNR.
        """
        golden_reference = "big_bug_bunny_{}x{}_{}fps_{}.mp4".format(
            self._width, self._height, self._framerate, self._action
        )

        full_path = os.path.join(
            VIDEO_CODEC_TESTING_DATA, SAMPLE_2_FOLDER, golden_reference
        )
        if not os.path.exists(full_path):
            raise SystemExit(
                "Error: Golden PSNR reference '{}' doesn't exist".format(
                    full_path
                )
            )

        return full_path

    def _transform_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline performing the rotate/flip action.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! v4l2convert "
            "extra-controls='cid,{}'"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._actions_map.get(self._action),
        )

        if self._action in [
            GStreamerTransformActions.ROTATE_90,
            GStreamerTransformActions.ROTATE_270,
        ]:
            pipeline = (
                "{} ! video/x-raw,width={},height={},"
                "pixel-aspect-ratio='(fraction)1/1'"
            ).format(pipeline, self._height, self._width)

        pipeline = ("{} ! {} ! {} ! mp4mux ! filesink location={}").format(
            pipeline,
            self._codec,
            self._codec_parser_map.get(self._codec),
            self.artifact_file,
        )
        return pipeline


class GenioTransformResizeProject(BaseCodecProject):
    """Genio resize transform pipeline handler and builder."""

    def __init__(
        self,
        platform: str,
        codec: str,
        width_from: int,
        height_from: int,
        width_to: int,
        height_to: int,
        framerate: int,
    ) -> None:
        super().__init__(
            platform=platform,
            codec=codec,
            width=width_from,
            height=height_from,
            framerate=framerate,
        )
        self._width_to = width_to
        self._height_to = height_to
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse"
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, self._codec
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._resize_pipeline_builder
            ),
        }

    @property
    def psnr_reference_file(self) -> str:
        """
        A golden reference which has been transformed in advance. It's used to
        be the compared reference file for PSNR.
        """
        golden_reference = get_test_file_path_by_params(
            self._width_to, self._height_to, self._framerate, self._codec
        )
        if not os.path.exists(golden_reference):
            raise SystemExit(
                "Error: Golden PSNR reference '{}' doesn't exist".format(
                    golden_reference
                )
            )

        return golden_reference

    def _resize_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline scaling the stream while encoding.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! v4l2convert ! "
            "video/x-raw,width={},height={} ! {} ! {} ! mp4mux ! filesink"
            " location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._width_to,
            self._height_to,
            self._codec,
            self._codec_parser_map.get(self._codec),
            self.artifact_file,
        )
        return pipeline
