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
import logging
import os

from enum import Enum
from camera_utils import (
    CameraInterface,
    execute_command,
    get_video_node,
    SupportedMethods,
    GST_LAUNCH_BIN,
)

logger = logging.getLogger(__name__)


class SoftwareArchitectures(Enum):
    """
    There are two software architectures supported on the Genio series EVK.
    One is MediaTek Imgsensor and another is V4L2 sensor.

        MediaTek Imgsensor is mainly for driving the SoC-internal ISP to
        process the Bayer RAW sensor. It needs more sensor-level controls to
        support the advanced features.

        V4L2 sensor provides a simpler way to use the V4L2 sensor driver.
        This is for the YUV sensor which doesn’t need any ISP processing
    """

    MediaTek_Imgsensor = "MediaTek_Imgsensor"
    V4L2_Sensor = "V4L2_Sensor"

    def __str__(self):
        return self.value


class SupportedCamera(Enum):
    """
    This enum reveals what camera module be supported on Genio platforms

    We need to implement the Class for each item
    """

    ONSEMI_AP1302_AR0430 = "onsemi_ap1302_ar0430"
    ONSEMI_AP1302_AR0830 = "onsemi_ap1302_ar0830"
    SONY_IMX214 = "sony_imx214"

    def __str__(self):
        return self.value


def genio_camera_factory(camera_module: str) -> CameraInterface:
    camera_handlers = {
        SupportedCamera.ONSEMI_AP1302_AR0430.value: OnsemiAP1302AR0430,
        SupportedCamera.ONSEMI_AP1302_AR0830.value: OnsemiAP1302AR0830,
        SupportedCamera.SONY_IMX214.value: SonyIMX214,
    }

    handler_class = camera_handlers.get(camera_module)
    if handler_class:
        return handler_class
    else:
        raise ValueError(f"Unsupported camera module: {camera_module}")


def get_dev_video_node_under_mediaTek_imgsensor_arch(
    v4l2_devices: str, camera: str, v4l2_device_name: str
) -> dict:
    dev_video_nodes = []
    lines = v4l2_devices.strip().split("\n")
    find_target = False
    count_of_line_be_parsed = 1
    if camera == SupportedCamera.SONY_IMX214:
        count_of_line_be_parsed = 3

    for line in lines:
        line = line.strip()
        if v4l2_device_name in line:
            find_target = True
            logger.debug("Find target node: {}".format(v4l2_device_name))
            continue
        elif (
            line.startswith("/dev/video")
            and find_target
            and count_of_line_be_parsed
        ):
            dev_video_nodes.append(line)
            count_of_line_be_parsed -= 1

    if not dev_video_nodes:
        logger.error(
            "Fail to get the video device node based on '{}'".format(
                v4l2_device_name
            )
        )
        raise SystemExit(1)

    if camera == SupportedCamera.SONY_IMX214:
        return {
            "preview": dev_video_nodes[0],
            "record": dev_video_nodes[1],
            "capture": dev_video_nodes[2],
        }
    elif camera == SupportedCamera.ONSEMI_AP1302_AR0830:
        return {"all": dev_video_nodes[0]}


def is_mediaTek_imgsensor_arch(v4l2_devices: str) -> bool:
    """
    Helper function to check if there's User Space Middleware in System
    """
    has_middleware = "mtk-v4l2-camera (platform:mtkcam" in v4l2_devices
    logger.info(
        "Software Arch: {}".format(
            SoftwareArchitectures.MediaTek_Imgsensor
            if has_middleware
            else SoftwareArchitectures.V4L2_Sensor
        )
    )
    return has_middleware


class OnsemiAP1302AR0430(CameraInterface):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)  # Call ABC's __init__
        self._v4l2_devices = v4l2_devices
        self._has_middleware = is_mediaTek_imgsensor_arch(v4l2_devices)

    def capture_image(
        self,
        width: int,
        height: int,
        format: str,
        store_path: str,
        artifact_name: str,
        method: str,
        v4l2_device_name: str,
    ) -> str:
        if method == SupportedMethods.GSTREANER:
            full_artifact_path = os.path.join(
                store_path, artifact_name + ".jpg"
            )
            logging.info("Capture image as {}".format(full_artifact_path))
            dev_video_node = get_video_node(
                self._v4l2_devices, v4l2_device_name
            )

            # G350 doesn't support v4l2jpecenc hardware codec, therefore,
            # use software codec, jpecenc, instead.
            cmd = (
                "{} v4l2src device={} num-buffers=1 ! video/x-raw,"
                "width={},height={},format={} ! jpegenc ! filesink"
                " location={}"
            ).format(
                GST_LAUNCH_BIN,
                dev_video_node,
                width,
                height,
                format,
                full_artifact_path,
            )
            logger.info("Executing command:\n{}".format(cmd))
            execute_command(cmd=cmd)
        else:
            logger.error("No suitable method such as 'gstreamer' be provided")
            raise SystemExit(1)

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
        if method == SupportedMethods.GSTREANER:
            full_artifact_path = os.path.join(
                store_path, artifact_name + ".mp4"
            )
            logging.info("Record a video as {}".format(full_artifact_path))
            dev_video_node = get_video_node(
                self._v4l2_devices, v4l2_device_name
            )

            # https://bugs.launchpad.net/baoshan/+bug/2039380/comments/4
            cmd = (
                "{} -v v4l2src device={} num-buffers={} ! "
                "video/x-raw,width={},height={},format={},framerate={}/1 !"
                ' capssetter replace=true caps="video/x-raw, width={}, '
                "height={}, framerate=(fraction){}/1, "
                "multiview-mode=(string)mono, "
                "interlace-mode=(string)progressive, format=(string){}"
                ',colorimetry=(string)bt709" ! v4l2convert '
                "output-io-mode=5 ! video/x-raw,width={},height={},"
                "framerate={}/1 ! v4l2h264enc ! h264parse ! queue ! mp4mux"
                " ! filesink location={}"
            ).format(
                GST_LAUNCH_BIN,
                dev_video_node,
                count,
                width,
                height,
                format,
                framerate,
                width,
                height,
                framerate,
                format,
                width,
                height,
                framerate,
                full_artifact_path,
            )
            logger.info("Executing command:\n{}".format(cmd))
            execute_command(cmd=cmd)
        else:
            logger.error("No suitable method such as 'gstreamer' be provided")
            raise SystemExit(1)


class OnsemiAP1302AR0830(CameraInterface):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)  # Call ABC's __init__
        self._v4l2_devices = v4l2_devices
        self._has_middleware = is_mediaTek_imgsensor_arch(v4l2_devices)

    def capture_image(
        self,
        width: int,
        height: int,
        format: str,
        store_path: str,
        artifact_name: str,
        method: str,
        v4l2_device_name: str,
    ) -> str:
        if method == SupportedMethods.GSTREANER:
            full_artifact_path = os.path.join(
                store_path, artifact_name + ".jpg"
            )
            logging.info("Capture image as {}".format(full_artifact_path))
            dev_video_capture_node = (
                get_dev_video_node_under_mediaTek_imgsensor_arch(
                    v4l2_devices=self._v4l2_devices,
                    camera=SupportedCamera.ONSEMI_AP1302_AR0830,
                    v4l2_device_name=v4l2_device_name,
                )
            )["all"]

            cmd = (
                "{} v4l2src device={} num-buffers=1 ! "
                "video/x-raw,width={},height={},format={} !"
                " v4l2convert ! v4l2jpegenc ! filesink location={}"
            ).format(
                GST_LAUNCH_BIN,
                dev_video_capture_node,
                width,
                height,
                format,
                full_artifact_path,
            )

            logger.info("Executing command:\n{}".format(cmd))
            execute_command(cmd=cmd)
            # TODO: handle gstreamer under V4L2 Sensor Arch
        else:
            logger.error("No suitable method such as 'gstreamer' be provided")
            raise SystemExit(1)

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
        if method == SupportedMethods.GSTREANER:
            full_artifact_path = os.path.join(
                store_path, artifact_name + ".mp4"
            )
            logging.info("Record video as {}".format(full_artifact_path))
            dev_video_record_node = (
                get_dev_video_node_under_mediaTek_imgsensor_arch(
                    v4l2_devices=self._v4l2_devices,
                    camera=SupportedCamera.ONSEMI_AP1302_AR0830,
                    v4l2_device_name=v4l2_device_name,
                )
            )["all"]

            cmd = (
                "{} v4l2src device={} num-buffers={} !"
                " video/x-raw,width={},height={},format={} ! v4l2h264enc ! "
                "h264parse ! queue ! mp4mux ! filesink location={}"
            ).format(
                GST_LAUNCH_BIN,
                dev_video_record_node,
                count,
                width,
                height,
                format,
                full_artifact_path,
            )
            logger.info("Executing command:\n{}".format(cmd))
            execute_command(cmd=cmd)
        else:
            logger.error("No suitable method such as 'gstreamer' be provided")
            raise SystemExit(1)


class SonyIMX214(CameraInterface):
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)  # Call ABC's __init__
        self._v4l2_devices = v4l2_devices
        self._has_middleware = is_mediaTek_imgsensor_arch(v4l2_devices)

    def capture_image(
        self,
        width: int,
        height: int,
        format: str,
        store_path: str,
        artifact_name: str,
        method: str,
        v4l2_device_name: str,
    ) -> str:
        if method == SupportedMethods.GSTREANER:
            full_artifact_path = os.path.join(
                store_path, artifact_name + ".jpg"
            )
            logging.info("Capture image as {}".format(full_artifact_path))
            dev_video_capture_node = (
                get_dev_video_node_under_mediaTek_imgsensor_arch(
                    v4l2_devices=self._v4l2_devices,
                    camera=SupportedCamera.SONY_IMX214,
                    v4l2_device_name=v4l2_device_name,
                )
            )["capture"]

            cmd = (
                "{} v4l2src device={} num-buffers=1 ! image/jpeg,"
                "width={},height={},format={} ! filesink"
                " location={}"
            ).format(
                GST_LAUNCH_BIN,
                dev_video_capture_node,
                width,
                height,
                format,
                full_artifact_path,
            )
            logger.info("Executing command:\n{}".format(cmd))
            execute_command(cmd=cmd)
        else:
            logger.error("No suitable method such as 'gstreamer' be provided")
            raise SystemExit(1)

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
        if method == SupportedMethods.GSTREANER:
            full_artifact_path = os.path.join(
                store_path, artifact_name + ".mp4"
            )
            logging.info("Record video as {}".format(full_artifact_path))
            dev_video_record_node = (
                get_dev_video_node_under_mediaTek_imgsensor_arch(
                    v4l2_devices=self._v4l2_devices,
                    camera=SupportedCamera.SONY_IMX214,
                    v4l2_device_name=v4l2_device_name,
                )
            )["record"]

            cmd = (
                "{} v4l2src device={} num-buffers={} !"
                " video/x-raw,width={},height={},format={} ! v4l2h264enc ! "
                "h264parse ! queue ! mp4mux ! filesink location={}"
            ).format(
                GST_LAUNCH_BIN,
                dev_video_record_node,
                count,
                width,
                height,
                format,
                full_artifact_path,
            )
            logger.info("Executing command:\n{}".format(cmd))
            execute_command(cmd=cmd)
        else:
            logger.error("No suitable method such as 'gstreamer' be provided")
            raise SystemExit(1)
