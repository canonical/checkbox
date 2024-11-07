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
from typing import Dict, List, Optional
from urllib.parse import urlparse

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


# XXX: The repository part of this should go away if we package mixbench
NVIDIA_URL = "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu{}/{}".format(  # noqa: E501
    RELEASE.replace(".", ""), ARCH
)
GPU_VENDORS = {
    "nvidia": {
        "repos": [
            {
                "name": "cuda",
                "repo_line": "{} /".format(NVIDIA_URL),
                "gpg_url": "{}/3bf863cc.pub".format(NVIDIA_URL),
                "gpg_fingerprint": "EB693B3035CD5710E231E123A4B469963BF863CC",
                "pinfile": "{}/cuda-ubuntu{}.pin".format(
                    NVIDIA_URL, RELEASE.replace(".", "")
                ),
            }
        ],
    },
}
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

    @property
    def template(self) -> Optional[str]:
        """Gets path to template tarball."""
        if not self._template and self.template_url:
            targetfile = urlparse(self.template_url).path.split("/")[-1]
            filename = os.path.join("/tmp", targetfile)
            if not os.path.isfile(filename):
                self.download_image(self.template_url, filename)
            self._template = filename

        return self._template

    @property
    def image(self) -> Optional[str]:
        """Gets path to image tarball."""
        if not self._image and self.image_url:
            targetfile = urlparse(self.image_url).path.split("/")[-1]
            filename = os.path.join("/tmp", targetfile)
            if not os.path.isfile(filename):
                self.download_image(self.image_url, filename)
            self._image = filename

        return self._image

    def run(
        self,
        cmd: str,
        log_stderr: bool = True,
        on_guest: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        """Runs a command on the host or instance."""
        if on_guest:
            cmd = "lxc exec {} -- {}".format(self.name, cmd)
        proc = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
            check=False,
        )

        logging.debug("Command: %s", cmd)
        if proc.stdout:
            logging.debug(" STDOUT: %s", proc.stdout)
        if log_stderr and proc.stderr:
            logging.debug(" STDERR: %s", proc.stderr)

        if check:
            proc.check_returncode()

        return proc

    def download_image(self, url, filename):
        """Downloads LXD files for same release as host machine."""
        logging.debug("Attempting download of %s from %s", filename, url)
        try:
            urllib.request.urlretrieve(url, filename)
        except (
            IOError,
            OSError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as e:
            logging.exception(e)
        except ValueError as verr:
            logging.exception(verr)

        if not os.path.isfile(filename):
            raise FileNotFoundError(filename)

    def insert_images(self):
        """Insert LXD template and image images."""
        if self.template and self.image:
            logging.debug("Importing images into LXD")
            self.run(
                "lxc image import {} rootfs {} --alias {}".format(
                    self.template, self.image, self.image_alias.hex
                ),
                check=True,
            )
        else:
            logging.debug("No local images, attempting import from remote")
            retries = 2
            for _ in range(retries):
                proc = self.run(
                    "lxc image copy {}{} local: --alias {}".format(
                        self.remote, RELEASE, self.image_alias.hex
                    )
                )
                if proc.returncode == 0:
                    return
                logging.error("Error encountered while importing images")
                logging.error("Attempting up to %d times", retries)
            raise RuntimeError("Images could not be inserted")

    def init_lxd(self):
        """Initializes LXD."""
        if self.run("lxd waitready --timeout=5").returncode != 0:
            self.run("lxd init --auto", check=True)
        self.insert_images()

    def cleanup(self):
        """Cleans up instance."""
        self.run("lxc image delete {}".format(self.image_alias.hex))
        self.run("lxc delete --force {}".format(self.name))

    def launch(self, options: Optional[List] = None):
        """Sets up and creates the instance."""
        if not options:
            options = []

        cmd = "lxc launch {} {}".format(self.image_alias.hex, self.name)
        if options:
            cmd = "{} {}".format(cmd, " ".join(options))
        self.run(cmd, check=True)

    def stop(self, force: bool = False):
        """Stops LXD instance."""
        cmd = "lxc stop {}".format(self.name)
        if force:
            cmd += " --force"
        self.run(cmd, check=True)

    def start(self):
        """Starts LXD instance."""
        self.run("lxc start {}".format(self.name), check=True)

    def restart(self):
        """Restarts LXD instance."""
        self.run("lxc restart {}".format(self.name), check=True)

    def add_device(
        self, device: str, device_type: str, options: Optional[List] = None
    ):
        """Adds a device to the LXD instance."""
        if not options:
            options = []
        self.run(
            "lxc config device add {} {} {} {}".format(
                self.name, device, device_type, " ".join(options)
            ),
            check=True,
        )


class LXDVM(LXD):
    """This class represents a LXD VM instance."""

    def insert_images(self):
        if self.template and self.image:
            logging.debug("Importing images into LXD")
            self.run(
                "lxc image import {} {} --alias {}".format(
                    self.template, self.image, self.image_alias.hex
                ),
                check=True,
            )

    def launch(self, options=None):
        if not options:
            options = []

        logging.debug("Initializing virtual machine")
        if not self.image and not self.template:
            logging.debug("No local image, importing from remote")
            cmd = "lxc init {}{} {} --vm".format(
                self.remote, RELEASE, self.name
            )
        else:
            cmd = "lxc init {} {} --vm".format(self.image, self.name)
        if options:
            cmd = "{} {}".format(cmd, " ".join(options))
        self.run(cmd, check=True)

        logging.debug("Starting virtual machine")
        self.run("lxc start {}".format(self.name), check=True)

    def add_device(self, device: str, device_type: str, options=None):
        # Hot plugging is only supported on containers
        self.stop(force=True)
        super().add_device(device, device_type, options)
        self.start()


# XXX: If we package the mixbench program, this wouldn't be needed
def add_apt_repo(instance: LXD, repo: Dict):
    """Adds an APT repository to a LXD instance."""
    name = repo["name"]
    repo_line = repo["repo_line"]
    gpg_url = repo["gpg_url"]
    gpg_fingerprint = repo["gpg_fingerprint"]
    pinfile = repo["pinfile"]

    logging.debug("Downloading GPG key from %s", gpg_url)
    temp_keyring = "./tmp.gpg"
    gpg_dest = "/usr/share/keyrings/{}.gpg".format(name)
    instance.run(
        "wget -O {}.gpg '{}'".format(name, gpg_url),
        on_guest=True,
        check=True,
    )
    instance.run(
        "gpg --no-default-keyring --keyring {} --import {}.gpg".format(
            temp_keyring, name
        ),
        on_guest=True,
        check=True,
    )
    instance.run(
        "gpg --no-default-keyring --keyring {} --fingerprint {}".format(
            temp_keyring, gpg_fingerprint
        ),
        on_guest=True,
        check=True,
    )
    instance.run(
        "gpg --yes --no-default-keyring --keyring {} --export -o {}".format(
            temp_keyring, gpg_dest
        ),
        on_guest=True,
        check=True,
    )
    instance.run(
        "rm {0} {0}~ ./{1}.gpg".format(temp_keyring, name),
        on_guest=True,
        check=True,
    )

    if pinfile:
        pinfile_dest = "/etc/apt/preferences.d/{}-pin-600".format(name)
        if pinfile.startswith("http"):
            logging.debug("Downloading pinfile")
            cmd = "wget -O {} {}".format(pinfile_dest, pinfile)
        else:
            logging.debug("Creating pinfile")
            cmd = "bash -c \"echo -e '{}' | tee {}\"".format(
                pinfile, pinfile_dest
            )
        instance.run(cmd, on_guest=True, check=True)

    logging.debug("Setting up APT repository: %s", name)
    repo_dest = "/etc/apt/sources.list.d/{}.list".format(name)
    list_file = "deb [signed-by={}] {}".format(gpg_dest, repo_line)
    instance.run(
        "bash -c \"echo '{}' | tee {}\"".format(list_file, repo_dest),
        on_guest=True,
        check=True,
    )

    logging.debug("Updating APT cache")
    instance.run("apt-get -q update", on_guest=True, check=True)


# TODO: Package test program (e.g., as a snap) to simplify this logic
#       If we package mixbench, then this function goes away entirely
def build_gpu_test(instance: LXD, vendor: str):
    """Builds the GPU passthrough test."""
    test_name = ""
    cmake_cmd = "cmake ../mixbench-{test_name}"

    # Add necessary APT repositories to instance
    for repo in GPU_VENDORS[vendor].get("repos", []):
        add_apt_repo(instance, repo)

    if vendor == "nvidia":
        logging.debug("Installing CUDA Toolkit on instance")
        packages = ["build-essential", "cmake", "cuda-toolkit"]
        instance.run(
            "apt-get -q install -y --no-install-recommends {}".format(
                " ".join(packages)
            ),
            on_guest=True,
            check=True,
        )

        logging.debug("Finding CUDA capability for GPU")
        cuda_arch = "native"
        proc = instance.run(
            "nvidia-smi --query-gpu=compute_cap --format=csv,noheader",
            on_guest=True,
        )
        if proc.returncode == 0 and proc.stdout:
            cuda_arch = proc.stdout.strip().replace(".", "")
        logging.debug("Using CUDA architecture '%s'", cuda_arch)

        test_name = "cuda"
        nvcc_path = "/usr/local/cuda/bin/nvcc"
        cmake_cmd = "CUDACXX={} {} -DCMAKE_CUDA_ARCHITECTURES={}".format(
            nvcc_path, cmake_cmd, cuda_arch
        )

    logging.info("Fetching and compiling GPU passthrough test on instance")
    cmds = [
        "set -e",
        "git clone https://github.com/ekondis/mixbench.git",
        "mkdir mixbench/build-{}".format(test_name),
        "cd mixbench/build-{}".format(test_name),
        cmake_cmd.format(test_name=test_name),
        "make",
        "ln -s ~/mixbench/build-{0}/mixbench-{0} ~/test".format(test_name),
    ]
    instance.run(
        "bash -c '{}'".format("; ".join(cmds)), on_guest=True, check=True
    )


def run_gpu_test(
    instance: LXD,
    run_count: int = GPU_RUNS,
    threshold_sec: float = GPU_THRESHOLD_SEC,
):
    """Executes GPU passthrough test."""
    logging.info("Running GPU passthrough test %d times", run_count)
    total_runtime_sec = 0.0
    for i in range(run_count):
        tic = time.time()
        # XXX: If we package the test, this line needs to be updated
        instance.run("./test", on_guest=True, check=True)
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
    try:
        instance.init_lxd()
        options = []
        if args.vendor == "nvidia":
            options = ["-c nvidia.runtime=true"]
        instance.launch(options=options)
        instance.add_device("gpu", "gpu", options=["pci={}".format(args.pci)])

        logging.info("Waiting for network to be up")
        time.sleep(20)

        build_gpu_test(instance, args.vendor)
        run_gpu_test(instance, args.count, args.threshold)
    finally:
        instance.cleanup()


def test_lxdvm_gpu(args):
    """Tests GPU passthrough with a LXD virtual machine."""
    logging.info("Executing LXD VM GPU passthrough test")

    instance = LXDVM(args.template, args.image)
    try:
        instance.init_lxd()
        instance.launch(
            options=["-d root,size=50GB", "-c security.secureboot=false"]
        )

        logging.info("Waiting for network to be up")
        time.sleep(20)

        # Add and configure GPU device
        instance.add_device("gpu", "gpu", ["pci={}".format(args.pci)])
        if args.vendor == "nvidia":
            logging.debug("Installing ubuntu-drivers tool")
            instance.run(
                "apt-get -q install -y ubuntu-drivers-common",
                on_guest=True,
                check=True,
            )
            instance.run("ubuntu-drivers install", on_guest=True, check=True)
        instance.restart()

        logging.info("Waiting for network to be up")
        time.sleep(20)

        build_gpu_test(instance, args.vendor)
        run_gpu_test(instance, args.count, args.threshold)
    finally:
        instance.cleanup()


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
