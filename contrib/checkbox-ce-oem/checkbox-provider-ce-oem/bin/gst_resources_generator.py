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
from typing import Dict, List
from checkbox_support.scripts.image_checker import has_desktop_environment
from checkbox_support.snap_utils.system import on_ubuntucore

logging.basicConfig(level=logging.INFO)


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

    # video_golden_samples is the name of folder in hardware_codec_testing_data
    # repo. https://github.com/canonical/hardware_codec_testing_data
    VIDEO_GOLDEN_SAMPLES = "video_golden_samples"

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

    def _v4l2_video_decoder_md5_checksum_comparison_helper(
        self,
        decoder_plugin: str,
        width: str,
        height: str,
        color_space: str,
        source_format: str,
    ) -> Dict:
        """
        Generate a resource item dictionary for
        gst_v4l2_video_decoder_md5_checksum_comparison scenario
        """
        name = "{}x{}-{}-{}".format(width, height, decoder_plugin, color_space)
        name_with_format = "{}.{}".format(name, source_format)
        golden_sample_file = os.path.join(
            self._args.video_codec_testing_data_path,
            self.VIDEO_GOLDEN_SAMPLES,
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
            "decoder_plugin": decoder_plugin,
            "width": width,
            "height": height,
            "color_space": color_space,
            "golden_sample_file": golden_sample_file,
            "golden_md5_checkum_file": golden_md5_checkum_file,
        }

        return returned_dict

    def gst_v4l2_video_decoder_md5_checksum_comparison(
        self, scenario_data: List[Dict]
    ) -> None:
        for item in scenario_data:
            self._resource_items.extend(
                [
                    self._v4l2_video_decoder_md5_checksum_comparison_helper(
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

    def gst_v4l2_audio_video_synchronization(
        self, scenario_data: Dict
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
                        "video_sink": video_sink,
                        "decoder_plugin": item["decoder_plugin"],
                        "golden_sample_file_name": sample_file["file_name"],
                        "golden_sample_file": os.path.join(
                            self._args.video_codec_testing_data_path,
                            self.VIDEO_GOLDEN_SAMPLES,
                            sample_file["file_name"],
                        ),
                        "capssetter_pipeline": sample_file[
                            "capssetter_pipeline"
                        ],
                    }
                )

    def gst_v4l2_video_decoder_performance_fakesink(
        self, scenario_data: List[Dict]
    ) -> None:
        for item in scenario_data:
            self._resource_items.append(
                {
                    "scenario": self._current_scenario_name,
                    "decoder_plugin": item["decoder_plugin"],
                    "minimum_fps": item["minimum_fps"],
                    "golden_sample_file": os.path.join(
                        self._args.video_codec_testing_data_path,
                        self.VIDEO_GOLDEN_SAMPLES,
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
