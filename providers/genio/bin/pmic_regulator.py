#!/usr/bin/env python3

import os
import argparse
import sys


MAIN_REGULATORS = (
    "vs1",
    "vgpu11",
    "vmodem",
    "vpu",
    "vcore",
    "vs2",
    "vpa",
    "vproc2",
    "vproc1",
    "vgpu11_sshub",
    "vaud18",
    "vsim1",
    "vibr",
    "vrf12",
    "vusb",
    "vsram_proc2",
    "vio18",
    "vcamio",
    "vcn18",
    "vfe28",
    "vcn13",
    "vcn33_1_bt",
    "vcn33_1_wifi",
    "vaux18",
    "vsram_others",
    "vefuse",
    "vxo22",
    "vrfck",
    "vbif28",
    "vio28",
    "vemc",
    "vcn33_2_bt",
    "vcn33_2_wifi",
    "va12",
    "va09",
    "vrf18",
    "vsram_md",
    "vufs",
    "vm18",
    "vbbck",
    "vsram_proc1",
    "vsim2",
    "vsram_others_sshub",
)
mt8365_MAIN_REGULATORS = (
    "vproc",
    "vcore",
    "vmodem",
    "vs1",
    "vpa",
    "vfe28",
    "vxo22",
    "vrf18",
    "vrf12",
    "vefuse",
    "vcn33-bt",
    "vcn33-wifi",
    "vcn28",
    "vcn18",
    "vcama",
    "vcamd",
    "vcamio",
    "vldo28",
    "vsram-others",
    "vsram-proc",
    "vaux18",
    "vaud28",
    "vio28",
    "vio18",
    "vdram",
    "vmc",
    "vmch",
    "vemc",
    "vsim1",
    "vsim2",
    "vibr",
    "vusb33",
)


def read_attr(attr):
    path = os.path.join("/sys/class/regulator", attr)
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        tmp = f.read().strip()
        return tmp


def read_attr_name(attr):
    tmp = read_attr(attr)
    if not tmp:
        return -1

    return tmp


def read_name(reg):
    return read_attr_name("regulator.%d/name" % reg)


def read_all_name():
    tmp = []
    i = 0
    while True:
        t = read_name(i)
        if t == -1:
            break

        tmp.append(t)
        i += 1

    return set(tmp)


def test_regulator(soc):
    missing_node = False
    expect_set = mt8365_MAIN_REGULATORS if soc == "mt8365" else MAIN_REGULATORS
    current_set = read_all_name()
    for node in expect_set:
        print("Checking the '{0}' node exists in System...".format(node))
        if node not in current_set:
            missing_node = True
            print(
                " - ERROR: expect the '{0}' node exist but it doesn't".format(
                    node
                )
            )

    if missing_node:
        print("Test Fail")
        sys.exit(1)
    print("Test Pass")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "soc",
        help="SoC type. e.g mt8395",
        choices=["mt8395", "mt8390", "mt8365"],
    )
    args = parser.parse_args()
    test_regulator(args.soc)


if __name__ == "__main__":
    main()
