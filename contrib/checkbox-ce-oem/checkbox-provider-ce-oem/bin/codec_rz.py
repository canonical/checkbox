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
"""Renesas RZ platform pipelines for the video-codec scenarios."""

import argparse
import logging

from codec_base import BaseCodecProject
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    GStreamerDecodePlugins,
    get_test_file_path_by_params,
)


def create_encoder_psnr_project(args: argparse.Namespace):
    """Create the encoder-PSNR pipeline project for Renesas RZ."""
    return RenesasProject(
        platform=args.platform,
        codec=args.encoder_plugin,
        color_space=args.color_space,
        width=args.width,
        height=args.height,
        framerate=args.framerate,
    )


def create_decoder_performance_project(args: argparse.Namespace):
    """Create the decoder-performance pipeline project for Renesas RZ."""
    return RenesasDecoderPerformanceProject(args)


class RenesasDecoderPerformanceProject(BaseCodecProject):
    """Renesas RZ decoder-performance pipeline handler and builder."""

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
        # Renesas RZ series support h264 and h265 as hardware decoder
        # And some platform support both decoder.
        self._codec_parser_map = {
            GStreamerDecodePlugins.OMXH264DEC.value: "h264parse",
            GStreamerDecodePlugins.OMXH265DEC.value: "h265parse",
        }
        self._pipeline_builders = {
            decoder: self._performance_pipeline_builder
            for decoder in self._codec_parser_map
        }

    def _performance_pipeline_builder(self) -> str:
        logging.info("Building pipeline for platform: %s", self._platform)
        encode_parser = self._codec_parser_map.get(self._codec)
        part_pipeline = "qtdemux ! {} ! {} use-dmabuf=true".format(
            encode_parser, self._codec
        )
        return (
            "{} -v filesrc location={} ! {} ! queue !"
            " vspmfilter dmabuf-use=true !"
            " queue ! fpsdisplaysink video-sink='{}' text-overlay=false"
            " sync={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            part_pipeline,
            self._sink,
            self._fpsdisplaysink_sync,
        )


class RenesasProject(BaseCodecProject):
    """Renesas project pipeline handler and builder"""

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
        self._codec_parser_map = {
            GStreamerEncodePlugins.OMXH264ENC.value: "h264parse",
            GStreamerEncodePlugins.OMXH265ENC.value: "h265parse",
        }
        self._pipeline_builders = {
            GStreamerEncodePlugins.OMXH264ENC.value: (
                self._264_265_pipeline_builder
            ),
            GStreamerEncodePlugins.OMXH265ENC.value: (
                self._264_265_pipeline_builder
            ),
        }

    def _264_265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for omxh264enc
        """
        encode_parser = self._codec_parser_map.get(self._codec)
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, "h264"
        )
        if "h264" in self._codec:
            decoder = GStreamerDecodePlugins.OMXH264DEC.value
        elif "h265" in self._codec:
            decoder = GStreamerDecodePlugins.OMXH265DEC.value
        pipeline = (
            "{} filesrc location={} ! qtdemux ! {} !"
            " {} use-dmabuf=false !"
            " video/x-raw,format={} ! {} use-dmabuf=true"
            " target-bitrate=10485760 !"
            " {} ! mp4mux ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            encode_parser,
            decoder,
            self._color_space,
            self._codec,
            encode_parser,
            self.artifact_file,
        )

        return pipeline
