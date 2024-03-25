#!/usr/bin/env python3

import argparse

GOVERNORS = ["userspace", "powersave", "performance", "simple_ondemand"]
print("Expected Governors: {}".format(GOVERNORS))


def test_sysfs_attrs_read(soc):
    fail = 0
    mail_type = "13000000.mali"
    if soc == "mt8365":
        mail_type = "13040000.mali"
    node_path = (
        "/sys/devices/platform/soc/{}/devfreq/{}/"
        "available_governors".format(mail_type, mail_type)
    )

    with open(node_path) as f:
        for node in f.read().strip().split():
            if node not in GOVERNORS:
                fail = 1
                print(
                    "Failed: found governor '{}' out of "
                    "expectation".format(node)
                )
    return fail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "soc",
        help="SoC type. e.g mt8395",
        choices=["mt8395", "mt8390", "mt8365"],
    )
    args = parser.parse_args()
    ret = test_sysfs_attrs_read(args.soc)
    if ret:
        exit(1)
    print("Pass")


if __name__ == "__main__":
    main()
