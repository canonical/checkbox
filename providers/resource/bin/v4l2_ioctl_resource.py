#! /usr/bin/env python3

import subprocess as sp

from checkbox_support.parsers.v4l2_compliance import TEST_NAME_TO_IOCTL_MAP
from checkbox_support.parsers.udevadm import UdevadmParser


def main():
    udevadm_output = sp.check_output(
        ["udevadm", "info", "--export-db"], universal_newlines=True
    )

    udev = UdevadmParser(udevadm_output)
    for device in udev.run():
        category = getattr(device, "category", None)
        device_name = getattr(device, "name", None)

        if category == "CAPTURE" and device_name is not None:
            for ioctl_names in TEST_NAME_TO_IOCTL_MAP.values():
                for ioctl_name in ioctl_names:
                    print("name: {}".format(device_name))
                    print("ioctl_name: {}".format(ioctl_name))
                    print()  # empty line to mark end of list item


if __name__ == "__main__":
    main()
