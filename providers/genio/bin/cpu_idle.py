#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Authors:
#   Patrick Chang <patrick.chang@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.


import os
import argparse


GENERAL_PATH = "cpu%d/cpuidle/state%d/%s"


def read_attr(attr):
    path = os.path.join("/sys/devices/system/cpu", attr)
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        tmp = f.read().strip()
        return tmp


def read_attr_num(attr):
    tmp = read_attr(attr)
    if not tmp:
        return -1

    return int(tmp)


def read_idle_attr(cpu, state, attr):
    return read_attr(GENERAL_PATH % (cpu, state, attr))


def read_idle_attr_num(cpu, state, attr):
    return read_attr_num(GENERAL_PATH % (cpu, state, attr))


def error_handler(node_type, node_path, expect, reality):
    if node_type == "name" or node_type == "disable":
        print(
            "Failed: the expected {} value of node '{}' should be '{}' but "
            "got '{}'".format(node_type, node_path, expect, reality)
        )
    if node_type == "usage":
        print(
            "Failed: the expected usage value of node '{}' should be greater "
            "than 0".format(node_path)
        )


def output_checker(cpu, state, name, disable, usage):
    """
    @param:name, type: tuple. (reality value, expected value)
    @param:disable, type: tuple. (reality value, expected value)
    @param:usage
    """
    fail = 0
    print("CPU node: cpu/{}/cpuidle/state{}".format(cpu, state))
    print(
        "Got name: {}, disable: {}, usage: {}".format(
            name[0], disable[0], usage
        )
    )
    if name[0] != name[1]:
        node_path = GENERAL_PATH.format(cpu, state, "name")
        error_handler("name", node_path, name[0], name[1])
        fail = 1
    if disable[0] != disable[1]:
        node_path = GENERAL_PATH.format(cpu, state, "disable")
        error_handler("disable", node_path, disable[0], disable[1])
        fail = 1
    if usage <= 0:
        node_path = GENERAL_PATH.format(cpu, state, "usage")
        error_handler("usage", node_path)
        fail = 1
    if fail:
        exit(1)


def test_wfi():
    cpu = 0
    state = 0
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu, state, name=(name, "WFI"), disable=(disable, "0"), usage=usage
    )


def test_mcdi_cpu(soc):
    if soc != "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 0
    state = 1
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu,
        state,
        name=(name, "mcdi-cpu"),
        disable=(disable, "0"),
        usage=usage,
    )


def test_mcdi_cluster(soc):
    if soc != "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 0
    state = 2
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu,
        state,
        name=(name, "mcdi-cluster"),
        disable=(disable, "0"),
        usage=usage,
    )


def test_dpidle(soc):
    if soc != "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 0
    state = 3
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu, state, name=(name, "dpidle"), disable=(disable, "0"), usage=usage
    )


def test_clusteroff_l(soc):
    if soc == "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 0
    state = 2
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu,
        state,
        name=(name, "clusteroff-l" if soc == "mt8390" else "clusteroff_l"),
        disable=(disable, "0"),
        usage=usage,
    )


def test_clusteroff_b(soc):
    if soc == "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 6 if soc == "mt8390" else 4
    state = 2
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu,
        state,
        name=(name, "clusteroff-b" if soc == "mt8390" else "clusteroff_b"),
        disable=(disable, "0"),
        usage=usage,
    )


def test_cpuoff_l(soc):
    if soc == "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 0
    state = 1
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu,
        state,
        name=(name, "cpuoff-l" if soc == "mt8390" else "cpuoff_l"),
        disable=(disable, "0"),
        usage=usage,
    )


def test_cpuoff_b(soc):
    if soc == "mt8365":
        print("Isn't supported for '{}'".format(soc))
        return

    cpu = 6 if soc == "mt8390" else 4
    state = 1
    name = read_idle_attr(cpu, state, "name")
    disable = read_idle_attr(cpu, state, "disable")
    usage = read_idle_attr_num(cpu, state, "usage")
    output_checker(
        cpu,
        state,
        name=(name, "cpuoff-b" if soc == "mt8390" else "cpuoff_b"),
        disable=(disable, "0"),
        usage=usage,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "soc",
        help="SoC type. e.g mt8395",
        choices=["mt8395", "mt8390", "mt8365"],
    )
    parser.add_argument(
        "-c",
        "--case",
        help="The available cases of CPU Idle",
        choices=[
            "wfi",
            "mcdi-cpu",
            "mcdi-cluster",
            "dpidle",
            "clusteroff-l",
            "clusteroff-b",
            "cpuoff-l",
            "cpuoff-b",
        ],
        type=str,
        required=True,
    )
    args = parser.parse_args()
    if args.case == "wfi":
        test_wfi()
    if args.case == "mcdi-cpu":
        test_mcdi_cpu(args.soc)
    if args.case == "mcdi-cluster":
        test_mcdi_cluster(args.soc)
    if args.case == "dpidle":
        test_dpidle(args.soc)
    if args.case == "clusteroff-l":
        test_clusteroff_l(args.soc)
    if args.case == "clusteroff-b":
        test_clusteroff_b(args.soc)
    if args.case == "cpuoff-l":
        test_cpuoff_l(args.soc)
    if args.case == "cpuoff-b":
        test_cpuoff_b(args.soc)


if __name__ == "__main__":
    main()
