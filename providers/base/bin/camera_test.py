#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2008-2018 Canonical Ltd.
# Written by:
#   Matt Fischer <matt@mattfischer.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
import imghdr
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
        ctypes.c_int32(dir_ << _IOC_DIRSHIFT).value |
        ctypes.c_int32(ord(type_) << _IOC_TYPESHIFT).value |
        ctypes.c_int32(nr << _IOC_NRSHIFT).value |
        ctypes.c_int32(size << _IOC_SIZESHIFT).value)


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
        ('driver', ctypes.c_char * 16),
        ('card', ctypes.c_char * 32),
        ('bus_info', ctypes.c_char * 32),
        ('version', ctypes.c_uint32),
        ('capabilities', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 4),
    ]


# Values for 'capabilities' field
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
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
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
    ]


class v4l2_frmsize_stepwise(ctypes.Structure):
    _fields_ = [
        ('min_width', ctypes.c_uint32),
        ('min_height', ctypes.c_uint32),
        ('step_width', ctypes.c_uint32),
        ('min_height', ctypes.c_uint32),
        ('max_height', ctypes.c_uint32),
        ('step_height', ctypes.c_uint32),
    ]


class v4l2_frmsizeenum(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('discrete', v4l2_frmsize_discrete),
            ('stepwise', v4l2_frmsize_stepwise),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('pixel_format', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('_u', _u),
        ('reserved', ctypes.c_uint32 * 2)
    ]

    _anonymous_ = ('_u',)


class v4l2_fmtdesc(ctypes.Structure):
    _fields_ = [
        ('index', ctypes.c_uint32),
        ('type', ctypes.c_int),
        ('flags', ctypes.c_uint32),
        ('description', ctypes.c_char * 32),
        ('pixelformat', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 4),
    ]


V4L2_FMT_FLAG_COMPRESSED = 0x0001
V4L2_FMT_FLAG_EMULATED = 0x0002


# ioctl code for video devices
VIDIOC_QUERYCAP = _IOR('V', 0, v4l2_capability)
VIDIOC_ENUM_FRAMESIZES = _IOWR('V', 74, v4l2_frmsizeenum)
VIDIOC_ENUM_FMT = _IOWR('V', 2, v4l2_fmtdesc)


class CameraTest:
    """
    A simple class that displays a test image via GStreamer.
    """
    def __init__(self, args):
        self.args = args
        self._width = 640
        self._height = 480
        self._devices = []

    def detect(self):
        """
        Display information regarding webcam hardware
        """
        cap_status = dev_status = 1
        for i in range(10):
            cp = v4l2_capability()
            device = '/dev/video%d' % i
            try:
                with open(device, 'r') as vd:
                    fcntl.ioctl(vd, VIDIOC_QUERYCAP, cp)
            except IOError:
                continue
            dev_status = 0
            print("%s: OK" % device)
            print("    name   : %s" % cp.card.decode('UTF-8'))
            print("    driver : %s" % cp.driver.decode('UTF-8'))
            print(
                "    version: %s.%s.%s"
                % (cp.version >> 16, (cp.version >> 8) & 0xff,
                   cp.version & 0xff))
            print("    flags  : 0x%x [" % cp.capabilities,
                  ' CAPTURE' if cp.capabilities & V4L2_CAP_VIDEO_CAPTURE
                  else '',
                  ' OVERLAY' if cp.capabilities & V4L2_CAP_VIDEO_OVERLAY
                  else '',
                  ' READWRITE' if cp.capabilities & V4L2_CAP_READWRITE
                  else '',
                  ' STREAMING' if cp.capabilities & V4L2_CAP_STREAMING
                  else '',
                  ' ]', sep="")

            resolutions = self._supported_resolutions_to_string(
                self._get_supported_resolutions(device))
            resolutions = resolutions.replace(
                "Resolutions:", "    Resolutions:")
            resolutions = resolutions.replace("Format:", "    Format:")
            print(resolutions)

            if cp.capabilities & V4L2_CAP_VIDEO_CAPTURE:
                cap_status = 0
        return dev_status | cap_status

    def _stop(self):
        self.camerabin.set_state(Gst.State.NULL)
        Gtk.main_quit()

    def _on_error(self, bus, msg):
        Gtk.main_quit()

    def _on_destroy(self, *args):
        Clutter.main_quit()

    def _take_photo(self, filename):
        self.camerabin.set_property("location", filename)
        self.camerabin.emit("start-capture")

    def _setup(self, sink=None):
        webcam = Gst.ElementFactory.make('v4l2src')
        webcam.set_property('device', self.args.device)
        wrappercamerabinsrc = Gst.ElementFactory.make('wrappercamerabinsrc')
        wrappercamerabinsrc.set_property('video-source', webcam)
        self.camerabin = Gst.ElementFactory.make("camerabin")
        self.camerabin.set_property('camera-source', wrappercamerabinsrc)
        if sink:
            vf_sink = Gst.ElementFactory.make(sink)
            self.camerabin.set_property('viewfinder-sink', vf_sink)
        self.camerabin.set_state(Gst.State.PAUSED)
        caps = self.camerabin.get_property('viewfinder-supported-caps')
        supported_resolutions = {}
        for i in range(caps.get_size()):
            key = caps.get_structure(i).get_int('width').value
            if key not in supported_resolutions.keys():
                supported_resolutions[key] = set()
            supported_resolutions[key].add(
                caps.get_structure(i).get_int('height').value)
        if not supported_resolutions:
            raise SystemExit("No supported resolutions found!")
        width = min(supported_resolutions.keys(),
                    key=lambda x: abs(x - self._width))
        height = min(supported_resolutions[width],
                     key=lambda y: abs(y - self._height))
        vf_caps = Gst.Caps.from_string(
            'video/x-raw, width={}, height={}'.format(width, height))
        self.camerabin.set_property('viewfinder-caps', vf_caps)
        bus = self.camerabin.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._on_error)
        self.camerabin.set_state(Gst.State.PLAYING)

    def led(self):
        """
        Activate camera (switch on led), but don't display any output
        """
        self._setup(sink='fakesink')
        GLib.timeout_add_seconds(3, self._stop)
        Gtk.main()

    def display(self):
        """
        Displays the preview window
        """
        self._setup()
        GLib.timeout_add_seconds(10, self._stop)
        Gtk.main()

    def still(self):
        """
        Captures an image to a file
        """
        if self.args.filename:
            self._still_helper(self.args.filename, self._width, self._height,
                               self.args.quiet)
        else:
            with NamedTemporaryFile(prefix='camera_test_', suffix='.jpg') as f:
                self._still_helper(f.name, self._width, self._height,
                                   self.args.quiet)

    def _still_helper(self, filename, width, height, quiet, pixelformat=None):
        """
        Captures an image to a given filename.  width and height specify the
        image size and quiet controls whether the image is displayed to the
        user (quiet = True means do not display image).
        """
        command = ["fswebcam", "-D 1", "-S 50", "--no-banner",
                   "-d", self.args.device,
                   "-r", "%dx%d"
                   % (width, height), filename]
        use_camerabin = False
        if pixelformat:
            if 'MJPG' == pixelformat:  # special tweak for fswebcam
                pixelformat = 'MJPEG'
            command.extend(["-p", pixelformat])

        try:
            check_call(command, stdout=open(os.devnull, 'w'), stderr=STDOUT)
            if os.path.getsize(filename) == 0:
                use_camerabin = True
        except (CalledProcessError, OSError):
            use_camerabin = True
        if use_camerabin:
            self._setup(sink='fakesink')
            GLib.timeout_add_seconds(3, self._take_photo, filename)
            GLib.timeout_add_seconds(4, self._stop)
            Gtk.main()
        if not quiet:
            stage = Clutter.Stage()
            stage.set_title('Camera still picture test')
            stage.set_size(width, height)
            stage.connect('destroy', self._on_destroy)
            Clutter.threads_add_timeout(0, 10000, self._on_destroy, None, None)
            still_texture = Clutter.Texture.new_from_file(filename)
            stage.add_actor(still_texture)
            stage.show()
            Clutter.main()

    def _supported_resolutions_to_string(self, supported_resolutions):
        """
        Return a printable string representing a list of supported resolutions
        """
        ret = ""
        for resolution in supported_resolutions:
            ret += "Format: %s (%s)\n" % (resolution['pixelformat'],
                                          resolution['description'])
            ret += "Resolutions: "
            for res in resolution['resolutions']:
                ret += "%sx%s," % (res[0], res[1])
            # truncate the extra comma with :-1
            ret = ret[:-1] + "\n"
        return ret

    def resolutions(self):
        """
        After querying the webcam for supported formats and resolutions,
        take multiple images using the first format returned by the driver,
        and see if they are valid
        """
        resolutions = self._get_supported_resolutions(self.args.device)
        # print supported formats and resolutions for the logs
        print(self._supported_resolutions_to_string(resolutions))

        # pick the first format, which seems to be what the driver wants for a
        # default.  This also matches the logic that fswebcam uses to select
        # a default format.
        resolution = resolutions[0]
        if resolution:
            print("Taking multiple images using the %s format"
                  % resolution['pixelformat'])
            for res in resolution['resolutions']:
                w = res[0]
                h = res[1]
                f = NamedTemporaryFile(prefix='camera_test_%s%sx%s' %
                                       (resolution['pixelformat'], w, h),
                                       suffix='.jpg', delete=False)
                print("Taking a picture at %sx%s" % (w, h))
                self._still_helper(f.name, w, h, True,
                                   pixelformat=resolution['pixelformat'])
                if self._validate_image(f.name, w, h):
                    print("Validated image %s" % f.name)
                    os.remove(f.name)
                else:
                    print("Failed to validate image %s" % f.name,
                          file=sys.stderr)
                    os.remove(f.name)
                    return 1
            return 0

    def _get_pixel_formats(self, device, maxformats=5):
        """
        Query the camera to see what pixel formats it supports.  A list of
        dicts is returned consisting of format and description.  The caller
        should check whether this camera supports VIDEO_CAPTURE before
        calling this function.
        """
        supported_formats = []
        fmt = v4l2_fmtdesc()
        fmt.index = 0
        fmt.type = V4L2_CAP_VIDEO_CAPTURE
        try:
            while fmt.index < maxformats:
                with open(device, 'r') as vd:
                    if fcntl.ioctl(vd, VIDIOC_ENUM_FMT, fmt) == 0:
                        pixelformat = {}
                        # save the int type for re-use later
                        pixelformat['pixelformat_int'] = fmt.pixelformat
                        pixelformat['pixelformat'] = "%s%s%s%s" % \
                            (chr(fmt.pixelformat & 0xFF),
                             chr((fmt.pixelformat >> 8) & 0xFF),
                             chr((fmt.pixelformat >> 16) & 0xFF),
                             chr((fmt.pixelformat >> 24) & 0xFF))
                        pixelformat['description'] = fmt.description.decode()
                        supported_formats.append(pixelformat)
                fmt.index = fmt.index + 1
        except IOError as e:
            # EINVAL is the ioctl's way of telling us that there are no
            # more formats, so we ignore it
            if e.errno != errno.EINVAL:
                print("Unable to determine Pixel Formats, this may be a "
                      "driver issue.")
            return supported_formats
        return supported_formats

    def _get_supported_resolutions(self, device):
        """
        Query the camera for supported resolutions for a given pixel_format.
        Data is returned in a list of dictionaries with supported pixel
        formats as the following example shows:
        resolution['pixelformat'] = "YUYV"
        resolution['description'] = "(YUV 4:2:2 (YUYV))"
        resolution['resolutions'] = [[width, height], [640, 480], [1280, 720] ]

        If we are unable to gather any information from the driver, then we
        return YUYV and 640x480 which seems to be a safe default.
        Per the v4l2 spec the ioctl used here is experimental
        but seems to be well supported.
        """
        supported_formats = self._get_pixel_formats(device)
        if not supported_formats:
            resolution = {}
            resolution['description'] = "YUYV"
            resolution['pixelformat'] = "YUYV"
            resolution['resolutions'] = [[640, 480]]
            supported_formats.append(resolution)
            return supported_formats

        for supported_format in supported_formats:
            resolutions = []
            framesize = v4l2_frmsizeenum()
            framesize.index = 0
            framesize.pixel_format = supported_format['pixelformat_int']
            with open(device, 'r') as vd:
                try:
                    while fcntl.ioctl(vd,
                                      VIDIOC_ENUM_FRAMESIZES,
                                      framesize) == 0:
                        if framesize.type == V4L2_FRMSIZE_TYPE_DISCRETE:
                            resolutions.append([framesize.discrete.width,
                                               framesize.discrete.height])
                        # for continuous and stepwise, let's just use min and
                        # max they use the same structure and only return
                        # one result
                        elif (framesize.type in (V4L2_FRMSIZE_TYPE_CONTINUOUS,
                              V4L2_FRMSIZE_TYPE_STEPWISE)):
                            resolutions.append([framesize.stepwise.min_width,
                                                framesize.stepwise.min_height]
                                               )
                            resolutions.append([framesize.stepwise.max_width,
                                                framesize.stepwise.max_height]
                                               )
                            break
                        framesize.index = framesize.index + 1
                except IOError as e:
                    # EINVAL is the ioctl's way of telling us that there are no
                    # more formats, so we ignore it
                    if e.errno != errno.EINVAL:
                        print("Unable to determine supported framesizes "
                              "(resolutions), this may be a driver issue.")
            supported_format['resolutions'] = resolutions
        return supported_formats

    def _validate_image(self, filename, width, height):
        """
        Given a filename, ensure that the image is the width and height
        specified and is a valid image file.
        """
        if imghdr.what(filename) != 'jpeg':
            return False

        outw = outh = 0
        with open(filename, mode='rb') as jpeg:
            jpeg.seek(2)
            b = jpeg.read(1)
            try:
                while (b and ord(b) != 0xDA):
                    while (ord(b) != 0xFF):
                        b = jpeg.read(1)
                    while (ord(b) == 0xFF):
                        b = jpeg.read(1)
                    if (ord(b) >= 0xC0 and ord(b) <= 0xC3):
                        jpeg.seek(3, 1)
                        h, w = struct.unpack(">HH", jpeg.read(4))
                        break
                    b = jpeg.read(1)
                outw, outh = int(w), int(h)
            except (struct.error, ValueError):
                pass

            if outw != width:
                print("Image width does not match, was %s should be %s" %
                      (outw, width), file=sys.stderr)
                return False
            if outh != height:
                print("Image width does not match, was %s should be %s" %
                      (outh, height), file=sys.stderr)
                return False

            return True

        return True


def parse_arguments(argv):
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser(description="Run a camera-related test")
    subparsers = parser.add_subparsers(dest='test',
                                       title='test',
                                       description='Available camera tests')

    parser.add_argument('--debug', dest='log_level',
                        action="store_const", const=logging.DEBUG,
                        default=logging.INFO, help="Show debugging messages")

    def add_device_parameter(parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-d", "--device", default="/dev/video0",
                           help="Device for the webcam to use")
        group.add_argument("--highest-device", action="store_true",
                           help=("Use the /dev/videoN "
                                 "where N is the highest value available"))
        group.add_argument("--lowest-device", action="store_true",
                           help=("Use the /dev/videoN "
                                 "where N is the lowest value available"))
    subparsers.add_parser('detect')
    led_parser = subparsers.add_parser('led')
    add_device_parameter(led_parser)
    display_parser = subparsers.add_parser('display')
    add_device_parameter(display_parser)
    still_parser = subparsers.add_parser('still')
    add_device_parameter(still_parser)
    still_parser.add_argument("-f", "--filename",
                              help="Filename to store the picture")
    still_parser.add_argument("-q", "--quiet", action="store_true",
                              help=("Don't display picture, "
                                    "just write the picture to a file"))
    resolutions_parser = subparsers.add_parser('resolutions')
    add_device_parameter(resolutions_parser)
    args = parser.parse_args(argv)

    def get_video_devices():
        devices = sorted(glob('/dev/video[0-9]'),
                         key=lambda d: re.search(r'\d', d).group(0))
        assert len(devices) > 0, "No video devices found"
        return devices

    if hasattr(args, 'highest_device') and args.highest_device:
        args.device = get_video_devices()[-1]
    elif hasattr(args, 'lowest_device') and args.lowest_device:
        args.device = get_video_devices()[0]
    return args


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])

    if not args.test:
        args.test = 'detect'

    logging.basicConfig(level=args.log_level)

    # Import Gst only for the test cases that will need it
    if args.test in ['display', 'still', 'led', 'resolutions']:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        gi.require_version('GLib', '2.0')
        from gi.repository import GLib
        gi.require_version('Clutter', '1.0')
        from gi.repository import Clutter
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        Gst.init(None)
        Clutter.init()
        Gtk.init([])
    camera = CameraTest(args)
    sys.exit(getattr(camera, args.test)())
