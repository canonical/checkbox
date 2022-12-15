#!/usr/bin/env python3

import gi
import time
import re
import subprocess
import sys
import argparse
gi.require_version('Gio', '2.0')
from gi.repository import Gio  # noqa: E402


class Battery():

    def __init__(self, data):
        lines = data.split("\n")
        for line in lines:
            if line.find("state:") != -1:
                self._state = line.split(':')[1].strip()
            elif line.find("energy:") != -1:
                self._energy, self._energy_units = self._get_capacity(line)
            elif line.find("energy-full:") != -1:
                self._energy_full, self._energy_full_units =\
                    self._get_capacity(line)
            elif line.find("energy-full-design:") != -1:
                self._energy_full_design, self._energy_full_design_units =\
                    self._get_capacity(line)

    def _get_capacity(self, line):
        """
        Given a line of input that represents a battery capacity (energy)
        value, return a tuple of (value, units).  Value is returned as a
        float.
        """
        capacity = line.split(':')[1].strip()
        values = capacity.split()
        return (float(values[0]), values[1])

    def __str__(self):
        ret = "-----------------------------------------\n"
        ret += "State: %s\n" % self._state
        ret += "Energy: %s %s\n" % (self._energy, self._energy_units)
        ret += "Energy Full: %s %s\n" % (self._energy_full,
                                         self._energy_full_units)
        ret += "Energy Full-Design: %s %s\n" % (self._energy_full_design,
                                                self._energy_full_design_units)
        return ret


def find_battery():
    batinfo = subprocess.Popen('upower -d',
                               stdout=subprocess.PIPE, shell=True,
                               universal_newlines=True)
    if not batinfo:
        return None
    else:
        out, err = batinfo.communicate()
        if out:
            device_regex = re.compile("Device: (.*battery_.*)")
            batteries = device_regex.findall(out)
            if len(batteries) == 0:
                return None
            elif len(batteries) > 1:
                print("Warning: This system has more than 1 battery, only the"
                      "first battery will be measured")
            return batteries[0]
        else:
            return None


def get_battery_state():
    battery_name = find_battery()
    if battery_name is None:
        return None

    batinfo = subprocess.Popen('upower -i %s' % battery_name,
                               stdout=subprocess.PIPE, shell=True,
                               universal_newlines=True)
    if not batinfo:
        return None
    else:
        out, err = batinfo.communicate()
        if out:
            return Battery(out)
        else:
            return None


def validate_battery_info(battery):
    if battery is None:
        print("Error obtaining battery info")
        return False
    if battery._state != "discharging":
        print("Error: battery is not discharging, test will not be valid")
        return False
    return True


def battery_life(before, after, time):
    capacity_difference = before._energy - after._energy
    print("Battery drained by %f %s" % (capacity_difference,
                                        before._energy_units))
    if capacity_difference == 0:
        print("Battery capacity did not change, unable to determine remaining"
              " time", file=sys.stderr)
        return 1
    drain_per_second = capacity_difference / time
    print("Battery drained %f %s per second" % (drain_per_second,
                                                before._energy_units))

    # the battery at it's max design capacity (when it was brand new)
    design_life_minutes = round(
        ((before._energy_full_design / drain_per_second) / 60), 2)
    print("Battery Life with full battery at design capacity (when new): %.2f"
          "minutes" % (design_life_minutes))

    # the battery at it's current max capacity
    current_full_life_minutes = round(
        ((before._energy_full / drain_per_second) / 60), 2)
    print("Battery Life with a full battery at current capacity: %.2f minutes"
          % (current_full_life_minutes))

    # the battery at it's current capacity
    current_life_minutes = round(
        ((before._energy / drain_per_second) / 60), 2)
    print("Battery Life with at current battery capacity: %.2f minutes" %
          (current_life_minutes))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="""Determine battery drain and battery life by running
                       the specified action.  Battery life is shown for:
                       current capacity, capacity when battery is full,
                       and capacity when battery is full and was brand new
                       (design capacity)""")
    parser.add_argument('-i', '--idle', help="Run the test while system is"
                        " idling", action='store_true')
    parser.add_argument('-s3', '--sleep', help="Run the test while system"
                        " is suspended", action='store_true')
    parser.add_argument('-t', '--time',
                        help="Specify the allotted time in seconds to run",
                        type=int, required=True)
    parser.add_argument('-m', '--movie',
                        help="Run the test while playing the file MOVIE")
    args = parser.parse_args()

    test_time = args.time
    battery_before = get_battery_state()
    if not validate_battery_info(battery_before):
        return 1
    print(battery_before)

    if args.idle:
        time.sleep(test_time)
    elif args.movie:
        totem_settings = Gio.Settings.new("org.gnome.totem")
        totem_settings.set_boolean("repeat", True)
        a = subprocess.Popen(['totem', '--fullscreen', args.movie])
        time.sleep(test_time)
        a.kill()
        totem_settings = Gio.Settings.new("org.gnome.totem")
        totem_settings.set_boolean("repeat", False)
    elif args.sleep:
        subprocess.call(['fwts', 's3', '--s3-sleep-delay=' + str(test_time)])

    battery_after = get_battery_state()
    if not validate_battery_info(battery_after):
        return 1
    print(battery_after)

    return (battery_life(battery_before, battery_after, test_time))


if __name__ == "__main__":
    sys.exit(main())
