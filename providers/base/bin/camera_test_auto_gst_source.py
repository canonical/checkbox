#! /usr/bin/python3

import os
from tempfile import TemporaryDirectory
import gi
from argparse import ArgumentParser
import typing as T
import logging
from checkbox_support import camera_pipelines as cam
from contextlib import ExitStack
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)s - %(message)s\n",
    datefmt="%m/%d %H:%M:%S",
)
logger.setLevel(logging.DEBUG)

gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")
from gi.repository import Gst, GstPbutils  # type: ignore # noqa: E402

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore # noqa: E402


ENCODING_PROFILES = {
    "mp4_h264": {
        "profile_str": "video/quicktime,variant=iso:video/x-h264",
        "file_extension": "mp4",
    },
    "ogv_theora": {
        "profile_str": "application/ogg:video/x-theora",
        "file_extension": "ogv",
    },
    "webm_vp8": {
        "profile_str": "video/webm:video/x-vp8",
        "file_extension": "webm",
    },
}

SPECIAL_WARNINGS_BY_DEVICE = {
    "Intel MIPI Camera (V4L2)": (
        "This DUT seems to have an Intel MIPI camera. "
        "If all the pipeline fails, the error message is "
        '"cannot negotiate buffers on port", '
        'and the generated pipeline uses "pipewiresrc", '
        "check if VIDIOC_REQBUF passes the test by running "
        '"v4l2-compliance | grep VIDIOC_REQBUF". '
        "Additionally if a pipeline using v4l2src works, then the pipewire "
        "installation on this DUT likely doesn't contain the fix that handles "
        "unsupported USERPTR io mode."
    )
}  # type: dict[str, str]


class MediaValidator:
    def __init__(self) -> None:
        self.discoverer = GstPbutils.Discoverer()

    def validate_image_dimensions(
        self,
        image_file_path: Path,
        *,
        expected_width: int,
        expected_height: int
    ) -> bool:
        const_str_path = str(image_file_path)
        if not os.path.isfile(const_str_path):
            logger.error(
                "Image file doesn't exist at {}".format(const_str_path)
            )
            return False

        try:
            info = self.discoverer.discover_uri(
                "file://{}".format(const_str_path)
            )
        except (GLib.GError, GLib.Error) as e:
            logger.error(
                "Encountered an error when attempting to read {}. ".format(
                    const_str_path
                )
                + str(e)  # cleaner message is in e.message
            )
            return False

        image_video_stream = info.get_video_streams()
        width = image_video_stream[0].get_width()  # type: int
        height = image_video_stream[0].get_height()  # type: int

        passed = True
        if width != expected_width:
            passed = False
            logger.error(
                "Image width mismatch. Expected = {}, actual = {}".format(
                    expected_width, width
                )
            )
        if height != expected_height:
            passed = False
            logger.error(
                "Image height mismatch. Expected = {}, actual = {}".format(
                    expected_height, height
                )
            )

        return passed

    def validate_video_info(
        self,
        video_file_path: Path,
        *,
        expected_width: int,
        expected_height: int,
        expected_duration_seconds: int,
        expected_fps: int,
        duration_tolerance_seconds: float
    ) -> bool:
        const_str_path = str(video_file_path)
        if not os.path.isfile(const_str_path):
            logger.error(
                "Video file doesn't exist at {}".format(const_str_path)
            )
            return False

        try:
            info = self.discoverer.discover_uri(
                "file://{}".format(const_str_path)
            )
        except (GLib.GError, GLib.Error) as e:
            logger.error(
                "Encountered an error when attempting to read {}. ".format(
                    const_str_path
                )
                + str(e)
            )
            return False

        duration = info.get_duration()  # type: int # This is in nanoseconds
        video_streams = info.get_video_streams()
        if len(video_streams) == 0:
            logger.error("{} has no video streams.".format(const_str_path))
            return False

        width = video_streams[0].get_width()  # type: int
        height = video_streams[0].get_height()  # type: int
        fps = video_streams[0].get_framerate_num()  # type: int

        passed = True

        if (
            abs(duration - expected_duration_seconds * Gst.SECOND)
            > duration_tolerance_seconds * Gst.SECOND
        ):
            logger.error(
                "Duration not within tolerance. "
                "Got {}s, but expected {} +- {}s".format(
                    round(duration / Gst.SECOND, 3),
                    expected_duration_seconds,
                    duration_tolerance_seconds,
                )
            )
            passed = False

        if width != expected_width:
            logger.error(
                "Video width mismatch. Expected = {}, actual = {}".format(
                    expected_width, width
                )
            )
            passed = False
        if height != expected_height:
            logger.error(
                "Video height mismatch. Expected = {}, actual = {}".format(
                    expected_height, height
                )
            )
            passed = False
        if fps != expected_fps:
            logger.error(
                "Video FPS mismatch. Expected = {}fps, actual = {}fps".format(
                    expected_fps, fps
                )
            )
            passed = False

        return passed


def get_devices() -> T.List[Gst.Device]:
    monitor = Gst.DeviceMonitor.new()  # type: Gst.DeviceMonitor
    monitor.add_filter("Video/Source")
    monitor.start()

    devices = monitor.get_devices() or []

    monitor.stop()
    return devices


def parse_args():
    parser = ArgumentParser(
        prog="Automatically test all cameras for each of their capabilities. "
        "Specify a subcommand and -h to show more help messages."
    )

    subparser = parser.add_subparsers(dest="subcommand")
    subparser.required = True  # workaround for older python versions
    photo_subparser = subparser.add_parser("take-photo")
    default_wait_seconds = 2
    photo_subparser.add_argument(
        "-ws",
        "--wait-seconds",
        type=int,
        dest="seconds",
        help="Number of seconds to keep the pipeline running "
        "before taking the photo. 0 is allowed here. "
        "Default = {}.".format(default_wait_seconds),
        default=default_wait_seconds,
    )
    photo_subparser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip image dimension validation",
    )

    video_subparser = subparser.add_parser("record-video")
    default_record_seconds = 5
    video_subparser.add_argument(
        "-s",
        "--seconds",
        type=int,
        help="Number of seconds to record. Default = {}.".format(
            default_record_seconds
        ),
        default=default_record_seconds,
    )
    default_tolerance = 0.5
    video_subparser.add_argument(
        "-t",
        "--tolerance",
        type=float,
        help=(
            "Tolerance for validating the recording duration in seconds. "
            "Ex. If the video is supposed to be 5s, tolerance is 0.1s, "
            "then 4.9s <= duration <= 5.1s will pass the validation. "
            + "Default is {}s.".format(default_tolerance)
        ),
        default=default_tolerance,
    )
    video_subparser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip video dimension & duration validation",
    )
    encoding_group = video_subparser.add_mutually_exclusive_group(
        required=True
    )
    encoding_group.add_argument(
        "--encoding",
        type=str,
        choices=list(ENCODING_PROFILES.keys()),
        help=(
            "Choose an encoding preset with this option. "
            "Make sure your system actually has the proper elements "
            "that supports this profile."
        ),
    )
    encoding_group.add_argument(
        "--custom-encoding-string",
        type=str,
        help=(
            "Directly set the encoding string for encodebin. "
            "See GStreamer's GstEncodingProfile page for examples. "
            "The examples on that page are included in the --encoding option. "
            "Only use this option if you have a custom encoding string."
        ),
    )
    video_subparser.add_argument(
        "--file-extension",
        type=str,
        help=(
            "Custom file extension. "
            "This is required when --custom-encoding-string is specified. "
            "If --encoding is specified, "
            "this overrides the default file extension."
        ),
    )  # need to explicitly check this

    viewfinder_subparser = subparser.add_parser("show-viewfinder")
    default_viewfinder_seconds = 10
    viewfinder_subparser.add_argument(
        "-s",
        "--seconds",
        type=int,
        help="Show the viewfinder for n seconds. Default = {}".format(
            default_viewfinder_seconds
        ),
        default=default_viewfinder_seconds,
    )
    for file_needed_parser in (video_subparser, photo_subparser):
        file_needed_parser.add_argument(
            "-p",
            "--path",
            type=str,
            help="Where to save output files. This should be a directory. "
            "If not specified, a directory will be created in /tmp "
            'with the prefix "camera_test_auto_gst_" and cleaned up upon exit',
        )
        default_max_caps = 10000
        file_needed_parser.add_argument(
            "--max-caps",
            type=int,
            default=default_max_caps,
            help="Set the maximum number of caps to check for each device. "
            "Default = {}. ".format(default_max_caps)
            + "This is useful for restraining the number of caps on devices "
            'that have "continuous" caps. '
            "Note that the caps are chosen by GStreamer's GstCaps.fixate()",
        )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.getuid() == 0:
        logger.warning(
            "Running this script as root. "
            "This may lead to different results than running as regular user."
        )

    devices = get_devices()

    if len(devices) == 0:
        logger.error(
            "GStreamer cannot find any cameras on this device. "
            "If you know a camera element exists, then it did not implement "
            "Gst.DeviceProvider to make itself visible to GStreamer "
            "or it is inaccessible without sudo."
        )
        return 1

    logger.info("Found {} cameras!".format(len(devices)))
    print(
        '[ HINT ] For debugging, remove the "valve" element to get a pipeline',
        'that can be run with "gst-launch-1.0".',
        (
            "Also keep the pipeline running for {} seconds.\n".format(
                args.seconds
            )
            if args.seconds > 0
            else "Terminate the pipeline as soon as possible.\n"
        ),
    )

    return_value = 0
    # conditionally enter the temp file context
    with ExitStack() as stack:
        if not (hasattr(args, "path") and args.path):
            tmp_dir = stack.enter_context(
                TemporaryDirectory(prefix="camera_test_auto_gst_")
            )
            abs_path = Path(tmp_dir)
        else:
            abs_path = Path(
                os.path.abspath(
                    os.path.expanduser(os.path.expandvars(args.path))
                )
            )
        if not os.path.isdir(str(abs_path)):
            # must validate early
            # multifilesink does not check if the path exists
            raise FileNotFoundError(
                'Path "{}" does not exist'.format(abs_path)
            )

        validator = MediaValidator()
        resolver = cam.CapsResolver()
        for dev_i, device in enumerate(devices):
            dev_element = device.create_element()
            if dev_element is None:
                logger.error(
                    "Could not create element for this device: {}".format(
                        device.get_display_name()
                    )
                )
                return_value = 1
                continue

            device_caps = device.get_caps()
            if device_caps is None:
                logger.error(
                    "Could not get capabilities for this device: {}".format(
                        device.get_display_name()
                    )
                )
                return_value = 1
                continue

            if device.get_display_name() in SPECIAL_WARNINGS_BY_DEVICE:
                logger.warning(
                    SPECIAL_WARNINGS_BY_DEVICE[device.get_display_name()]
                )

            if args.subcommand == "show-viewfinder":
                cam.show_viewfinder(dev_element, show_n_seconds=args.seconds)
                continue

            all_fixed_caps = resolver.get_all_fixated_caps(
                device_caps, "known_values", limit=args.max_caps
            )

            if len(all_fixed_caps) == 0:
                logger.error("This device did not provide any capability.")
                return_value = 1
                continue

            logger.info("Testing device {}/{}".format(dev_i + 1, len(devices)))
            logger.info(  # just an estimate
                "Test for this device may take {} seconds for {} caps.".format(
                    len(all_fixed_caps) * max(args.seconds, 1),
                    len(all_fixed_caps),
                )
            )

            for cap_i, capability in enumerate(all_fixed_caps):
                # since we use the same element for all caps
                # previous parent pipelines are not auto removed
                # need to explicitly unref
                dev_element.unparent()
                cap_struct = capability.get_structure(0)
                if args.subcommand == "take-photo":
                    logger.info(
                        "Taking a photo with capability: "
                        + '"{}"'.format(capability.to_string())
                        + "for device: "
                        + '"{}"'.format(device.get_display_name()),
                    )
                    file_path = abs_path / "photo_dev_{}_cap_{}.jpeg".format(
                        dev_i, cap_i
                    )
                    cam.take_photo(
                        dev_element,
                        delay_seconds=args.seconds,
                        caps=capability,
                        file_path=file_path,
                    )

                    if args.skip_validation:
                        continue

                    if not validator.validate_image_dimensions(
                        file_path,
                        expected_width=cap_struct.get_int("width")[1],
                        expected_height=cap_struct.get_int("height")[1],
                    ):
                        return_value = 1
                elif args.subcommand == "record-video":
                    if args.encoding is not None:
                        encoding_profile = ENCODING_PROFILES[args.encoding][
                            "profile_str"
                        ]
                        file_extension = ENCODING_PROFILES[args.encoding][
                            "file_extension"
                        ]
                        if args.file_extension is not None:
                            file_extension = args.file_extension
                    else:
                        encoding_profile = args.custom_encoding_string
                        assert args.file_extension, (
                            "File extension must be specified "
                            "when using custom encoding string"
                        )
                        file_extension = args.file_extension

                    file_path = abs_path / "video_dev_{}_cap_{}.{}".format(
                        dev_i, cap_i, file_extension
                    )

                    cam.record_video(
                        dev_element,
                        file_path=file_path,
                        caps=capability,
                        record_n_seconds=args.seconds,
                        encoding_profile=encoding_profile,
                    )

                    if args.skip_validation:
                        continue

                    if not validator.validate_video_info(
                        file_path,
                        expected_duration_seconds=args.seconds,
                        expected_width=cap_struct.get_int("width")[1],
                        expected_height=cap_struct.get_int("height")[1],
                        duration_tolerance_seconds=args.tolerance,
                        expected_fps=cap_struct.get_fraction("framerate")[1],
                    ):
                        return_value = 1

    logger.info("[ OK ] All done!")
    return return_value


if __name__ == "__main__":
    Gst.init(None)
    GstPbutils.pb_utils_init()

    exit(main())
