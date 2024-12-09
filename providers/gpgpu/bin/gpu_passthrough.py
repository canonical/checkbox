#!/usr/bin/env python3
"""Script to test virtualization GPU passthrough functionality.

Copyright (C) 2024 Canonical Ltd.

Authors
  Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import logging
import os
import time

from checkbox_support.lxd_support import LXD, LXDVM

GPU_VENDORS = {
    "nvidia": {
        "test": "mixbench.cuda",
        "lxd": {
            "launch_options": [
                "-c",
                "nvidia.runtime=true",
                "-c",
                "nvidia.driver.capabilities=all",
            ]
        },
        "lxdvm": {
            "launch_options": ["-c", "security.secureboot=false"],
            "config_cmds": [
                "apt-get -q update -y",
                "apt-get -q upgrade -y",
                "apt-get -q install -y linux-generic ubuntu-drivers-common",
                "ubuntu-drivers install --gpgpu",
            ],
        },
    },
}
"""Mapping of supported vendor names to test configuration."""

GPU_RUNS = 20
"""How many times to run the GPU test.

This can be overwritten by the `--count` option or by setting the environment
variable `LXD_GPU_RUNS`. With priority in that order.
"""

GPU_THRESHOLD_SEC = 12.0
"""The threshold for the GPU test to pass.

This can be overwritten by the `--threshold` option or by setting the
environment variable `LXD_GPU_THRESHOLD`. With priority in that order.
"""


def run_gpu_test(
    instance: LXD,
    cmd: str,
    run_count: int = GPU_RUNS,
    threshold_sec: float = GPU_THRESHOLD_SEC,
):
    """Executes GPU passthrough test."""
    logging.info("Running GPU passthrough test %d times", run_count)
    total_runtime_sec = 0.0
    for i in range(run_count):
        tic = time.time()
        instance.run(cmd, on_guest=True)
        toc = time.time()
        runtime_sec = toc - tic
        total_runtime_sec += runtime_sec
        logging.debug("Runtime #%d (sec): %f", i, runtime_sec)

    avg_runtime_sec = total_runtime_sec / run_count
    logging.info("Average runtime (sec): %f", avg_runtime_sec)
    if avg_runtime_sec >= threshold_sec:
        logging.error(
            "Average runtime %fs greater than threshold %fs",
            avg_runtime_sec,
            threshold_sec,
        )
        raise SystemExit(1)


def test_lxd_gpu(args):
    """Tests GPU passthrough with a LXD container."""
    logging.info("Executing LXD GPU passthrough test")

    instance = LXD(args.template, args.rootfs)
    with LXD(args.template, args.rootfs) as instance:
        logging.info("Launching container: %s", instance.name)
        instance.launch(
            options=GPU_VENDORS[args.vendor]["lxd"].get("launch_options")
        )

        logging.info("Passing GPU %s through to %s", args.pci, instance.name)
        instance.add_device("gpu", "gpu", options=["pci={}".format(args.pci)])

        logging.info("Waiting for %s to be up", instance.name)
        instance.wait_until_running()

        logging.info("Installing mixbench snap")
        instance.run("snap install mixbench", on_guest=True)

        run_gpu_test(
            instance,
            GPU_VENDORS[args.vendor]["test"],
            args.count,
            args.threshold,
        )


def test_lxdvm_gpu(args):
    """Tests GPU passthrough with a LXD virtual machine."""
    logging.info("Executing LXD VM GPU passthrough test")

    with LXDVM(args.template, args.image) as instance:
        logging.info("Launching virtual machine: %s", instance.name)
        instance.launch(
            options=GPU_VENDORS[args.vendor]["lxdvm"].get("launch_options")
        )

        logging.info("Waiting for %s to be up", instance.name)
        instance.wait_until_running()

        logging.info("Passing GPU %s through to %s", args.pci, instance.name)
        instance.add_device("gpu", "gpu", options=["pci={}".format(args.pci)])

        logging.info("Waiting for %s to be up", instance.name)
        instance.wait_until_running()

        logging.info("Configuring %s", instance.name)
        for cmd in GPU_VENDORS[args.vendor]["lxdvm"].get("config_cmds", []):
            instance.run(cmd, on_guest=True)

        logging.info("Restarting %s", instance.name)
        instance.restart()

        logging.info("Waiting for %s to be up", instance.name)
        instance.wait_until_running()

        logging.info("Installing mixbench snap")
        instance.run("snap install mixbench", on_guest=True)

        run_gpu_test(
            instance,
            GPU_VENDORS[args.vendor]["test"],
            args.count,
            args.threshold,
        )


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="GPU passthrough tests")
    subparsers = parser.add_subparsers()

    parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        action="store_const",
        default=logging.INFO,
        const=logging.DEBUG,
        help="Increase logging level",
    )

    test_group = parser.add_argument_group("test")
    test_group.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("LXD_GPU_THRESHOLD") or GPU_THRESHOLD_SEC),
        help="Threshold (sec) for GPU test",
    )
    test_group.add_argument(
        "--count",
        type=int,
        default=int(os.getenv("LXD_GPU_RUNS") or GPU_RUNS),
        help="Times to run GPU test",
    )

    gpu_group = parser.add_argument_group("gpu")
    gpu_group.add_argument(
        "--pci", type=str, help="PCI address of GPU", required=True
    )
    gpu_group.add_argument(
        "--vendor",
        type=str,
        choices=GPU_VENDORS.keys(),
        help="GPU vendor",
        required=True,
    )

    lxd_subparser = subparsers.add_parser("lxd", help="Run on LXD container")
    lxd_subparser.add_argument(
        "--template",
        type=str,
        default=os.getenv("LXD_TEMPLATE"),
        help="URL to template",
    )
    lxd_subparser.add_argument(
        "--rootfs",
        type=str,
        default=os.getenv("LXD_ROOTFS"),
        help="URL to rootfs image",
    )
    lxd_subparser.set_defaults(func=test_lxd_gpu)

    lxdvm_subparser = subparsers.add_parser("lxdvm", help="Run on LXD VM")
    lxdvm_subparser.add_argument(
        "--template",
        type=str,
        default=os.getenv("LXD_TEMPLATE"),
        help="URL to template",
    )
    lxdvm_subparser.add_argument(
        "--image",
        type=str,
        default=os.getenv("KVM_IMAGE"),
        help="URL to image",
    )
    lxdvm_subparser.set_defaults(func=test_lxdvm_gpu)

    return parser.parse_args()


def main():
    """Main entrypoint to the program."""
    args = parse_args()

    logging.basicConfig(level=args.log_level)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    args.func(args)


if __name__ == "__main__":
    main()
