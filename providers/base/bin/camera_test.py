#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2008-2024 Canonical Ltd.
# Written by:
#   Matt Fischer <matt@mattfischer.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#
# The v4l2 ioctl code comes from the Python bindings for the v4l2
# userspace api (http://pypi.python.org/pypi/v4l2):
# Copyright (C) 1999-2009 the contributors
#
# The JPEG metadata parser is a part of bfg-pages:
# http://code.google.com/p/bfg-pages/source/browse/trunk/pages/getimageinfo.py
# Copyright (C) Tim Hoffman
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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#

import argparse
import ctypes
import errno
import fcntl
import logging
import os
import re
import struct
import sys

from glob import glob
from subprocess import check_call, CalledProcessError, STDOUT
from tempfile import NamedTemporaryFile


_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_WRITE = 1
_IOC_READ = 2


def _IOC(dir_, type_, nr, size):
    return (
        ctypes.c_int32(dir_ << _IOC_DIRSHIFT).value
        | ctypes.c_int32(ord(type_) << _IOC_TYPESHIFT).value
        | ctypes.c_int32(nr << _IOC_NRSHIFT).value
        | ctypes.c_int32(size << _IOC_SIZESHIFT).value
    )


def _IOC_TYPECHECK(t):
    return ctypes.sizeof(t)


def _IOR(type_, nr, size):
    return _IOC(_IOC_READ, type_, nr, ctypes.sizeof(size))


def _IOWR(type_, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, type_, nr, _IOC_TYPECHECK(size))


class v4l2_capability(ctypes.Structure):
    """
    Driver capabilities
    """

    _fields_ = [
        ("driver", ctypes.c_char * 16),
        ("card", ctypes.c_char * 32),
        ("bus_info", ctypes.c_char * 32),
        ("version", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]


# Values for 'capabilities' field
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_VIDEO_CAPTURE_MPLANE = 0x00001000
V4L2_CAP_VIDEO_OVERLAY = 0x00000004
V4L2_CAP_READWRITE = 0x01000000
V4L2_CAP_STREAMING = 0x04000000

v4l2_frmsizetypes = ctypes.c_uint
(
    V4L2_FRMSIZE_TYPE_DISCRETE,
    V4L2_FRMSIZE_TYPE_CONTINUOUS,
    V4L2_FRMSIZE_TYPE_STEPWISE,
) = range(1, 4)


class v4l2_frmsize_discrete(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
    ]


class v4l2_frmsize_stepwise(ctypes.Structure):
    _fields_ = [
        ("min_width", ctypes.c_uint32),
        ("max_width", ctypes.c_uint32),
        ("step_width", ctypes.c_uint32),
        ("min_height", ctypes.c_uint32),
        ("max_height", ctypes.c_uint32),
        ("step_height", ctypes.c_uint32),
    ]


class v4l2_frmsizeenum(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ("discrete", v4l2_frmsize_discrete),
            ("stepwise", v4l2_frmsize_stepwise),
        ]

    _fields_ = [
        ("index", ctypes.c_uint32),
        ("pixel_format", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("_u", _u),
        ("reserved", ctypes.c_uint32 * 2),
    ]

    _anonymous_ = ("_u",)


class v4l2_fmtdesc(ctypes.Structure):
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("type", ctypes.c_int),
        ("flags", ctypes.c_uint32),
        ("description", ctypes.c_char * 32),
        ("pixelformat", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]


V4L2_FMT_FLAG_COMPRESSED = 0x0001
V4L2_FMT_FLAG_EMULATED = 0x0002


# ioctl code for video devices
VIDIOC_QUERYCAP = _IOR("V", 0, v4l2_capability)
VIDIOC_ENUM_FRAMESIZES = _IOWR("V", 74, v4l2_frmsizeenum)
VIDIOC_ENUM_FMT = _IOWR("V", 2, v4l2_fmtdesc)


class CameraTest:
    """
    This class is handles all the different camera tests. The tests available
    are:
        - detect: Display information regarding webcam hardware
        - led: Activate camera (switch on led), but don't display any output
        - video: Displays the preview window for a video stream
        - image: Captures an image to a file
        - resolutions: After querying the webcam for supported formats and
            resolutions, take multiple images using the first format returned
            by the driver, and see if they are valid.
    """

    PHOTO_DELAY_SECONDS = 2

    def __init__(self, **kwargs):
        self._width = 640
        self._height = 480
        self._devices = []
        self.device = kwargs.get("device", "/dev/video0")
        self.headless = kwargs.get("headless", False)
        self.output = kwargs.get("output", "")
        self.log_level = kwargs.get("log_level", logging.INFO)

        self.main_loop = None
        self.pipeline = None
        self.timeout = None

    def init_gstreamer(self):
        """
        Initialize the GStreamer and GLib libraries
        """
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        gi.require_version("GLib", "2.0")
        from gi.repository import GLib

        self.Gst = Gst
        self.GLib = GLib

        self.Gst.init(None)

    def init_gtk(self):
        """
        Initialize the Gtk library
        """
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        self.Gtk = Gtk
        self.Gtk.init([])

    def detect(self):
        """
        Display information regarding webcam hardware
        """
        cap_status = dev_status = 1
        for i in range(10):
            cp = v4l2_capability()
            device = "/dev/video%d" % i
            try:
                with open(device, "r") as vd:
                    fcntl.ioctl(vd, VIDIOC_QUERYCAP, cp)
            except IOError:
                continue
            dev_status = 0
            cap_status = self._detect_and_show_camera_info(device, cp)

        return dev_status | cap_status

    def _detect_and_show_camera_info(self, device, cp):
        """
        Detect the capture capability and show the information of a specific
        camera device

        :param device:
            Full path of camera device under /dev. e.g. /dev/video0
        :param cp:
            The v4l2 capability

        :returns:
            0 if the camera supports the capture capability
            1 if the camera doesn't support the capture capability
        """
        capture_capabilities = (
            cp.capabilities & V4L2_CAP_VIDEO_CAPTURE
            or cp.capabilities & V4L2_CAP_VIDEO_CAPTURE_MPLANE
        )

        print("%s: OK" % device)
        print("    name   : %s" % cp.card.decode("UTF-8"))
        print("    driver : %s" % cp.driver.decode("UTF-8"))
        print(
            "    version: %s.%s.%s"
            % (cp.version >> 16, (cp.version >> 8) & 0xFF, cp.version & 0xFF)
        )
        print(
            "    flags  : 0x%x [" % cp.capabilities,
            " CAPTURE" if capture_capabilities else "",
            " OVERLAY" if cp.capabilities & V4L2_CAP_VIDEO_OVERLAY else "",
            " READWRITE" if cp.capabilities & V4L2_CAP_READWRITE else "",
            " STREAMING" if cp.capabilities & V4L2_CAP_STREAMING else "",
            " ]",
            sep="",
        )

        formats = self._supported_formats_to_string(
            self._get_supported_formats(device)
        )
        formats = formats.replace("Resolutions:", "    Resolutions:")
        formats = formats.replace("Format:", "    Format:")
        print(formats)

        return 0 if capture_capabilities else 1

    def _on_gst_message(self, bus, message):
        # Process End-of-stream messages
        if message.type == self.Gst.MessageType.EOS:
            # Stop the pipeline
            self.pipeline.set_state(self.Gst.State.NULL)
            # Quit the GLib main loop
            self.main_loop.quit()

            logging.debug("End-of-stream")

        # Process Error messages
        elif message.type == self.Gst.MessageType.ERROR:
            # Stop the pipeline
            self.pipeline.set_state(self.Gst.State.NULL)
            # Quit the GLib main loop
            self.main_loop.quit()
            err, debug = message.parse_error()
            print("Error: {}".format(err.message))

            logging.debug("Debug info: {}".format(debug))

            raise SystemExit("Error: {}".format(err.message))

        # Process Pipeline state change messages
        elif (
            message.type == self.Gst.MessageType.STATE_CHANGED
            and message.src.get_name() == "pipeline"
        ):
            old_state, new_state, _ = message.parse_state_changed()
            logging.debug(
                "Pipeline changed state from {} to {}".format(
                    old_state.value_nick, new_state.value_nick
                )
            )

    def _stop_pipeline(self):
        """
        Stop the GLib main loop and set the pipeline state to NULL
        """
        self.main_loop.quit()
        self.pipeline.set_state(self.Gst.State.NULL)

    def _on_timeout(self):
        """
        Stop the  pipeline when the timeout is reached and remove the timeout
        """
        print("Timeout exceeded")
        self.timeout = None
        self._stop_pipeline()

    def led(self):
        """
        Activate camera (switch on led), but don't display any output
        """
        self.main_loop = self.GLib.MainLoop()
        self.GLib.timeout_add_seconds(3, self._stop_pipeline)
        self._setup_video_gstreamer("fakesink")

    def video(self):
        """
        Displays the preview window for a video stream
        """
        # Don't display the video, just run the camera
        if self.headless:
            self.main_loop = self.GLib.MainLoop()
            self.GLib.timeout_add_seconds(4, self._stop_pipeline)
            self._setup_video_gstreamer("fakesink")
        else:
            print("Starting video preview")
            self.GLib.timeout_add_seconds(10, self._stop_pipeline)
            self._setup_video_gstreamer()

    def _setup_video_gstreamer(self, sink=None):
        """
        Setup the gstreamer pipeline to create the video stream
        """
        webcam = self.Gst.ElementFactory.make("v4l2src")
        webcam.set_property("device", self.device)
        wrappercamerabinsrc = self.Gst.ElementFactory.make(
            "wrappercamerabinsrc"
        )
        wrappercamerabinsrc.set_property("video-source", webcam)
        pipeline = self.Gst.ElementFactory.make("camerabin", "pipeline")
        pipeline.set_property("camera-source", wrappercamerabinsrc)
        if sink:
            vf_sink = self.Gst.ElementFactory.make(sink)
            pipeline.set_property("viewfinder-sink", vf_sink)
        pipeline.set_state(self.Gst.State.PAUSED)
        caps = pipeline.get_property("viewfinder-supported-caps")
        supported_resolutions = {}
        for i in range(caps.get_size()):
            key = caps.get_structure(i).get_int("width").value
            if key not in supported_resolutions.keys():
                supported_resolutions[key] = set()
            supported_resolutions[key].add(
                caps.get_structure(i).get_int("height").value
            )
        if not supported_resolutions:
            raise SystemExit("No supported resolutions found!")
        width = min(
            supported_resolutions.keys(), key=lambda x: abs(x - self._width)
        )
        height = min(
            supported_resolutions[width], key=lambda y: abs(y - self._height)
        )
        vf_caps = self.Gst.Caps.from_string(
            "video/x-raw, width={}, height={}".format(width, height)
        )
        pipeline.set_property("viewfinder-caps", vf_caps)

        bus = pipeline.get_bus()
        bus.add_signal_watch()

        self.pipeline = pipeline
        bus.connect("message", self._on_gst_message)
        self.pipeline.set_state(self.Gst.State.PLAYING)

        self.main_loop = self.GLib.MainLoop()
        try:
            self.main_loop.run()
        except self.GLib.Error:
            self.main_loop.quit()
            self.pipeline.set_state(self.Gst.State.NULL)

    def image(self):
        """
        Captures an image to a file
        """
        pixelformat = self._get_default_format()["pixelformat"]
        if self.output:
            self._capture_image(
                self.output, self._width, self._height, pixelformat
            )
        else:
            with NamedTemporaryFile(
                prefix="camera_test_", suffix=".jpg", delete=False
            ) as f:
                self._capture_image(
                    f.name, self._width, self._height, pixelformat
                )

    def _capture_image(self, filename, width, height, pixelformat):
        """
        Captures an image to a given filename. If the image capture fails with
        fswebcam, it will try to capture the image with gstreamer.
        """
        # Try to take a picture with fswebcam
        if not self._capture_image_fswebcam(
            filename, width, height, pixelformat
        ):
            print("Failed to capture image with fswebcam, using gstreamer")
            # If fswebcam fails, try with gstreamer
            self._capture_image_gstreamer(filename, width, height, pixelformat)
        print("Image saved to %s" % filename)
        if not self.headless:
            self._display_image(filename, width, height)

    def _capture_image_fswebcam(self, filename, width, height, pixelformat):
        """
        Simple wrapper around fswebcam to capture an image
        """
        command = [
            "fswebcam",
            "-D 1",
            "-S 50",
            "--no-banner",
            "-d",
            self.device,
            "-r",
            "%dx%d" % (width, height),
            filename,
        ]
        if pixelformat:
            # special tweak for fswebcam
            command.extend(
                ["-p", pixelformat if pixelformat != "MJPG" else "MJPEG"]
            )
        try:
            check_call(command, stdout=open(os.devnull, "w"), stderr=STDOUT)
            return os.path.getsize(filename) != 0
        except (CalledProcessError, OSError):
            return False

    def _capture_image_gstreamer(self, filename, width, height, pixelformat):
        """
        Setup the gstreamer pipeline to capture an image.
        This pipeline consists of the following elements:
        - v4l2src: Capture video from a V4L2 device
        - caps: Set the video stream to the desired resolution
        - rgb_capture: last element in the pipeline to capture the image. If
            no conversion is needed, this is the same as caps
        - jpegenc: Encode the video stream to a JPEG image
        - filesink: Save the JPEG image to a file
        """

        pipeline = self.Gst.Pipeline.new("pipeline")

        # Add source
        source = self.Gst.ElementFactory.make("v4l2src", "video-source")
        source.set_property("device", self.device)
        pipeline.add(source)

        # Add the caps element and include a format converter if needed to
        # always get a RGB format.
        caps = self.Gst.ElementFactory.make("capsfilter", "caps")
        if pixelformat == "RG10":
            caps.set_property(
                "caps",
                self.Gst.Caps.from_string(
                    "video/x-bayer, format=gbrg, width={},height={}".format(
                        width, height
                    )
                ),
            )
            # Add bayer2rgb
            bayer2rgb = self.Gst.ElementFactory.make("bayer2rgb", "bayer2rgb")

            pipeline.add(caps)
            pipeline.add(bayer2rgb)
            caps.link(bayer2rgb)
            rgb_capture = bayer2rgb

        else:
            caps.set_property(
                "caps",
                self.Gst.Caps.from_string(
                    "video/x-raw,width={},height={}".format(width, height)
                ),
            )
            pipeline.add(caps)
            rgb_capture = caps

        # Add valve, doc says drop=True is default
        valve = self.Gst.ElementFactory.make("valve", "photo-valve")
        assert valve, "Valve element could not be created"
        valve.set_property("drop", True)
        pipeline.add(valve)

        # Add encoder
        encoder = self.Gst.ElementFactory.make("jpegenc", "encoder")
        # snapshot=True sends a EOS downstream 
        # when the first buffer reaches jpegenc
        encoder.set_property("snapshot", True)
        pipeline.add(encoder)

        # Add sink
        sink = self.Gst.ElementFactory.make("filesink", "sink")
        sink.set_property("location", filename)
        pipeline.add(sink)

        # Link elements
        source.link(caps)
        rgb_capture.link(valve)
        valve.link(encoder)
        encoder.link(sink)
        # source ! rgbcapture ! valve ! encoder ! filesink

        # Connect the bus to the message handler
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_gst_message)

        # Start the pipeline
        self.pipeline = pipeline
        self.pipeline.set_state(self.Gst.State.PLAYING)

        # Add a global timeout of 90 seconds to capture the image
        self.timeout = self.GLib.timeout_add_seconds(90, self._on_timeout)
        self.GLib.timeout_add_seconds(
            self.PHOTO_DELAY_SECONDS,
            lambda: valve.set_property("drop", False)
        )

        # Start the main loop. If the loop finishes successfully, we will
        # remove the timeout. If the timeout is reached, we will stop the
        # pipeline calling the _on_timeout method and stop both the
        self.main_loop = self.GLib.MainLoop()
        try:
            self.main_loop.run()
        except self.GLib.Error:
            self.main_loop.quit()
            self.pipeline.set_state(self.Gst.State.NULL)

        # If the image is captured correctly and the timeout is not reached,
        # remove the GLib timeout, so it does not interfere with the next
        # iteration.
        if self.timeout:
            self.GLib.source_remove(self.timeout)

    def _display_image(self, filename, width, height):
        """
        Display an image using Gtk
        """
        print("starting GTK")
        # Initialize GTK application
        window = self.Gtk.Window(title="Image Viewer")
        window.set_default_size(width, height)

        # Load and display the image
        image = self.Gtk.Image.new_from_file(filename)
        window.add(image)

        # Connect the destroy event to quit the GTK main loop
        window.connect("destroy", self.Gtk.main_quit)
        self.GLib.timeout_add_seconds(10, self.Gtk.main_quit)

        # Show all widgets in the window
        window.show_all()

        # Start the GTK main loop
        self.Gtk.main()

    def _supported_formats_to_string(self, supported_formats):
        """
        Return a printable string representing a list of supported resolutions
        """
        ret = ""
        for format in supported_formats:
            ret += "Format: %s (%s)\n" % (
                format["pixelformat"],
                format["description"],
            )
            ret += "Resolutions: "
            for resolution in format["resolutions"]:
                ret += "%sx%s," % (resolution[0], resolution[1])
            # truncate the extra comma with :-1
            ret = ret[:-1] + "\n"
        return ret

    def resolutions(self):
        """
        After querying the webcam for supported formats and resolutions,
        take multiple images using the first format returned by the driver,
        and see if they are valid
        """
        self.headless = True

        format = self._get_default_format()
        print(
            "Taking multiple images using the %s pixelformat"
            % format["pixelformat"]
        )

        if self.output:
            self._save_debug_image(format, self.device, self.output)

        for resolution in reversed(format["resolutions"]):
            w = resolution[0]
            h = resolution[1]
            f = NamedTemporaryFile(
                prefix="camera_test_%s%sx%s" % (format["pixelformat"], w, h),
                suffix=".jpg",
                delete=False,
            )
            print("Taking a picture at %sx%s" % (w, h))

            self._capture_image(
                f.name, w, h, pixelformat=format["pixelformat"]
            )
            if self._validate_image(f.name, w, h):
                print("Validated image %s" % f.name)
                os.remove(f.name)
            else:
                print("Failed to validate image %s" % f.name, file=sys.stderr)
                os.remove(f.name)
                return 1
        return 0

    def _save_debug_image(self, format, device, output):
        """
        Save an image to a file
        """
        # Check if the output directory exists
        if not os.path.exists(output):
            raise SystemExit(
                "Output directory does not exist: {}".format(output)
            )

        # Choose one resolution image to store as an artifact. We will use
        # the closest resolution to 640x480 as the target to have some
        # uniformity in the output
        target = 640
        closest_resolution = min(
            format["resolutions"], key=lambda x: abs(x[0] - target)
        )
        w, h = closest_resolution
        device_name = device.split("/")[-1]
        filepath = os.path.join(
            output, "resolution_test_image_{}.jpg".format(device_name)
        )
        print("Saving debug image to %s" % filepath)
        with open(filepath, "w") as f:
            self._capture_image(f.name, w, h, format["pixelformat"])

    def _get_supported_pixel_formats(self, device, maxformats=5):
        """
        Query the camera to see what pixel formats it supports.  A list of
        dicts is returned consisting of format and description.  The caller
        should check whether this camera supports VIDEO_CAPTURE before
        calling this function.
        """
        supported_pixel_formats = []
        fmt = v4l2_fmtdesc()
        fmt.index = 0
        fmt.type = V4L2_CAP_VIDEO_CAPTURE
        try:
            while fmt.index < maxformats:
                with open(device, "r") as vd:
                    if fcntl.ioctl(vd, VIDIOC_ENUM_FMT, fmt) == 0:
                        pixelformat = {}
                        # save the int type for re-use later
                        pixelformat["pixelformat_int"] = fmt.pixelformat
                        pixelformat["pixelformat"] = "%s%s%s%s" % (
                            chr(fmt.pixelformat & 0xFF),
                            chr((fmt.pixelformat >> 8) & 0xFF),
                            chr((fmt.pixelformat >> 16) & 0xFF),
                            chr((fmt.pixelformat >> 24) & 0xFF),
                        )
                        pixelformat["description"] = fmt.description.decode()
                        supported_pixel_formats.append(pixelformat)
                fmt.index = fmt.index + 1
        except IOError as e:
            # EINVAL is the ioctl's way of telling us that there are no
            # more formats, so we ignore it
            if e.errno != errno.EINVAL:
                print(
                    "Unable to determine Pixel Formats, this may be a "
                    "driver issue."
                )
            return supported_pixel_formats
        return supported_pixel_formats

    def _get_supported_formats(self, device):
        """
        Query the camera for supported format info for a given pixel_format.
        Data is returned in a list of dictionaries with supported pixel
        formats as the following example shows:
        format_info['pixelformat'] = "YUYV"
        format_info['description'] = "(YUV 4:2:2 (YUYV))"
        format_info['resolutions'] = [[width, height], [640, 480], [1280, 720]]

        If we are unable to gather any information from the driver, then we
        return YUYV and 640x480 which seems to be a safe default.
        Per the v4l2 spec the ioctl used here is experimental
        but seems to be well supported.
        """
        supported_formats_info = self._get_supported_pixel_formats(device)

        # If we can't get any formats, we will return YUYV and 640x480
        if not supported_formats_info:
            format_info = {}
            format_info["description"] = "YUYV"
            format_info["pixelformat"] = "YUYV"
            format_info["resolutions"] = [[640, 480]]
            return [format_info]

        for supported_format in supported_formats_info:
            resolutions = []
            framesize = v4l2_frmsizeenum()
            framesize.index = 0
            framesize.pixel_format = supported_format["pixelformat_int"]
            with open(device, "r") as vd:
                try:
                    while (
                        fcntl.ioctl(vd, VIDIOC_ENUM_FRAMESIZES, framesize) == 0
                    ):
                        if framesize.type == V4L2_FRMSIZE_TYPE_DISCRETE:
                            resolutions.append(
                                [
                                    framesize.discrete.width,
                                    framesize.discrete.height,
                                ]
                            )
                        # for continuous and stepwise, let's just use min and
                        # max they use the same structure and only return
                        # one result
                        elif framesize.type in (
                            V4L2_FRMSIZE_TYPE_CONTINUOUS,
                            V4L2_FRMSIZE_TYPE_STEPWISE,
                        ):
                            resolutions.append(
                                [
                                    framesize.stepwise.min_width,
                                    framesize.stepwise.min_height,
                                ]
                            )
                            resolutions.append(
                                [
                                    framesize.stepwise.max_width,
                                    framesize.stepwise.max_height,
                                ]
                            )
                            break
                        framesize.index = framesize.index + 1
                except IOError as e:
                    # EINVAL is the ioctl's way of telling us that there are no
                    # more formats, so we ignore it
                    if e.errno != errno.EINVAL:
                        print(
                            "Unable to determine supported framesizes "
                            "(resolutions), this may be a driver issue."
                        )
            supported_format["resolutions"] = resolutions
        return supported_formats_info

    def _get_default_format(self):
        formats = self._get_supported_formats(self.device)
        # print supported formats and formats for the logs
        print(self._supported_formats_to_string(formats))

        # pick the first format, which seems to be what the driver wants for a
        # default.  This also matches the logic that fswebcam uses to select
        # a default format.
        if not formats:
            raise SystemExit("No supported formats found")
        format = formats[0]
        return format

    def _validate_image(self, filename, width, height):
        """
        Given a filename, ensure that the image is the width and height
        specified and is a valid image file.
        """
        if not os.path.exists(filename):
            print("Image file not found")
            return False

        outw = outh = 0
        with open(filename, mode="rb") as f:

            # Check if the header of the image to see if it's a valid JPEG file
            header = f.read(32)
            if (
                header[6:10] != b"JFIF"
                and header[6:10] != b"Exif"
                and header[6:11] != b"Adobe"
            ):
                print("Image is not a JPEG file")
                return False

            f.seek(2)
            b = f.read(1)
            try:
                w = 0
                h = 0
                while b and ord(b) != 0xDA:
                    while ord(b) != 0xFF:
                        b = f.read(1)
                    while ord(b) == 0xFF:
                        b = f.read(1)
                    if ord(b) >= 0xC0 and ord(b) <= 0xC3:
                        f.seek(3, 1)
                        h, w = struct.unpack(">HH", f.read(4))
                        break
                    b = f.read(1)
                outw, outh = int(w), int(h)
            except (struct.error, ValueError):
                pass

            if outw == 0 or outh == 0:
                print("Image dimensions not found in JPEG file")
                return False
            if outw != width:
                print(
                    "Image width does not match, was %s should be %s"
                    % (outw, width),
                    file=sys.stderr,
                )
                return False
            if outh != height:
                print(
                    "Image width does not match, was %s should be %s"
                    % (outh, height),
                    file=sys.stderr,
                )
                return False

            return True


def parse_arguments(argv):
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser(description="Run a camera-related test")

    # Add subparsers for the different tests
    subparsers = parser.add_subparsers(
        dest="test", title="test", description="Available camera tests"
    )

    # Add a debug option
    parser.add_argument(
        "--debug",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
        help="Show debugging messages",
    )

    # Function to manage the device parameter, either by specifying the device
    # or by using the highest or lowest available device
    def add_device_parameter(parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-d",
            "--device",
            default="/dev/video0",
            help="Device for the webcam to use",
        )
        group.add_argument(
            "--highest-device",
            action="store_true",
            help=(
                "Use the /dev/videoN where N is the highest value available"
            ),
        )
        group.add_argument(
            "--lowest-device",
            action="store_true",
            help=("Use the /dev/videoN where N is the lowest value available"),
        )

    # Detect subparser
    subparsers.add_parser("detect")

    # Led subparser
    led_parser = subparsers.add_parser("led")
    add_device_parameter(led_parser)

    # Video subparser
    video_parser = subparsers.add_parser("video")
    add_device_parameter(video_parser)
    # add a headless option, false by default
    video_parser.add_argument(
        "-hl",
        "--headless",
        action="store_true",
        help=("Don't display video, just run the camera"),
    )

    # Image subparser
    image_parser = subparsers.add_parser("image")
    add_device_parameter(image_parser)
    image_parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Output directory to store the image",
    )
    image_parser.add_argument(
        "-hl",
        "--headless",
        action="store_true",
        help=("Don't display picture, just write the picture to a file"),
    )

    # Resolutions subparser
    resolutions_parser = subparsers.add_parser("resolutions")
    resolutions_parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Output directory to store a small debug image",
    )
    add_device_parameter(resolutions_parser)

    args = parser.parse_args(argv)

    # Handle the selection of the highest or lowest device
    def get_video_devices():
        devices = sorted(
            glob("/dev/video[0-9]"), key=lambda d: re.search(r"\d", d).group(0)
        )
        assert len(devices) > 0, "No video devices found"
        return devices

    if hasattr(args, "highest_device") and args.highest_device:
        args.device = get_video_devices()[-1]
    elif hasattr(args, "lowest_device") and args.lowest_device:
        args.device = get_video_devices()[0]
    return vars(args)


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])

    # Set the default test to detect if not specified
    if not args.get("test"):
        args["test"] = "detect"

    # Set the log level
    logging.basicConfig(level=args["log_level"])

    camera = CameraTest(**args)
    # Import Gst only for the test cases that will need it
    if args["test"] in ["video", "image", "led", "resolutions"]:
        camera.init_gstreamer()

        # Import Gtk only for the test cases that will need it
        if args["test"] in ["video", "image"] and not args["headless"]:
            camera.init_gtk()

    sys.exit(getattr(camera, args["test"])())
