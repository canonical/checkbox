#! /usr/bin/python3

import sys
import gi
from argparse import ArgumentParser
import typing as T
import re

# https://github.com/TheImagingSource/tiscamera/blob/master/examples/python/00-list-devices.py

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore

Gst.init(None)


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
    for cap_str in caps.to_string().split(";"):
        mixed_caps = Gst.Caps.from_string(cap_str)
        while not mixed_caps.is_fixed():
            # keep fixiating it until it's fixed
            fixated_cap = mixed_caps.fixate()
            fixated_caps.append(fixated_cap)
            mixed_caps = mixed_caps.subtract(fixated_cap)
            # this is useful to get around missing types
            # in default gst python binding on ubuntu, like Gst.Fraction
        fixated_caps.append(mixed_caps)  # append tha final one

    return fixated_caps


def pipeline_add_many(pipeline: Gst.Pipeline, *elements: Gst.Element):
    for elem in elements:
        pipeline.add(elem)


def element_link_many(*elements: Gst.Element):
    elem_list = list(elements)
    for i in range(len(elem_list) - 1):
        assert Gst.Element.link(elem_list[i], elem_list[i + 1]), "not linked!"


def element_to_str(
    element: Gst.Element,
    exclude=["parent"],
    simple_elem=["jpegdec", "videoconvert", "videorate", "multifilesink"],
) -> str:
    """Stringifies the given element

    :param element: which element to convert to str
    :param exclude: which property names to exclude, defaults to ["parent"]
    :return: string usable in gst-launch-1.0
    """
    properties = element.list_properties()  # list[GObject.GParamSpec]
    element_name = element.get_factory().get_name()

    if element_name in simple_elem:
        return element_name

    prop_strings = []  # type: list[str]
    for prop in properties:
        if prop.name in exclude:
            continue
        prop_value = element.get_property(prop.name)
        if hasattr(prop_value, "to_string"):
            # sometimes we have a nice to_string method, prioritize this
            prop_strings.append(
                "{}={}".format(prop.name, prop_value.to_string())
            )
        else:
            prop_strings.append(
                "{}={}".format(prop.name, str(prop_value))
            )  # handle native python types
    return "{} {}".format(
        element_name, " ".join(prop_strings)
    )  # libcamerasrc name=cam_name location=p.jpeg


def parse_args():
    parser = ArgumentParser()


def take_photo(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    filename="/home/fgfg/photo",
    delay_seconds=0,
):
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
        elements["source-capsfilter"].set_property("caps", caps)
        # structure 0 is guaranteed to exist
        mime_type = caps.get_structure(0).get_name()  # type: str
        if mime_type == "image/jpeg":
            elements["decoder"] = Gst.ElementFactory.make("jpegdec")
            assert elements["decoder"] is not None
        elif mime_type == "video/x-raw":
            del elements["decoder"]
    else:
        del elements["source-capsfilter"]

    if delay_seconds > 0 and caps:
        elements["video-rate-capsfilter"].set_property(
            "caps",
            Gst.Caps.from_string(
                "video/x-raw,framerate=1/{}".format(delay_seconds)
            ),
        )
        # framerate=(fraction)30/1
        framerate_match = re.search(
            r"framerate=\(fraction\)(\d+)\/1", caps.to_string()
        )
        if framerate_match:
            num_buffers = delay_seconds * int(framerate_match.group(1))
            source.set_property("num-buffers", num_buffers)
            print("Dynamically computed num-buffers={}".format(num_buffers))
        else:
            source.set_property("num-buffers", 60)
            print(
                "Non standard framerate object: {}".format(caps.to_string()),
                "Defaulting to 60 buffers",
                file=sys.stderr,
            )

    else:
        del elements["source-capsfilter"]
        del elements["video-rate-capsfilter"]

    # link elements and create pipeline
    pipeline = Gst.Pipeline()  # type: Gst.Pipeline
    # add many does not exist in default ubuntu gst python binding
    pipeline_add_many(pipeline, source, *elements.values())
    element_link_many(source, *elements.values())

    # print("Created pipeline")
    # for elem in source, *elements.values():
    #     print(element_to_str(elem))
    #     print()

    main_loop = GLib.MainLoop.new(  # type: GLib.MainLoop
        None, False  # type: ignore
    )

    def eos_handler(_, message: Gst.Message):
        nonlocal pipeline
        if message.type == Gst.MessageType.EOS:
            print("We reached EOS!")
            # use closure here since this function must take 2 parameters
            # none of which can be the pipeline
            pipeline.set_state(Gst.State.NULL)
            main_loop.quit()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", eos_handler)

    print("Setting playing state")
    pipeline.set_state(Gst.State.PLAYING)

    main_loop.run()
    while main_loop.is_running():
        pass


def main():
    devices = get_devices()
    for di, device in enumerate(devices):
        caps = device.get_caps()
        for ci, cap in enumerate(get_all_fixated_caps(caps)):
            print(
                "Testing",
                cap.to_string(),
                "for device",
                device.get_display_name(),
            )
            take_photo(
                device.create_element(),
                delay_seconds=1,
                caps=cap,
                filename="/home/zhongning/fgfg/photo_dev{}_cap{}".format(
                    di, ci
                ),
            )


if __name__ == "__main__":
    main()
