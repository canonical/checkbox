#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from typing import Dict, List, Optional, Type


from abc import ABC, abstractmethod
from enum import Enum
from itertools import product

PLAINBOX_SESSION_SHARE = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")
GST_LAUNCH_BIN = shutil.which(os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0"))
MEDIA_CTL_CMD = shutil.which(os.getenv("MEDIA_CTL_CMD", "media-ctl"))
V4L2_CTL_CMD = shutil.which(os.getenv("V4L2_CTL_CMD", "v4l2-ctl"))
GST_DISCOVERER = shutil.which(
    os.getenv("GST_DISCOVERER", "gst-discoverer-1.0")
)

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Base exception for camera-related errors."""

    pass


class CameraConfigurationError(CameraError):
    """Raised when camera configuration is invalid."""

    pass


class CameraOperationError(CameraError):
    """Raised when camera operations fail."""

    pass


class CameraTimeoutError(CameraError):
    """Raised when camera operations timeout."""

    pass


class CameraSetupError(CameraError):
    """Raised when camera setup fails."""

    pass


def log_and_raise_error(msg: str, exception_class=CameraError):
    logger.error(msg)
    raise exception_class(msg)


class SupportedMethods(Enum):
    # v4l2-ctl can be used to generate the raw and yuv files.
    # It's more like the unit test to make sure the whole data line of
    # streaming captured from camera to received by SoC is working.
    V4L2_CTL = "v4l2-ctl"
    # gstreamer can be used to generate the mp4, jpeg and other common files.
    # It's more like the real user scenario.
    GSTREAMER = "gstreamer"

    def __str__(self):
        return self.value


class CameraInterface(ABC):
    """
    CameraInterface defines the generic and mandatory scenarios, we think
    every camera has the following abilities and need to conduct them.

    If you need to conduct the extra scenario, please implement it in your own
    plaftform/camera class.
    """

    def __init__(self, v4l2_devices: str):
        self._v4l2_devices = v4l2_devices  # /dev/videoX

    @abstractmethod
    def capture_image(
        self,
        width: int,
        height: int,
        format: str,
        store_path: str,
        artifact_name: str,
        method: str,
        v4l2_device_name: str,
    ) -> None:
        """
        Execute the Capture image scenario.
        """
        pass

    @abstractmethod
    def record_video(
        self,
        width: int,
        height: int,
        framerate: int,
        format: str,
        count: int,
        store_path: str,
        artifact_name: str,
        method: str,
        v4l2_device_name: str,
    ) -> None:
        """
        Execute the Video record scenario.
        """
        pass


def execute_command(cmd: str = "", timeout: int = 300) -> str:
    """
    Executes a command and extracts the specific data from the
    output.

    :param cmd:
        A command to be executed.

    :returns:
        The extracted last_message.
    """
    try:
        ret = subprocess.run(
            shlex.split(cmd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
        return ret.stdout
    except subprocess.TimeoutExpired as e:
        log_and_raise_error(
            "Command timed out: {}".format(e),
            CameraTimeoutError,
        )
    except Exception as e:
        log_and_raise_error(
            "Failed to execute command: {}".format(e),
            CameraOperationError,
        )


def generate_artificat_folder(artifact_full_path: str) -> None:
    os.makedirs(artifact_full_path, exist_ok=True)


def camera_factory(platform: str, camera_module: str) -> Type[CameraInterface]:
    """ """
    if "genio" in platform:
        from camera_genio import genio_camera_factory

        return genio_camera_factory(camera_module=camera_module)
    else:
        log_and_raise_error(
            "Cannot find the '{}' platform".format(platform),
            CameraError,
        )


def list_device_by_v4l2_ctl() -> str:
    outcome = execute_command(cmd="{} --list-devices".format(V4L2_CTL_CMD))
    return outcome


def get_video_node(v4l2_devices: str, v4l2_device_name: str) -> str:
    if not v4l2_device_name:
        log_and_raise_error(
            "Invalid value to get proper video device node",
            CameraConfigurationError,
        )

    # Regex pattern to match the name and capture the device path
    pattern = r"{}:\n\t(/dev/\S+)".format(re.escape(v4l2_device_name))
    match = re.search(pattern, v4l2_devices)

    if match:
        logger.info("video device node: {}".format(match.group(1)))
        return match.group(1)
    else:
        logger.error("==== V4L2 Devices ====\n{}".format(v4l2_devices))
        log_and_raise_error(
            "Fail to get the video device node based on '{}'".format(
                v4l2_device_name
            ),
            CameraConfigurationError,
        )


class VideoMediaNodeResolver:
    """
    General-purpose resolver for V4L2 video and media device nodes.

    This class parses V4L2 device lists and provides easy access to grouped
    device nodes. It can be used across different camera implementations.
    """

    def __init__(self, v4l2_devices: str):
        """
        Initialize the resolver with V4L2 devices information.

        Args:
            v4l2_devices: String containing V4L2 device information from
                         v4l2-ctl --list-devices
        """
        self._v4l2_devices = v4l2_devices
        self._device_groups = self._parse_device_groups(v4l2_devices)

    def _parse_device_groups(
        self, v4l2_devices: str
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Parse V4L2 device list into grouped structure.

        Args:
            v4l2_devices: Raw V4L2 device list string from
            `v4l2-ctl --list-devices`

        Returns:
            Dictionary mapping device group names to their categorized device
            nodes
            Format:
            {
                "v4l2_device_name": {
                    "video": [
                        "/dev/videoX",
                        "/dev/videoY",
                        "/dev/videoZ",
                    ],
                    "media": ["/dev/mediaX"],
                    "others": []
                }
            }
        """
        device_groups = {}
        current_group = None
        lines = v4l2_devices.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a group header (ends with ':')
            if line.endswith(":"):
                current_group = line[:-1]  # Remove the trailing ':'
                device_groups[current_group] = {
                    "video": [],
                    "media": [],
                    "others": [],
                }
            elif current_group and line.startswith("/dev/"):
                # Categorize device nodes
                if line.startswith("/dev/video"):
                    device_groups[current_group]["video"].append(line)
                elif line.startswith("/dev/media"):
                    device_groups[current_group]["media"].append(line)
                else:
                    device_groups[current_group]["others"].append(line)

        return device_groups

    def get_all_groups(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Get all device groups.

        Returns:
            Complete dictionary of all device groups
        """
        return self._device_groups.copy()

    def find_group_by_name(self, group_name: str) -> Dict[str, List[str]]:
        """
        Find a specific device group by name.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            Device group dictionary or None if not found
        """
        for name, devices in self._device_groups.items():
            if group_name in name:
                return devices.copy()
        return {}

    def get_video_nodes(self, group_name: str) -> List[str]:
        """
        Get video nodes for a specific device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            List of video device nodes
        """
        group = self.find_group_by_name(group_name)
        return group["video"] if group else []

    def get_media_nodes(self, group_name: str) -> List[str]:
        """
        Get media nodes for a specific device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            List of media device nodes
        """
        group = self.find_group_by_name(group_name)
        return group["media"] if group else []

    def get_other_nodes(self, group_name: str) -> List[str]:
        """
        Get other device nodes for a specific device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            List of other device nodes
        """
        group = self.find_group_by_name(group_name)
        return group["others"] if group else []

    def get_first_video_node(self, group_name: str) -> Optional[str]:
        """
        Get the first video node for a specific device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            First video device node or None if not found
        """
        video_nodes = self.get_video_nodes(group_name)
        return video_nodes[0] if video_nodes else None

    def get_first_media_node(self, group_name: str) -> Optional[str]:
        """
        Get the first media node for a specific device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            First media device node or None if not found
        """
        media_nodes = self.get_media_nodes(group_name)
        return media_nodes[0] if media_nodes else None

    def get_video_node_by_index(
        self, group_name: str, index: int
    ) -> Optional[str]:
        """
        Get a specific video node by index for a device group.

        Args:
            group_name: Name or partial name of the device group
            index: Index of the video node (0-based)

        Returns:
            Video device node at the specified index or None if not found
        """
        video_nodes = self.get_video_nodes(group_name)
        return video_nodes[index] if 0 <= index < len(video_nodes) else ""

    def count_video_nodes(self, group_name: str) -> int:
        """
        Count the number of video nodes for a device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            Number of video nodes
        """
        return len(self.get_video_nodes(group_name))

    def count_media_nodes(self, group_name: str) -> int:
        """
        Count the number of media nodes for a device group.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            Number of media nodes
        """
        return len(self.get_media_nodes(group_name))

    def has_group(self, group_name: str) -> bool:
        """
        Check if a device group exists.

        Args:
            group_name: Name or partial name of the device group

        Returns:
            True if the group exists, False otherwise
        """
        return self.find_group_by_name(group_name) is not None

    def list_all_group_names(self) -> List[str]:
        """
        Get a list of all device group names.

        Returns:
            List of all device group names
        """
        return list(self._device_groups.keys())

    def get_group_summary(self) -> Dict[str, Dict[str, int]]:
        """
        Get a summary of all device groups with node counts.

        Returns:
            Dictionary mapping group names to their node counts
            Format:
            {
                "v4l2_device_name": {
                    "video": 3,  # number of video nodes
                    "media": 1,  # number of media nodes
                    "others": 0  # number of other nodes
                }
            }
        """
        summary = {}
        for group_name, devices in self._device_groups.items():
            summary[group_name] = {
                "video": len(devices["video"]),
                "media": len(devices["media"]),
                "others": len(devices["others"]),
            }
        return summary


class MediaController:
    def __init__(self, setup_conf: dict = {}, v4l2_devices: str = ""):
        self._setup_conf = setup_conf
        self._v4l2_devices = v4l2_devices
        self._dev_media_node = ""
        self._resolver = (
            VideoMediaNodeResolver(v4l2_devices) if v4l2_devices else None
        )
        logger.info("Setup Configuration:\n{}".format(self._setup_conf))

    def _get_the_media_dev_node(self):
        """
        Get the full path of specific media node under /dev path using
        VideoMediaNodeResolver.

        e.g.
            The following output is from "v4l2-ctl --list-devices" command
            ========================================
            mtk-mdp (platform:14004000.mdp_rdma0):
                /dev/media1

            mtk-camsys-3.0 (platform:15040000.seninf):
                /dev/media0
            ========================================

            Get and assign the "/dev/media0" value according to the given value
            of "media_node_v4l2_name" field in setup_conf.
        """
        if not self._resolver:
            self._log_and_raise_error(
                "VideoMediaNodeResolver not initialized - no V4L2 devices "
                "provided"
            )

        candidate_node = self._setup_conf["media_node_v4l2_name"]

        # Use VideoMediaNodeResolver to find the media node
        media_node = self._resolver.get_first_media_node(candidate_node)

        if media_node:
            self._dev_media_node = media_node
            logger.info(
                "Found media device node: {}".format(self._dev_media_node)
            )
        else:
            # Log available groups for debugging
            available_groups = self._resolver.list_all_group_names()
            self._log_and_raise_error(
                "Fail to get the media device node based on '{}', "
                "available groups: {}".format(
                    candidate_node,
                    available_groups,
                ),
                CameraConfigurationError,
            )

    def _set_pad_format_and_resolution(
        self, pads: list, width: int, height: int
    ) -> None:
        logger.info("Configuring pads...{}:{}".format(width, height))
        base_cmd = "{} -d {} -V".format(MEDIA_CTL_CMD, self._dev_media_node)
        for p in pads:
            action = p["action"]
            if action == "set_format":
                # Build the format string with optional field parameter
                fmt_part = "fmt:{}/{}x{}".format(p["fmt"], width, height)
                if "field" in p:
                    fmt_part += " field:{}".format(p["field"])

                cmd = "{} \"'{}':{} [{}]\"".format(
                    base_cmd,
                    p["node"],
                    p["source"],
                    fmt_part,
                )
                logger.info(cmd)
                execute_command(cmd=cmd)
            else:
                log_and_raise_error(
                    "Unsupported action: {}".format(action),
                    CameraConfigurationError,
                )

    def _create_links(self, links: list) -> None:
        logger.info("Configuring links...")
        base_cmd = "{} -d {} -l".format(MEDIA_CTL_CMD, self._dev_media_node)
        for link in links:
            cmd = "{} \"'{}':{} -> '{}':{} [{}]\"".format(
                base_cmd,
                link["source_entity"],
                link["source_pad_number"],
                link["sink_entity"],
                link["sink_pad_number"],
                link["flags"],
            )
            logger.info(cmd)
            execute_command(cmd=cmd)

    def _validate_setup_config(self) -> None:
        """
        Validate the setup configuration.

        Raises:
            CameraConfigurationError: If configuration is invalid
        """
        if not self._setup_conf:
            log_and_raise_error(
                "Setup configuration is empty", CameraConfigurationError
            )

        required_fields = ["media_node_v4l2_name", "cameras"]
        missing_fields = [
            field for field in required_fields if field not in self._setup_conf
        ]
        if missing_fields:
            log_and_raise_error(
                "Missing required fields in setup configuration: {}".format(
                    missing_fields
                ),
                CameraConfigurationError,
            )

    def _validate_camera_config(self, camera: dict) -> None:
        """
        Validate individual camera configuration.

        Args:
            camera: Camera configuration dictionary

        Raises:
            CameraConfigurationError: If camera configuration is invalid
        """
        required_fields = ["physical_interface", "pads"]
        missing_fields = [
            field for field in required_fields if field not in camera
        ]
        if missing_fields:
            log_and_raise_error(
                "Missing required fields in camera config: {}".format(
                    missing_fields
                ),
                CameraConfigurationError,
            )

    def do_setup(self, width: int, height: int):
        """
        Perform camera setup with validation.

        Args:
            width: Image width
            height: Image height
        """
        # Validate setup configuration
        self._validate_setup_config()

        # Assign the dev media node
        self._get_the_media_dev_node()

        for c in self._setup_conf["cameras"]:
            try:
                self._validate_camera_config(c)

                logger.info(
                    "Configuring the camera physical "
                    "interface '{}'...".format(c["physical_interface"])
                )

                # Create Link
                links = c.get("links", [])
                if links:
                    self._create_links(links)
                else:
                    logger.info("No links to configure")

                # Setup fmt and resolution
                pads = c["pads"]
                if pads:
                    self._set_pad_format_and_resolution(pads, width, height)
                else:
                    log_and_raise_error(
                        "No pads to configure",
                        CameraConfigurationError,
                    )
            except Exception as e:
                logger.error(
                    "Error configuring camera {}: {}".format(
                        c.get("physical_interface", "unknown"), e
                    )
                )
                raise

    def dump_the_full_topology(self, media_node: str = "") -> str:
        logger.info("Dump the topology of '{}'".format(media_node))
        return execute_command(
            cmd="{} -d {} -p".format(MEDIA_CTL_CMD, media_node)
        )


class CameraScenarios(Enum):
    """
    An enumeration of camera's scenarios.

    Feel free to define new scenario here
    """

    # CAPTURE_IMAGE scenario demonstrate the capture case
    CAPTURE_IMAGE = "capture_image"
    # RECORD_VIDEO scenario demonstrate the record case
    RECORD_VIDEO = "record_video"

    def __str__(self):
        return self.value

    @classmethod
    def get_description(cls, scenario_type: str) -> str:
        """
        Get description for a scenario type.

        Args:
            scenario_type: The scenario type string

        Returns:
            Description of the scenario type
        """
        descriptions = {
            "capture_image": "Image capture scenarios",
            "record_video": "Video recording scenarios",
        }
        return descriptions.get(scenario_type, "Unknown scenario type")

    @classmethod
    def get_all_types(cls) -> list:
        """
        Get all supported scenario types.

        Returns:
            List of all supported scenario type strings
        """
        return [scenario.value for scenario in cls]

    @classmethod
    def is_supported(cls, scenario_type: str) -> bool:
        """
        Check if a scenario type is supported.

        Args:
            scenario_type: The scenario type string to check

        Returns:
            True if supported, False otherwise
        """
        return scenario_type in cls.get_all_types()


class CameraResources:
    """
    Generate camera resources for Checkbox based on scenario files.

    Args:
        scenario_file_path: JSON file path of scenario file
    """

    PLAINBOX_PROVIDER_DATA = os.getenv("PLAINBOX_PROVIDER_DATA", "")

    def __init__(self, scenario_file_path: str = None) -> None:
        """
        Initialize CameraResources with scenario file.

        Args:
            scenario_file_path: JSON file path of scenario file
        """
        self._scenarios = self._load_scenarios(scenario_file_path)
        self._resource_items = []
        self._current_scenario_name = ""

    def _load_scenarios(self, scenario_file_path: str) -> dict:
        """
        Load scenarios from file with proper error handling.

        Args:
            scenario_file_path: Path to the scenario file

        Returns:
            Dictionary containing scenarios or empty dict if loading fails
        """
        # First try to find the scenario file relative to
        # PLAINBOX_PROVIDER_DATA
        # then fall back to the scenario_file_path (absolute path)
        if not scenario_file_path:
            logger.debug("No scenario file path provided")
            return {}

        # Try to load from PLAINBOX_PROVIDER_DATA first if it's set
        if self.PLAINBOX_PROVIDER_DATA:
            provider_scenario_path = os.path.join(
                self.PLAINBOX_PROVIDER_DATA, scenario_file_path
            )
            if os.path.exists(provider_scenario_path):
                logger.debug(
                    "Loading scenario from provider data dir: {}".format(
                        provider_scenario_path
                    )
                )
                return self._load_scenario_file(provider_scenario_path)

        # Fall back to the original scenario_file_path
        if not os.path.exists(scenario_file_path):
            logger.warning(
                "Scenario file does not exist: {}".format(scenario_file_path)
            )
            return {}

        return self._load_scenario_file(scenario_file_path)

    def _load_scenario_file(self, file_path: str) -> dict:
        """
        Load and parse a scenario file.

        Args:
            file_path: Path to the scenario file

        Returns:
            Dictionary containing scenarios or empty dict if loading fails
        """
        try:
            with open(file_path, "r") as file:
                scenarios = json.load(file)
                logger.debug(
                    "Successfully loaded {} scenarios from {}".format(
                        len(scenarios), file_path
                    )
                )
                return scenarios
        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON in scenario file '{}': {} "
                "(line {}, column {})".format(
                    file_path, e.msg, e.lineno, e.colno
                )
            )
            return {}
        except FileNotFoundError:
            logger.error("Scenario file not found: '{}'".format(file_path))
            return {}
        except PermissionError:
            logger.error(
                "Permission denied accessing scenario file: '{}'".format(
                    file_path
                )
            )
            return {}
        except Exception as e:
            logger.error(
                "Failed to load scenario file {}: {}".format(file_path, e)
            )
            return {}

    def main(self) -> bool:
        """
        Process all scenarios and generate resources.

        Returns:
            bool: True if all scenarios processed successfully, False otherwise
        """
        if not self._scenarios:
            return False

        for scenario_name, scenario_data in self._scenarios.items():
            try:
                self._current_scenario_name = scenario_name
                self._process_scenario(scenario_name, scenario_data)
                self._dump_resources()
            except Exception as e:
                logger.error(
                    "Error processing scenario '{}': {}".format(
                        scenario_name, e
                    )
                )
                return False

        return True

    def _process_scenario(
        self, scenario_name: str, scenario_data: list
    ) -> None:
        """
        Process a single scenario by calling the appropriate handler method.

        Args:
            scenario_name: Name of the scenario to process
            scenario_data: List of scenario configuration items

        Raises:
            AttributeError: If no handler method found for scenario
            ValueError: If scenario data is not a list
        """
        # Validate scenario type
        if not CameraScenarios.is_supported(scenario_name):
            raise AttributeError(
                "Unsupported scenario type '{}'. "
                "Supported types: {}".format(
                    scenario_name, CameraScenarios.get_all_types()
                )
            )

        handler_method = getattr(self, scenario_name, None)
        if handler_method is None:
            raise AttributeError(
                "No handler method found for scenario '{}'".format(
                    scenario_name
                )
            )

        if not isinstance(scenario_data, list):
            raise ValueError(
                "Scenario data for '{}' must be a list, got {}".format(
                    scenario_name, type(scenario_data).__name__
                )
            )

        handler_method(scenario_data)

    def _validate_scenario_item(
        self, item: dict, required_fields: list
    ) -> None:
        """
        Validate that a scenario item contains all required fields.
        """
        missing_fields = [
            field for field in required_fields if field not in item
        ]
        if missing_fields:
            log_and_raise_error(
                "Missing required fields in scenario item: {}".format(
                    missing_fields
                ),
                CameraConfigurationError,
            )

    def _validate_resolution_formats(
        self, item: dict, scenario_type: str
    ) -> None:
        """
        Validate resolution and format configurations for a scenario item.

        Args:
            item: Scenario item configuration
            scenario_type: Type of scenario being validated

        Raises:
            CameraConfigurationError: If validation fails
        """
        camera_name = item["camera"]

        # Validate resolutions list
        if not item["resolutions"]:
            log_and_raise_error(
                "Empty resolutions list for camera '{}'".format(camera_name),
                CameraConfigurationError,
            )

        # Validate formats list
        if not item["formats"]:
            log_and_raise_error(
                "Empty formats list for camera '{}'".format(camera_name),
                CameraConfigurationError,
            )

        # Validate each resolution
        for i, res in enumerate(item["resolutions"]):
            self._validate_single_resolution(
                res, i, camera_name, scenario_type
            )

        # Validate each format
        for i, fmt in enumerate(item["formats"]):
            self._validate_single_format(fmt, i, camera_name)

    def _validate_single_resolution(
        self,
        resolution: dict,
        index: int,
        camera_name: str,
        scenario_type: str,
    ) -> None:
        """
        Validate a single resolution configuration.

        Args:
            resolution: Resolution configuration dict
            index: Index of the resolution
            camera_name: Name of the camera
            scenario_type: Type of scenario

        Raises:
            CameraConfigurationError: If validation fails
        """
        # Check if resolution is a dict
        if not isinstance(resolution, dict):
            log_and_raise_error(
                "Resolution {} for camera '{}' must be a dict".format(
                    index, camera_name
                ),
                CameraConfigurationError,
            )

        # Check required fields
        required_fields = ["width", "height"]
        missing_fields = [
            field for field in required_fields if field not in resolution
        ]
        if missing_fields:
            log_and_raise_error(
                "Resolution {} for camera '{}' missing fields: {}".format(
                    index, camera_name, missing_fields
                ),
                CameraConfigurationError,
            )

        # Validate width and height
        self._validate_dimension(
            resolution["width"], "width", index, camera_name
        )
        self._validate_dimension(
            resolution["height"], "height", index, camera_name
        )

        # Validate fps for video scenarios
        if scenario_type == "record_video":
            if "fps" not in resolution:
                log_and_raise_error(
                    "Missing fps for video resolution "
                    "{} of camera '{}'".format(index, camera_name),
                    CameraConfigurationError,
                )
            self._validate_dimension(
                resolution["fps"], "fps", index, camera_name
            )

    def _validate_single_format(
        self, format_str: str, index: int, camera_name: str
    ) -> None:
        """
        Validate a single format string.

        Args:
            format_str: Format string to validate
            index: Index of the format
            camera_name: Name of the camera

        Raises:
            CameraConfigurationError: If validation fails
        """
        if not isinstance(format_str, str) or not format_str.strip():
            log_and_raise_error(
                "Invalid format '{}' at index {} for camera '{}'".format(
                    format_str, index, camera_name
                ),
                CameraConfigurationError,
            )

    def _validate_dimension(
        self, value: int, field_name: str, index: int, camera_name: str
    ) -> None:
        """
        Validate a dimension value (width, height, fps).

        Args:
            value: Value to validate
            field_name: Name of the field being validated
            index: Index of the resolution
            camera_name: Name of the camera

        Raises:
            CameraConfigurationError: If validation fails
        """
        if not isinstance(value, int) or value <= 0:
            log_and_raise_error(
                "Invalid {} '{}' for camera '{}' resolution {}".format(
                    field_name, value, camera_name, index
                ),
                CameraConfigurationError,
            )

    def _process_scenario_items(
        self, scenarios: list, scenario_type: str
    ) -> None:
        """
        Process scenario items and generate resources.

        Args:
            scenarios: List of scenario items to process
            scenario_type: Type of scenario
            (e.g., 'capture_image', 'record_video')
        """
        required_fields = [
            "camera",
            "method",
            "physical_interface",
            "v4l2_device_name",
            "resolutions",
            "formats",
        ]

        for item in scenarios:
            try:
                self._validate_scenario_item(item, required_fields)
                self._validate_resolution_formats(item, scenario_type)

                # Generate resources for each resolution/format combination
                for resolution, format_str in product(
                    item["resolutions"], item["formats"]
                ):
                    resource_item = {
                        "scenario": self._current_scenario_name,
                        "camera": item["camera"],
                        "method": item["method"],
                        "physical_interface": item["physical_interface"],
                        "v4l2_device_name": item["v4l2_device_name"],
                        "format": format_str,
                        "width": resolution["width"],
                        "height": resolution["height"],
                    }

                    # Add fps for video scenarios
                    if scenario_type == "record_video":
                        resource_item["fps"] = resolution["fps"]

                    self._resource_items.append(resource_item)

            except Exception as e:
                logger.error(
                    "Error processing {} item: {}".format(scenario_type, e)
                )
                continue

    def capture_image(self, scenarios: list) -> None:
        """
        Handle and generate the resource of the capture_image scenario
        """
        self._process_scenario_items(
            scenarios, CameraScenarios.CAPTURE_IMAGE.value
        )

    def record_video(self, scenarios: list) -> None:
        """
        Handle and generate the resource of the record_video scenario
        """
        self._process_scenario_items(
            scenarios, CameraScenarios.RECORD_VIDEO.value
        )

    def _dump_resources(self) -> None:
        """
        Prints each key-value pair from the self._resource_items in the format
        "key": "value".
        """
        if not self._resource_items:
            logger.debug("No resource items to dump")
            return

        logger.debug(
            "Dumping {} resource items for scenario '{}'".format(
                len(self._resource_items), self._current_scenario_name
            )
        )

        for item in self._resource_items:
            for key, value in item.items():
                print("{}: {}".format(key, value))
            print()
        print()

        # Clear for next scenario
        self._resource_items = []


def check_nonzero_files(directory: str) -> None:
    """
    Check if all files in a directory and its subdirectories are non-empty.

    Args:
        directory: Path to the directory to check

    Raises:
        CameraError: If directory doesn't exist or contains empty files
        CameraConfigurationError: If directory is empty
    """
    if not os.path.isdir(directory):
        msg = "The directory '{}' does not exist.".format(directory)
        logger.error(msg)
        raise CameraError(msg)

    empty_files = []
    has_files = False

    for root, _, files in os.walk(directory):
        if files:
            has_files = True
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getsize(file_path) == 0:
                    empty_files.append(file_path)
                    logger.error("Empty file found: {}".format(file_path))

    if not has_files:
        msg = "Empty directory '{}'".format(directory)
        log_and_raise_error(msg, CameraError)

    if empty_files:
        msg = "Found {} empty files".format(len(empty_files))
        log_and_raise_error(msg, CameraError)

    logger.info("Pass: All files have a size greater than zero.")
