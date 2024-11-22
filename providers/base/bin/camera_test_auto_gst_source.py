#! /usr/bin/python3

from enum import Enum
import sys
import gi
from argparse import ArgumentParser
import typing as T

# from checkbox_support.helpers.timeout import timeout
timeout = lambda _: lambda f: f

# https://github.com/TheImagingSource/tiscamera/blob/master/examples/python/00-list-devices.py


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # type: ignore

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore


Gst.init(None)
Gtk.init([])
main_loop = GLib.MainLoop.new(  # type: GLib.MainLoop
    None, False  # type: ignore
)


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
        # keep fixating it until it's fixed
        fixated_cap = caps.fixate()
        fixated_caps.append(fixated_cap)
        caps = caps.subtract(fixated_cap)
        # this is useful to get around missing types
        # in default gst python binding on ubuntu, like Gst.Fraction
    fixated_caps.append(caps)  # append the final one

    return fixated_caps


def parse_args():
    p = ArgumentParser()
    p.add_argument(
        "-s",
        "--wait-seconds",
        type=int,
        help="Number of seconds to keep the pipeline running "
        "before taking the photo. Default = 1",
        default=2,
    )
    p.add_argument(
        "-p",
        "--path",
        type=str,
        help="Where to save all the files",
        default="/home/ubuntu",
    )
    return p.parse_args()


def elem_to_str(element: Gst.Element) -> str:
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
            print(
                "[ INFO ] Property {} is unreadable in {}".format(
                    prop.name, element_name
                )
            )
            continue
        if hasattr(prop_value, "to_string"):
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


def run_pipeline(pipeline: Gst.Pipeline, run_n_seconds: int):
    @timeout(5)  # pipeline needs to start within 5 seconds
    def start():
        pipeline.set_state(Gst.State.PLAYING)
        # it's possible to hang here if the source is broken
        # but the main thread will keep running,
        # so we check both an explicit fail and a hang
        if pipeline.get_state(0)[0] == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to transition to playing state")

    def quit():
        pipeline.set_state(Gst.State.NULL)
        main_loop.quit()

    start()
    print("[ OK ] Pipeline is playing!")

    GLib.timeout_add_seconds(run_n_seconds, quit)

    main_loop.run()


def display_viewfinder(
    source: Gst.Element,
    *,
    show_n_seconds=5,
):
    partial_pipeline = "videoconvert name=head ! autovideosink name=sink"
    pipeline = Gst.parse_launch(partial_pipeline)  # type: Gst.Pipeline
    head = pipeline.get_by_name("head")
    print(pipeline.get_by_name("sink"))

    assert pipeline.add(source)
    assert head
    assert source.link(head)

    print(
        "[ OK ] Created pipeline: {} ! {}".format(
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
        - If none, no caps filter will be inserted between source and decoder
    :param file_path: the path to the photo
    :param delay_seconds: number of seconds to keep the pipeline running
        before taking the photo
    """

    # this may seem unorthodox
    # but it's way less verbose than creating individual elements
    str_elements = [
        'capsfilter name=source-caps caps="{}"',  # 0
        "decodebin",  # 1
        "videoconvert",  # 2
        "videorate",  # 3
        'capsfilter name=videorate-caps caps="video/x-raw,framerate=1/{}"',  # 4
        "jpegenc",  # 5
        "multifilesink location={}".format(file_path),  # 6
    ]

    # using empty string as null values here
    # they are filtered out at parse_launch
    if caps:
        assert caps.is_fixed(), '"{}" is not fixed.'.format(caps.to_string())
        str_elements[0] = str_elements[0].format(caps.to_string())
        mime_type = caps.get_structure(0).get_name()  # type: str
        if mime_type == "image/jpeg":
            # decodebin has funny clock problem with image/jpeg
            str_elements[1] = "jpegdec"
        elif mime_type == "video/x-raw":
            # don't need a decoder for raw
            str_elements[1] = ""
        # else case is using decodebin as a fallback

    if delay_seconds > 0:
        str_elements[4] = str_elements[4].format(delay_seconds)
    else:
        str_elements[3] = ""
        str_elements[4] = ""

    partial = " ! ".join(elem for elem in str_elements if elem != "")
    pipeline = Gst.parse_launch(partial)  # type: Gst.Pipeline

    assert pipeline.add(source)
    head_elem = pipeline.get_by_name("source-caps")
    assert head_elem
    assert source.link(head_elem)

    print(
        "[ OK ] Created pipeline: {} ! {}".format(elem_to_str(source), partial)
    )

    print("[ INFO ] Setting playing state")

    run_pipeline(pipeline, delay_seconds)

    print("[ OK ] Photo was saved to {}".format(file_path))


def main():
    args = parse_args()
    devices = get_devices()
    if len(devices) == 0:
        print(
            "GStreamer cannot find any cameras on this device.",
            "If you know a camera element exists, then it did not implement",
            "Gst.DeviceProvider to make itself visible to GStreamer",
            file=sys.stderr,
        )
        exit(1)

    print("Found {} cameras!".format(len(devices)))
    for dev_i, device in enumerate(devices):
        caps = device.get_caps()
        for cap_i, capability in enumerate(get_all_fixated_caps(caps)):
            print(
                "[ INFO ] Testing",
                '"{}"'.format(capability.to_string()),
                "for device",
                '"{}"'.format(device.get_display_name()),
            )
            take_photo(
                device.create_element(),
                delay_seconds=args.wait_seconds,
                caps=capability,
                file_path="{}/photo_dev{}_cap{}.jpeg".format(
                    args.path, dev_i, cap_i
                ),
            )
            break
        display_viewfinder(device.create_element())


if __name__ == "__main__":
    main()
