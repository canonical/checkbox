#! /usr/bin/python3

from enum import Enum
import os
import time
import gi
from argparse import ArgumentParser
import typing as T
import logging

VoidFn = T.Callable[[], None]  # takes nothing and returns nothing

# https://github.com/TheImagingSource/tiscamera/blob/master/examples/python/00-list-devices.py

logging.basicConfig(
    format="%(asctime)s %(levelname)s - %(message)s",
    datefmt="%m/%d %H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


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
    """Gets all the fixated(1 value per property) caps from a Gst.Caps object

    :param caps: A mixed Gst.Caps
    """
    fixed_caps = []
    while not caps.is_fixed():
        # keep fixating it until it's fixed
        fixed_cap = caps.fixate()
        fixed_caps.append(fixed_cap)
        caps = caps.subtract(fixed_cap)
        # this is useful to get around missing types
        # in default gst python binding on ubuntu, like Gst.Fraction
    fixed_caps.append(caps)  # append the final one

    return fixed_caps


def parse_args():
    p = ArgumentParser()
    p.add_argument(
        "-ws",
        "--wait-seconds",
        type=int,
        help="Number of seconds to keep the pipeline running "
        "before taking the photo. Default = 2",
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
            logger.info(
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
    run_n_seconds: int,
    intermediate_calls: T.List[T.Tuple[int, VoidFn]] = [],
):
    """Run the pipeline

    :param pipeline: Gst.Pipeline. All element creation/linking steps
        should be done by this point
    :param run_n_seconds: how long until we stop the main loop
    :param intermedate_calls: a list of functions to call
        while the pipeline is running. list[(() -> None, int)], where 2nd elem
        is the number of seconds to wait RELATIVE to
        when the pipeline started running
    :raises RuntimeError: When set_state(PLAYING) fails
    """

    # pipeline needs to start within 5 seconds
    def start():
        pipeline.set_state(Gst.State.PLAYING)
        # it's possible to hang here if the source is broken
        # but the main thread will keep running,
        # so we check both an explicit fail and a hang
        if pipeline.get_state(5)[0] == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("Failed to transition to playing state")

    def quit():
        logger.debug("Setting null to stop the pipeline")
        pipeline.set_state(Gst.State.NULL)
        main_loop.quit()

    start()
    logger.info(f"[ OK ] Pipeline is playing! {run_n_seconds}")

    GLib.timeout_add_seconds(run_n_seconds, quit)
    for delay, call in intermediate_calls:
        assert (
            delay < run_n_seconds
        ), "delay for each call must be smaller than total run seconds"
        GLib.timeout_add_seconds(delay, call)

    main_loop.run()


def display_viewfinder(
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

    partial_pipeline = " ! ".join(["videoconvert name=head", "autovideosink"])
    pipeline = Gst.parse_launch(partial_pipeline)  # type: Gst.Pipeline
    head = pipeline.get_by_name("head")

    assert pipeline.add(source)
    assert head
    assert source.link(head)

    logging.info(
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
        "videorate drop-only=True",  # 3
        'capsfilter name=videorate-caps caps="video/x-raw,framerate=1/{}"',  # 4
        "jpegenc",  # 5
        "valve name=photo-valve",  # 6
        "filesink location={}".format(file_path),  # 7
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
        # videorate doesn't work if source-caps was not created
        str_elements[0] = str_elements[1] = str_elements[3] = str_elements[
            4
        ] = ""
        head_elem_name = "converter"

    if delay_seconds > 0:
        # if this caps filter was deleted earlier, this does nothing
        str_elements[4] = str_elements[4].format(delay_seconds)
    else:
        str_elements[3] = ""
        str_elements[4] = ""

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

    logging.info(
        "[ OK ] Created photo pipeline with {} second delay".format(
            delay_seconds
        )
    )
    # this is just printing the pipeline and separate it from the rest
    logging.info("{} ! {}".format(elem_to_str(source), partial))

    logging.debug("Setting playing state")

    run_pipeline(
        pipeline,
        delay_seconds
        + 1,  # run the pipeline for 1 more second to take tha actual photo
        [(delay_seconds, open_valve)],
    )

    logging.info(
        "[ OK ] Photo for this capability: "
        + "{}".format(caps.to_string() if caps else "[device default]")
        + "was saved to {}".format(file_path)
    )


def record_video(
    source: Gst.Element,
    *,
    caps: T.Optional[Gst.Caps] = None,
    file_path: str,
    record_n_seconds=0,
):
    assert file_path.endswith(
        ".avi"
    ), "This function uses avimux, so the filename must end in .avi"

    str_elements = [
        'capsfilter name=source-caps caps="{}"',  # 0
        "decodebin",  # 1
        "videoconvert name=converter",  # 2
        "avimux",  # 3
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
    else:
        # decode bin doesn't work with video/x-raw
        # videorate doesn't work if source-caps was not created
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

    logging.info(
        "[ OK ] Created video pipeline to record {} seconds".format(
            record_n_seconds
        )
    )
    logging.info("{} ! {}".format(elem_to_str(source), partial))
    logging.debug("Setting playing state")

    run_pipeline(pipeline, record_n_seconds)

    logging.info(
        "[ OK ] Video for this capability: "
        + "{}".format(caps.to_string() if caps else "[device default]")
        + "was saved to {}".format(file_path)
    )

    """record
    videotestsrc num-buffers=120 !
    queue !
    encodebin profile="video/quicktime,variant=iso:video/x-h264" !
    filesink location=video.mp4
    """
    """decode
    filesrc location=video.mp4 ! decodebin ! autovideosink
    """


def main():
    args = parse_args()
    if not os.path.isdir(args.path):
        # must validate early, filesink does not check if the path exists
        raise FileNotFoundError('Path "{}" does not exist'.format(args.path))

    if os.getuid() == 0:
        logging.warning(
            "Running this script as root. "
            "This may lead to different results than running as regular user."
        )

    devices = get_devices()
    if len(devices) == 0:
        logging.error(
            "GStreamer cannot find any cameras on this device. "
            "If you know a camera element exists, then it did not implement "
            "Gst.DeviceProvider to make itself visible to GStreamer "
            "or it is inaccessible without sudo."
        )
        exit(1)

    print("Found {} cameras!".format(len(devices)))
    print(
        '[ HINT ] For debugging, remove the "valve" element to get a pipeline',
        "that can be run with gst-launch-1.0",
        "Also keep the pipeline running for {} seconds".format(
            args.wait_seconds
        ),
    )

    for dev_i, device in enumerate(devices):
        dev_element = device.create_element()
        record_video(
            dev_element,
            file_path="{}/video_dev_{}_cap_{}.avi".format(
                args.path, dev_i, "default"
            ),
            record_n_seconds=args.wait_seconds
        )
        break
        take_photo(
            dev_element,
            delay_seconds=args.wait_seconds,
            caps=None,
            file_path="{}/photo_dev_{}_cap_{}.jpeg".format(
                args.path, dev_i, "default"
            ),
        )
        caps = device.get_caps()
        for cap_i, capability in enumerate(get_all_fixated_caps(caps)):
            print(
                "[ INFO ] Testing",
                '"{}"'.format(capability.to_string()),
                "for device",
                '"{}"'.format(device.get_display_name()),
            )
            take_photo(
                dev_element,
                delay_seconds=args.wait_seconds,
                caps=capability,
                file_path="{}/photo_dev{}_cap{}.jpeg".format(
                    args.path, dev_i, cap_i
                ),
            )
            break

        display_viewfinder(dev_element)

        sleep_sec = 3
        logging.info(
            "Sleep {} seconds to release current device pipeline".format(
                sleep_sec
            )
            + '"{}"'.format(elem_to_str(dev_element)),
        )
        time.sleep(3)


if __name__ == "__main__":
    main()
