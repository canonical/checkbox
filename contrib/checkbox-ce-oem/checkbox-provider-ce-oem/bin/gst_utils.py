import logging
import os
import re
import shlex
import subprocess
import uuid

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from checkbox_support.scripts.psnr import get_average_psnr

GST_LAUNCH_BIN = os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0")
PLAINBOX_SESSION_SHARE = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")
VIDEO_CODEC_TESTING_DATA = os.getenv("VIDEO_CODEC_TESTING_DATA")
if not VIDEO_CODEC_TESTING_DATA or not os.path.exists(
    VIDEO_CODEC_TESTING_DATA
):
    raise SystemExit(
        "Error: Please define the proper path of golden sample folder to "
        "the environment variable 'VIDEO_CODEC_TESTING_DATA'"
    )
# Folder stores the golden samples
SAMPLE_2_FOLDER = "sample_2_big_bug_bunny"


class GStreamerEncodePlugins(Enum):
    V4L2H264ENC = "v4l2h264enc"
    V4L2H265ENC = "v4l2h265enc"
    V4L2JPEGENC = "v4l2jpegenc"


class GStreamerMuxerType(Enum):
    """
    An enumeration representing different GStreamer muxers and their
    corresponding file extensions.

    Attributes:
        MP4MUX (str): Represents the MP4 muxer, associated with the 'mp4' file
                        extension.
        AVIMUX (str): Represents the AVI muxer, associated with the 'avi' file
                        extension.
        MATROSKAMUX (str): Represents the Matroska muxer, associated with the
                        'mkv' file extension.
    """

    MP4MUX = "mp4"
    AVIMUX = "avi"
    MATROSKAMUX = "mkv"

    @classmethod
    def get_extension(cls, mux_type):
        if mux_type.upper() in cls.__members__:
            return cls[mux_type].value
        else:
            raise ValueError(
                "Invalid mux type: {}."
                " Available types are: {}".format(
                    mux_type, ", ".join(cls.__members__.keys())
                )
            )


def execute_command(cmd: str = "", timeout: int = 300) -> str:
    """
    Executes the GStreamer command and extracts the specific data from the
    output. The specific data is the value of last-message which is exposed by
    fpsdisplaysink.

    :param cmd:
        The GStreamer command to execute.

    :returns:
        The extracted last_message.
    """
    try:
        logging.info("Starting command: '{}'".format(cmd))
        ret = subprocess.run(
            shlex.split(cmd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
        logging.info(ret.stdout)
        return ret.stdout
    except Exception as e:
        raise SystemExit(e)


class PipelineInterface(ABC):
    @abstractmethod
    def build_pipeline(self) -> str:
        pass

    @property
    @abstractmethod
    def artifact_file(self) -> str:
        pass

    @property
    @abstractmethod
    def psnr_reference_file(self) -> str:
        pass


def delete_file(file_path: str = "") -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.warn("Error occurred while deleting file: {}".format(str(e)))


def compare_psnr(
    golden_reference_file: str = "", artifact_file: str = ""
) -> None:
    logging.info(
        "Compare the PSNR: {} vs {}".format(
            golden_reference_file, artifact_file
        )
    )
    avg_psnr, _ = get_average_psnr(golden_reference_file, artifact_file)
    logging.info("Average PSNR: {}".format(avg_psnr))
    if avg_psnr < 30 and avg_psnr > 0:
        raise SystemExit(
            "Error: The average PSNR value did not reach the acceptable"
            " threshold (30 dB)"
        )
    logging.info("Pass: Average PSNR meets the acceptable threshold")


def generate_artifact_name(extension: str = "mp4") -> str:
    n = "{}.{}".format(str(uuid.uuid4()).replace("-", "")[:6], extension)
    return os.path.join(PLAINBOX_SESSION_SHARE, n)


def get_big_bug_bunny_golden_sample(
    width: int = 3840,
    height: int = 2160,
    framerate: int = 60,
    codec: str = "h264",
    container: str = "mp4",
) -> str:
    """
    Idealy, we can consume a h264 mp4 file then encode by any other codecs and
    mux it with a specific muxer such as mp4mux into mp4 container.
    Therefore, we only need to adjust the width, height and framerate for
    getting golden sample.

    If you need a golden sample which doesn't exist in our sample pool, please
    contribute it and get it as your requirement.
    """
    golden_sample = "big_bug_bunny_{}x{}_{}fps_{}.{}".format(
        width, height, framerate, codec, container
    )

    full_path = os.path.join(
        VIDEO_CODEC_TESTING_DATA, SAMPLE_2_FOLDER, golden_sample
    )
    logging.debug("Golden Sample: '{}'".format(full_path))
    if not os.path.exists(full_path):
        raise SystemExit(
            "Error: Golden sample '{}' doesn't exist".format(full_path)
        )

    return full_path


class MetadataValidator:
    INVALID_PATTERN = "Validation failed: expected '{}: {}' be found"

    def __init__(self, file_path: str):
        """
        Initialize the MetadataValidator with the parsed metadata.

        :param cmd:
            file_path (str): TBD
        """
        self._file_path = file_path
        self._metadata = execute_command(
            cmd="gst-discoverer-1.0 {}".format(self._file_path)
        )
        self._errors = []

    def validate(self, key: str, expected: Any) -> "MetadataValidator":
        """
        Validates the metadata for a specific key against an expected value.

        :param key:
            The property to be validated.
            Support 'width', 'height', 'frame_rate' and 'codec' currently
        :param expected:
            The expected value for the property.

        :returns:
            MetadataValidator: Returns self to allow method chaining.
        """
        lk = key.lower()
        if lk == "width":
            self._validate_width(expected)
        elif lk == "height":
            self._validate_height(expected)
        elif lk == "frame_rate":
            self._validate_frame_rate(expected)
        elif lk == "codec":
            self._validate_codec(expected)

        return self

    def _validate_width(self, expected: int) -> None:
        width_pattern = "Width: {}".format(expected)
        if width_pattern not in self._metadata:
            self._errors.append(self.INVALID_PATTERN.format("Width", expected))

    def _validate_height(self, expected: int) -> None:
        logging.debug("Validating Height: {}".format(expected))
        height_pattern = "Height: {}".format(expected)
        if height_pattern not in self._metadata:
            self._errors.append(
                self.INVALID_PATTERN.format("Height", expected)
            )

    def _validate_frame_rate(self, expected: int) -> None:
        logging.debug("Validating Frame Rate: {}".format(expected))
        frame_rate_pattern = re.compile(
            r"Frame rate:\s*({}/\d+)".format(expected)
        )
        if not frame_rate_pattern.search(self._metadata):
            self._errors.append(
                self.INVALID_PATTERN.format("Frame rate", expected)
            )

    def _validate_codec(self, expected: str) -> None:
        """
        :param expected: the name of gstreamer plugin
        """
        logging.debug("Validating Codec: {}".format(expected))
        codec_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "H.264",
            GStreamerEncodePlugins.V4L2H265ENC.value: "H.265",
            GStreamerEncodePlugins.V4L2JPEGENC.value: "JPEG",
        }
        if expected not in codec_map:
            raise SystemExit(
                "Error: cannot get the mapping of _validate_codec function"
            )
        video_pattern = re.compile(
            r"video(\(image\))? #\d+: .*{}.*".format(codec_map[expected])
        )
        if not video_pattern.search(self._metadata):
            self._errors.append(
                self.INVALID_PATTERN.format("video_or_image", expected)
            )

    def is_valid(self) -> bool:
        """
        Checks if there are any validation errors.

        :returns: True if all validations passed, False otherwise.
        """
        if bool(self._errors):
            for i in self._errors:
                logging.error(i)
            raise SystemExit("Error: validate the metadata failed")
