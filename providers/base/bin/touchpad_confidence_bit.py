#!/usr/bin/env python3

import sys
from subprocess import check_output, CalledProcessError
from checkbox_support.parsers.udevadm import UdevadmParser


class TouchpadDevices:

    def __init__(self):
        self.devices = {}
        self._collect_devices()

    def _collect_devices(self):
        cmd = ['udevadm', 'info', '--export-db']
        try:
            output = check_output(cmd).decode(sys.stdout.encoding, errors='ignore')
        except CalledProcessError as err:
            sys.stderr.write(err)
            return
        udev = UdevadmParser(output)
        for device in udev.run():
            if getattr(device, 'category') == 'TOUCHPAD':
                self.devices[getattr(device, 'product_slug')
                             ] = getattr(device, 'path')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('ERROR: expected a product slug')
    product_slug = sys.argv[1]

    path = TouchpadDevices().devices[product_slug]
    abs_path = "/sys" + path + "/capabilities/abs"

    f = open(abs_path, "r")
    abs_cap_str = f.readline()
    f.close()
    support = (int(abs_cap_str[-15], 16) & 8) >> 3

    if support == 0:
        modalias_path = "/sys" + path + "/modalias"
        f = open(modalias_path, "r")
        modalias_str = f.readline()
        f.close()
        print("Touchpad modalias: {}".format(modalias_str[0:-2]))
        print("Touchpad EV_ABS capabilities: {}".format(abs_cap_str[0:-2]))
        sys.exit(1)

    return 0


if __name__ == "__main__":
    main()
