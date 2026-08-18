#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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

import argparse
import os
import json
import logging
from itertools import product
from checkbox_support.scripts.image_checker import has_desktop_environment
from checkbox_support.snap_utils.system import on_ubuntucore
from codec_platforms import PLATFORM_FAMILIES, get_platform_family

logging.basicConfig(level=logging.INFO)


def compose_encoder_psnr_name(conf_name: str, config: dict) -> str:
    """
    Compose the job name for a gst_encoder_psnr record from the family's
    PLATFORM_FAMILIES entry, reproducing each platform's historical job-id
    shape exactly, so the single generic template renders byte-identical
    ids.
    """
    base = "{}-{}-{}x{}@{}fps".format(
        config["scenario"],
        config["encoder_plugin"],
        config["width"],
        config["height"],
        config["framerate"],
    )
    family = get_platform_family(conf_name)
    if family:
        spec = PLATFORM_FAMILIES[family]
        parts = [spec.id_prefix] if spec.id_prefix else []
        parts.append(base)
        parts.extend(
            str(config[field]) for field in spec.encoder_id_suffix_fields
        )
        return "-".join(parts)
    # unknown platform: no prefix, append the optional fields only when set
    parts = [base]
    parts.extend(
        str(config[field]) for field in ("color_space", "mux") if config[field]
    )
    return "-".join(parts)


def compose_decoder_performance_name(
    conf_name: str, decoder_plugin: str, sample_name: str, scenario: str
) -> str:
    """
    Compose the job name for a decoder-performance record from the
    family's PLATFORM_FAMILIES entry.
    """
    base = "{}-{}".format(scenario, decoder_plugin)
    family = get_platform_family(conf_name)
    # historical performance ids carry no family prefix; only families
    # whose ids need the sample name for uniqueness get the full shape
    if not family or not PLATFORM_FAMILIES[family].perf_id_includes_sample:
        return base
    spec = PLATFORM_FAMILIES[family]
    parts = [spec.id_prefix] if spec.id_prefix else []
    parts.extend([base, sample_name])
    return "-".join(parts)


def register_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("This script generates the resource for all scenarios"),
    )

    parser.add_argument(
        "video_codec_conf_file",
        type=str,
        help=(
            "Path of the specified test configuration file. "
            "When only the file name is provided, such as genio-1200, it will"
            " default to searching for the genio-1200.json file within the "
            "video-codec-test-confs folder under the environment variable "
            "PLAINBOX_PROVIDER_DATA path. When a complete path is specified, "
            "the file will be opened according to the specified path."
        ),
    )

    parser.add_argument(
        "-gtdp",
        "--video_codec_testing_data_path",
        type=str,
        help="Path of the testing data.",
    )

    args = parser.parse_args()
    return args


class GstResources:

    # Find the video sample to test hardward codec
    # repo. https://github.com/canonical/CodecCrafter

    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        try:
            conf_path = self._args.video_codec_conf_file
            # If the path is not full path, find and use the config under
            # default path. All gstreamer related configs should be put into
            # video-codec-test-confs direcotry by design
            if not os.path.exists(conf_path):
                conf_path = os.path.join(
                    os.environ["PLAINBOX_PROVIDER_DATA"],
                    "video-codec-test-confs",
                    "{}.json".format(self._args.video_codec_conf_file),
                )
            with open(conf_path, "r") as file:
                self._scenarios = json.load(file)
            self._conf_name = os.path.split(conf_path)[1].replace(".json", "")
        except Exception as e:
            raise SystemExit("{}".format(e))
        self._current_scenario_name = ""
        self._resource_items = []
        self._has_desktop_environment = has_desktop_environment()

    def _video_decoder_md5_checksum_comparison_helper(
        self,
        decoder_plugin: str,
        width: str,
        height: str,
        color_space: str,
        source_format: str,
    ) -> dict:
        """
        Generate a resource item dictionary for
        gst_video_decoder_md5_checksum_comparison scenario
        """
        name = "{}x{}-{}-{}".format(width, height, decoder_plugin, color_space)
        name_with_format = "{}.{}".format(name, source_format)
        golden_sample_file = os.path.join(
            self._args.video_codec_testing_data_path,
            name_with_format,
        )
        md5_name = "{}.md5".format(name)
        golden_md5_checkum_file = os.path.join(
            self._args.video_codec_testing_data_path,
            self._current_scenario_name,
            "golden_md5_checksum",
            self._conf_name,
            md5_name,
        )

        returned_dict = {
            "scenario": self._current_scenario_name,
            "name": "{}-{}-{}x{}-{}".format(
                self._current_scenario_name,
                decoder_plugin,
                width,
                height,
                color_space,
            ),
            "decoder_plugin": decoder_plugin,
            "width": width,
            "height": height,
            "color_space": color_space,
            "golden_sample_file": golden_sample_file,
            "golden_md5_checkum_file": golden_md5_checkum_file,
        }

        return returned_dict

    def gst_video_decoder_md5_checksum_comparison(
        self, scenario_data: "list[dict]"
    ) -> None:
        for item in scenario_data:
            self._resource_items.extend(
                [
                    self._video_decoder_md5_checksum_comparison_helper(
                        decoder_plugin=item["decoder_plugin"],
                        width=resolution["width"],
                        height=resolution["height"],
                        color_space=color_space,
                        source_format=item["source_format"],
                    )
                    for resolution in item["resolutions"]
                    for color_space in item["color_spaces"]
                ]
            )

    def gst_encoder_psnr(self, scenario_data: "list[dict]") -> None:
        # Iterate through each encoder plugin configuration
        for item in scenario_data:
            encoder_plugin = item.get("encoder_plugin")
            if not encoder_plugin:
                continue
            mux_list = item.get("mux", [""])
            color_spaces = item.get("color_spaces", [""])
            resolutions = item.get("resolutions", [{}])

            # Use itertools.product to create combinations of all parameters
            for resolution, color_space, mux in product(
                resolutions, color_spaces, mux_list
            ):
                config = {
                    "platform": self._conf_name,
                    "scenario": self._current_scenario_name,
                    "encoder_plugin": encoder_plugin,
                    "width": resolution.get("width"),
                    "height": resolution.get("height"),
                    "framerate": resolution.get("fps"),
                    "color_space": color_space,
                    "mux": mux,
                }
                config["name"] = compose_encoder_psnr_name(
                    self._conf_name, config
                )
                self._resource_items.append(config)

    def gst_v4l2_audio_video_synchronization(
        self, scenario_data: dict
    ) -> None:
        video_sink = ""
        if on_ubuntucore():
            video_sink = scenario_data["video_sinks"]["on_core"]
        elif self._has_desktop_environment:
            video_sink = scenario_data["video_sinks"]["on_desktop"]
        else:
            video_sink = scenario_data["video_sinks"]["on_server"]

        for item in scenario_data["cases"]:
            for sample_file in item["golden_sample_files"]:
                self._resource_items.append(
                    {
                        "scenario": self._current_scenario_name,
                        "name": "{}-{}-{}-{}".format(
                            self._current_scenario_name,
                            item["decoder_plugin"],
                            sample_file["file_name"],
                            video_sink,
                        ),
                        "video_sink": video_sink,
                        "decoder_plugin": item["decoder_plugin"],
                        "golden_sample_file_name": sample_file["file_name"],
                        "golden_sample_file": os.path.join(
                            self._args.video_codec_testing_data_path,
                            sample_file["file_name"],
                        ),
                        "capssetter_pipeline": sample_file[
                            "capssetter_pipeline"
                        ],
                    }
                )

    def gst_video_decoder_performance_fakesink(
        self, scenario_data: "list[dict]"
    ) -> None:
        for item in scenario_data:
            sample_name = os.path.splitext(
                os.path.basename(item["golden_sample_file"])
            )[0]
            self._resource_items.append(
                {
                    "scenario": self._current_scenario_name,
                    "name": compose_decoder_performance_name(
                        self._conf_name,
                        item["decoder_plugin"],
                        sample_name,
                        self._current_scenario_name,
                    ),
                    "platform": self._conf_name,
                    "decoder_plugin": item["decoder_plugin"],
                    "golden_sample_file_name": sample_name,
                    "minimum_fps": item["minimum_fps"],
                    "golden_sample_file": os.path.join(
                        self._args.video_codec_testing_data_path,
                        item["golden_sample_file"],
                    ),
                    # performance_target is "" means won't enable performance
                    # mode.
                    "performance_target": (
                        self._args.video_codec_conf_file
                        if item["enable_performance_mode"]
                        else ""
                    ),
                }
            )

    def gst_transform_rotate_and_flip(
        self, scenario_data: "list[dict]"
    ) -> None:
        # Iterate through each encoder plugin configuration
        for item in scenario_data:
            encoder_plugin = item.get("encoder_plugin")
            if not encoder_plugin:
                continue
            actions = item.get("actions", [""])
            resolutions = item.get("resolutions", [{}])

            # Use itertools.product to create combinations of all parameters
            for resolution, action in product(resolutions, actions):
                config = {
                    "platform": self._conf_name,
                    "scenario": self._current_scenario_name,
                    "encoder_plugin": encoder_plugin,
                    "width": resolution.get("width"),
                    "height": resolution.get("height"),
                    "framerate": resolution.get("fps"),
                    "action": action,
                }
                config["name"] = "{}-{}_{}_{}x{}_{}fps".format(
                    config["scenario"],
                    config["encoder_plugin"],
                    config["action"],
                    config["width"],
                    config["height"],
                    config["framerate"],
                )
                self._resource_items.append(config)

    def gst_transform_resize(self, scenario_data: "list[dict]") -> None:
        # Iterate through each encoder plugin configuration
        for item in scenario_data:
            encoder_plugin = item.get("encoder_plugin")
            if not encoder_plugin:
                continue
            resolutions = item.get("resolutions", [{}])

            # Use itertools.product to create combinations of all parameters
            for resolution in resolutions:
                config = {
                    "platform": self._conf_name,
                    "scenario": self._current_scenario_name,
                    "encoder_plugin": encoder_plugin,
                    "width_from": resolution.get("width_from"),
                    "height_from": resolution.get("height_from"),
                    "width_to": resolution.get("width_to"),
                    "height_to": resolution.get("height_to"),
                    "framerate": resolution.get("fps"),
                }
                config["name"] = "{}-{}_from_{}x{}_{}fps_to_{}x{}".format(
                    config["scenario"],
                    config["encoder_plugin"],
                    config["width_from"],
                    config["height_from"],
                    config["framerate"],
                    config["width_to"],
                    config["height_to"],
                )
                self._resource_items.append(config)

    def main(self):
        for scenario in self._scenarios:
            self._current_scenario_name = scenario
            getattr(self, scenario)(self._scenarios[scenario])
            self._dump_resources()

    def _dump_resources(self):
        """
        Prints each key-value pair from the self._resource_items in the format
        "key": "value".
        """
        for item in self._resource_items:
            for key, value in item.items():
                print("{}: {}".format(key, value))
            print()
        print()
        # Renew for next scenario
        self._resource_items = []


def main() -> None:
    args = register_arguments()
    GstResources(args).main()


if __name__ == "__main__":
    main()
