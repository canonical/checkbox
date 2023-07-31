#!/usr/bin/env python3
'''
script to test accerometer functionality

Copyright (C) 2012 Canonical Ltd.

Authors
  Jeff Marcom <jeff.marcom@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to simply interact with an onboard
accelerometer, and check to be sure that the x, y, z axis respond
to physical movement of hardware.
'''

from argparse import ArgumentParser
import gi
import logging
import os
import re
import sys
import threading
import time
gi.require_version('Gdk', '3.0')
gi.require_version('GLib', '2.0')
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk                    # noqa: E402
from subprocess import Popen, PIPE, check_output, STDOUT    # noqa: E402
from subprocess import CalledProcessError                   # noqa: E402
from checkbox_support.parsers.modinfo import ModinfoParser  # noqa: E402

handler = logging.StreamHandler()
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class AccelerometerUI(Gtk.Window):
    """Builds UI Framework for axis threshold tests using Gtk"""

    def __init__(self):
        Gtk.Window.__init__(self, title="Accelerometer Test")

        self.set_default_size(450, 100)
        self.set_type_hint(Gdk.WindowType.TOPLEVEL)

        self.enabled = False

        # Create UI Grid
        w_table = Gtk.Grid()
        self.add(w_table)

        # Create axis buttons
        self.up_icon = Gtk.Image(stock=Gtk.STOCK_GO_UP)
        self.up_icon.set_padding(10, 30)
        self.down_icon = Gtk.Image(stock=Gtk.STOCK_GO_DOWN)
        self.down_icon.set_padding(10, 30)
        self.left_icon = Gtk.Image(stock=Gtk.STOCK_GO_BACK)
        self.right_icon = Gtk.Image(stock=Gtk.STOCK_GO_FORWARD)

        # Set debug
        self.debug_label = Gtk.Label("Debug")

        # Set Grid layout for UI
        message = "Please tilt your hardware in the positions shown below:"
        w_table.attach(Gtk.Label(message), 0, 0, 4, 1)

        w_table.attach(self.up_icon, 2, 2, 1, 1)
        w_table.attach_next_to(self.debug_label, self.up_icon,
                               Gtk.PositionType.BOTTOM, 1, 1)
        w_table.attach_next_to(self.down_icon, self.debug_label,
                               Gtk.PositionType.BOTTOM, 1, 1)
        w_table.attach_next_to(self.left_icon, self.debug_label,
                               Gtk.PositionType.LEFT, 1, 1)
        w_table.attach_next_to(self.right_icon, self.debug_label,
                               Gtk.PositionType.RIGHT, 1, 1)

    def update_axis_icon(self, direction):
        """Change desired directional icon to checkmark"""
        exec('self.%s_icon.set_from_stock' % (direction) +
             '(Gtk.STOCK_YES, size=Gtk.IconSize.BUTTON)')

    def update_debug_label(self, text):
        """Update axis information in center of UI"""
        self.debug_label.set_text(text)

    def destroy(self):
        Gtk.main_quit()

    def enable(self):
        self.enabled = True
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()

        # Enable GLib/Gdk threading so the UI won't lock main
        GLib.threads_init()
        Gdk.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()


class PermissionException(RuntimeError):
    def __init__(self, error):
        message = "Please re-run with root permissions: %s" % error.strip()
        super(PermissionException, self).__init__(message)


class AxisData(threading.Thread):
    """Acquire information from kernel regarding the state of the
    accelerometer axis positions. Gathered data will be compared to
    a preset threshold reading. The default threshold (either - or + )
    for any direction is 600. Return values for thread are SUCCESS:0
    FAILURE:1. FAILURE is likely to exists when thread is unable to
    obtain a valid reading from the hardware."""

    def __init__(self, device_path, ui_control=None):
        threading.Thread.__init__(self)
        self.ui = ui_control
        self.device_path = device_path.strip("/")
        self.tilt_threshold = 600
        self.x_test_pool = ["up", "down"]
        self.y_test_pool = ["left", "right"]

        if self.ui is None:
            self.ui.enabled = False

    def grab_current_readings(self):
        """Search device path and return axis tuple"""
        time.sleep(0.5)  # Sleep to accomodate slower processors
        data_file = os.path.join("/sys", self.device_path,
                                 "device", "position")

        # Try and retrieve positional data from kernel
        try:
            position_tuple = open(data_file)
        except (OSError, IOError):
            logging.error("Failed to open: %s" % data_file)
            return False

        # Split data for x, y, z as it's easier to manage threshold tests.
        axis_set = position_tuple.read().strip("\n()")

        return axis_set.split(",")

    def parse_reading(self, value, mapping):
        """Check for positive or negative threshold match"""
        if abs(value) >= abs(self.tilt_threshold):
            # And return test pool array position based on integer
            if value < 0:
                return 2
            return 1

    def direction_poll(self, x_axis, y_axis):
        """Poll for threshold being met per x, and y axis"""
        direction_map = {"X": x_axis, "Y": y_axis}

        for mapping, data in direction_map.items():
            reading = self.parse_reading(int(data), mapping)

            if isinstance(reading, int):
                return reading, mapping

        # Return nothing if threshold is not met
        return False, None

    def run(self):
        rem_tests = self.y_test_pool + self.x_test_pool
        while len(rem_tests) > 0:
            axis_data_bundle = self.grab_current_readings()

            if not isinstance(axis_data_bundle, list):
                logging.error("Failed to grab appropriate readings")
                return 1

            # Parse for current positional values
            # Hdaps will only report X, and Y positional data
            x_data = int(axis_data_bundle[0])
            y_data = int(axis_data_bundle[1])
            if len(axis_data_bundle) > 2:
                z_data = int(axis_data_bundle[2])
            else:
                z_data = 0

            debug_info = "X: %s Y: %s Z: %s" % (x_data, y_data, z_data)

            if self.ui.enabled:
                # Update positional values in UI
                self.ui.update_debug_label(debug_info)

                position, axis = self.direction_poll(x_data, y_data)
                if position:
                    # Check axis set and delete test from pool
                    if axis == "X":
                        pool = self.x_test_pool
                    else:
                        pool = self.y_test_pool
                    if len(pool) >= position:
                        direction = pool[position - 1]
                        if direction in rem_tests:
                            # Remove direction from test pool
                            del rem_tests[rem_tests.index(direction)]
                            self.ui.update_axis_icon(direction)
            else:
                # Accept readings as successful test result
                logging.debug("Latest Readings: %s" % debug_info)
                break

        if self.ui.enabled:
            self.ui.destroy()
        return 0


def insert_supported_module(oem_module):
    """Try and insert supported module to see if we get any init errors"""
    try:
        stream = check_output(
            ['modinfo', oem_module], stderr=STDOUT, universal_newlines=True)
    except CalledProcessError as err:
        print("Error accessing modinfo for %s: " % oem_module, file=sys.stderr)
        print(err.output, file=sys.stderr)
        return err.returncode

    parser = ModinfoParser(stream)
    module = os.path.basename(parser.get_field('filename'))

    insmod_output = Popen(['insmod %s' % module], stderr=PIPE,
                          shell=True, universal_newlines=True)

    error = insmod_output.stderr.read()
    if "Permission denied" in error:
        raise PermissionException(error)

    return insmod_output.returncode


def check_module_status():
    """Looks to see if it can determine the hardware manufacturer
    and report corresponding accelerometer driver status"""
    oem_driver_pool = {"hewlett-packard": "hp_accel",
                       "toshiba": "hp_accel",
                       "ibm": "hdaps", "lenovo": "hdaps"}

    oem_module = None
    dmi_info = Popen(['dmidecode'], stdout=PIPE, stderr=PIPE,
                     universal_newlines=True)

    output, error = dmi_info.communicate()

    if "Permission denied" in error:
        raise PermissionException(error)

    vendor_data = re.findall(r"Vendor:\s.*", output)
    try:
        manufacturer = vendor_data[0].split(":")[1].strip()
    except IndexError:
        logging.error("Failed to find Manufacturing data")
        return

    logging.debug(manufacturer)

    # Now we look to see if there was any info during boot
    # time that would help in debugging this failure
    for vendor, module in oem_driver_pool.items():
        if manufacturer.lower() == vendor:
            oem_module = oem_driver_pool.get(vendor)
            break  # We've found our desired module to probe.

    if oem_module is not None:
        if insert_supported_module(oem_module) is not None:
            logging.error("Failed module insertion")
        # Check dmesg status for supported module
        driver_status = Popen(['dmesg'], stdout=PIPE, universal_newlines=True)
        module_regex = oem_module + ".*"
        kernel_notes = re.findall(module_regex, driver_status.stdout.read())
        # Report ALL findings, it's useful to note it the driver failed init
        # more than once of actually passed despite a reading failure
        logging.debug("\n".join((kernel_notes)))
    else:
        logging.error("No supported module")


def check_for_accelerometer():
    """Checks device list for existence of accelerometer and returns
    name, manufacturer, and system path info."""

    found = False
    device_info = open("/proc/bus/input/devices").readlines()
    for line in device_info:
        if "accelerometer" in line.lower():
            target = device_info.index(line)

            name = device_info[target].split("=")[1]
            path = device_info[target + 2].split("=")[1]
            found = True
            break

    if found:
        logger.debug("Name: %s\nPath: %s" % (name, path))
        return path.strip()
    else:
        # Return False as it's expected
        logger.error("Accelerometer hardware not found")

    return False


def main():

    parser = ArgumentParser(description="Tests accelerometer functionality")

    parser.add_argument('-m', '--manual', default=False,
                        action='store_true',
                        help="For manual test with visual notification")
    parser.add_argument('-a', '--automated', default=True,
                        action='store_true',
                        help="For automated test using defined parameters")

    args = parser.parse_args()

    sys_path = check_for_accelerometer()
    if not sys_path:
        try:
            check_module_status()
        except PermissionException as error:
            print(error, file=sys.stderr)
        sys.exit(1)

    ui = AccelerometerUI()
    grab_data = AxisData(sys_path, ui)
    grab_data.setDaemon(True)
    grab_data.start()

    if args.manual:
        ui.enable()
    else:
        # Sleep for enough time to retrieve a reading.
        # Reading is not instant.
        time.sleep(5)


if __name__ == '__main__':
    main()
