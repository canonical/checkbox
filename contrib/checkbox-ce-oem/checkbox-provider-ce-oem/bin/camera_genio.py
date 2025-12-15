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
    MEDIA_CTL_CMD,
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

    MediaTek_Imgsensor:
        Drives the SoC-internal ISP to process Bayer RAW sensor data.
        Requires sensor-level controls for advanced features.
        Used with sensors that output RAW data needing ISP processing.

    V4L2_Sensor:
        Simple V4L2 sensor driver interface.
        Used with YUV sensors that don't require ISP processing.
        Provides basic camera functionality through standard V4L2 controls.
    """

    MediaTek_Imgsensor = "MediaTek_Imgsensor"
    V4L2_Sensor = "V4L2_Sensor"

    def __str__(self):
        return self.value


class SupportedCamera(Enum):
    """
    Supported camera modules on Genio platforms.

    Each enum value corresponds to a concrete camera implementation class.
    The string value matches the camera module identifier used in the system.
    """

    ONSEMI_AP1302_AR0430 = "onsemi_ap1302_ar0430"  # OnSemi AP1302 + AR0430 sensor
    ONSEMI_AR0430 = "onsemi_ar0430"  # OnSemi AR0430 sensor only
    ONSEMI_AP1302_AR0830 = "onsemi_ap1302_ar0830"  # OnSemi AP1302 + AR0830 sensor
    SONY_IMX214 = "sony_imx214"  # Sony IMX214 sensor

    def __str__(self):
        return self.value


def genio_camera_factory(camera_module: str) -> Type[CameraInterface]:
    """
    Factory function to create camera handler instances.

    Args:
        camera_module: String identifier of the camera module

    Returns:
        Camera handler class that implements CameraInterface

    Raises:
        ValueError: If camera_module is not supported
    """
    # Map camera module strings to their handler classes
    camera_handlers = {
        str(cam): handler
        for cam, handler in {
            SupportedCamera.ONSEMI_AP1302_AR0430: OnsemiAP1302AR0430,
            SupportedCamera.ONSEMI_AR0430: OnsemiAR0430,
            SupportedCamera.ONSEMI_AP1302_AR0830: OnsemiAP1302AR0830,
            SupportedCamera.SONY_IMX214: SonyIMX214,
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


def img_sensor_arch(v4l2_devices: str) -> SoftwareArchitectures:
    """
    Helper function to check if there's User Space Middleware in System
    """
    has_middleware = "mtk-v4l2-camera (platform:mtkcam" in v4l2_devices
    architecture = (
        SoftwareArchitectures.MediaTek_Imgsensor
        if has_middleware
        else SoftwareArchitectures.V4L2_Sensor
    )
    logger.info("Software Arch: {}".format(architecture))
    return architecture


class GenioVideoNodeResolver(VideoMediaNodeResolver):
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
        arch: SoftwareArchitectures,
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
        camera_value = camera.value if isinstance(camera, SupportedCamera) else camera

        # Classify by camera type instead of architecture
        if camera_value == SupportedCamera.SONY_IMX214.value:
            return self._resolve_sony_imx214(v4l2_device_name, arch, camera_value)
        elif camera_value == SupportedCamera.ONSEMI_AP1302_AR0830.value:
            return self._resolve_onsemi_ap1302_ar0830(
                v4l2_device_name, arch, camera_value
            )
        elif camera_value in (
            SupportedCamera.ONSEMI_AP1302_AR0430.value,
            SupportedCamera.ONSEMI_AR0430.value,
        ):
            return self._resolve_onsemi_ar0430(v4l2_device_name, arch, camera_value)
        else:
            log_and_raise_error(
                "Unsupported camera type: {}".format(camera), CameraError
            )

    def _resolve_sony_imx214(
        self,
        v4l2_device_name: str,
        arch: SoftwareArchitectures,
        camera_value: str,
    ) -> Dict[str, str]:
        """Resolve video nodes for SONY IMX214 camera."""
        self._validate_architecture_support(
            arch, [SoftwareArchitectures.MediaTek_Imgsensor], camera_value
        )

        # SONY_IMX214 requires 3 video nodes (preview, record, capture)
        dev_video_nodes = self.get_video_nodes(v4l2_device_name)
        self._validate_video_nodes(dev_video_nodes, 3, camera_value, v4l2_device_name)

        return {
            "preview": dev_video_nodes[0],
            "record": dev_video_nodes[1],
            "capture": dev_video_nodes[2],
        }

    def _resolve_onsemi_ap1302_ar0830(
        self,
        v4l2_device_name: str,
        arch: SoftwareArchitectures,
        camera_value: str,
    ) -> Dict[str, str]:
        """Resolve video nodes for ONSEMI AP1302 AR0830 camera."""
        if arch == SoftwareArchitectures.MediaTek_Imgsensor:
            # MediaTek Imgsensor: use first video node
            dev_video_nodes = self.get_video_nodes(v4l2_device_name)
            self._validate_video_nodes(
                dev_video_nodes, 1, camera_value, v4l2_device_name
            )
            return {"all": dev_video_nodes[0]}

        elif arch == SoftwareArchitectures.V4L2_Sensor:
            # V4L2 Sensor: use media-ctl to find video node
            return self._resolve_v4l2_sensor_ap1302_ar0830(
                v4l2_device_name, camera_value
            )
        else:
            self._validate_architecture_support(
                arch,
                [
                    SoftwareArchitectures.MediaTek_Imgsensor,
                    SoftwareArchitectures.V4L2_Sensor,
                ],
                camera_value,
            )

    def _resolve_v4l2_sensor_ap1302_ar0830(
        self, v4l2_device_name: str, camera_value: str
    ) -> Dict[str, str]:
        """Resolve video nodes for V4L2 sensor AP1302 AR0830."""
        media_dev = self.get_first_media_node(v4l2_device_name)
        if not media_dev:
            log_and_raise_error(
                "Could not find media device for {}".format(camera_value),
                CameraConfigurationError,
            )

        self._log_info(
            "Found media device for '{}' - '{}': {}".format(
                v4l2_device_name, camera_value, media_dev
            )
        )

        cmd = "{} -d {} --entity 'mtk-cam camsv-0 main-stream'".format(
            MEDIA_CTL_CMD, media_dev
        )
        video_node = execute_command(cmd).strip()
        if not video_node:
            log_and_raise_error(
                "Could not find video node for {}".format(camera_value),
                CameraConfigurationError,
            )
        return {"all": video_node}

    def _resolve_onsemi_ar0430(
        self,
        v4l2_device_name: str,
        arch: SoftwareArchitectures,
        camera_value: str,
    ) -> Dict[str, str]:
        """Resolve video nodes for ONSEMI AR0430 cameras."""
        self._validate_architecture_support(
            arch, [SoftwareArchitectures.V4L2_Sensor], camera_value
        )

        # ONSEMI_AP1302_AR0430 and ONSEMI_AR0430: simple video node lookup
        video_nodes = self.get_video_nodes(v4l2_device_name)
        if not video_nodes:
            log_and_raise_error(
                "Could not find video node for {}".format(camera_value),
                CameraConfigurationError,
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
                "No video device nodes found for '{}'".format(v4l2_device_name),
                CameraConfigurationError,
            )

        self._log_info(
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

    def _validate_architecture_support(
        self,
        arch: SoftwareArchitectures,
        supported_archs: List[SoftwareArchitectures],
        camera_value: str,
    ) -> None:
        """Validate architecture support for camera."""
        if arch not in supported_archs:
            log_and_raise_error(
                "Unsupported architecture: {} on {}".format(arch, camera_value),
                CameraError,
            )

    def _log_info(self, msg: str):
        """Log info message."""
        logger.info(msg)


class GenioBaseCamera(CameraInterface):
    """
    Base class for Genio camera implementations.
    """

    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)  # Call ABC's __init__
        self._v4l2_devices = v4l2_devices
        self._img_sensor_arch = img_sensor_arch(v4l2_devices)

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
        format_str += ",width={},height={},format={}".format(width, height, format)

        if framerate is not None:
            format_str += ",framerate={}/1".format(framerate)

        if count is not None:
            sink = "filesink location={}".format(full_artifact_path)
        else:
            sink = "multifilesink location={} max-files=1".format(full_artifact_path)

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

        return base_cmd + " --stream-to={} --verbose".format(full_artifact_path)

    def _get_camera_dev_video_node(self, v4l2_device_name: str) -> dict:
        """Get the video device node for the given v4l2 device name."""
        resolver = GenioVideoNodeResolver(self._v4l2_devices)
        return resolver.get_camera_video_nodes(
            self._camera, v4l2_device_name, self._img_sensor_arch
        )

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
        full_artifact_path = self._get_artifact_path(store_path, artifact_name, format)
        logging.info("Capture image as {}".format(full_artifact_path))

        dev_video_nodes = self._get_camera_dev_video_node(v4l2_device_name)
        dev_video_node = dev_video_nodes.get("capture") or dev_video_nodes.get("all")
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
        full_artifact_path = self._get_artifact_path(store_path, artifact_name, "YUV")
        logging.info("Record a video as {}".format(full_artifact_path))

        dev_video_nodes = self._get_camera_dev_video_node(v4l2_device_name)
        dev_video_node = dev_video_nodes.get("record") or dev_video_nodes.get("all")
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


class OnsemiAP1302AR0430(GenioBaseCamera):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.ONSEMI_AP1302_AR0430


class OnsemiAR0430(GenioBaseCamera):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.ONSEMI_AR0430


class OnsemiAP1302AR0830(GenioBaseCamera):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.ONSEMI_AP1302_AR0830


class SonyIMX214(GenioBaseCamera):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.SONY_IMX214
