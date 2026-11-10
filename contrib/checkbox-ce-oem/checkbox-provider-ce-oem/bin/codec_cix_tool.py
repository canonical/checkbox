#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
CIX P1 (CIX P1 CD8180, Mali 'Linlon'/mvx VPU) pipelines for the
video-codec scenarios.

This platform's GStreamer stack (checked against OEMQA-6925) has no
v4l2convert element, so every generic pipeline built around v4l2convert
(in gst_transform_resize.py, gst_transform_rotate_and_flip.py,
and gst_video_decoder_performance.py) fails to even construct the
pipeline. The overrides below swap in the plain software
videoconvert/videoscale/videoflip elements instead; everything else
(decoder/encoder plugin selection, parser/mux choice) matches the
generic default behavior.

gst_encoder_psnr's generic pipeline already uses videoconvert; CIX only
pins its colorimetry (see CixEncoderPsnrProject).
"""

import argparse

from codec_base import BaseCodecProject
from gst_encoder_psnr import GenericEncoderProject
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    GStreamerTransformActions,
    get_test_file_path_by_params,
)

DMABUF_IO_MODES = "capture-io-mode=mmap output-io-mode=dmabuf"


def encoder_element(codec: str) -> str:
    return "{} {}".format(codec, DMABUF_IO_MODES)


class CixTransformResizeProject(BaseCodecProject):
    """
    CIX P1 resize transform pipeline: identical to the generic
    gst_transform_resize.py pipeline, except videoconvert + videoscale
    replace v4l2convert since this platform has no v4l2convert element.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(
            platform=args.platform,
            codec=args.encoder_plugin,
            width=args.width_from,
            height=args.height_from,
            framerate=args.framerate,
        )
        self._width_to = args.width_to
        self._height_to = args.height_to
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

    def _resize_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline scaling the stream while encoding.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert !"
            " videoscale ! video/x-raw,width={},height={} ! {} ! {}"
            " ! mp4mux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._width_to,
            self._height_to,
            encoder_element(self._codec),
            "h264parse",
            self.artifact_file,
        )
        return pipeline


create_transform_resize_project = CixTransformResizeProject


class CixTransformRotateAndFlipProject(BaseCodecProject):
    """
    CIX P1 rotate/flip transform pipeline: identical in intent to the
    generic gst_transform_rotate_and_flip.py pipeline, except videoflip
    replaces the v4l2convert extra-controls rotation since this platform
    has no v4l2convert element.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(
            platform=args.platform,
            codec=args.encoder_plugin,
            width=args.width,
            height=args.height,
            framerate=args.framerate,
        )
        self._action = args.action
        self._actions_map = {
            GStreamerTransformActions.ROTATE_90: "clockwise",
            GStreamerTransformActions.ROTATE_180: "rotate-180",
            GStreamerTransformActions.ROTATE_270: "counterclockwise",
            GStreamerTransformActions.HORIZONTAL_FLIP: "horizontal-flip",
            GStreamerTransformActions.VERTICAL_FLIP: "vertical-flip",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, args.encoder_plugin
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._transform_pipeline_builder
            ),
        }

    def _transform_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline performing the rotate/flip action.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert !"
            " videoflip method={} ! {} ! {} ! mp4mux ! filesink"
            " location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._actions_map.get(self._action),
            encoder_element(self._codec),
            "h264parse",
            self.artifact_file,
        )
        return pipeline


create_transform_rotate_and_flip_project = CixTransformRotateAndFlipProject


class CixDecoderPerformanceProject(BaseCodecProject):
    """
    CIX P1 decoder-performance pipeline: identical to the generic
    gst_video_decoder_performance.py pipeline, except videoconvert
    replaces v4l2convert since this platform has no v4l2convert element.
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
            "{} -v filesrc location={} ! parsebin ! queue ! {} ! queue !"
            ' videoconvert ! queue ! fpsdisplaysink video-sink="{}"'
            " text-overlay=false sync={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._codec,
            self._sink,
            self._fpsdisplaysink_sync,
        )


create_decoder_performance_project = CixDecoderPerformanceProject


class CixEncoderPsnrProject(GenericEncoderProject):
    """
    The mvx encoders default their sink caps to bt601, so videoconvert
    re-matrixes the BT.709 HD golden sample before encoding and PSNR drops
    to ~24 dB on every codec. Pinning bt709 keeps the input YUV untouched,
    so PSNR measures only the encoder.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        # Assumes HD golden samples (bt709); SD inputs need bt601.
        self._color_space = "{},colorimetry=bt709".format(
            self._color_space or "NV12"
        )

    def _generic_pipeline_builder(self) -> str:
        # The base builder emits " ! <codec>" right after the caps filter.
        pipeline = super()._generic_pipeline_builder()
        return pipeline.replace(
            " ! {} ".format(self._codec),
            " ! {} ".format(encoder_element(self._codec)),
            1,
        )


create_encoder_psnr_project = CixEncoderPsnrProject
