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
    KNOWN_RANGE_VALUES = {
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
    def select_known_values_from_range(
        self, prop: str, low: int, high: int
    ) -> T.List[int]: ...

    @T.overload
    def select_known_values_from_range(
        self, prop: str, low: FractionTuple, high: FractionTuple
    ) -> T.List[FractionTuple]: ...

    def select_known_values_from_range(
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
            prop in self.KNOWN_RANGE_VALUES
        ), "Property {} does not have a known value definition".format(prop)

        for val in self.KNOWN_RANGE_VALUES[prop]:
            # lt gt are defined as pairwise comparison on tuples
            if val >= low and val <= high:
                out.append(val)

        return out

    def get_all_fixated_caps(
        self,
        caps: Gst.Caps,
        resolve_method: str,  # type T.Literal["known_values", "limit"]
        limit: int = 10000,
    ) -> T.List[Gst.Caps]:
        """Gets all the fixated(1 value per property) caps from a Gst.Caps obj

        :param caps: a mixed Gst.Caps
        :param resolve_method: how to resolve IntRange and FractionRange values
        - Only applies to width, height, and framerate for now
        - "known_values" => picks out known values within the original range
        - "limit" => Use the caps.is_fixed while loop until we reaches limit

        :param limit: the limit to use for the "limit" resolver
        - if resolve method is known_values, this is still in effect
        :return: a list of fixed caps
        """
        if caps.is_fixed():
            return [caps]

        fixed_caps = []  # type: list[Gst.Caps]

        for i in range(caps.get_size()):
            struct = caps.get_structure(i)

            if resolve_method == "known_values":
                for prop in self.KNOWN_RANGE_VALUES.keys():

                    finite_list = None  # type: GObject.ValueArray | None
                    if struct.has_field_typed(prop, Gst.IntRange):
                        low, high = self.extract_int_range(struct, prop)
                        finite_list = GObject.ValueArray()
                        for elem in self.select_known_values_from_range(
                            prop, low, high
                        ):
                            finite_list.append(elem)

                    elif struct.has_field_typed(prop, Gst.FractionRange):
                        low, high = self.extract_fraction_range(struct, prop)
                        fraction_list = self.select_known_values_from_range(
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
                            logger.debug(
                                "Resolve method is known_values,"
                                "but original caps doesn't have any",
                                "of the common values.",
                                "Skipping.",
                            )
                        struct.set_list(
                            prop,
                            finite_list,
                        )

                        caps_i = Gst.Caps.from_string(struct.to_string())

            caps_i = Gst.Caps.from_string(struct.to_string())  # type: Gst.Caps
            while not caps_i.is_fixed() and not caps_i.is_empty():
                if len(fixed_caps) >= limit:
                    break
                fixed_cap = caps_i.fixate()  # type: Gst.Caps
                if len(fixed_caps) != 0 and fixed_cap.is_equal(fixed_caps[-1]):
                    # if the caps is already seen last time,
                    # we are probably stuck at an unresolvable value
                    # can happen e.g when we have framerate = [1/3, 1/4]
                    # - doesn't contain any known value
                    # - fixate() will keep returning the same thing
                    # - subtract() does nothing
                    break
                fixed_caps.append(fixed_cap)
                caps_i = caps_i.subtract(fixed_cap)

            if caps_i.is_fixed():
                fixed_caps.append(caps_i)

        return fixed_caps


def elem_to_str(
    element: Gst.Element, exclude: T.List[str] = ["parent", "client-name"]
) -> str:
    """Prints an element to string

    :param element: GStreamer element
    :param exclude: property names to exclude
    :return: String representation. This is a best guess for debug purposes,
        not 100% accurate since there can be arbitrary objects in properties.
    """
    properties = element.list_properties()  # list[GObject.GParamSpec]
    element_name = element.get_factory().get_name()

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
    custom_quit_handler: T.Optional[T.Callable[[Gst.Message], bool]] = None,
):
    """Runs a GStreamer pipeline and handle Gst messages

    :param pipeline: the pipeline to run
    :param run_n_seconds: Number of seconds to run the pipeline
        before sending EOS, defaults to None
        - If None, only wait for an EOS signal
    :param intermediate_calls: list of functions to run
        while the pipeline is running
        - Each element is a (delay, callback) tuple
        - Delay is the number of seconds to wait
            (relative to the start of the pipeline) before calling the callback
    :param custom_quit_handler: quit the pipeline if this function returns true
    :raises RuntimeError: if the source element did not transition to playing
        state in 500ms after set_state(PLAYING) is called
    """
    loop = GLib.MainLoop()
    timeout_sources = set()  # type: set[GLib.Source]

    assert (
        run_n_seconds is None or run_n_seconds >= 1
    ), "run_n_seconds must be >= 1 if specified"

    def gst_msg_handler(_, msg: Gst.Message):
        should_quit = False

        if msg.type == Gst.MessageType.WARNING:
            logger.warning(Gst.Message.parse_warning(msg))

        if msg.type == Gst.MessageType.EOS:
            logger.debug("Received EOS.")
            should_quit = True

        if msg.type == Gst.MessageType.ERROR:
            logger.error(
                "Pipeline encountered an error, stopping. "
                + str(Gst.Message.parse_error(msg))
            )
            should_quit = True

        if custom_quit_handler:
            should_quit = custom_quit_handler(msg)

        if should_quit:
            loop.quit()
            pipeline.set_state(Gst.State.NULL)
            for timeout in timeout_sources:
                # if the pipeline is terminated early, remove all timers asap
                # because loop.quit() won't remove/stop those
                # that are already scheduled => segfault (EOS on null pipeline)
                # See: https://docs.gtk.org/glib/method.MainLoop.quit.html
                timeout.destroy()

    def send_eos():
        logger.debug("Sending EOS.")
        pipeline.send_event(Gst.Event.new_eos())

    if run_n_seconds:
        eos_timeout_id = GLib.timeout_add_seconds(run_n_seconds, send_eos)
        # get the actual source object, so we can call .destroy() later.
        # Removing a timeout by id will cause warnings if it doesn't exist,
        # but destroying an already destroyed source is ok
        # See: https://docs.gtk.org/glib/method.Source.destroy.html
        # and: https://docs.gtk.org/glib/type_func.Source.remove.html
        timeout_sources.add(
            loop.get_context().find_source_by_id(eos_timeout_id)
        )

    for delay, call in intermediate_calls:
        assert run_n_seconds is None or delay < run_n_seconds, (
            "Delay for each call must be smaller than total run seconds, "
            " (Got delay = {} for {}, run_n_seconds = {})".format(
                delay, call.__name__, run_n_seconds
            )
        )
        timeout_id = GLib.timeout_add_seconds(delay, call)
        timeout_sources.add(loop.get_context().find_source_by_id(timeout_id))

    bus = pipeline.get_bus()
    assert bus
    bus.add_signal_watch()
    bus.connect("message", gst_msg_handler)

    pipeline.set_state(Gst.State.PLAYING)

    source_state_change_result = pipeline.get_child_by_index(0).get_state(
        500 * Gst.MSECOND
    )
    # get_state returns a 3-tuple
    # (Gst.StateChangeReturn, curr_state: Gst.State, target_state: Gst.State)
    # the 1st element isn't named, so we must access by index
    if source_state_change_result[0] != Gst.StateChangeReturn.SUCCESS:
        pipeline.set_state(Gst.State.NULL)
        raise RuntimeError(
            "Failed to transition to playing state. "
            + "Source is still in {} state after 500ms, ".format(
                source_state_change_result.state
            )
            + "was trying to transition to {}".format(
                source_state_change_result.pending
            )
        )

    logger.info("[ OK ] Pipeline is playing!")
    loop.run()


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


def msg_is_multifilesink_save(msg: Gst.Message) -> bool:
    """Returns true when multifilesink saves a buffer

    :param msg: the GstMessage object
    :return: whether msg is a multifilesink save message
    """
    if msg.type == Gst.MessageType.ELEMENT:
        struct = msg.get_structure()
        return (
            struct is not None
            and struct.get_name() == "GstMultiFileSink"
            and struct.has_field("filename")
        )
    else:
        return False


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
        "valve name=photo-valve drop=True",  # 3
        "jpegenc",  # 4
        "multifilesink post-messages=True location={}".format(file_path),  # 5
    ]
    head_elem_name = "source-caps"

    # using empty string as null values here
    # they are filtered out at parse_launch
    if caps:
        assert caps.is_fixed(), '"{}" is not fixed.'.format(caps.to_string())

        str_elements[0] = str_elements[0].format(caps.to_string())
        mime_type = caps.get_structure(0).get_name()  # type: str

        if mime_type == "image/jpeg":
            # decodebin has a clock problem with pipewiresrc
            # that outputs image/jpeg
            str_elements[1] = "jpegdec"
        elif mime_type == "video/x-raw":
            # don't need a decoder for raw
            str_elements[1] = ""
        elif mime_type == "video/x-bayer":
            # bayer2rgb is not considered a decoder
            # so decodebin can't automatically find this
            str_elements[1] = "bayer2rgb"
        # else case is using decodebin as a fallback
    else:
        # decode bin doesn't work with video/x-raw
        str_elements[0] = str_elements[1] = str_elements[3] = ""
        head_elem_name = "converter"

    delay_seconds = max(delay_seconds, 0)
    if delay_seconds == 0:
        str_elements[3] = ""

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

    if delay_seconds == 0:
        intermediate_calls = []
        logger.info(
            "Created photo pipeline with no delay. "
            + '"{} ! {}"'.format(elem_to_str(source), partial)
        )
    else:
        valve = pipeline.get_by_name("photo-valve")

        def open_valve():
            assert valve
            logger.debug("Opening valve!")
            valve.set_property("drop", False)

        intermediate_calls = [(delay_seconds, open_valve)]
        logger.info(
            "Created photo pipeline with {} second delay. ".format(
                delay_seconds
            )
            + '"{} ! {}"'.format(elem_to_str(source), partial)
        )

    run_pipeline(
        pipeline,
        intermediate_calls=intermediate_calls,
        custom_quit_handler=msg_is_multifilesink_save,
    )

    logger.info(
        "[ OK ] Photo pipeline for this capability: "
        + "{}".format(caps.to_string() if caps else "device default")
        + " has finished!"
    )


def record_video(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    file_path: str,
    record_n_seconds: int,
    encoding_profile: str
):
    assert record_n_seconds >= 1, (
        "Recording pipeline must run for at least 1 second. "
        "Got {} seconds.".format(record_n_seconds)
    )

    str_elements = [
        'capsfilter name=source-caps caps="{}"',  # 0
        "decodebin",  # 1
        "videoconvert name=converter",  # 2
        "encodebin profile={}".format(encoding_profile),  # 3
        "filesink location={}".format(file_path),  # 4
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
            str_elements[1] = "bayer2rgb"
    else:
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
        "[ OK ] Created video pipeline to record {} seconds: ".format(
            record_n_seconds
        )
        + '"{} ! {}"'.format(elem_to_str(source), partial)
    )

    run_pipeline(pipeline, record_n_seconds)

    logger.info(
        "[ OK ] Recording pipeline for this capability: "
        + "{}".format(caps.to_string() if caps else "device default")
        + " has finished!"
    )
