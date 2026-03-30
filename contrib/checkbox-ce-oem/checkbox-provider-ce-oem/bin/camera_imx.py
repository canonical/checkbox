#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Stanley Huang <stanley.huang@canonical.com>
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

from enum import Enum
from typing import Union, Dict, List, Optional, Type
from camera_utils import (
    CameraInterface,
    execute_command,
    SupportedMethods,
    GST_LAUNCH_BIN,
    V4L2_CTL_CMD,
    CameraError,
    CameraConfigurationError,
    VideoMediaNodeResolver,
    log_and_raise_error,
)

logger = logging.getLogger(__name__)


class SoftwareArchitectures(Enum):
    """
    Software architectures supported on the Genio series EVK.

    There are two architectures:

    IMX8M_Imgsensor:
        Drives the SoC-internal ISP to process Bayer RAW sensor data.
        Requires sensor-level controls for advanced features.
        Used with sensors that output RAW data needing ISP processing.
    """

    Imx8m_Imgsensor = "IMX8M_Imgsensor"

    def __str__(self):
        return self.value


class SupportedCamera(Enum):
    """
    Supported camera modules on Genio platforms.

    Each enum value corresponds to a concrete camera implementation class.
    The string value matches the camera module identifier used in the system.
    """

    IMX_OS0820 = "imx_os08a20"  # IMX OS08A20 sensor
    OV_5640 = "ov5640"  # OV5640 sensor
    GENERAL = "general"  # General camera module placeholder for testing only

    def __str__(self):
        return self.value


def imx_camera_factory(
    platform: str, camera_module: str
) -> Type[CameraInterface]:
    """
    Factory function to create camera handler instances.

    Args:
        camera_module: String identifier of the camera module

    Returns:
        Camera handler class that implements CameraInterface

    Raises:
        ValueError: If camera_module is not supported
    """
    # return Imx8mBaseCamera for all supported cameras for now
    # unless specific implementations are needed later
    try:
        camera = SupportedCamera(camera_module)
    except ValueError:
        raise CameraError(
            "Unsupported camera module: {}. "
            "Supported modules are: {}".format(
                camera_module, list(SupportedCamera)
            )
        )

    if "imx8m" in platform:
        handler = Imx8mBaseCamera
    else:
        raise CameraError(
            "Unsupported platform: {}. Supported platform is: imx8m".format(
                platform
            )
        )
    setattr(handler, "_camera", camera)
    return handler


class ImxVideoNodeResolver(VideoMediaNodeResolver):
    """
    Genio-specific video node resolver that extends the general
    VideoMediaNodeResolver.

    This class provides Genio-specific logic for resolving video device nodes
    based on camera type and architecture while leveraging the general parsing
    functionality from VideoMediaNodeResolver.
    """

    def get_camera_video_nodes(
        self,
        camera: Union[str, SupportedCamera],
        v4l2_device_name: str,
    ) -> Dict[str, str]:
        """
        Get video device nodes classified by camera type.

        Args:
            camera: Camera type (string or SupportedCamera enum)
            v4l2_device_name: Name of the V4L2 device
            arch: Software architecture

        Returns:
            Dictionary mapping node types to device paths

        Raises:
            CameraError: For unsupported camera types or architectures
            CameraOperationError: For operational errors
        """
        return self._resolve_common_camera(v4l2_device_name, camera.value)

    def _resolve_common_camera(
        self,
        v4l2_device_name: str,
        camera_value: str,
    ) -> Dict[str, str]:
        """Resolve video nodes for common cameras."""
        # Common camera: simple video node lookup
        video_nodes = self.get_video_nodes(v4l2_device_name)
        self._validate_video_nodes(
            video_nodes, 1, camera_value, v4l2_device_name
        )
        return {"all": video_nodes[0]}

    def _validate_video_nodes(
        self,
        dev_video_nodes: List[str],
        expected_count: int,
        camera_value: str,
        v4l2_device_name: str,
    ) -> None:
        """Validate video nodes count and log results."""
        if not dev_video_nodes:
            log_and_raise_error(
                "No video device nodes found for '{}'".format(
                    v4l2_device_name
                ),
                CameraConfigurationError,
            )

        logger.info(
            "Found {} video device nodes for '{}' - '{}': {}".format(
                len(dev_video_nodes),
                v4l2_device_name,
                camera_value,
                dev_video_nodes,
            )
        )

        if len(dev_video_nodes) != expected_count:
            log_and_raise_error(
                "Expected {} video node(s) for {}, found {}".format(
                    expected_count, camera_value, len(dev_video_nodes)
                ),
                CameraConfigurationError,
            )


class Imx8mBaseCamera(CameraInterface):
    """
    Base class for Genio camera implementations.
    """

    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)  # Call ABC's __init__
        self._v4l2_devices = v4l2_devices
        self._img_sensor_arch = SoftwareArchitectures.Imx8m_Imgsensor

    def _get_artifact_path(
        self, store_path: str, artifact_name: str, format: str
    ) -> str:
        """Get the appropriate file extension based on format."""
        suffix = ".jpg" if format == "JPEG" else ".yuv"
        return os.path.join(store_path, artifact_name + suffix)

    def _build_gstreamer_cmd(
        self,
        dev_video_node: str,
        width: int,
        height: int,
        format: str,
        full_artifact_path: str,
        count: Optional[int] = None,
        framerate: Optional[int] = None,
    ) -> str:
        """Build the GStreamer command."""
        base_cmd = "{} -v v4l2src device={} io-mode=dmabuf ".format(
            GST_LAUNCH_BIN, dev_video_node
        )

        if count is not None:
            base_cmd += "num-buffers={} ! ".format(count)
        else:
            base_cmd += "num-buffers=30 ! "

        if format == "JPEG":
            format_str = "image/jpeg"
        else:
            format_str = "video/x-raw"
        format_str += ",width={},height={},format={}".format(
            width, height, format
        )

        if framerate is not None:
            format_str += ",framerate={}/1".format(framerate)

        if count is not None:
            sink = "filesink location={}".format(full_artifact_path)
        else:
            sink = "multifilesink location={} max-files=1".format(
                full_artifact_path
            )

        return base_cmd + format_str + " ! " + sink

    def _build_v4l2_cmd(
        self,
        dev_video_node: str,
        width: int,
        height: int,
        format: str,
        full_artifact_path: str,
        count: Optional[int] = None,
    ) -> str:
        """Build the v4l2-ctl command."""
        base_cmd = (
            "{} -d {} --set-fmt-video=width={},height={},pixelformat={} "
            "--stream-mmap"
        ).format(V4L2_CTL_CMD, dev_video_node, width, height, format)

        if count is not None:
            base_cmd += " --stream-count={}".format(count)
        else:
            base_cmd += " --stream-skip=30 --stream-count=1"

        return base_cmd + " --stream-to={} --verbose".format(
            full_artifact_path
        )

    def _get_camera_dev_video_node(self, v4l2_device_name: str) -> dict:
        """Get the video device node for the given v4l2 device name."""
        resolver = ImxVideoNodeResolver(self._v4l2_devices)
        return resolver.get_camera_video_nodes(self._camera, v4l2_device_name)

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
        """Capture an image using the specified method."""
        full_artifact_path = self._get_artifact_path(
            store_path, artifact_name, format
        )
        logging.info("Capture image as {}".format(full_artifact_path))

        dev_video_nodes = self._get_camera_dev_video_node(v4l2_device_name)
        dev_video_node = dev_video_nodes.get("capture") or dev_video_nodes.get(
            "all"
        )
        if not dev_video_node:
            log_and_raise_error(
                "No video device node found for {}".format(v4l2_device_name),
                CameraConfigurationError,
            )

        logger.info("Capture image with {}".format(method))

        if method == SupportedMethods.GSTREAMER:
            cmd = self._build_gstreamer_cmd(
                dev_video_node, width, height, format, full_artifact_path
            )
        elif method == SupportedMethods.V4L2_CTL:
            cmd = self._build_v4l2_cmd(
                dev_video_node, width, height, format, full_artifact_path
            )
        else:
            msg = "No suitable method such as '{}' or '{}' be provided".format(
                SupportedMethods.GSTREAMER, SupportedMethods.V4L2_CTL
            )
            log_and_raise_error(msg, CameraConfigurationError)

        logger.info("Executing command:\n{}".format(cmd))
        output = execute_command(cmd=cmd)
        logger.info("Output:\n{}".format(output))

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
        """Record a video using the specified method."""
        full_artifact_path = self._get_artifact_path(
            store_path, artifact_name, "YUV"
        )
        logging.info("Record a video as {}".format(full_artifact_path))

        dev_video_nodes = self._get_camera_dev_video_node(v4l2_device_name)
        dev_video_node = dev_video_nodes.get("record") or dev_video_nodes.get(
            "all"
        )
        if not dev_video_node:
            log_and_raise_error(
                "No video device node found for {}".format(v4l2_device_name),
                CameraConfigurationError,
            )

        logger.info("Record video with {}".format(method))

        if method == SupportedMethods.GSTREAMER:
            cmd = self._build_gstreamer_cmd(
                dev_video_node,
                width,
                height,
                format,
                full_artifact_path,
                count=count,
                framerate=framerate,
            )
        elif method == SupportedMethods.V4L2_CTL:
            cmd = self._build_v4l2_cmd(
                dev_video_node,
                width,
                height,
                format,
                full_artifact_path,
                count=count,
            )
        else:
            msg = "No suitable method such as '{}' or '{}' be provided".format(
                SupportedMethods.GSTREAMER, SupportedMethods.V4L2_CTL
            )
            log_and_raise_error(msg, CameraConfigurationError)

        logger.info("Executing command:\n {}".format(cmd))
        output = execute_command(cmd=cmd)
        logger.info("Output:\n{}".format(output))
