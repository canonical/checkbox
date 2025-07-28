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
import shutil
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
    CameraInterface,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)


def _generate_artifact_pattern(
    args: argparse.Namespace, scenario_name: CameraScenarios
) -> str:
    """
    Generate artifact pattern based on scenario and arguments.

    Args:
        args: Command line arguments
        scenario_name: Camera scenario name

    Returns:
        str: Generated pattern string
    """
    base_pattern = "{}_{}_{}_{}_{}".format(
        args.camera,
        args.physical_interface,
        args.method,
        args.width,
        args.height,
    )

    if scenario_name == CameraScenarios.CAPTURE_IMAGE:
        return base_pattern + "_{}".format(args.format)
    elif scenario_name == CameraScenarios.RECORD_VIDEO:
        return base_pattern + "@{}fps_{}".format(args.framerate, args.format)
    else:
        raise ValueError("Unsupported scenario: {}".format(scenario_name))


def _create_artifact_store_path(
    args: argparse.Namespace, scenario_name: CameraScenarios
) -> str:
    """
    Create and prepare artifact store path.

    Args:
        args: Command line arguments
        scenario_name: Camera scenario name

    Returns:
        str: Path to artifact store directory
    """
    pattern = _generate_artifact_pattern(args, scenario_name)
    artifact_store_path = os.path.join(
        PLAINBOX_SESSION_SHARE,
        scenario_name.value,
        pattern,
    )
    generate_artificat_folder(artifact_store_path)
    return artifact_store_path


def _execute_capture_image_scenario(
    args: argparse.Namespace,
    handler_instance: CameraInterface,
    artifact_store_path: str,
    artifact_name: str,
) -> None:
    """
    Execute capture image scenario.

    Args:
        args: Command line arguments
        handler_instance: Camera handler instance
        artifact_store_path: Path to store artifacts
        artifact_name: Base name for artifacts
    """
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
            v4l2_device_name=args.v4l2_device_name,
        )


def _execute_record_video_scenario(
    args: argparse.Namespace,
    handler_instance: CameraInterface,
    artifact_store_path: str,
    artifact_name: str,
) -> None:
    """
    Execute record video scenario.

    Args:
        args: Command line arguments
        handler_instance: Camera handler instance
        artifact_store_path: Path to store artifacts
        artifact_name: Base name for artifacts
    """
    handler_instance.record_video(
        width=args.width,
        height=args.height,
        framerate=args.framerate,
        format=args.format,
        count=300,  # 300 frames
        store_path=artifact_store_path,
        artifact_name=artifact_name,
        method=args.method,
        v4l2_device_name=args.v4l2_device_name,
    )


def _execute_scenario(
    args: argparse.Namespace,
    handler_instance: CameraInterface,
    scenario_name: CameraScenarios,
    artifact_name: str,
) -> str:
    """
    Execute a camera scenario with proper setup and cleanup.

    Args:
        args: Command line arguments
        handler_instance: Camera handler instance
        scenario_name: Camera scenario to execute
        artifact_name: Base name for artifacts

    Returns:
        str: Path to artifact store directory
    """
    # Create artifact store path
    artifact_store_path = _create_artifact_store_path(args, scenario_name)

    # Execute the appropriate scenario
    if scenario_name == CameraScenarios.CAPTURE_IMAGE:
        _execute_capture_image_scenario(
            args,
            handler_instance,
            artifact_store_path,
            artifact_name,
        )
    elif scenario_name == CameraScenarios.RECORD_VIDEO:
        _execute_record_video_scenario(
            args,
            handler_instance,
            artifact_store_path,
            artifact_name,
        )
    else:
        raise ValueError("Unsupported scenario: {}".format(scenario_name))

    return artifact_store_path


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
        default=None,
        help=(
            "Optional: Path to camera setup configuration (JSON file). "
            "Only required for cameras that need media-ctl configuration. "
            "For cameras that work without setup, this can be omitted."
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
        "--v4l2_device_name",
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
        type=int,
        help=("width of camera"),
    )

    parser_testing.add_argument(
        "-hi",
        "--height",
        type=int,
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
        type=int,
        help=("fps of camera"),
    )

    args = parser.parse_args()
    return args


def _setup_camera_config(args: argparse.Namespace, v4l2_devices: str) -> None:
    """
    Setup camera configuration if setup config file is provided.

    This function handles two cases:
    1. Camera setup config is provided: Load and apply the configuration
    2. No camera setup config: Skip setup (for cameras that don't need it)

    Args:
        args: Command line arguments
        v4l2_devices: V4L2 devices information

    Raises:
        SystemExit:
            If camera setup configuration is invalid or cannot be loaded
    """
    # Check if camera setup config is provided when it might be needed
    if args.camera_setup_conf_path is None:
        logger.info(
            "No camera setup configuration provided - this is normal for "
            "cameras that don't require media-ctl configuration."
        )
        return

    # Validate that the path is not just whitespace
    config_path = args.camera_setup_conf_path.strip()
    if not config_path:
        logger.info(
            "Empty camera setup configuration path - skipping camera setup"
        )
        return

    logger.info("Setting up camera configuration from: {}".format(config_path))

    if not os.path.exists(config_path):
        raise SystemExit(
            "Camera setup config file not found: {}".format(config_path)
        )

    try:
        with open(config_path, "r") as file:
            setup_conf = json.load(file)
            logger.debug("==== Camera Setup Conf ====\n{}".format(setup_conf))
    except json.JSONDecodeError as e:
        error_msg = "Invalid JSON in camera setup config: {}".format(e)
        logger.error(error_msg)
        raise SystemExit(error_msg)
    except Exception as e:
        error_msg = "Failed to load camera setup config: {}".format(e)
        logger.error(error_msg)
        raise SystemExit(error_msg)

    try:
        MediaController(
            setup_conf=setup_conf, v4l2_devices=v4l2_devices
        ).do_setup(width=args.width, height=args.height)
        logger.info("Camera setup configuration applied successfully")
    except Exception as e:
        error_msg = "Failed to setup camera configuration: {}".format(e)
        logger.error(error_msg)
        raise SystemExit(error_msg)


def _cleanup_artifacts_if_needed(
    args: argparse.Namespace, artifact_store_path: str
) -> None:
    """
    Clean up artifacts if needed (currently only for RECORD_VIDEO scenario).

    Args:
        args: Command line arguments
        artifact_store_path: Path to artifact store directory
    """
    if args.scenario_name == CameraScenarios.RECORD_VIDEO:
        logger.info(
            "The storage is not enough to store all videos, so we need to "
            "delete the artifacts for 'record video' after testing"
        )
        shutil.rmtree(artifact_store_path)


def _run_camera_test(args: argparse.Namespace) -> None:
    """
    Run the camera test with the given arguments.

    Args:
        args: Command line arguments
    """
    # Get the devices via v4l2 command
    v4l2_devices = list_device_by_v4l2_ctl()
    logger.debug("==== V4L2 Devices ====\n{}".format(v4l2_devices))

    # Create camera handler instance
    handler_class = camera_factory(args.platform, args.camera)
    handler_instance = handler_class(v4l2_devices)

    # Setup camera configuration if needed
    _setup_camera_config(args, v4l2_devices)

    # Generate unique artifact name using UUID to ensure no conflicts
    artifact_name = str(uuid.uuid4()).replace("-", "")[:6]

    # Execute the scenario
    artifact_store_path = _execute_scenario(
        args, handler_instance, args.scenario_name, artifact_name
    )

    # Verify artifacts
    logger.debug(
        "Checking all files' size in directory: '{}'".format(
            artifact_store_path
        )
    )
    check_nonzero_files(artifact_store_path)

    # Cleanup artifacts if needed
    _cleanup_artifacts_if_needed(args, artifact_store_path)


def main() -> None:
    args = register_arguments()

    if args.action == "generate_resource":
        CameraResources(scenario_file_path=args.scenario_file).main()
        return

    if args.action == "testing":
        _run_camera_test(args)


if __name__ == "__main__":
    main()
