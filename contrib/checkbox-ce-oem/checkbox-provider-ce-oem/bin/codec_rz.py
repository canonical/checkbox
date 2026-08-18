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
        The decoder to use for the video, e.g., "omxh264dec".
    :param sink:
        The desired sink option, e.g., "fakesink".
    :param fpsdisplaysink_sync:
        The property option of fpsdisplaysink."
        Ref: https://gstreamer.freedesktop.org/documentation/debugutilsbad/
        fpsdisplaysink.html?gi-language=python#fpsdisplaysink:sync
    :param platform:
        The platform (conf file name).

    :returns:
        The GStreamer command to execute.
    """
    # Renesas RZ series support h264 and h265 as hardware decoder
    # And some platform support both decoder.
    # We make a simple logic to choose the decoder and build the pipeline,
    # If the decoder is omxh265dec, we use h265parse, else we use h264parse.
    codec_parser_map = {
        GStreamerDecodePlugins.OMXH264DEC.value: "h264parse",
        GStreamerDecodePlugins.OMXH265DEC.value: "h265parse",
    }
    logging.info("Building pipeline for platform: %s", platform)

    encode_parser = codec_parser_map.get(decoder)
    part_pipeline = "qtdemux ! {} ! {} use-dmabuf=true".format(
        encode_parser, decoder
    )

    cmd = (
        "{} -v filesrc location={} ! {} ! queue !"
        " vspmfilter dmabuf-use=true !"
        " queue ! fpsdisplaysink video-sink='{}' text-overlay=false sync={}"
    ).format(
        gst_bin, golden_sample_path, part_pipeline, sink, fpsdisplaysink_sync
    )

    return cmd


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
