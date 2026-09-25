import logging
import os
import re
import shlex
import subprocess
import uuid
import contextlib
import glob

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

from checkbox_support.scripts.psnr import get_average_psnr

GST_CODEC_EXECUTION_TIMEOUT = int(
    os.getenv("GST_CODEC_EXECUTION_TIMEOUT", "300")
)
GST_LAUNCH_BIN = os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0")
GST_DISCOVERER = os.getenv("GST_DISCOVERER", "gst-discoverer-1.0")
V4L2_CTL_BIN = os.getenv("V4L2_CTL_BIN", "v4l2-ctl")
# Default encoder bitrate used as a last resort when the target V4L2
# device/control cannot be discovered or queried (e.g. missing v4l2-ctl,
# non-V4L2 encoder backend).
DEFAULT_ENCODER_BITRATE = 15_000_000
PLAINBOX_SESSION_SHARE = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")
VIDEO_CODEC_TESTING_DATA = os.getenv("VIDEO_CODEC_TESTING_DATA")
if not VIDEO_CODEC_TESTING_DATA:
    VIDEO_CODEC_TESTING_DATA = os.path.join(
        os.path.expanduser("~"), "checkbox-video"
    )

if not os.path.exists(VIDEO_CODEC_TESTING_DATA):
    os.makedirs(VIDEO_CODEC_TESTING_DATA, exist_ok=True)
# Folder stores the golden samples

logger = logging.getLogger(__name__)


class GStreamerEncodePlugins(Enum):
    V4L2H264ENC = "v4l2h264enc"
    V4L2H265ENC = "v4l2h265enc"
    V4L2JPEGENC = "v4l2jpegenc"
    V4L2VP8ENC = "v4l2vp8enc"
    OMXH264ENC = "omxh264enc"
    OMXH265ENC = "omxh265enc"


class GStreamerDecodePlugins(Enum):
    OMXH264DEC = "omxh264dec"
    OMXH265DEC = "omxh265dec"


class GStreamerTransformActions(Enum):
    ROTATE_90 = "rotate_90"
    ROTATE_180 = "rotate_180"
    ROTATE_270 = "rotate_270"
    VERTICAL_FLIP = "vertical_flip"
    HORIZONTAL_FLIP = "horizontal_flip"

    def __str__(self):
        return self.value


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
    QTMUX = "mov"

    @classmethod
    def get_extension(cls, mux_type: str = "MP4MUX"):
        if mux_type.upper() in cls.__members__:
            return cls[mux_type].value
        else:
            raise ValueError(
                "Invalid mux type: {}."
                " Available types are: {}".format(
                    mux_type, ", ".join(cls.__members__.keys())
                )
            )


def _identify_gst_bin_from_snap(bin_name: str) -> bool:
    """
    Identify the gstreamer binary path.

    :param bin_name:
        The gstreamer binary name.

    :returns:
        The gstreamer binary path.
    """
    ret = subprocess.run(["which", bin_name], capture_output=True)
    if ret.returncode != 0:
        raise SystemExit(
            "Error: Cannot find the gstreamer binary. name: {}".format(
                bin_name
            )
        )
    if ret.stdout.decode("utf-8").strip().startswith("/snap/"):
        return True
    return False


def execute_command(
    cmd: str = "", timeout: int = GST_CODEC_EXECUTION_TIMEOUT
) -> str:
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
        bin_from_snap = _identify_gst_bin_from_snap(GST_LAUNCH_BIN)

        if bin_from_snap:
            logging.info(
                "GStreamer binary is from snap package, "
                "skip setting USER_DEFINED_GST_LD_LIBRARY_PATH "
                "and USER_DEFINED_GST_PLUGIN_PATH"
            )
            env = None
        else:
            env = os.environ.copy()
            # Update GStreamer library path and plugin path if user defined
            gst_ld_path = os.environ.get("USER_DEFINED_GST_LD_LIBRARY_PATH")
            gst_plugin_path = os.environ.get("USER_DEFINED_GST_PLUGIN_PATH")
            logging.info("User defined LD_LIBRARY_PATH: %s", gst_ld_path)
            logging.info("User defined LD_PLUGIN_PATH: %s", gst_plugin_path)
            if gst_ld_path:
                logging.info(
                    "Append %s to LD_LIBRARY_PATH for GStreamer", gst_ld_path
                )
                env.update(LD_LIBRARY_PATH=gst_ld_path)
            if gst_plugin_path:
                logging.info(
                    "Append %s to GST_PLUGIN_PATH for GStreamer",
                    gst_plugin_path,
                )
                env.update(GST_PLUGIN_PATH=gst_plugin_path)

        logging.info("Starting command: '{}'".format(cmd))
        ret = subprocess.run(
            shlex.split(cmd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
            env=env,
        )
        logging.info(ret.stdout)
        return ret.stdout
    except Exception as e:
        raise SystemExit(e)


def _find_v4l2_encoder_device(codec_fourcc: str) -> Optional[str]:
    """
    Find the /dev/videoN node whose Capture queue advertises the given
    compressed codec fourcc (e.g. 'H264', 'VP80', 'HEVC'). V4L2 M2M
    encoders enumerate their supported output codec(s) on the Capture
    queue side, so this identifies which device node actually backs a
    given GStreamer v4l2*enc element without hardcoding a device path
    (different platforms/boards can expose the encoder on a different
    /dev/videoN).

    :param codec_fourcc:
        The V4L2 fourcc name of the compressed codec, e.g. 'H264', 'VP80'.

    :returns:
        The device path (e.g. '/dev/video0') if found, otherwise None.
    """
    try:
        video_nodes = sorted(glob.glob("/dev/video*"))
    except Exception:
        return None

    for node in video_nodes:
        try:
            ret = subprocess.run(
                [V4L2_CTL_BIN, "-d", node, "--list-formats"],
                capture_output=True,
                universal_newlines=True,
                timeout=10,
            )
        except Exception:
            continue
        if ret.returncode != 0:
            continue
        if re.search(r"'{}'".format(re.escape(codec_fourcc)), ret.stdout):
            return node
    return None


def _get_v4l2_control_range(device: str, control_name: str) -> Optional[tuple]:
    """
    Query the (min, max) range of an integer V4L2 control on a device.

    :param device:
        The V4L2 device path, e.g. '/dev/video0'.
    :param control_name:
        The control name as reported by v4l2-ctl, e.g. 'video_bitrate'.

    :returns:
        A (min, max) tuple of ints if the control is found, otherwise
        None.
    """
    try:
        ret = subprocess.run(
            [V4L2_CTL_BIN, "-d", device, "--list-ctrls-menus"],
            capture_output=True,
            universal_newlines=True,
            timeout=10,
        )
    except Exception:
        return None
    if ret.returncode != 0:
        return None

    pattern = re.compile(
        (
            r"{}\s+0x[0-9a-fA-F]+\s+\(int\)\s*:\s*"
            r"min=(-?\d+)\s+max=(-?\d+)"
        ).format(re.escape(control_name))
    )
    match = pattern.search(ret.stdout)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def calculate_encoder_bitrate(
    width: int,
    height: int,
    framerate: int,
    codec_fourcc: str,
    bits_per_pixel: float = 0.1,
) -> int:
    """
    Calculate a video bitrate scaled to the actual resolution/framerate
    under test, then clamp it to the target V4L2 encoder device's own
    supported 'video_bitrate' control range so the value is always valid
    on the platform actually running the test (different VPUs/boards can
    have different min/max bitrate limits).

    A flat/hardcoded bitrate is avoided on purpose: it would either be
    unrealistically high for small resolutions/framerates, or exceed/miss
    the valid range on a VPU with different limits than the one this was
    tuned on.

    :param width:
        Video width in pixels.
    :param height:
        Video height in pixels.
    :param framerate:
        Video framerate in fps.
    :param codec_fourcc:
        The V4L2 fourcc name of the target codec, e.g. 'H264', 'VP80'.
    :param bits_per_pixel:
        Target bits-per-pixel-per-frame used to scale the bitrate
        estimate (0.1 is a common "high quality" guideline for
        H.264/VP8).

    :returns:
        The calculated bitrate in bits/sec, clamped to the encoder
        device's supported range when that range can be determined.
    """
    target_bitrate = int(width * height * framerate * bits_per_pixel)

    device = _find_v4l2_encoder_device(codec_fourcc)
    if not device:
        logging.warning(
            "Could not find a V4L2 device advertising codec '%s'. "
            "Using unclamped calculated bitrate: %s",
            codec_fourcc,
            target_bitrate,
        )
        return target_bitrate

    bitrate_range = _get_v4l2_control_range(device, "video_bitrate")
    if not bitrate_range:
        logging.warning(
            "Could not query 'video_bitrate' control range on %s. "
            "Using unclamped calculated bitrate: %s",
            device,
            target_bitrate,
        )
        return target_bitrate

    min_bitrate, max_bitrate = bitrate_range
    clamped_bitrate = max(min_bitrate, min(target_bitrate, max_bitrate))
    if clamped_bitrate != target_bitrate:
        logging.info(
            "Calculated bitrate %s clamped to %s to fit %s's supported "
            "range [%s, %s]",
            target_bitrate,
            clamped_bitrate,
            device,
            min_bitrate,
            max_bitrate,
        )
    return clamped_bitrate


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
    if avg_psnr < 25 and avg_psnr > 0:
        raise SystemExit(
            "Error: The average PSNR value did not reach the acceptable"
            " threshold (25 dB)"
        )
    logging.info("Pass: Average PSNR meets the acceptable threshold")


def generate_artifact_name(extension: str = "mp4") -> str:
    n = "{}.{}".format(str(uuid.uuid4()).replace("-", "")[:6], extension)
    return os.path.join(PLAINBOX_SESSION_SHARE, n)


@contextlib.contextmanager
def manage_test_file_by_name(
    file_name: str, target_dir: str = VIDEO_CODEC_TESTING_DATA
):
    """
    Context manager that downloads the test file and deletes it upon
    exiting the context. If the file already exists before this context,
    it will skip downloading and will NOT delete it upon exiting.
    """
    file_path = os.path.join(target_dir, file_name)
    file_existed = os.path.exists(file_path)

    if not file_existed:
        base_url = os.environ.get(
            "CODEC_FILE_SOURCE",
            "https://github.com/canonical/CodecCrafter/raw/main/video/",
        )
        if not base_url.endswith("/"):
            base_url += "/"

        url = "{}{}".format(base_url, file_name)
        logging.info("Downloading test file from %s to %s", url, file_path)
        try:
            subprocess.run(["wget", "-O", file_path, url], check=True)
        except subprocess.CalledProcessError as e:
            raise SystemExit(
                "Failed to download test file from {}: {}".format(url, e)
            )

    try:
        yield file_path
    finally:
        if not file_existed and os.path.exists(file_path):
            delete_file(file_path)


def file_name_placeholder(
    width: int,
    height: int,
    codec_short_name: str,
    ext: str,
    framerate: Optional[int] = None,
) -> str:
    file_name = "{}x{}_{}fps_{}.{}".format(
        width, height, framerate, codec_short_name, ext
    )
    # For non video files, such as jpg
    if framerate is None:
        file_name = "{}x{}_{}.{}".format(width, height, codec_short_name, ext)
    logging.debug("Generated file name: %s", file_name)
    return file_name


def get_codec_short_name(plugin_name: str) -> str:
    if "264" in plugin_name:
        return "h264"
    elif "265" in plugin_name:
        return "h265"
    elif "vp8" in plugin_name:
        return "vp8"
    elif "vp9" in plugin_name:
        return "vp9"
    elif "jpg" in plugin_name or "jpeg" in plugin_name:
        return "jpg"
    else:
        return ""


def get_test_file_name_by_params(
    width: int, height: int, framerate: int, plugin_name: str
) -> str:
    core_codec = get_codec_short_name(plugin_name).lower()
    if core_codec in ["h264", "h265"]:
        ext = "mp4"
    elif core_codec in ["vp8", "vp9"]:
        ext = "webm"
    else:
        ext = "mp4"
        core_codec = "h264"

    file_name = file_name_placeholder(
        width=width,
        height=height,
        codec_short_name=core_codec,
        ext=ext,
        framerate=framerate,
    )
    return file_name


@contextlib.contextmanager
def manage_test_file_by_params(
    width: int, height: int, framerate: int, plugin_name: str
):
    """
    Context manager that downloads the generic test file based on params
    and deletes it upon exiting the context.
    """
    file_name = get_test_file_name_by_params(
        width, height, framerate, plugin_name
    )
    with manage_test_file_by_name(file_name) as file_path:
        yield file_path


def get_test_file_path_by_params(
    width: int, height: int, framerate: int, plugin_name: str
) -> str:
    """Returns the absolute path for the target generic test file."""
    file_name = get_test_file_name_by_params(
        width, height, framerate, plugin_name
    )
    return os.path.join(VIDEO_CODEC_TESTING_DATA, file_name)


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
            cmd="{} {}".format(GST_DISCOVERER, self._file_path)
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
            GStreamerEncodePlugins.V4L2VP8ENC.value: "VP8",
            GStreamerEncodePlugins.OMXH264ENC.value: "H.264",
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
