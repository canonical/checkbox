#!/usr/bin/env python3

import os
import argparse
import subprocess

PLAINBOX_SESSION_SHARE = os.environ.get("PLAINBOX_SESSION_SHARE")
PLAINBOX_PROVIDER_DATA = os.environ.get("PLAINBOX_PROVIDER_DATA")


def runcmd(command):
    ret = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        timeout=1,
    )
    return ret


def check_env_variables():
    if not PLAINBOX_SESSION_SHARE:
        print("no env var PLAINBOX_SESSION_SHARE")
        exit(1)
    if not PLAINBOX_PROVIDER_DATA:
        print("no env var PLAINBOX_PROVIDER_DATA")
        exit(1)


def test_linux_ccf(soc):
    if soc == "mt8365":
        print("mt8365 is not supported")
        exit(1)

    clk_summary_path = "{}/clk-summary.txt".format(PLAINBOX_SESSION_SHARE)
    cat_ret = runcmd(
        [
            "cat /sys/kernel/debug/clk/clk_summary "
            "| tee {}".format(clk_summary_path)
        ]
    )

    if cat_ret.returncode:
        print(
            "Failed: unable to dump clk_summary data "
            "to {}".format(clk_summary_path)
        )
        exit(1)
    print("Dump /sys/kernel/debug/clk/clk_summary:")
    print(cat_ret.stdout)

    if soc == "mt8390":
        verify_ret = runcmd(
            [
                (
                    "verify-mt8188-ccf.sh"
                    " -t {}/linux-ccf/mt8188-clk.h"
                    " -s {}".format(PLAINBOX_PROVIDER_DATA, clk_summary_path)
                )
            ]
        )
    elif soc == "mt8395" or soc == "mt8195":
        verify_ret = runcmd(
            [
                (
                    "verify-mt8195-ccf.sh"
                    " -t {}/linux-ccf/mt8195-clk.h"
                    " -s {}".format(PLAINBOX_PROVIDER_DATA, clk_summary_path)
                )
            ]
        )

    if verify_ret.returncode:
        print("Failed: {}".format(verify_ret.stdout))
        exit(1)
    if (
        verify_ret.stdout.split("\n")[0]
        != "[-] Success, all clocks are mapped !"
    ):
        print("Wrong output: {}".format(verify_ret.stdout))
        exit(1)

    print("Test Pass")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "soc",
        help="SoC type. e.g mt8395",
        choices=["mt8395", "mt8195", "mt8390", "mt8390"],
    )
    args = parser.parse_args()
    check_env_variables()
    test_linux_ccf(args.soc)


if __name__ == "__main__":
    main()
