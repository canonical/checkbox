#! /usr/bin/python3

import os
import PIL.Image
import gi
from argparse import ArgumentParser
import typing as T
import logging
from checkbox_support import camera_pipelines as cam

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)s - %(message)s\n",
    datefmt="%m/%d %H:%M:%S",
)
logger.setLevel(logging.DEBUG)

Gtk = None

gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")
from gi.repository import Gst, GstPbutils  # type: ignore # noqa: E402

gi.require_version("GLib", "2.0")


class MediaValidator:

    @staticmethod
    def validate_image_dimensions(
        image_file_path: str, *, expected_width: int, expected_height: int
    ) -> bool:
        if not os.path.isfile(image_file_path):
            logger.error(
                "Image file doesn't exist at {}".format(image_file_path)
            )
            return False

        image = PIL.Image.open(image_file_path)
        passed = True

        if image.width != expected_width:
            passed = False
            logger.error(
                "Image width mismatch. Expected = {}, actual = {}".format(
                    expected_width, image.width
                )
            )
        if image.height != expected_height:
            passed = False
            logger.error(
                "Image height mismatch. Expected = {}, actual = {}".format(
                    expected_height, image.height
                )
            )

        return passed

    @staticmethod
    def validate_video_info(
        video_file_path: str,
        *,
        expected_width: int,
        expected_height: int,
        expected_duration_seconds: int,
        expected_fps: int,
        duration_tolerance_seconds: float
    ) -> bool:
        if not os.path.isfile(video_file_path):
            logger.error(
                "Video file doesn't exist at {}".format(video_file_path)
            )
            return False

        discoverer = GstPbutils.Discoverer()

        video_file_path.lstrip("/")
        info = discoverer.discover_uri("file://" + video_file_path)
        duration = info.get_duration()  # type: int # This is in nanoseconds
        video_streams = info.get_video_streams()
        if len(video_streams) == 0:
            logger.error("{} has no video streams.".format(video_file_path))
            return False

        width = video_streams[0].get_width()  # type: int
        height = video_streams[0].get_height()  # type: int
        fps = video_streams[0].get_framerate_num()  # type: int

        passed = True

        if (
            abs(duration - expected_duration_seconds * 10**9)
            > duration_tolerance_seconds * 10**9
        ):
            logger.error(
                "Duration not within tolerance. "
                "Got {}s, but expected {} +- {}s".format(
                    round(duration / (10**9), 3),
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


def get_devices() -> T.List[Gst.Device]:
    monitor = Gst.DeviceMonitor.new()  # type: Gst.DeviceMonitor
    monitor.add_filter("Video/Source")
    monitor.start()

    devices = monitor.get_devices()

    monitor.stop()
    return devices


def parse_args():
    parser = ArgumentParser()

    subparser = parser.add_subparsers(dest="subcommand", required=True)
    photo_subparser = subparser.add_parser("take-photo")
    default_wait_seconds = 2
    photo_subparser.add_argument(
        "-ws",
        "--wait-seconds",
        type=int,
        dest="seconds",
        help="Number of seconds to keep the pipeline running "
        "before taking the photo. Default = {}.".format(default_wait_seconds),
        default=default_wait_seconds,
    )
    photo_subparser.add_argument(
        "-p",
        "--path",
        type=str,
        help="Where to save the file. This should be a directory.",
        required=True,
    )
    photo_subparser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip image dimension validation",
    )
    default_max_caps = 10000
    photo_subparser.add_argument(
        "--max-caps",
        type=int,
        default=default_max_caps,
        help="Set the maximum number of caps to check for each device. "
        "Default = {}. ".format(default_max_caps)
        + "This is useful for restraining the number of caps on devices "
        'that have "continuous" caps. '
        "Note that the caps are chosen by GStreamer's GstCaps.fixate()",
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
    video_subparser.add_argument(
        "-p",
        "--path",
        type=str,
        help="Where to save the file. This should be a directory.",
        required=True,
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

    player_subparser = subparser.add_parser("play-video")
    player_subparser.add_argument(
        "-p",
        "--path",
        type=str,
        help="Path to the video file",
        required=True,
    )

    return parser.parse_args()


def main():
    args = parse_args()
    if os.getuid() == 0:
        logger.warning(
            "Running this script as root. "
            "This may lead to different results than running as regular user."
        )

    if args.subcommand == "play-video":
        abs_path = os.path.abspath(
            os.path.expanduser(os.path.expandvars(args.path))
        )
        cam.play_video(abs_path)
        return

    devices = get_devices()

    if len(devices) == 0:
        logger.error(
            "GStreamer cannot find any cameras on this device. "
            "If you know a camera element exists, then it did not implement "
            "Gst.DeviceProvider to make itself visible to GStreamer "
            "or it is inaccessible without sudo."
        )
        exit(1)

    logger.info("Found {} cameras!".format(len(devices)))
    print(
        '[ HINT ] For debugging, remove the "valve" element to get a pipeline',
        'that can be run with "gst-launch-1.0".',
        "Also keep the pipeline running for {} seconds".format(args.seconds),
    )

    for dev_i, device in enumerate(devices):
        dev_element = device.create_element()  # type: Gst.Element

        if args.subcommand == "show-viewfinder":
            cam.show_viewfinder(dev_element, show_n_seconds=args.seconds)
            continue

        abs_path = os.path.abspath(
            os.path.expanduser(os.path.expandvars(args.path))
        )
        if not os.path.isdir(abs_path):
            # must validate early
            # multifilesink does not check if the path exists
            raise FileNotFoundError(
                'Path "{}" does not exist'.format(abs_path)
            )

        resolver = cam.CapsResolver()
        all_fixed_caps = resolver.get_all_fixated_caps(
            device.get_caps(), "known_values"
        )

        logger.info("Testing device {}/{}".format(dev_i + 1, len(devices)))
        logger.info(
            "Test for this device may take {} seconds for {} caps.".format(
                len(all_fixed_caps) * args.seconds, len(all_fixed_caps)
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
                file_path = "{}/photo_dev_{}_cap_{}.jpeg".format(
                    abs_path, dev_i, cap_i
                )
                cam.take_photo(
                    dev_element,
                    delay_seconds=args.seconds,
                    caps=capability,
                    file_path=file_path,
                )

                if args.skip_validation:
                    continue

                MediaValidator.validate_image_dimensions(
                    file_path,
                    expected_width=cap_struct.get_int("width").value,
                    expected_height=cap_struct.get_int("height").value,
                )
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

                file_path = "{}/video_dev_{}_cap_{}.{}".format(
                    abs_path, dev_i, cap_i, file_extension
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

                MediaValidator.validate_video_info(
                    file_path,
                    expected_duration_seconds=args.seconds,
                    expected_width=cap_struct.get_int("width").value,
                    expected_height=cap_struct.get_int("height").value,
                    duration_tolerance_seconds=args.tolerance,
                    expected_fps=cap_struct.get_fraction(
                        "framerate"
                    ).value_numerator,
                )

    logger.info("[ OK ] All done!")


if __name__ == "__main__":
    Gst.init(None)
    GstPbutils.pb_utils_init()

    main()
