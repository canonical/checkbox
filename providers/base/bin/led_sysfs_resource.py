#!/usr/bin/env python3
import argparse


USAGE = """
led_sysfs_resource.py resource

Note:
    format of led_patterns:
    {name1}|{path1}|{color_type} {name2}|{path2}|{color_type} ...

    path under "/sys/class/leds/{path}"
    e.g.,
        DL1|beat-yel-led|single DL2|rgb:status|multi
    Note: DONT include any space character in the name field
"""
SupportedColorType = ["single", "multi"]


def check_environment(resource):
    if not resource:
        raise SystemExit("SYS_LEDS is not defined")

    for led_data in resource.split(" "):
        tmp_data = led_data.split("|")
        if len(tmp_data) != 3:
            raise SystemExit("Incorrect led data: {}".format(led_data))

        if tmp_data[2] not in SupportedColorType:
            raise SystemExit("Unexpected color type: {}".format(tmp_data[2]))

    print("the format of SYS_LEDS is correct")


def parse_sysfs_led_resource(resource):
    for led_data in resource.split(" "):
        tmp_data = led_data.split("|")
        if len(tmp_data) != 3:
            continue

        led_phys, sysfs_name, color_type = tmp_data
        if color_type not in SupportedColorType:
            continue

        print("name: {}".format(led_phys))
        print("path: {}".format(sysfs_name))
        print("color_type: {}".format(color_type))
        print()

def main():
    args = register_arguments()

    if args.validate:
        check_environment(args.resource)
    else:
        parse_sysfs_led_resource(args.resource)


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Sysfs LED Resource parser", usage=USAGE
    )
    parser.add_argument("resource", type=str, default="")
    parser.add_argument(
        "--validate",
        action="store_true",
        default=False,
        help="check if the format of led_patterns correctly"
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    main()
