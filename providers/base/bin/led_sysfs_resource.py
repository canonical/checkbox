#!/usr/bin/env python3
import argparse
from enum import Enum


UNDEFINED = "undefined"


class SupportedColorTypeEnum(Enum):
    SINGLE = "single"
    MULTIPLE = "multi"


def parse_sysfs_led_resource(resource):
    # Usage of parameter:
    # SYS_LEDS={name1}|{path1}|{color_type} {name2}|{path2}|{color_type} ...
    #
    # path under "/sys/class/leds/{path}"
    # e.g.,
    #   SYS_LEDS=DL1|beat-yel-led|single DL2|rgb:status|multi
    # Note: DONT include any space character in the name field
    for led_data in resource.split(" "):
        tmp_data = led_data.split("|")
        led_phys = tmp_data[0]
        sysfs_name = tmp_data[1] if len(tmp_data) >= 2 else UNDEFINED
        color_type = tmp_data[2] if len(tmp_data) == 3 else UNDEFINED

        try:
            color_type = SupportedColorTypeEnum(color_type).value
        except ValueError:
            pass

        print("name: {}".format(led_phys))
        print("path: {}".format(sysfs_name))
        print("color_type: {}".format(color_type))
        print()


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Sysfs LED Resource parser",
    )
    parser.add_argument("resource", type=str)

    args = parser.parse_args()
    return args


if __name__ == "__main__":

    args = register_arguments()
    if not args.resource:
        print(
            "name: {}\npath: {}\ncolor_type: {}".format(
                UNDEFINED, UNDEFINED, UNDEFINED
            )
        )
        # DO NOT return exit code 1 due to this is use for resource job
    else:
        parse_sysfs_led_resource(args.resource)
