#! /usr/bin/python3

from enum import Enum
import os
import PIL.Image
import gi
from argparse import ArgumentParser
import typing as T
import logging
import time

VoidFn = T.Callable[[], None]  # takes nothing and returns nothing

# https://github.com/TheImagingSource/tiscamera/blob/master/examples/python/00-list-devices.py

# detect intrange
# http://gstreamer-devel.230.s1.nabble.com/gstreamer-python-binding-and-intRange-td969231.html#a969232

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)s - %(message)s",
    datefmt="%m/%d %H:%M:%S",
)
logger.setLevel(logging.DEBUG)

from gi.repository import GObject  # type: ignore

Gtk = None

gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")
from gi.repository import Gst, GstPbutils  # type: ignore

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore


def get_devices() -> T.List[Gst.Device]:
    monitor = Gst.DeviceMonitor.new()  # type: Gst.DeviceMonitor
    monitor.add_filter("Video/Source")
    monitor.start()

    devices = monitor.get_devices()

    monitor.stop()
    return devices


class MediaValidator:

    @staticmethod
    def validate_image_dimensions(
        image_file_path: str,
        *,
        expected_width: int,
        expected_height: int,
    ) -> bool:
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
        duration_tolerance_seconds=0.1,
    ) -> bool:
        discoverer = GstPbutils.Discoverer()

        video_file_path.removeprefix("/")
        info = discoverer.discover_uri("file://" + video_file_path)
        duration = info.get_duration()  # type: int # This is in nanoseconds
        video_track = info.get_stream_info().get_streams()[0]
        width = video_track.get_width()
        height = video_track.get_height()

        passed = True

        if (
            abs(duration - expected_duration_seconds * 10**9)
            > duration_tolerance_seconds * 10**9
        ):
            logger.error(
                "Duration not within tolerance. Got {}s, but expected {} +- {}s".format(
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

        return passed


class CapsResolver:
    INT32_MIN = -2147483648
    INT32_MAX = 2147483647

    # (top, bottom) or (numerator, denominator)
    FractionTuple = tuple[int, int]
    # Used when we encounter IntRange or FractionRange types
    # Simply fixating the caps will produce too many caps,
    # so we restrict to these common ones
    RangeResolveMethod = T.Literal["remap", "limit"]
    RANGE_REMAP = {
        "width": [640, 1280, 1920, 2560, 3840],
        "height": [480, 720, 1080, 1440, 2160],
        "framerate": [(15, 1), (30, 1), (60, 1)],  # 15fpx, 30fps, 60fps
    }

    def extract_fraction_range(
        self, struct: Gst.Structure, prop_name: str
    ) -> T.Tuple[FractionTuple, FractionTuple]:
        """Extracts (low, high) fraction range from a Gst.Structure

        :param struct: structure whose prop_name is a Gst.FractionRange
        :param prop_name: name of the property
        :return: (low, high) fraction tuple
            - NOTE: low is defined as having a smaller numerator
        """
        assert struct.has_field_typed(prop_name, Gst.FractionRange)
        low = struct.copy()  # type: Gst.Structure
        high = struct.copy()  # type: Gst.Structure
        low.fixate_field_nearest_fraction(prop_name, 0, 1)
        high.fixate_field_nearest_fraction(prop_name, self.INT32_MAX, 1)

        return (
            low.get_fraction(prop_name)[1:],
            high.get_fraction(prop_name)[1:],
        )

    def extract_int_range(
        self, struct: Gst.Structure, prop_name: str
    ) -> T.Tuple[int, int]:
        """Bit of a hack to work around the missing Gst.IntRange type

        :param struct: structure whose prop_name property is a Gst.IntRange
        :param prop_name: name of the property
        :return: (low, high) integer tuple
        """
        # the introspected class exists, but we can't construct it
        assert struct.has_field_typed(prop_name, Gst.IntRange)

        low = struct.copy()  # type: Gst.Structure
        high = struct.copy()  # type: Gst.Structure
        low.fixate_field_nearest_int(prop_name, self.INT32_MIN)
        high.fixate_field_nearest_int(prop_name, self.INT32_MAX)

        # get_int returns a (success, value) tuple
        return low.get_int(prop_name)[1], high.get_int(prop_name)[1]

    @T.overload
    def remap_range_to_list(
        self, prop: str, low: int, high: int
    ) -> T.List[int]: ...
    @T.overload
    def remap_range_to_list(
        self, prop: str, low: FractionTuple, high: FractionTuple
    ) -> T.List[FractionTuple]: ...
    def remap_range_to_list(
        self,
        prop: str,
        low: T.Union[int, FractionTuple],
        high: T.Union[int, FractionTuple],
    ) -> T.List:
        """Creates a GObject.ValueArray based on range
        that can be used in Gst.Caps

        :param low: min value, inclusive
        :param high: max value, inclusive
        :return: ValueArray object. Usage: Caps.set_property(prop, value_array)
        """
        out = []
        assert (
            prop in self.RANGE_REMAP
        ), "Property {} does not have a remap definition".format(prop)

        for val in self.RANGE_REMAP[prop]:
            # lt gt are defined as pairwise comparison on tuples
            if val >= low and val <= high:
                out.append(val)

        return out

    def list_to_gobject_value_array(self, l: T.List):
        out = GObject.ValueArray()
        for e in l:
            out.append(e)
        return out  # this does not guarantee that out has a sensible value

    def get_all_fixated_caps(
        self,
        caps: Gst.Caps,
        resolve_method: RangeResolveMethod,
        limit: T.Optional[int] = None,
    ) -> T.List[Gst.Caps]:
        """Gets all the fixated(1 value per property) caps from a Gst.Caps object

        :param caps: a mixed Gst.Caps
        :param resolve_method: how to resolve IntRange and FractionRange values
        - Only applies to width, height, and framerate for now
        - "remap" => picks out a set of common values within the original range
        - "limit" => Use the caps.is_fixed while loop until we reaches limit

        :param limit: the limit to use for the "limit" resolver, ignored otherwise
        :return: a list of fixed caps
        """
        if caps.is_fixed():
            return [caps]

        fixed_caps = []  # type: list[Gst.Caps]

        for i in range(caps.get_size()):
            struct = caps.get_structure(i)
            caps_i = Gst.Caps.from_string(struct.to_string())  # type: Gst.Caps

            if resolve_method == "remap":
                for prop in self.RANGE_REMAP.keys():
                    s_i = caps_i.get_structure(0)  # type: Gst.Structure

                    finite_list = None  # type GObject.ValueArray
                    if s_i.has_field_typed(prop, Gst.IntRange):
                        low, high = self.extract_int_range(s_i, prop)
                        finite_list = self.list_to_gobject_value_array(
                            self.remap_range_to_list(prop, low, high)
                        )
                    elif s_i.has_field_typed(prop, Gst.FractionRange):
                        low, high = self.extract_fraction_range(s_i, prop)
                        fraction_list = self.remap_range_to_list(
                            prop, low, high
                        )
                        # workaround missing Gst.Fraction
                        # we can't directly create fraction objects
                        # but we can create a struct from str, then access it
                        temp = Gst.Structure.from_string(
                            "temp, {}={{{}}}".format(
                                prop,
                                ",".join(
                                    "{}/{}".format(f[0], f[1])
                                    for f in fraction_list
                                ),
                            )
                        )[0]
                        finite_list = temp.get_list(prop)[1]

                    if finite_list is not None:
                        assert finite_list.n_values != 0
                        s_i.set_list(
                            prop,
                            finite_list,
                        )

                        caps_i = Gst.Caps.from_string(s_i.to_string())

            while not caps_i.is_fixed() and not caps_i.is_empty():
                fixed_cap = caps_i.fixate()  # type: Gst.Caps
                if fixed_cap.get_structure(0).get_name() == "video/x-bayer":
                    continue
                fixed_caps.append(fixed_cap)
                caps_i = caps_i.subtract(fixed_cap)

            if caps_i.is_fixed():
                fixed_caps.append(caps_i)

        return fixed_caps


def parse_args():
    parser = ArgumentParser()

    subparser = parser.add_subparsers(dest="subcommand", required=True)
    photo_subparser = subparser.add_parser("take-photo")
    photo_subparser.add_argument(
        "-ws",
        "--wait-seconds",
        type=int,
        help="Number of seconds to keep the pipeline running "
        "before taking the photo. Default = 2.",
        default=2,
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
    photo_subparser.add_argument(
        "--max-caps",
        type=int,
        help="Set the maximum number of capabilities to check for each device. "
        "Default = 100. "
        "This is useful for restraining the number of caps on devices "
        'that have "continuous" caps.',
    )

    video_subparser = subparser.add_parser("record-video")
    video_subparser.add_argument(
        "-s",
        "--seconds",
        type=int,
        help="Number of seconds to record. Default = 5.",
        default=5,
    )
    video_subparser.add_argument(
        "-p",
        "--path",
        type=str,
        help="Where to save the file. This should be a directory.",
        required=True,
    )
    video_subparser.add_argument(
        "-t",
        "--tolerance",
        type=float,
        help=(
            "Tolerance for validating the recording duration in seconds. "
            "Ex. If the video is supposed to be 5s, tolerance is 0.1s, "
            "then durations in [4.9s, 5.1s] inclusive will pass the validation"
            "Default is 0.5s."
        ),
        default=0.5,
    )
    video_subparser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip video dimension & duration validation",
    )

    viewfinder_subparser = subparser.add_parser("show-viewfinder")
    viewfinder_subparser.add_argument(
        "-s",
        "--seconds",
        type=int,
        help="Show the viewfinder for n seconds",
        default=10,
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


def elem_to_str(element: Gst.Element) -> str:
    """Prints an element to string
    - Excluding parent & client name

    :param element: gstreamer element
    :return: String representaion
    """
    properties = element.list_properties()  # list[GObject.GParamSpec]
    element_name = element.get_factory().get_name()

    exclude = ["parent", "client-name"]
    prop_strings = []  # type: list[str]

    for prop in properties:
        if prop.name in exclude:
            continue

        try:
            prop_value = element.get_property(prop.name)
        except:
            logger.debug(
                "Property {} is unreadable in {}".format(
                    prop.name, element_name
                )  # not every property is readable, ignore unreadable ones
            )
            continue

        if (
            hasattr(prop_value, "to_string")
            and type(prop_value.to_string).__name__ == "method"
        ):
            # sometimes we have a nice to_string method, prioritize this
            prop_strings.append(
                "{}={}".format(prop.name, prop_value.to_string())
            )
        elif type(prop_value) is Enum:
            prop_strings.append("{}={}".format(prop.name, prop_value.value))
        else:
            prop_strings.append(
                "{}={}".format(prop.name, str(prop_value))
            )  # handle native python types

    return "{} {}".format(
        element_name, " ".join(prop_strings)
    )  # libcamerasrc name=cam_name location=p.jpeg


def run_pipeline(
    pipeline: Gst.Pipeline,
    run_n_seconds: T.Optional[int] = None,
    force_kill_timeout: int = 300,
    intermediate_calls: T.List[T.Tuple[int, VoidFn]] = [],
):
    """Run the pipeline

    :param pipeline: Gst.Pipeline. All element creation/linking steps
        should be done by this point
    :param run_n_seconds: how long until we stop the main loop.
        - If None, only wait for EOS.
    :param force_kill_timeout: how long until a force kill is triggered.
        - If None and run_n_seconds != None, then force_kill = run_n_seconds * 2
        - If != None and run_n_seconds != None, an error is raised if force kill <= run_n_seconds
    :param intermedate_calls: a list of functions to call
        while the pipeline is running. list[(() -> None, int)], where 2nd elem
        is the number of seconds to wait RELATIVE to
        when the pipeline started running
    :raises RuntimeError: When set_state(PLAYING) fails
    """
    bus = pipeline.get_bus()
    assert bus
    main_loop = GLib.MainLoop.new(  # type: GLib.MainLoop
        None, False  # type: ignore
    )

    # pipeline needs to start within 5 seconds
    def start():
        pipeline.set_state(Gst.State.PLAYING)
        # it's possible to hang here if the source is broken
        # but the main thread will keep running,
        # so we check both an explicit fail and a hang
        if pipeline.get_state(5 * 10**9)[0] != Gst.StateChangeReturn.SUCCESS:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("Failed to transition to playing state")

    def graceful_quit():
        logger.debug("Sending EOS.")
        # Terminate gracefully with EOS.
        # Directly setting it to null can cause videos to have timestamp issues
        eos_handled = pipeline.send_event(Gst.Event.new_eos())

        if not eos_handled:
            logger.error("EOS was not handled by the pipeline. ")
            pipeline.set_state(Gst.State.NULL)  # force stop
            main_loop.quit()
            return

        if not force_kill_timeout and run_n_seconds:
            bus_pop_timeout = run_n_seconds * 2
        else:
            bus_pop_timeout = force_kill_timeout

        time.sleep(1)

        # it's possible to immediately pop None (got EOS, but message is None)
        # so wait 1 second for the message to be constructed before popping
        eos_msg = bus.timed_pop_filtered(bus_pop_timeout, Gst.MessageType.EOS)
        pipeline.set_state(Gst.State.NULL)
        main_loop.quit()

        if eos_msg is None:
            # have to force system exit here,
            # GLib.Mainloop overrides the sys.excepthook
            raise SystemExit(
                "Did not receive EOS after {} seconds. ".format(
                    bus_pop_timeout
                )
                + "Pipeline likely hanged."
            )

    def quit():
        logger.debug("Setting state to NULL.")
        pipeline.set_state(Gst.State.NULL)
        main_loop.quit()
        # Must explicitly unref if ref_count is somehow not 1,
        # otherwise source is never released
        # not sure why graceful_quit doesn't need this
        if pipeline.ref_count > 1:
            pipeline.unref()

    for delay, call in intermediate_calls:
        assert run_n_seconds is None or delay < run_n_seconds, (
            "Delay for each call must be smaller than total run seconds, "
            " (Got delay = {}, run_n_seconds = {})".format(
                delay, run_n_seconds
            )
        )
        GLib.timeout_add_seconds(delay, call)

    if run_n_seconds is None:
        bus.add_signal_watch()
        bus.connect(
            "message",
            lambda _, msg: msg.type
            in (Gst.MessageType.EOS, Gst.MessageType.ERROR)
            and quit(),
        )
    else:
        GLib.timeout_add_seconds(run_n_seconds, graceful_quit)

    start()
    logger.info("[ OK ] Pipeline is playing!")
    main_loop.run()


def play_video(filepath: str):
    global Gtk
    if not Gtk:
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # type: ignore

        Gtk.init([])

    pipeline = Gst.parse_launch(
        " ! ".join(
            [
                "filesrc location={}".format(filepath),
                "decodebin",
                "videoconvert",
                "autovideosink",
            ]
        )
    )
    run_pipeline(pipeline)


def show_viewfinder(
    source: Gst.Element,
    *,
    show_n_seconds=5,
):
    """Shows a viewfinder for the given camera source

    :param source: camera source element.
        If there is any property that needs to be set,
        do that before calling this function
    :param show_n_seconds: number of seconds to keep the viewfinder on screen
    """
    global Gtk
    if not Gtk:
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # type: ignore

        Gtk.init([])

    partial_pipeline = " ! ".join(["videoconvert name=head", "autovideosink"])
    pipeline = Gst.parse_launch(partial_pipeline)  # type: Gst.Pipeline
    head = pipeline.get_by_name("head")

    assert pipeline.add(source)
    assert head
    assert source.link(head)

    logger.info(
        "[ OK ] Created pipeline for viewfinder: {} ! {}".format(
            elem_to_str(source), partial_pipeline
        )
    )
    run_pipeline(pipeline, show_n_seconds)


def take_photo(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    file_path: str,
    delay_seconds=0,
):
    """Take a photo using the source element

    :param source: The camera source element
    :param caps: Which capability to use for the source
        - If None, no caps filter will be inserted between source and decoder
    :param file_path: the path to the photo
    :param delay_seconds: number of seconds to keep the source "open"
        before taking the photo
    """

    # this may seem unorthodox
    # but it's way less verbose than creating individual elements
    str_elements = [
        'capsfilter name=source-caps caps="{}"',  # 0
        "decodebin",  # 1
        "videoconvert name=converter",  # 2
        "valve name=photo-valve drop=True",  # 4
        "jpegenc",  # 3
        "multifilesink location={}".format(file_path),  # 5
    ]
    head_elem_name = "source-caps"

    # using empty string as null values here
    # they are filtered out at parse_launch
    if caps:
        assert caps.is_fixed(), '"{}" is not fixed.'.format(caps.to_string())

        str_elements[0] = str_elements[0].format(caps.to_string())
        mime_type = caps.get_structure(0).get_name()  # type: str

        if mime_type == "image/jpeg":
            # decodebin has funny clock problem with live sources in image/jpeg
            str_elements[1] = "jpegdec"
        elif mime_type == "video/x-raw":
            # don't need a decoder for raw
            str_elements[1] = ""
        # else case is using decodebin as a fallback
    else:
        # decode bin doesn't work with video/x-raw
        str_elements[0] = str_elements[1] = str_elements[3] = ""
        head_elem_name = "converter"

    partial = " ! ".join(elem for elem in str_elements if elem)
    pipeline = Gst.parse_launch(partial)  # type: Gst.Pipeline
    head_elem = pipeline.get_by_name(head_elem_name)
    valve = pipeline.get_by_name("photo-valve")

    # parse the partial pipeline, then get head element by name
    assert pipeline.add(
        source
    ), "Could not add source element {} to the pipeline".format(
        elem_to_str(source)
    )
    assert head_elem and valve
    assert source.link(
        head_elem
    ), "Could not link source element to {}".format(head_elem)

    def open_valve():
        logging.debug("Opening valve!")
        valve.set_property("drop", False)

    logger.info(
        "Created photo pipeline with {} second delay. ".format(delay_seconds)
        + '"{} ! {}"'.format(elem_to_str(source), partial)
    )
    logging.debug("Setting playing state")

    run_pipeline(
        pipeline,
        delay_seconds + 1,  # workaround for now, weird problem with ref count
        intermediate_calls=[(delay_seconds, open_valve)],
    )

    logger.info("[ OK ] Photo was saved to {}".format(file_path))


def record_video(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    file_path: str,
    record_n_seconds=0,
):
    assert file_path.endswith(
        ".mkv"
    ), "This function uses matroskamux, so the filename must end in .mkv"

    str_elements = [
        'capsfilter name=source-caps caps="{}"',  # 0
        "decodebin",  # 1
        "videoconvert name=converter",  # 2
        "jpegenc",  # 3, avoid massiave uncompressed videos
        "matroskamux",  # 4
        "multifilesink location={}".format(file_path),  # 5
    ]

    head_elem_name = "source-caps"

    if caps:
        assert caps.is_fixed(), '"{}" is not fixed.'.format(caps.to_string())

        str_elements[0] = str_elements[0].format(caps.to_string())
        mime_type = caps.get_structure(0).get_name()  # type: str

        if mime_type == "image/jpeg":
            str_elements[1] = "jpegdec"
        elif mime_type == "video/x-raw":
            str_elements[1] = ""
    else:
        # decodebin doesn't work with video/x-raw
        str_elements[0] = str_elements[1] = ""
        head_elem_name = "converter"

    partial = " ! ".join(elem for elem in str_elements if elem)
    pipeline = Gst.parse_launch(partial)  # type: Gst.Pipeline
    head_elem = pipeline.get_by_name(head_elem_name)

    # parse the partial pipeline, then get head element by name
    assert pipeline.add(
        source
    ), "Could not add source element {} to the pipeline".format(
        elem_to_str(source)
    )
    assert head_elem
    assert source.link(
        head_elem
    ), "Could not link source element to {}".format(head_elem)

    logger.info(
        "[ OK ] Created video pipeline to record {} seconds".format(
            record_n_seconds
        )
    )
    logger.info("{} ! {}".format(elem_to_str(source), partial))
    logging.debug("Setting playing state")

    run_pipeline(pipeline, record_n_seconds)

    logger.info(
        "[ OK ] Video for this capability: "
        + "{}".format(caps.to_string() if caps else "[device default]")
        + " was saved to {}".format(file_path)
    )

    """record
    videotestsrc num-buffers=120 !
    queue !
    encodebin profile="video/quicktime,variant=iso:video/x-h264" !
    multifilesink location=video.mp4
    """
    """decode
    filesrc location=video.mp4 ! decodebin ! autovideosink
    """


def main():
    args = parse_args()
    print(args)

    if os.getuid() == 0:
        logger.warning(
            "Running this script as root. "
            "This may lead to different results than running as regular user."
        )

    if args.subcommand == "play-video":
        play_video(args.path)
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

    seconds_per_pipeline = (
        args.wait_seconds if args.subcommand == "take-photo" else args.seconds
    )
    logger.info("Found {} cameras!".format(len(devices)))
    print(
        '[ HINT ] For debugging, remove the "valve" element to get a pipeline',
        'that can be run with "gst-launch-1.0".',
        "Also keep the pipeline running for {} seconds".format(
            seconds_per_pipeline
        ),
    )

    for dev_i, device in enumerate(devices):
        dev_element = device.create_element()

        if args.subcommand == "show-viewfinder":
            show_viewfinder(dev_element, show_n_seconds=args.seconds)
            continue

        if not os.path.isdir(args.path):
            # must validate early, multifilesink does not check if the path exists
            raise FileNotFoundError(
                'Path "{}" does not exist'.format(args.path)
            )

        resolver = CapsResolver()
        all_fixed_caps = resolver.get_all_fixated_caps(
            device.get_caps(), "remap"
        )

        logger.info("Testing device {}/{}".format(dev_i + 1, len(devices)))
        logger.info(
            "Test for this device may take {} seconds for {} caps.".format(
                len(all_fixed_caps) * seconds_per_pipeline, len(all_fixed_caps)
            )
        )

        for cap_i, capability in enumerate(all_fixed_caps):
            cap_struct = capability.get_structure(0)
            if args.subcommand == "take-photo":
                logger.info(
                    "Taking a photo with capability: "
                    + '"{}"'.format(capability.to_string())
                    + "for device: "
                    + '"{}"'.format(device.get_display_name()),
                )
                file_path = "{}/photo_dev_{}_cap_{}.jpeg".format(
                    args.path, dev_i, cap_i
                )
                take_photo(
                    dev_element,
                    delay_seconds=args.wait_seconds,
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
                file_path = "{}/video_dev_{}_cap_{}.mkv".format(
                    args.path, dev_i, cap_i
                )
                record_video(
                    dev_element,
                    file_path=file_path,
                    caps=capability,
                    record_n_seconds=args.seconds,
                )

                if args.skip_validation:
                    continue

                MediaValidator.validate_video_info(
                    file_path,
                    expected_duration_seconds=args.seconds,
                    expected_width=cap_struct.get_int("width").value,
                    expected_height=cap_struct.get_int("height").value,
                    duration_tolerance_seconds=args.tolerance,
                )

    logger.info("[ OK ] All done!")


if __name__ == "__main__":
    Gst.init(None)
    GstPbutils.pb_utils_init()

    main()
