from enum import Enum
import gi
import typing as T
import logging


logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)s - %(message)s\n",
    datefmt="%m/%d %H:%M:%S",
)
logger.setLevel(logging.DEBUG)

from gi.repository import GObject  # type: ignore # noqa: E402

Gtk = None

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore # noqa: E402

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore # noqa: E402

TimeoutCallback = T.Callable[[], None]


class CapsResolver:

    INT32_MIN = -2147483648
    INT32_MAX = 2147483647

    # (top, bottom) or (numerator, denominator)
    FractionTuple = T.Tuple[int, int]
    RANGE_REMAP = {
        "width": [640, 1280, 1920, 2560, 3840],
        "height": [480, 720, 1080, 1440, 2160],
        "framerate": [
            (15, 1),
            (30, 1),
            (60, 1),
            (120, 1),
        ],  # 15fpx, 30fps, 60fps, 120fps
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

    def get_all_fixated_caps(
        self,
        caps: Gst.Caps,
        resolve_method: str,  # type T.Literal["remap", "limit"]
        limit: int = 10000,
    ) -> T.List[Gst.Caps]:
        """Gets all the fixated(1 value per property) caps from a Gst.Caps obj

        :param caps: a mixed Gst.Caps
        :param resolve_method: how to resolve IntRange and FractionRange values
        - Only applies to width, height, and framerate for now
        - "remap" => picks out a set of common values within the original range
        - "limit" => Use the caps.is_fixed while loop until we reaches limit

        :param limit: the limit to use for the "limit" resolver
        - if resolve method is remap, this is still in effect
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

                    finite_list = None  # type: GObject.ValueArray | None
                    if s_i.has_field_typed(prop, Gst.IntRange):
                        low, high = self.extract_int_range(s_i, prop)
                        finite_list = GObject.ValueArray()
                        for elem in self.remap_range_to_list(prop, low, high):
                            finite_list.append(elem)  # type: ignore

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
                                    "{}/{}".format(numerator, denominator)
                                    for (
                                        numerator,
                                        denominator,
                                    ) in fraction_list
                                ),
                            )
                        )[0]
                        # creates a struct of the form: temp, prop={30/1, 15/1}
                        # now we simply get the prop by name
                        finite_list = temp.get_list(prop)[1]

                    if finite_list is not None:
                        if finite_list.n_values == 0:
                            print(
                                "Resolve method is remap,"
                                "but original caps doesn't have any",
                                "of the common values.",
                                "Skipping.",
                            )
                        s_i.set_list(
                            prop,
                            finite_list,
                        )

                        caps_i = Gst.Caps.from_string(s_i.to_string())

            while not caps_i.is_fixed() and not caps_i.is_empty():
                if len(fixed_caps) >= limit:
                    break
                fixed_cap = caps_i.fixate()  # type: Gst.Caps
                if len(fixed_caps) != 0 and fixed_cap.is_equal(fixed_caps[-1]):
                    # if the caps is already seen
                    break
                fixed_caps.append(fixed_cap)
                caps_i = caps_i.subtract(fixed_cap)

            if caps_i.is_fixed():
                fixed_caps.append(caps_i)

        return fixed_caps


def elem_to_str(element: Gst.Element) -> str:
    """Prints an element to string
    - Excluding parent & client name

    :param element: GStreamer element
    :return: String representation
    """
    properties = element.list_properties()  # list[GObject.GParamSpec]
    element_name = element.get_factory().get_name()

    exclude = ["client-name"]
    prop_strings = []  # type: list[str]

    for prop in properties:
        if prop.name in exclude:
            continue

        try:
            prop_value = element.get_property(prop.name)
        except Exception:
            logger.debug(
                "Property {} is unreadable in {}, ignored.".format(
                    prop.name, element_name
                )  # not every property is readable, ignore unreadable ones
            )
            continue

        if hasattr(prop_value, "to_string") and callable(prop_value.to_string):
            # sometimes we have a nice to_string method, prioritize this
            prop_strings.append(
                "{}={}".format(prop.name, prop_value.to_string())
            )
        elif isinstance(prop, Enum):
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
    intermediate_calls: T.List[T.Tuple[int, TimeoutCallback]] = [],
):
    loop = GLib.MainLoop()
    remaining_timeouts = set()  # type: set[int]

    def gst_msg_handler(_, msg: Gst.Message):
        if msg.type == Gst.MessageType.EOS:
            logger.info("Received EOS")
            loop.quit()
            pipeline.set_state(Gst.State.NULL)

        if msg.type == Gst.MessageType.ERROR:
            logger.error(
                "Pipeline encountered an error, stopping. "
                + str(Gst.Message.parse_error(msg))
            )
            loop.quit()
            pipeline.set_state(Gst.State.NULL)

            for timeout in remaining_timeouts:
                # if the pipeline is terminated early, remove all timers
                # because loop.quit() won't remove those
                # that are already scheduled => segfault (EOS on null pipeline)
                # calling source_remove may produce warnings,
                # but won't stop normal execution
                GLib.source_remove(timeout)

        if msg.type == Gst.MessageType.WARNING:
            logger.warning(Gst.Message.parse_warning(msg))

    def send_eos():
        logger.debug("Sending EOS.")
        pipeline.send_event(Gst.Event.new_eos())

    if run_n_seconds:
        remaining_timeouts.add(
            GLib.timeout_add_seconds(run_n_seconds, send_eos)
        )

    for delay, call in intermediate_calls:
        assert run_n_seconds is None or delay < run_n_seconds, (
            "Delay for each call must be smaller than total run seconds, "
            " (Got delay = {}, run_n_seconds = {})".format(
                delay, run_n_seconds
            )
        )
        remaining_timeouts.add(GLib.timeout_add_seconds(delay, call))

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", gst_msg_handler)

    pipeline.set_state(Gst.State.PLAYING)
    source_state = pipeline.get_child_by_index(0).get_state(1 * Gst.SECOND)[0]
    if source_state != Gst.StateChangeReturn.SUCCESS:
        pipeline.set_state(Gst.State.NULL)
        raise RuntimeError(
            "Failed to transition to playing state. "
            "Source is still in {} state after 1 second.".format(source_state)
        )

    logger.info("[ OK ] Pipeline is playing!")
    loop.run()


def play_video(filepath: str):
    global Gtk
    if not Gtk:
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk as _Gtk  # type: ignore

        Gtk = _Gtk
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


def show_viewfinder(source: Gst.Element, *, show_n_seconds=5):
    """Shows a viewfinder for the given camera source

    :param source: camera source element.
        If there is any property that needs to be set,
        do that before calling this function
    :param show_n_seconds: number of seconds to keep the viewfinder on screen
    """
    global Gtk
    if not Gtk:
        gi.require_version("Gtk", "3.0")
        try:
            from gi.repository import Gtk as _Gtk  # type: ignore

            Gtk = _Gtk
            Gtk.init([])
        except ImportError:
            logger.error("Unable to import Gtk")
            return

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
    run_pipeline(
        pipeline,
        show_n_seconds,
    )


def take_photo(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    file_path: str,
    delay_seconds: int
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
        elif mime_type == "video/x-bayer":
            str_elements[1] = "bayer2rgb"
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
        logger.debug("Opening valve!")
        valve.set_property("drop", False)

    logger.info(
        "Created photo pipeline with {} second delay. ".format(delay_seconds)
        + '"{} ! {}"'.format(elem_to_str(source), partial)
    )
    logger.debug("Setting playing state")

    run_pipeline(
        pipeline,
        delay_seconds + 1,  # workaround for now, weird problem with ref count
        intermediate_calls=[
            (delay_seconds, open_valve),
        ],
    )

    logger.info("[ OK ] Photo was saved to {}".format(file_path))


def record_video(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    file_path: str,
    record_n_seconds: int,
    encoding_profile: str
):
    str_elements = [
        'capsfilter name=source-caps caps="{}"',  # 0
        "decodebin",  # 1
        "videoconvert name=converter",  # 2
        "encodebin profile={}".format(encoding_profile),
        "filesink location={}".format(file_path),  # 5
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
        elif mime_type == "video/x-bayer":
            # bayer2rgb is not considered a decoder
            # so decodebin can't automatically find this
            str_elements[1] = "bayer2rgb"
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
    logger.debug("Setting playing state")

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
