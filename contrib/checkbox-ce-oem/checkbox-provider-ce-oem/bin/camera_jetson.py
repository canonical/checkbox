#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
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
import shutil

from enum import Enum
from typing import Optional, Type
from camera_utils import (
    CameraInterface,
    execute_command,
    SupportedMethods,
    GST_LAUNCH_BIN,
    CameraError,
    CameraConfigurationError,
    log_and_raise_error,
)

logger = logging.getLogger(__name__)

NVARGUS_NVRAW_BIN = shutil.which(
    os.getenv("NVARGUS_NVRAW_BIN", "nvargus_nvraw")
)

# DISPLAY must be unset for every Argus capture (both nvargus_nvraw and
# nvarguscamerasrc try to bring up an EGL preview when it is set, which
# wedges headless/ssh runs) - the legacy units/Jetson jobs all start with
# 'unset DISPLAY'. execute_command() runs without a shell, so /usr/bin/env
# carries the unset instead.
#
# The GStreamer plugin search paths (the NVIDIA plugins are not on the
# default search path) are deliberately NOT set here: GST_PLUGIN_PATH,
# GST_PLUGIN_SYSTEM_PATH and GST_PLUGIN_SCANNER are passed through the
# checkbox environment via the jobs' environ list, so each project supplies
# its own values - see units/camera/README.md.
ENV_PREFIX = "/usr/bin/env -u DISPLAY"

# Timeouts in seconds for execute_command(). Mandatory, not a nice-to-have:
# wedged Argus captures have happened, which is why every current Jetson job is
# wrapped in jetson_timeout_wrapper.sh. This module does not use that wrapper,
# so the bound has to come from here.
#
# The still-image values are today's, unchanged:
# units/Jetson/camera_job.pxu:30 and :52 use 10s for nvargus_nvraw, :76 and :99
# use 30s for a gstreamer still.
NVARGUS_TIMEOUT = 10
GST_IMAGE_TIMEOUT = 30
# Video needs more than today's 30s (camera_job.pxu:127, :155): that 30s only
# had to cover an H265-encoded 1080p mp4 (~30 MB). Dropping the encoder makes
# this path write-bound instead. Worst case here is 300 frames of 3280x2464
# NV12 (IMX219 mode 0 @21fps) = ~3.5 GiB, which is ~14s of capture but several
# times that to land on disk. 180s tolerates a ~20 MB/s sustained write floor
# while still bounding a wedge, and stays under execute_command()'s 300s
# default so the bound is strictly tighter than doing nothing.
GST_VIDEO_TIMEOUT = 180


class SupportedCamera(Enum):
    """
    Supported camera modules on Jetson platforms.

    Each enum value corresponds to a concrete camera implementation class.
    The string value matches the camera module identifier used in the system.
    """

    IMX274 = "imx274"  # Sony IMX274 sensor (AGX Orin Developer Kit, x2)
    IMX219 = "imx219"  # Sony IMX219 sensor (Orin NX and Orin Nano, x1)

    def __str__(self):
        return self.value


def jetson_camera_factory(camera_module: str) -> Type[CameraInterface]:
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
            SupportedCamera.IMX274: Imx274Handler,
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


class JetsonBaseCamera(CameraInterface):
    """
    Base class for Jetson camera implementations.

    Every capture goes through NVIDIA's Argus stack, which owns the media graph
    and addresses cameras by its own source index. There is therefore no
    media-ctl topology to configure and no /dev/videoN to resolve, so this
    class needs no __init__ of its own - CameraInterface's is enough.
    """

    def _get_artifact_path(
        self, store_path: str, artifact_name: str, format: str
    ) -> str:
        """Get the appropriate file extension based on format."""
        suffix = ".nvraw" if format == "NVRAW" else ".yuv"
        return os.path.join(store_path, artifact_name + suffix)

    def _get_sensor_id(self, v4l2_device_name: str) -> int:
        """
        Get the Argus source index for the given camera.

        On Jetson the scenario JSON declares camera_id - the Argus
        source_index as a string ("0" / "1"), which is what
        'nvargus_nvraw --c N' and 'nvarguscamerasrc sensor-id=N' actually
        consume - and the resource generator carries it in the framework's
        default identifier field, v4l2_device_name.

        Do not derive this from physical_interface, the VI channel or the i2c
        bus number: the AGX Orin's two sensors sit on VI channels 0 and 2, and
        the Orin NX's only sensor sits on VI channel 1, so neither tracks the
        Argus source index. physical_interface (cam0 / cam1) is a silkscreen
        label for the job id and carries no addressing meaning.
        """
        try:
            return int(v4l2_device_name)
        except (TypeError, ValueError):
            log_and_raise_error(
                "Invalid camera identifier '{}': on Jetson the scenario's "
                "camera_id carries the Argus source index (e.g. '0'), not "
                "a device name.".format(v4l2_device_name),
                CameraConfigurationError,
            )

    def _build_gstreamer_cmd(
        self,
        sensor_id: int,
        width: int,
        height: int,
        format: str,
        full_artifact_path: str,
        count: Optional[int] = None,
        framerate: Optional[int] = None,
        mode: Optional[int] = None,
    ) -> str:
        """
        Build the GStreamer command.

        No encoder anywhere: the Argus ISP emits NV12 into NVMM (GPU) memory
        and a file sink cannot consume NVMM buffers, so nvvidconv - the VIC
        hardware block, not an encoder - is mandatory to write the raw frames
        to disk. count/framerate decide filesink vs multifilesink.
        """
        src_words = [
            "nvarguscamerasrc",
            "num-buffers={}".format(count or 30),
            "sensor-id={}".format(sensor_id),
        ]
        # Omitted when unset, which leaves Argus on its sensor-mode=-1 default
        # and lets it auto-select. That is today's implicit behaviour.
        if mode is not None:
            src_words.append("sensor-mode={}".format(mode))

        caps_words = [
            "video/x-raw(memory:NVMM)",
            "width={}".format(width),
            "height={}".format(height),
            "format={}".format(format),
        ]
        if framerate is not None:
            caps_words.append("framerate={}/1".format(framerate))

        if count is not None:
            sink = "filesink location={}".format(full_artifact_path)
        else:
            sink = "multifilesink location={} max-files=1".format(
                full_artifact_path
            )

        # The caps are single-quoted so that the logged command can be pasted
        # straight into a shell, where the '(memory:NVMM)' parens would
        # otherwise be a syntax error. shlex.split() strips the quotes back off
        # before execution, so argv is unaffected either way.
        return "{} {} {} ! '{}' ! nvvidconv ! '{}' ! {}".format(
            ENV_PREFIX,
            GST_LAUNCH_BIN,
            " ".join(src_words),
            ",".join(caps_words),
            "video/x-raw,format={}".format(format),
            sink,
        )

    def _build_nvargus_cmd(
        self,
        sensor_id: int,
        full_artifact_path: str,
        mode: Optional[int] = None,
    ) -> str:
        """
        Build the nvargus_nvraw command.

        '--format nvraw' is the tool's own default and the sensor's native
        pre-ISP Bayer raw; today's jobs pass '--format jpg', which is the
        deviation being corrected. Resolution is not an argument here - the
        Argus mode selects it.
        """
        if not NVARGUS_NVRAW_BIN:
            log_and_raise_error(
                "Could not find the 'nvargus_nvraw' executable",
                CameraConfigurationError,
            )

        words = [ENV_PREFIX, NVARGUS_NVRAW_BIN, "--c {}".format(sensor_id)]
        if mode is not None:
            words.append("--mode {}".format(mode))
        words.append("--format nvraw")
        words.append("--file {}".format(full_artifact_path))

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
        mode: Optional[int] = None,
    ) -> None:
        """Capture an image using the specified method."""
        full_artifact_path = self._get_artifact_path(
            store_path, artifact_name, format
        )
        logging.info("Capture image as {}".format(full_artifact_path))

        sensor_id = self._get_sensor_id(v4l2_device_name)

        logger.info(
            "Capture image from {} sensor-id {} with {}".format(
                self._camera, sensor_id, method
            )
        )

        if method == SupportedMethods.GSTREAMER:
            cmd = self._build_gstreamer_cmd(
                sensor_id,
                width,
                height,
                format,
                full_artifact_path,
                mode=mode,
            )
            timeout = GST_IMAGE_TIMEOUT
        elif method == SupportedMethods.NVARGUS_NVRAW:
            cmd = self._build_nvargus_cmd(
                sensor_id, full_artifact_path, mode=mode
            )
            timeout = NVARGUS_TIMEOUT
        else:
            msg = "No suitable method such as '{}' or '{}' be provided".format(
                SupportedMethods.GSTREAMER, SupportedMethods.NVARGUS_NVRAW
            )
            log_and_raise_error(msg, CameraConfigurationError)

        logger.info("Executing command:\n{}".format(cmd))
        output = execute_command(cmd=cmd, timeout=timeout)
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
        mode: Optional[int] = None,
    ) -> None:
        """Record a video using the specified method."""
        full_artifact_path = self._get_artifact_path(
            store_path, artifact_name, "YUV"
        )
        logging.info("Record a video as {}".format(full_artifact_path))

        sensor_id = self._get_sensor_id(v4l2_device_name)

        logger.info(
            "Record video from {} sensor-id {} with {}".format(
                self._camera, sensor_id, method
            )
        )

        # nvargus_nvraw is a still-image tool, so gstreamer is the only method
        # able to record.
        if method == SupportedMethods.GSTREAMER:
            cmd = self._build_gstreamer_cmd(
                sensor_id,
                width,
                height,
                format,
                full_artifact_path,
                count=count,
                framerate=framerate,
                mode=mode,
            )
        else:
            msg = "No suitable method such as '{}' be provided".format(
                SupportedMethods.GSTREAMER
            )
            log_and_raise_error(msg, CameraConfigurationError)

        logger.info("Executing command:\n {}".format(cmd))
        output = execute_command(cmd=cmd, timeout=GST_VIDEO_TIMEOUT)
        logger.info("Output:\n{}".format(output))


class Imx274Handler(JetsonBaseCamera):
    """Handler for the Sony IMX274 camera."""

    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.IMX274


class Imx219Handler(JetsonBaseCamera):
    """Handler for the Sony IMX219 camera."""

    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.IMX219
