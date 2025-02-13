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
import json
import logging
import os
import re
import shlex
import shutil
import subprocess


from abc import ABC, abstractmethod
from enum import Enum
from itertools import product

PLAINBOX_SESSION_SHARE = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")
GST_LAUNCH_BIN = shutil.which(os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0"))
MEDIA_CTL_CMD = shutil.which("media-ctl")
V4L2_CTL_CMD = shutil.which("v4l2-ctl")
GST_DISCOVERER = shutil.which("gst-discoverer-1.0")

logger = logging.getLogger(__name__)


class SupportedMethods(Enum):
    # v4l2-ctl can be used to generate the raw and yuv files.
    # It's more like the unit test to make sure the whole data line of
    # streaming captured from camera to received by SoC is working.
    V4L2_CTL = "v4l2-ctl"
    # gstreamer can be used to generate the mp4, jpeg and other common files.
    # It's more like the real user scenario.
    GSTREANER = "gstreamer"

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
        v4l2_device_name: str,
    ) -> str:
        """
        Execute the Capture image scenario.

        Return {str}:
            The path of captured image
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
    ) -> str:
        """
        Execute the Video record scenario.

        Return {str}:
            The path of recored video
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
    except Exception as e:
        logger.error(e)
        raise SystemExit(1)


def generate_artificat_folder(artifact_full_path: str) -> None:
    try:
        os.makedirs(artifact_full_path)
    except FileExistsError:
        # Ignore the exception if artifact_store_path is existed
        pass


def camera_factory(platform: str, camera_module: str) -> object:
    """ """
    if "genio" in platform:
        from camera_genio import genio_camera_factory

        return genio_camera_factory(camera_module=camera_module)
    else:
        SystemExit("Cannot find the '{}' platform".format(platform))


def list_device_by_v4l2_ctl() -> str:
    outcome = execute_command(cmd="{} --list-devices".format(V4L2_CTL_CMD))
    return outcome


def get_video_node(v4l2_devices: str, v4l2_device_name: str) -> str:
    if not v4l2_device_name:
        raise SystemExit("Invalid value to get proper video device node")
    # Regex pattern to match the name and capture the device path
    pattern = r"{}:\n\t(/dev/\S+)".format(re.escape(v4l2_device_name))
    match = re.search(pattern, v4l2_devices)

    if match:
        logger.debug("video device node: {}".format(match.group(1)))
        return match.group(1)
    else:
        logger.error("==== V4L2 Devices ====\n{}".format(v4l2_devices))
        logger.error(
            "Fail to get the video device node based on '{}'".format(
                v4l2_device_name
            )
        )
        raise SystemExit(1)


class MediaController:
    def __init__(self, setup_conf: dict = {}, v4l2_devices: str = ""):
        self._setup_conf = setup_conf
        self._v4l2_devices = v4l2_devices
        self._dev_media_node = ""
        logger.debug("Setup Configuration:\n{}".format(self._setup_conf))

    def _get_the_media_dev_node(self):
        """
        Get the full path of specific media node under /dev path

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
        candidate_node = self._setup_conf["media_node_v4l2_name"]
        # Regex pattern to match the name and capture the device path
        pattern = r"{}:\n\t(/dev/\S+)".format(re.escape(candidate_node))
        match = re.search(pattern, self._v4l2_devices)

        if match:
            self._dev_media_node = match.group(1)
            logger.debug(self._dev_media_node)
        else:
            logger.error(
                "==== V4L2 Devices ====\n{}".format(self._v4l2_devices)
            )
            logger.error(
                "Fail to get the media device node based on '{}'".format(
                    candidate_node
                )
            )
            raise SystemExit(1)

    def _set_pad_format_and_resolution(
        self, pads: list, width: int, height: int
    ) -> None:
        logger.debug("Configuring pads...{}:{}".format(width, height))
        base_cmd = "{} -d {} -V".format(MEDIA_CTL_CMD, self._dev_media_node)
        for p in pads:
            if p["action"] == "set_format":
                cmd = "{} \"'{}':{} [fmt:{}/{}x{}]\"".format(
                    base_cmd, p["node"], p["source"], p["fmt"], width, height
                )
                logger.debug(cmd)
                execute_command(cmd=cmd)

    def _create_links(self, links: list) -> None:
        logger.debug("Configuring links...")

    def do_setup(self, width: int, height: int):
        # Assign the dev media node
        self._get_the_media_dev_node()
        for c in self._setup_conf["cameras"]:
            logger.info(
                "Configuring the camera at physical interface '{}'...".format(
                    c["physical_interface"]
                )
            )
            # Create Link
            self._create_links(c["links"])
            # Setup fmt and resolution
            self._set_pad_format_and_resolution(c["pads"], width, height)

    def dump_the_full_topology(self, media_node: str = "") -> str:
        logger.debug("Dump the topology of '{}'".format(media_node))
        output = execute_command(
            cmd="{} -d {} -p".format(MEDIA_CTL_CMD, media_node)
        )
        return output


class CameraScenarios(Enum):
    """
    An enumeration of camera's scenarios.

    Feel free to define new scenario here
    """

    # CPTURE_IMAGE scenario demonstrate the capture case
    CPTURE_IMAGE = "capture_image"
    # RECORD_VIDEO scenario demonstrate the record case
    RECORD_VIDEO = "record_video"

    def __str__(self):
        return self.value


class CameraResources:
    """
    Generate the camera resource for Checkbox based on scenario file

    Args:
        scenario_file_path: JSON file path of scenario file
    """

    def __init__(self, scenario_file_path) -> None:
        """
        Args:
            scenario_file_path: JSON file path of scenario file
        """
        try:
            with open(scenario_file_path, "r") as file:
                self._scenarios = json.load(file)
        except Exception as e:
            raise SystemExit("{}".format(e))
        self._resource_items = []
        self._current_scenario_name = ""

    def main(self) -> None:
        try:
            for scenario in self._scenarios:
                self._current_scenario_name = scenario
                getattr(self, scenario)(self._scenarios[scenario])
                self._dump_resources()
        except AttributeError as e:
            # Only dump the exception message to prevent any pollution while
            # generating resrouce job
            logger.debug(e)

    def _dump_resources(self) -> None:
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

    def capture_image(self, scenarios: list) -> None:
        """
        Handle and generate the resource of the capture_image scenario
        """
        for item in scenarios:
            for r, f in product(item["resolutions"], item["formats"]):
                self._resource_items.append(
                    {
                        "scenario": self._current_scenario_name,
                        "camera": item["camera"],
                        "method": item["method"],
                        "physical_interface": item["physical_interface"],
                        "v4l2_deivce_name": item["v4l2_deivce_name"],
                        "format": f,
                        "width": r["width"],
                        "height": r["height"],
                    }
                )

    def record_video(self, scenarios: list) -> None:
        """
        Handle and generate the resource of the record_video scenario
        """
        for item in scenarios:
            for r, f in product(item["resolutions"], item["formats"]):
                self._resource_items.append(
                    {
                        "scenario": self._current_scenario_name,
                        "camera": item["camera"],
                        "method": item["method"],
                        "physical_interface": item["physical_interface"],
                        "v4l2_deivce_name": item["v4l2_deivce_name"],
                        "format": f,
                        "width": r["width"],
                        "height": r["height"],
                        "fps": r["fps"],
                    }
                )


def check_nonzero_files(directory: str):
    if not os.path.isdir(directory):
        logger.error("The directory '{}' does not exist.".format(directory))
        raise SystemExit(1)

    all_nonzero = True
    for root, _, files in os.walk(directory):
        if not files:
            logger.error("Empty directory '{}'".format(directory))
            raise SystemExit(1)

        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getsize(file_path) == 0:
                logger.error("Empty file found: {}".format(file_path))
                all_nonzero = False

    if all_nonzero:
        logger.info("Pass: All files have a size greater than zero.")
    else:
        logger.error("Some files have zero size.")
        raise SystemExit(1)
