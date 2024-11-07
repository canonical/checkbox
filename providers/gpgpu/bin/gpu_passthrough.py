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
import shlex
import subprocess
import time
import urllib
import uuid
from typing import List, Optional
from urllib.parse import urlparse

from checkbox_support.helpers.retry import retry, run_with_retry
from plainbox.impl.decorators import cached_property

try:
    import distro

    if distro.id() == "ubuntu-core":
        RELEASE = "{}.04".format(distro.version())
        CODENAME = "focal"
        if distro.version() == "18":
            CODENAME = "bionic"
        elif distro.version() == "16":
            CODENAME = "xenial"
    else:
        RELEASE = distro.version()
        CODENAME = distro.codename().split()[0].lower()
except ImportError:
    import lsb_release  # type: ignore

    RELEASE = lsb_release.get_distro_information()["RELEASE"]
    CODENAME = lsb_release.get_distro_information()["CODENAME"]

ARCH = os.uname().machine


GPU_VENDORS = {
    "nvidia": {
        "test": "mixbench.cuda",
        "lxd": {"launch_options": ["-c nvidia.runtime=true"]},
        "lxdvm": {
            "launch_options": [],
            "config_cmds": [
                "apt-get -q install -y ubuntu-drivers-common",
                "ubuntu-drivers install",
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

GPU_THRESHOLD_SEC = 12.0  # TODO: finetune
"""The threshold for the GPU test to pass.

This can be overwritten by the `--threshold` option or by setting the
environment variable `LXD_GPU_THRESHOLD`. With priority in that order.
"""


class LXD:
    """This class represents a LXD instance."""

    def __init__(
        self,
        template_url: Optional[str] = None,
        image_url: Optional[str] = None,
        name: str = "testbed",
        remote: str = "ubuntu:",
    ):
        self.template_url = template_url
        self.image_url = image_url
        self.name = name
        self.remote = remote
        self.image_alias = uuid.uuid4()

        self._template = None
        self._image = None

    @cached_property
    def template(self) -> Optional[str]:
        """Gets path to template tarball."""
        if not self.template_url:
            return None
        targetfile = urlparse(self.template_url).path.split("/")[-1]
        filename = os.path.join("/tmp", targetfile)
        self.download_image(self.template_url, filename)
        return filename

    @cached_property
    def image(self) -> Optional[str]:
        """Gets path to image tarball."""
        if not self.image_url:
            return None
        targetfile = urlparse(self.image_url).path.split("/")[-1]
        filename = os.path.join("/tmp", targetfile)
        self.download_image(self.image_url, filename)
        return filename

    def run(
        self,
        cmd: str,
        log_stderr: bool = True,
        on_guest: bool = False,
        ignore_errors: bool = False,
    ):
        """Runs a command on the host or instance."""
        if on_guest:
            cmd = "lxc exec {} -- {}".format(self.name, cmd)
        stderr_pipe = subprocess.STDOUT if log_stderr else subprocess.DEVNULL
        try:
            _ = subprocess.check_output(
                shlex.split(cmd),
                stderr=stderr_pipe,
                stdin=subprocess.DEVNULL,
                universal_newlines=True,
            )
        except subprocess.CalledProcessError as e:
            logging.debug("Command failed: %s", cmd)
            logging.debug(" STDOUT: %s", e.stdout)
            if not ignore_errors:
                raise

    @retry(5, 2)
    def download_image(self, url, filename):
        """Downloads LXD files for same release as host machine."""
        if os.path.isfile(filename):
            return
        logging.debug("Attempting download of %s from %s", filename, url)
        urllib.request.urlretrieve(url, filename)
        if not os.path.isfile(filename):
            raise FileNotFoundError(filename)

    def insert_images(self):
        """Insert LXD template and image images."""
        if self.template and self.image:
            logging.debug("Importing images into LXD")
            self.run(
                "lxc image import {} rootfs {} --alias {}".format(
                    self.template, self.image, self.image_alias.hex
                )
            )
        else:
            logging.debug("No local images, attempting import from remote")
            run_with_retry(
                self.run,
                5,
                2,
                "lxc image copy {}{} local: --alias {}".format(
                    self.remote, RELEASE, self.image_alias.hex
                ),
            )

    def init_lxd(self):
        """Initializes LXD."""
        try:
            self.run("lxd waitready --timeout=5")
        except subprocess.CalledProcessError:
            self.run("lxd init --auto")
        self.insert_images()

    def cleanup(self):
        """Cleans up instance."""
        self.run(
            "lxc image delete {}".format(self.image_alias.hex),
            ignore_errors=True,
        )
        self.run("lxc delete --force {}".format(self.name), ignore_errors=True)

    def launch(self, options: Optional[List] = None):
        """Sets up and creates the instance."""
        cmd = ["lxc", "launch", self.image_alias.hex, self.name]
        if options:
            cmd += options
        self.run(shlex.join(cmd))

    def stop(self, force: bool = False):
        """Stops LXD instance."""
        cmd = "lxc stop {}".format(self.name)
        if force:
            cmd += " --force"
        self.run(cmd)

    def start(self):
        """Starts LXD instance."""
        self.run("lxc start {}".format(self.name))

    def restart(self):
        """Restarts LXD instance."""
        self.run("lxc restart {}".format(self.name))

    def add_device(
        self, device: str, device_type: str, options: Optional[List] = None
    ):
        """Adds a device to the LXD instance."""
        if not options:
            options = []
        self.run(
            "lxc config device add {} {} {} {}".format(
                self.name, device, device_type, " ".join(options)
            )
        )

    def __enter__(self):
        self.init_lxd()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.cleanup()


class LXDVM(LXD):
    """This class represents a LXD VM instance."""

    def insert_images(self):
        if self.template and self.image:
            logging.debug("Importing images into LXD")
            self.run(
                "lxc image import {} {} --alias {}".format(
                    self.template, self.image, self.image_alias.hex
                )
            )

    def launch(self, options: Optional[List] = None):
        logging.debug("Initializing virtual machine")
        cmd = ["lxc", "init"]
        if not self.image and not self.template:
            logging.debug("No local image, importing from remote")
            cmd += ["{}{}".format(self.remote, RELEASE)]
        else:
            cmd += [self.image]
        cmd += [self.name, "--vm"]
        if options:
            cmd += options
        self.run(shlex.join(cmd))

        logging.debug("Starting virtual machine")
        self.run("lxc start {}".format(self.name))

    def add_device(self, device: str, device_type: str, options=None):
        # Hot plugging is only supported on containers
        self.stop(force=True)
        super().add_device(device, device_type, options)
        self.start()


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
        instance.init_lxd()
        instance.launch(
            options=GPU_VENDORS[args.vendor]["lxd"].get("launch_options")
        )
        instance.add_device("gpu", "gpu", options=["pci={}".format(args.pci)])

        logging.info("Waiting for network to be up")
        time.sleep(20)

        instance.run("sudo snap install mixbench", on_guest=True)
        # XXX: Connecting manually until request is granted
        # https://forum.snapcraft.io/t/autoconnect-request-for-mixbench/43881
        instance.run(
            "sudo snap connect mixbench:hardware-observe", on_guest=True
        )

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
        instance.init_lxd()
        instance.launch(
            options=GPU_VENDORS[args.vendor]["lxdvm"].get("launch_options")
        )

        logging.info("Waiting for network to be up")
        time.sleep(20)

        # Add and configure GPU device
        instance.add_device("gpu", "gpu", ["pci={}".format(args.pci)])
        for cmd in GPU_VENDORS[args.vendor]["lxdvm"].get("config_cmds", []):
            logging.debug("Configuring instance")
            instance.run(cmd, on_guest=True)
        instance.restart()

        logging.info("Waiting for network to be up")
        time.sleep(20)

        instance.run("sudo snap install mixbench", on_guest=True)
        # XXX: Connecting manually until request is granted
        # https://forum.snapcraft.io/t/autoconnect-request-for-mixbench/43881
        instance.run(
            "sudo snap connect mixbench:hardware-observe", on_guest=True
        )

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
