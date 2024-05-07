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

logging.basicConfig(level=logging.INFO)


def register_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Script helps verify the MD5 checksum from specific Gstreamer"
            " Decoder with different resolutions and color spaces is exactly"
            " match golden reference"
        ),
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
        golden_sample_file = "{}/video_golden_samples/{}.{}".format(
            self._args.video_codec_testing_data_path, name, source_format
        )
        golden_md5_checkum_file = "{}/{}/golden_md5_checksum/{}/{}.md5".format(
            self._args.video_codec_testing_data_path,
            self._current_scenario_name,
            self._conf_name,
            name,
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
