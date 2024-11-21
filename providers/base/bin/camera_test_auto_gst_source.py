#! /usr/bin/python3

from enum import Enum
import sys
import gi
from argparse import ArgumentParser
import typing as T
import re

from checkbox_support.helpers.timeout import timeout

# https://github.com/TheImagingSource/tiscamera/blob/master/examples/python/00-list-devices.py

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore

Gst.init(None)
main_loop = GLib.MainLoop.new(  # type: GLib.MainLoop
    None, False  # type: ignore
)


class ElementPrinter:
    included_properties = {
        "capsfilter": ("caps",),
        "multifilesink": ("location",),
    }
    global_exclude_keys = ("parent", "client-name", "fd")
    simple_elements = (
        "videoconvert",
        "decodebin",
        "videorate",
        "jpegenc",
        "jpegdec",
    )

    @staticmethod
    def print(element: Gst.Element):
        properties = element.list_properties()  # list[GObject.GParamSpec]
        element_name = element.get_factory().get_name()

        if element_name in ElementPrinter.simple_elements:
            return element_name

        print_full = element_name not in ElementPrinter.included_properties

        prop_strings = []  # type: list[str]
        for prop in properties:
            if (
                not print_full
                and prop.name
                not in ElementPrinter.included_properties[element_name]
            ):
                continue
            if prop.name in ElementPrinter.global_exclude_keys:
                continue
            prop_value = element.get_property(prop.name)
            if prop.name == "caps":
                # need to double quote the caps
                prop_strings.append(
                    '{}="{}"'.format(prop.name, prop_value.to_string())
                )
            elif hasattr(prop_value, "to_string"):
                # sometimes we have a nice to_string method, prioritize this
                prop_strings.append(
                    "{}={}".format(prop.name, prop_value.to_string())
                )
            elif type(prop_value) is Enum:
                prop_strings.append(
                    "{}={}".format(prop.name, prop_value.value)
                )
            else:
                prop_strings.append(
                    "{}={}".format(prop.name, str(prop_value))
                )  # handle native python types
        return "{} {}".format(
            element_name, " ".join(prop_strings)
        )  # libcamerasrc name=cam_name location=p.jpeg


def get_devices() -> T.List[Gst.Device]:
    monitor = Gst.DeviceMonitor.new()  # type: Gst.DeviceMonitor
    monitor.add_filter("Video/Source")
    monitor.start()

    devices = monitor.get_devices()

    monitor.stop()
    return devices


def get_all_fixated_caps(caps: Gst.Caps) -> T.List[Gst.Caps]:
    """Gets all the fixated(unique) caps from a Gst.Caps object

    :param caps: A mixed Gst.Caps
    """
    fixated_caps = []
    while not caps.is_fixed():
        # keep fixiating it until it's fixed
        fixated_cap = caps.fixate()
        fixated_caps.append(fixated_cap)
        caps = caps.subtract(fixated_cap)
        # this is useful to get around missing types
        # in default gst python binding on ubuntu, like Gst.Fraction
    fixated_caps.append(caps)  # append tha final one

    return fixated_caps


def pipeline_add_many(
    pipeline: Gst.Pipeline, elements: T.Iterable[Gst.Element]
):
    for elem in elements:
        pipeline.add(elem)


def element_link_many(elements: T.Iterable[Gst.Element]):
    elem_list = list(elements)
    for i in range(len(elem_list) - 1):
        elem1, elem2 = elem_list[i], elem_list[i + 1]
        is_linked = Gst.Element.link(elem1, elem2)
        if not is_linked:
            if elem1.get_factory().get_name() == "decodebin":
                e2_copy = elem2  # force a reference copy

                def on_pad_added(
                    decodebin: Gst.Element, decodebin_src: Gst.Pad
                ):
                    print("\n\ndecode bin pad added\n\n")
                    e2_name = e2_copy.get_factory().get_name()
                    e2_sink = e2_copy.get_static_pad("sink")
                    assert e2_sink, "Null sink"
                    assert decodebin.link(e2_copy), f"cannot link to {e2_name}"
                    print("Linked decodebin to {}".format(e2_name))

                elem1.connect("pad-added", on_pad_added)
            else:
                raise RuntimeError(
                    "{} and {} could not be linked!".format(
                        ElementPrinter.print(elem1),
                        ElementPrinter.print(elem2),
                    )
                )


def parse_args():
    p = ArgumentParser()
    p.add_argument(
        "-s",
        "--wait-seconds",
        type=int,
        help="Number of seconds to keep the pipeline running "
        "before taking the photo. Default = 1",
        default=1,
    )
    return p.parse_args()


def take_photo(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    filename="/home/fgfg/photo",
    delay_seconds=0,
):
    """Take a photo using the source element

    :param source: The camera source element
    :param caps: Which capability to use for the source
        - If none, no caps filter will be inserted between source and decoder
    :param filename: the path to the photo
    :param delay_seconds: number of seconds to keep the pipeline running
        before taking the photo
    """
    # key is the name, value is the element. Ordered
    elements = {
        "source-capsfilter": Gst.ElementFactory.make(
            "capsfilter", "source-capsfilter"
        ),
        "decoder": Gst.ElementFactory.make("decodebin"),
        "videoconvert": Gst.ElementFactory.make("videoconvert"),
        "videorate": Gst.ElementFactory.make("videorate"),
        "video-rate-capsfilter": Gst.ElementFactory.make(
            "capsfilter", "video-rate-capsfilter"
        ),
        "jpegenc": Gst.ElementFactory.make("jpegenc"),
        "multifilesink": Gst.ElementFactory.make("multifilesink"),
    }  # type: dict[str, Gst.Element]
    assert all(element is not None for element in elements.values())

    # set properties
    elements["multifilesink"].set_property(
        "location", "{}.jpeg".format(filename)
    )

    if caps:
        assert caps.is_fixed(), '"{}" is not fixed.'.format(caps.to_string())
        elements["source-capsfilter"].set_property("caps", caps)
        # structure 0 is guaranteed to exist
        mime_type = caps.get_structure(0).get_name()  # type: str
        if mime_type == "image/jpeg":
            # decodebin has funny clock problem with image/jpeg
            elements["decoder"] = Gst.ElementFactory.make("jpegdec")
        assert elements["decoder"] is not None
        if mime_type == "video/x-raw":
            # don't need a decoder for raw
            del elements["decoder"]
        # else case is using decodebin as a fallback
    else:
        # remove the initial capsfilter if unused
        del elements["source-capsfilter"]

    if delay_seconds > 0 and caps:
        elements["video-rate-capsfilter"].set_property(
            "caps",
            Gst.Caps.from_string(
                "video/x-raw,framerate=1/{}".format(delay_seconds)
            ),
        )
        # framerate=(fraction)30/1, we can assume this format
        # because caps is fixated
        framerate_match = re.search(
            r"framerate=\(fraction\)(\d+)\/1", caps.to_string()
        )
        if framerate_match is not None:
            num_buffers = delay_seconds * int(framerate_match.group(1))
            source.set_property("num-buffers", num_buffers)
            print(
                "[ INFO ] Dynamically computed",
                "num-buffers={} to delay {} seconds".format(
                    num_buffers, delay_seconds
                ),
            )
        else:
            source.set_property("num-buffers", 60)
            print(
                "[ ERR ] Non standard framerate object: {}".format(
                    caps.to_string()
                ),
                "Defaulting to 60 buffers",
                file=sys.stderr,
            )

    else:
        del elements["source-capsfilter"]
        del elements["video-rate-capsfilter"]

    # link elements and create pipeline
    final_elements = (source, *elements.values())
    pipeline = Gst.Pipeline()
    # Gst.Pipeline.add_many and Gst.Element.link_many
    # do not exist in default ubuntu gst python binding
    pipeline_add_many(pipeline, final_elements)
    element_link_many(final_elements)

    print("Created pipeline: ")
    print(" ! ".join(ElementPrinter.print(e) for e in final_elements))

    def eos_handler(_, message: Gst.Message):
        nonlocal pipeline
        if message.type == Gst.MessageType.EOS:
            print("[ OK ] We reached EOS!")
            # use closure here since this function must take 2 parameters
            # none of which can be the pipeline
            pipeline.set_state(Gst.State.NULL)
            main_loop.quit()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", eos_handler)

    @timeout(delay_seconds + 5)
    def run():
        print("Setting playing state")
        pipeline.set_state(Gst.State.PLAYING)
        if pipeline.get_state(0)[0] == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to transition to playing state")

        print("Playing!")
        main_loop.run()
        while main_loop.is_running():
            pass

    run()


def main():
    args = parse_args()
    devices = get_devices()
    if len(devices) == 0:
        print(
            "GStreamer cannot find any cameras on this device.",
            file=sys.stderr,
        )
        exit(1)

    print("Found {} cameras!".format(len(devices)))
    for dev_i, device in enumerate(devices):
        caps = device.get_caps()
        for cap_i, capability in enumerate(get_all_fixated_caps(caps)):
            print(
                "[ INFO ] Testing",
                capability.to_string(),
                "for device",
                device.get_display_name(),
            )
            take_photo(
                device.create_element(),
                delay_seconds=args.wait_seconds,
                caps=capability,
                filename="/home/zhongning/fgfg/photo_dev{}_cap{}".format(
                    dev_i, cap_i
                ),
            )


if __name__ == "__main__":
    main()
