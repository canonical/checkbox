#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
import logging
import os
import shutil

from enum import Enum
from typing import Optional, Type
from camera_utils import (
    CameraInterface,
    execute_command,
    SupportedMethods,
    CameraError,
    CameraConfigurationError,
    log_and_raise_error,
)

logger = logging.getLogger(__name__)

# Resolved from PATH: /snap/bin/... (the multimedia snap alias set
# up before testing on Ubuntu Core) or /usr/bin / /usr/sbin on classic images
RPICAM_VID_BIN = shutil.which("rpicam-vid")
RPICAM_STILL_BIN = shutil.which("rpicam-still")


class SupportedCamera(Enum):
    """
    Supported camera modules on Jetson platforms.

    Each enum value corresponds to a concrete camera implementation class.
    The string value matches the camera module identifier used in the system.
    """

    IMX219 = "imx219"  # Sony IMX219 sensor

    def __str__(self):
        return self.value


def rpi_camera_factory(camera_module: str) -> Type[CameraInterface]:
    """
    Factory function to create camera handler instances.

    Args:
        camera_module: String identifier of the camera module

    Returns:
        Camera handler class that implements CameraInterface

    Raises:
        CameraError: If camera_module is not supported
    """
    # Map camera module strings to their handler classes
    camera_handlers = {
        str(cam): handler
        for cam, handler in {
            SupportedCamera.IMX219: Imx219Handler,
        }.items()
    }

    handler_class = camera_handlers.get(camera_module)
    if not handler_class:
        raise CameraError(
            "Unsupported camera module: {}. "
            "Supported modules are: {}".format(
                camera_module, list(camera_handlers.keys())
            )
        )
    return handler_class


class RPIBaseCamera(CameraInterface):
    """
    Base class for Raspberry Pi camera implementations.
    """

    def _get_sensor_id_for_rpicam(self, v4l2_device_name: str) -> int:
        """
        Get the libcamera camera index for the given camera.

        On Raspberry Pi CM5, the scenario JSON declares camera_id as a string
        ("0" / "1"), which is the libcamera enumeration index passed to
        'rpicam-still --camera N' and 'rpicam-vid --camera N'. The resource
        generator carries this value in the framework's default identifier
        field, v4l2_device_name.

        The CM5 IO board exposes two CSI connectors (CAM0 and
        CAM1). libcamera enumerates detected cameras in connector order,
        so a sensor on CAM0 is typically index 0 and a sensor on
        CAM1 is typically index 1.

        Ref: https://www.raspberrypi.com/documentation/accessories/camera.html#step-2-connect-the-cable-to-your-raspberry-pi  # noqa: E501
        """
        try:
            return int(v4l2_device_name)
        except (TypeError, ValueError):
            log_and_raise_error(
                "Invalid camera identifier '{}': the scenario's camera_id "
                "must be the libcamera enumeration index (e.g. '0'), not "
                "a device path.".format(v4l2_device_name),
                CameraConfigurationError,
            )

    def _get_artifact_path(
        self, store_path: str, artifact_name: str, extension: str
    ) -> str:
        """Get the appropriate file extension based on the provided
        extension."""
        suffix = (
            ".jpg"
            if extension == "JPEG"
            else ".h264" if extension == "H264" else ".mp4"
        )
        return os.path.join(store_path, artifact_name + suffix)

    def _rpicam_format_mapping(self, format: str) -> str:
        """Map the format string to the corresponding rpicam format.

        Ref: https://www.raspberrypi.com/documentation/computers/camera_software.html#list-cameras  # noqa: E501
        """
        if format == "SRGGB10_CSI2P":
            return "10"
        elif format == "SRGGB8":
            return "8"
        else:
            log_and_raise_error(
                "Unsupported format '{}' for rpicam".format(format),
                CameraConfigurationError,
            )

    def _build_rpicam_still_cmd(
        self,
        sensor_id: int,
        width: int,
        height: int,
        format: str,
        full_artifact_path: str,
        framerate: Optional[int] = None,
    ) -> str:
        """
        Build the rpicam-still command.
        """
        if not RPICAM_STILL_BIN:
            log_and_raise_error(
                "Could not find the 'rpicam-still' executable",
                CameraConfigurationError,
            )

        words = [RPICAM_STILL_BIN, "--camera {}".format(sensor_id)]
        format = self._rpicam_format_mapping(format)
        words.append("--mode {}:{}:{}".format(width, height, format))
        if framerate is not None:
            words.append("--framerate {}".format(framerate))
        words.append("-o {}".format(full_artifact_path))

        return " ".join(words)

    def _build_rpicam_vid_cmd(
        self,
        sensor_id: int,
        width: int,
        height: int,
        format: str,
        full_artifact_path: str,
        framerate: Optional[int] = None,
    ) -> str:
        """
        Build the rpicam-vid command.
        Record the video in 5-second segments by default.
        """
        if not RPICAM_VID_BIN:
            log_and_raise_error(
                "Could not find the 'rpicam-vid' executable",
                CameraConfigurationError,
            )

        words = [RPICAM_VID_BIN, "--camera {}".format(sensor_id)]
        format = self._rpicam_format_mapping(format)
        words.append("--mode {}:{}:{}".format(width, height, format))
        if framerate is not None:
            words.append("--framerate {}".format(framerate))
        words.append("-o {}".format(full_artifact_path))

        return " ".join(words)

    def capture_image(
        self,
        width: int,
        height: int,
        format: str,
        store_path: str,
        artifact_name: str,
        method: str,
        v4l2_device_name: str,
        framerate: Optional[int] = None,
    ) -> None:
        """Capture an image using the specified method."""
        full_artifact_path = self._get_artifact_path(
            store_path, artifact_name, "JPEG"
        )
        logging.info("Capture image as {}".format(full_artifact_path))

        sensor_id = self._get_sensor_id_for_rpicam(v4l2_device_name)

        logger.info(
            "Capture image from {} sensor-id {} with {}".format(
                self._camera, sensor_id, method
            )
        )

        if method == SupportedMethods.RPICAM_STILL:
            # framerate pins modes whose maximum rate is below the Argus
            # 30 fps negotiation default (e.g. IMX219 modes 0 and 1)
            cmd = self._build_rpicam_still_cmd(
                sensor_id,
                width,
                height,
                format,
                full_artifact_path,
                framerate=framerate,
            )
            logger.info("Running command: '{}'".format(cmd))
            execute_command(cmd=cmd)
        else:
            msg = "No suitable method such as '{}' be provided".format(
                SupportedMethods.RPICAM_STILL
            )
            log_and_raise_error(msg, CameraConfigurationError)

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
        mode: Optional[int] = None,
    ) -> None:
        """Record a video using the specified method."""
        # The rpicam-vid tool records video in H264 format by default.
        full_artifact_path = self._get_artifact_path(
            store_path, artifact_name, "H264"
        )
        logging.info("Record a video as {}".format(full_artifact_path))

        sensor_id = self._get_sensor_id_for_rpicam(v4l2_device_name)

        logger.info(
            "Record video from {} sensor-id {} with {}".format(
                self._camera, sensor_id, method
            )
        )

        if method == SupportedMethods.RPICAM_VID:
            # the default duration for the rpicam-vid tool is 5 seconds,
            # so we can ignore the count parameter
            cmd = self._build_rpicam_vid_cmd(
                sensor_id,
                width,
                height,
                format,
                full_artifact_path,
                framerate=framerate,
            )
            logger.info("Running command: '{}'".format(cmd))
            execute_command(cmd=cmd)
        else:
            msg = "No suitable method such as '{}' be provided".format(
                SupportedMethods.RPICAM_VID
            )
            log_and_raise_error(msg, CameraConfigurationError)


class Imx219Handler(RPIBaseCamera):
    """Handler for the Sony IMX219 camera."""

    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.IMX219
