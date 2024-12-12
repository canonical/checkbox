#! /usr/bin/python3

from checkbox_support.parsers.v4l2_compliance import TEST_NAME_TO_IOCTL_MAP
import subprocess as sp


def main():
    try:
        udev_out = sp.check_output(
            "udev_resource.py -f CAPTURE", universal_newlines=True, shell=True
        )
        lines = udev_out.splitlines()
    except Exception as e:
        lines = [f"name: broken {str(e)}"]

    for line in lines:
        if line.startswith("name:"):
            for ioctl_names in TEST_NAME_TO_IOCTL_MAP.values():
                for name in ioctl_names:
                    print(line)
                    print("ioctl_name:", format(name))
                    print()  # empty line to mark end of list item


if __name__ == "__main__":
    main()
