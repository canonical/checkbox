#!/usr/bin/env python3

import sys
from io import StringIO
from subprocess import Popen, PIPE, check_output, STDOUT, CalledProcessError
from checkbox_support.parsers.udevadm import UdevadmParser
from checkbox_support.parsers.modinfo import ModinfoParser


class TouchpadDriver:

    def __init__(self, driver):
        self._driver = driver
        self.driver_version = self._find_driver_version()

    def _find_driver_version(self):
        cmd = ["/sbin/modinfo", self._driver]
        try:
            stream = check_output(cmd, stderr=STDOUT, universal_newlines=True)
        except CalledProcessError as err:
            print("Error communicating with modinfo.")
            print(err.output)
            return None

        if not stream:
            print("Error: modinfo returned nothing.")
        else:
            parser = ModinfoParser(stream)
            version = parser.get_field("version")
            if not version:
                version = parser.get_field("vermagic").split()[0]

        return version


def get_touch_attributes():
    cmd = "udevadm info --export-db"
    output, err = Popen(cmd, stdout=PIPE, shell=True).communicate()
    if err:
        print("Error running $s" % " ".join(cmd))
        print(err)
        return None

    udev = UdevadmParser(StringIO(output.decode("unicode-escape")))
    attributes = {}
    for device in udev.run():
        if getattr(device, "category") == "TOUCHPAD":
            attributes["driver"] = getattr(device, "driver")
            attributes["product"] = getattr(device, "product")
    return attributes


def main():
    attributes = get_touch_attributes()
    if attributes:
        modinfo = TouchpadDriver(attributes["driver"])
        attributes["version"] = modinfo.driver_version
        print(
            "%s: %s\n%s: %s\n%s: %s\n"
            % (
                "Device",
                attributes["product"],
                "Driver",
                attributes["driver"],
                "Driver Version",
                attributes["version"],
            )
        )
    else:
        print("No Touchpad Detected")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
