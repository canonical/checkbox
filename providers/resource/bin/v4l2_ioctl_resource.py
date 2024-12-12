#! /usr/bin/python3

from checkbox_support.parsers.v4l2_compliance import TEST_NAME_TO_IOCTL_MAP


def main():
    for ioctl_names in TEST_NAME_TO_IOCTL_MAP.values():
        for name in ioctl_names:
            print("ioctl_name: {}".format(name))
            print()  # empty line to mark end of list item


if __name__ == "__main__":
    main()
