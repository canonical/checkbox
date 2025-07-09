# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Zhongning Li <zhongning.li@canonical.com>
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


from collections import OrderedDict
import gi
import typing as T
import logging
from pathlib import Path

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
PipelineQuitHandler = T.Callable[[Gst.Message], bool]


def get_launch_line(device: Gst.Device) -> T.Optional[str]:
    """Get the gst-device-monitor launch line for a device.
    - Useful for pipelines that don't need to do anything special
        while the pipeline is running
    - This basically re-implements the one in the cli
    https://github.com/GStreamer/gst-plugins-base/blob/master/tools/gst-device-monitor.c#L46 # noqa: E501

    :param device: the device given by Gst.DeviceMonitor
    :return: the gst-launch-1.0 launchline. Note that this only starts with the
    element name, not "gst-launch-1.0" like you would see in the cli
    """
    ignored_prop_names = set(
        ["name", "parent", "direction", "template", "caps"]
    )  # type: set[str]
    element = device.create_element()
    if element is None:
        return None

    factory = element.get_factory()
    if factory is None:
        return None

    factory_name = factory.get_name()
    if factory_name is None:
        return None

    pure_element = Gst.ElementFactory.make(factory_name, None)
    if pure_element is None:
        return None

    launch_line_components = [factory_name]  # type: list[str]
    for prop in element.list_properties():
        if prop.name in ignored_prop_names:
            continue
        # eliminate all default properties and non-read-writable props
        read_and_writable = (
            prop.flags & GObject.PARAM_READWRITE == GObject.PARAM_READWRITE
        )
        if not read_and_writable:
            continue

        default_value = pure_element.get_property(prop.name)
        actual_value = element.get_property(prop.name)

        if (
            actual_value is not None
            and default_value is not None
            and Gst.value_compare(default_value, actual_value)
            == Gst.VALUE_EQUAL
        ):
            continue

        if actual_value is None:
            continue

        # now we only have the non-default, non-null values
        try:
            serialized_value = Gst.value_serialize(actual_value)
        except Exception:
            # unserializable values sometimes can throw
            # such as non-int32 integers
            continue
        if not serialized_value:
            continue  # ignore non-serializable ones

        launch_line_components.append(
            "{}={}".format(prop.name, serialized_value)
        )

    # example: pipewiresrc target-object=49
    return " ".join(launch_line_components)


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
    element_name = element.get_factory().get_name()  # type: ignore

    prop_strings = []  # type: list[str]

    for prop in properties:
        if prop.name in exclude:
            continue

        try:
            prop_value = element.get_property(prop.name)
        except TypeError:
            logger.debug(
                "Property {} is unreadable in {}, ignored.".format(
                    prop.name, element_name
                )  # not every property is readable, ignore unreadable ones
            )
            continue

        if prop_value is None:
            continue

        try:
            serialized_value = Gst.value_serialize(prop_value)
        except Exception:
            # unserializable values sometimes can throw
            # such as non-int32 integers
            continue
        if not serialized_value:
            continue

        prop_strings.append(
            "{}={}".format(prop.name, serialized_value)
        )  # handle native python types

    return "{} {}".format(
        element_name, " ".join(prop_strings)
    )  # libcamerasrc name=cam_name location=p.jpeg


def gst_msg_handler(
    _: Gst.Bus,
    msg: Gst.Message,
    pipeline: Gst.Pipeline,
    custom_quit_handler: T.Optional[PipelineQuitHandler],
    loop: GLib.MainLoop,
    timeout_sources: T.List[GLib.Source] = [],
):
    should_quit = False

    if custom_quit_handler:
        # has the lowest precedence, ERROR and EOS will always take over
        should_quit = custom_quit_handler(msg)

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

    if should_quit:
        for timeout in timeout_sources:
            # if the pipeline is terminated early, remove all timers asap
            # because loop.quit() won't remove/stop those
            # that are already scheduled => segfault (EOS on null pipeline)
            # See: https://docs.gtk.org/glib/method.MainLoop.quit.html
            timeout.destroy()

        # NOTE: setting NULL can be slow on certain encoders
        # NOTE: it's also possible to block infinitely here
        pipeline.set_state(Gst.State.NULL)
        loop.quit()


def run_pipeline(
    pipeline: Gst.Pipeline,
    run_n_seconds: T.Optional[int] = None,
    intermediate_calls: T.List[T.Tuple[int, TimeoutCallback]] = [],
    custom_quit_handler: T.Optional[PipelineQuitHandler] = None,
):
    """Run a GStreamer pipeline and handle Gst messages (blocking)

    :param pipeline: the pipeline to run
    :param run_n_seconds: Number of seconds to run the pipeline before
        sending EOS, defaults to None
        - If None, only register the EOS handler
    :param intermediate_calls: functions to run while the pipeline is running
        - Each element is a (delay, callback) tuple
        - Delay is the number of seconds to wait
            (relative to the start of the pipeline) before calling the callback
    :param custom_quit_handler: quit the pipeline if this function returns true
        - Has lowest precedence
    :raises RuntimeError: if the source element did not transition to playing
        state in 5s after set_state(PLAYING) is called
    """
    loop = GLib.MainLoop()
    timeout_sources = []  # type: list[GLib.Source]

    if run_n_seconds is not None and run_n_seconds < 1:
        raise ValueError("run_n_seconds must be >= 1 if specified")

    if run_n_seconds:

        def send_eos():
            logger.debug("Sending EOS.")
            pipeline.send_event(Gst.Event.new_eos())

        eos_timeout_id = GLib.timeout_add_seconds(run_n_seconds, send_eos)
        # get the actual source object, so we can call .destroy() later.
        # Removing a timeout by id will cause warnings if it doesn't exist,
        # but destroying an already destroyed source is ok
        # See: https://docs.gtk.org/glib/method.Source.destroy.html
        # and: https://docs.gtk.org/glib/type_func.Source.remove.html
        timeout_sources.append(
            loop.get_context().find_source_by_id(eos_timeout_id)
        )

    for delay, intermediate_call in intermediate_calls:
        if run_n_seconds is not None and delay > run_n_seconds:
            raise ValueError(
                "Delay for each call must be smaller than total run seconds, "
                " (Got delay = {} for {}, run_n_seconds = {})".format(
                    delay, intermediate_call.__name__, run_n_seconds
                )
            )

        timeout_id = GLib.timeout_add_seconds(delay, intermediate_call)
        timeout_sources.append(
            loop.get_context().find_source_by_id(timeout_id)
        )

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect(
        "message",
        gst_msg_handler,
        pipeline,
        custom_quit_handler,
        loop,
        timeout_sources,
    )

    pipeline.set_state(Gst.State.PLAYING)

    try:
        # just a debugging message
        src_elem = pipeline.get_child_by_index(0)
        if isinstance(src_elem, Gst.Element):
            src_elem.iterate_src_pads().foreach(
                lambda pad: pad.get_current_caps()  # can be None
                and logger.info(
                    'The negotiated caps of the source "{}" is: "{}"'.format(
                        src_elem.name, pad.get_current_caps().to_string()
                    )
                )
            )
    except Exception:
        pass
    # this does not necessarily mean that the pipeline has the PLAYING state
    # it just means that set_state didn't hang
    logger.info("[ OK ] Pipeline is playing!")
    loop.run()


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
    file_path: Path,
    delay_seconds: int,
    caps: T.Optional[Gst.Caps] = None,
):
    """Take a photo using the source element

    :param source: The camera source element
    :param caps: Which capability to use for the source
        - If None, no caps filter will be inserted between source and decoder
    :param file_path: the path to the photo
    :param delay_seconds: number of seconds to keep the source "open"
        before taking the photo
    """

    # dict order is not guaranteed on python < 3.7
    str_elements = OrderedDict(
        (
            ("caps", 'capsfilter name=source-caps caps="{}"'),
            ("decoder", "decodebin"),
            ("converter", "videoconvert name=converter"),
            ("photo-valve", "valve name=photo-valve drop=True"),
            ("encoder", "jpegenc"),
            (
                "sink",
                "multifilesink post-messages=True location={}".format(
                    str(file_path)
                ),
            ),
        )
    )
    head_elem_name = "source-caps"

    # using empty string as null values here
    # they are filtered out at parse_launch
    if caps:
        if not caps.is_fixed():
            raise ValueError('"{}" is not fixed.'.format(caps.to_string()))

        str_elements["caps"] = str_elements["caps"].format(caps.to_string())
        mime_type = caps.get_structure(0).get_name()

        if mime_type == "image/jpeg":
            # decodebin has a clock problem with pipewiresrc
            # that outputs image/jpeg
            str_elements["decoder"] = "jpegdec"
        elif mime_type == "video/x-raw":
            # don't need a decoder for raw
            str_elements["decoder"] = ""
        elif mime_type == "video/x-bayer":
            # bayer2rgb is not considered a decoder
            # so decodebin can't automatically find this
            str_elements["decoder"] = "bayer2rgb"
        # else case is using decodebin as a fallback
    else:
        # decode bin doesn't work with video/x-raw
        str_elements["caps"] = str_elements["decoder"] = ""
        head_elem_name = "converter"

    delay_seconds = max(delay_seconds, 0)
    if delay_seconds == 0:
        str_elements["photo-valve"] = ""

    partial = " ! ".join(elem for elem in str_elements.values() if elem)
    pipeline = Gst.parse_launch(partial)

    if type(pipeline) is not Gst.Pipeline:
        raise TypeError(
            "Unexpected return type from parse_launch: Got {}".format(
                type(pipeline)
            )
        )

    head_elem = pipeline.get_by_name(head_elem_name)

    # parse the partial pipeline, then get head element by name
    # NOTE: this assertion only applies to the default python binding
    # if the python3-gst-1.0 package is installed, .add() always return None
    if not pipeline.add(source):
        raise RuntimeError(
            "Could not add source element {} to the pipeline".format(
                elem_to_str(source)
            )
        )

    if not head_elem or not source.link(head_elem):
        raise RuntimeError(
            "Could not link source element to {}".format(head_elem)
        )

    if delay_seconds == 0:
        intermediate_calls = []
        logger.info(
            "Created photo pipeline with no delay. "
            + '"{} ! {}"'.format(elem_to_str(source), partial)
        )
    else:
        valve = pipeline.get_by_name("photo-valve")
        assert valve

        def open_valve():
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

    # NOTE: reaching here just means the pipeline successfully stopped
    # not necessarily stopped gracefully

    logger.info(
        "[ OK ] Photo pipeline for this capability: {}".format(
            caps.to_string() if caps else "device default"
        )
        + " has finished!"
    )

    # unparent the source, so that this function can be called again
    source.unparent()
