#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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
import json
import logging
import os
import uuid

from camera_utils import (
    PLAINBOX_SESSION_SHARE,
    MediaController,
    CameraScenarios,
    CameraResources,
    SupportedMethods,
    generate_artificat_folder,
    camera_factory,
    list_device_by_v4l2_ctl,
    check_nonzero_files,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)


def register_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "This script as the enrty point for testing Vendor Specific"
            " Camera cases"
        ),
    )

    # Create subparsers
    subparsers = parser.add_subparsers(title="Action", dest="action")

    # Subparser for generating resource
    parser_resource = subparsers.add_parser(
        "generate_resource",
        help=(
            "Generate the resource by consumming a specific "
            "Checkbox Configuration."
        ),
    )

    parser_resource.add_argument(
        "-sf",
        "--scenario_file",
        type=str,
        required=True,
        help=("Path of the specified test configuration file."),
    )

    # Subparser for testing
    parser_testing = subparsers.add_parser(
        "testing",
        help=("Test camera according to the scenario"),
    )

    parser_testing.add_argument(
        "-sn",
        "--scenario_name",
        required=True,
        type=CameraScenarios,
        choices=list(CameraScenarios),
        help=("Name of the specific scenario"),
    )

    parser_testing.add_argument(
        "-cscf",
        "--camera_setup_conf_path",
        type=str,
        help=(
            "The path of camera setup configuration (JSON file). For some "
            "sitautions, user has to set the link, format and resolution by "
            "using 'media-ctl' command before using camera"
        ),
    )

    parser_testing.add_argument(
        "-p",
        "--platform",
        type=str,
        required=True,
        help=("Name of platform. e.g. genio-1200"),
    )

    parser_testing.add_argument(
        "-c",
        "--camera",
        type=str,
        required=True,
        help=("Name of camera"),
    )

    parser_testing.add_argument(
        "-pi",
        "--physical_interface",
        type=str,
        help=("physical_interface of camera"),
    )

    parser_testing.add_argument(
        "-vdn",
        "--v4l2_deivce_name",
        type=str,
        help=("Name of v4l2 deivce"),
    )

    parser_testing.add_argument(
        "-m",
        "--method",
        type=SupportedMethods,
        choices=list(SupportedMethods),
        required=True,
        help=("Method to be performed."),
    )

    parser_testing.add_argument(
        "-wi",
        "--width",
        type=str,
        help=("width of camera"),
    )

    parser_testing.add_argument(
        "-hi",
        "--height",
        type=str,
        help=("height of camera"),
    )

    parser_testing.add_argument(
        "-f",
        "--format",
        type=str,
        help=("format of camera"),
    )

    parser_testing.add_argument(
        "-fps",
        "--framerate",
        type=str,
        help=("fps of camera"),
    )

    args = parser.parse_args()
    return args


def main() -> None:
    args = register_arguments()
    if args.action == "generate_resource":
        CameraResources(scenario_file_path=args.scenario_file).main()
        return

    if args.action == "testing":
        # Get the devices via v4l2 command
        v4l2_devices = list_device_by_v4l2_ctl()
        logger.debug("==== V4L2 Devices ====\n{}".format(v4l2_devices))

        handler_instance = camera_factory(args.platform, args.camera)(
            v4l2_devices
        )

        # Configure before testing
        if args.camera_setup_conf_path:
            try:
                with open(args.camera_setup_conf_path, "r") as file:
                    setup_conf = json.load(file)
                    logger.debug(
                        "==== Camera Setup Conf ====\n{}".format(setup_conf)
                    )
            except Exception as e:
                logger.error(e)
                raise SystemExit("{}".format(e))

            MediaController(
                setup_conf=setup_conf, v4l2_devices=v4l2_devices
            ).do_setup(width=args.width, height=args.height)

        # Handle the path and name of artifacts
        artifact_store_path = ""
        artifact_name = str(uuid.uuid4()).replace("-", "")[:6]

        if args.scenario_name == CameraScenarios.CPTURE_IMAGE:
            pattern = "{}_{}_{}_{}_{}_{}".format(
                args.camera,
                args.physical_interface,
                args.method,
                args.width,
                args.height,
                args.format,
            )
            artifact_store_path = os.path.join(
                PLAINBOX_SESSION_SHARE,
                CameraScenarios.CPTURE_IMAGE.value,
                pattern,
            )
            generate_artificat_folder(artifact_store_path)

            iteration = 5  # Capture multiple images
            for i in range(1, iteration + 1):
                logger.info("\n\n===== Iteration {} =====\n".format(i))
                handler_instance.capture_image(
                    width=args.width,
                    height=args.height,
                    format=args.format,
                    method=args.method,
                    store_path=artifact_store_path,
                    artifact_name=artifact_name + "_{}".format(i),
                    v4l2_device_name=args.v4l2_deivce_name,
                )
            # For loop to capture multiple images
        elif args.scenario_name == CameraScenarios.RECORD_VIDEO:
            pattern = "{}_{}_{}_{}_{}@{}fps_{}".format(
                args.camera,
                args.physical_interface,
                args.method,
                args.width,
                args.height,
                args.framerate,
                args.format,
            )
            artifact_store_path = os.path.join(
                PLAINBOX_SESSION_SHARE,
                CameraScenarios.RECORD_VIDEO.value,
                pattern,
            )
            generate_artificat_folder(artifact_store_path)

            handler_instance.record_video(
                width=args.width,
                height=args.height,
                framerate=args.framerate,
                format=args.format,
                count=300,  # 300 frames
                store_path=artifact_store_path,
                artifact_name=artifact_name,
                method=args.method,
                v4l2_device_name=args.v4l2_deivce_name,
            )

        logger.debug(
            "Checking all files' size in directory: '{}'".format(
                artifact_store_path
            )
        )
        check_nonzero_files(artifact_store_path)


if __name__ == "__main__":
    main()
