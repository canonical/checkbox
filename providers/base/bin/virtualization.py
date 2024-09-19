#!/usr/bin/env python3

"""
Script to test virtualization functionality

Copyright (C) 2013, 2014 Canonical Ltd.

Authors
  Jeff Marcom <jeff.marcom@canonical.com>
  Daniel Manrique <roadmr@ubuntu.com>
  Jeff Lane <jeff@ubuntu.com>

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
import logging
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from argparse import ArgumentParser
from subprocess import (
    DEVNULL,
    PIPE,
    CalledProcessError,
    Popen,
    call,
    check_output,
)
from typing import Optional, override
from urllib.parse import urlparse
from uuid import uuid4

import requests

DEFAULT_TIMEOUT = 500

GPU_VENDORS = ["nvidia", "amd"]
VGPU_RUNS = 20
VGPU_THRESHOLD_SEC = 12.0  # TODO: Finetune this default threshold

# The "TAR" type is a tarball that contains both
# a disk image and a kernel binary. This is useful
# on architectures that don't (yet) have a bootloader
# in the disk image that we can chain to, and instead
# we need to have qemu load boot files externally
CLOUD_IMAGE_TYPE_TAR = 1
CLOUD_IMAGE_TYPE_DISK = 2

QEMU_DISK_TYPE_SD = 1
QEMU_DISK_TYPE_VIRTIO = 2
QEMU_DISK_TYPE_VIRTIO_BLK = 3

QEMU_ARCH_CONFIG = {
    "arm64": {
        "cloudimg_type": CLOUD_IMAGE_TYPE_TAR,
        "cloudimg_arch": "arm64",
        "qemu_bin": "qemu-system-aarch64",
        "qemu_disk_type": QEMU_DISK_TYPE_VIRTIO_BLK,
        "qemu_extra_args": [
            "-cpu",
            "host",
            "-enable-kvm",
        ],
    },
    "armhf": {
        "cloudimg_type": CLOUD_IMAGE_TYPE_TAR,
        "cloudimg_arch": "armhf",
        "qemu_bin": "qemu-system-arm",
        "qemu_disk_type": QEMU_DISK_TYPE_VIRTIO_BLK,
        "qemu_extra_args": [
            "-machine",
            "virt",
            "-cpu",
            "host",
            "-enable-kvm",
            "-serial",
            "stdio",
        ],
    },
    "amd64": {
        "cloudimg_type": CLOUD_IMAGE_TYPE_DISK,
        "cloudimg_arch": "amd64",
        "qemu_bin": "qemu-system-x86_64",
        "qemu_disk_type": QEMU_DISK_TYPE_VIRTIO,
        "qemu_extra_args": [
            "-machine",
            "accel=kvm:tcg",
        ],
    },
    "i386": {
        "cloudimg_type": CLOUD_IMAGE_TYPE_DISK,
        "cloudimg_arch": "i386",
        "qemu_bin": "qemu-system-x86_64",
        "qemu_disk_type": QEMU_DISK_TYPE_VIRTIO,
        "qemu_extra_args": [
            "-machine",
            "accel=kvm:tcg",
        ],
    },
    "ppc64el": {
        "cloudimg_type": CLOUD_IMAGE_TYPE_DISK,
        "cloudimg_arch": "ppc64el",
        "qemu_bin": "qemu-system-ppc64",
        "qemu_disk_type": QEMU_DISK_TYPE_VIRTIO,
        "qemu_extra_args": [
            "-enable-kvm",
            "-machine",
            "pseries,usb=off",
            "-cpu",
            "host",
        ],
    },
    "s390x": {
        "cloudimg_type": CLOUD_IMAGE_TYPE_DISK,
        "cloudimg_arch": "s390x",
        "qemu_bin": "qemu-system-s390x",
        "qemu_disk_type": QEMU_DISK_TYPE_VIRTIO,
        "qemu_extra_args": [
            "-enable-kvm",
            "-machine",
            "s390-ccw-virtio",
        ],
    },
}


def get_release_to_test():
    try:
        import distro

        if distro.id() == "ubuntu-core":
            return "{}.04".format(distro.version())
        return distro.version()
    except (ImportError, CalledProcessError):
        import lsb_release

        return lsb_release.get_distro_information()["RELEASE"]


def get_codename_to_test():
    try:
        import distro

        if distro.id() == "ubuntu-core":
            codename = "focal"
            if distro.version() == "18":
                codename = "bionic"
            elif distro.version() == "16":
                codename = "xenial"
            return codename
        return distro.codename().split()[0].lower()
    except (ImportError, CalledProcessError):
        import lsb_release

        lsb_release.get_distro_information()["CODENAME"]


class QemuRunner(object):
    def __init__(self, arch):
        self.arch = arch
        self.config = QEMU_ARCH_CONFIG[arch]
        self.drive_id = 0
        # Parameters common to all architectures
        self.params = [
            self.config["qemu_bin"],
            "-m",
            "1024",
            "-display",
            "none",
            "-nographic",
            "-net",
            "nic",
            "-net",
            "user,net=10.0.0.0/8,host=10.0.0.1,hostfwd=tcp::2222-:22",
        ]
        # If arch is arm64, add the machine type for gicv3, or default to old
        # type
        if self.arch == "arm64":
            (
                self.config["qemu_extra_args"].extend(
                    ["-machine", "virt,gic_version=host"]
                )
            )
        # Add any architecture-specific parameters
        if "qemu_extra_args" in self.config:
            self.params = self.params + self.config["qemu_extra_args"]

        self.append = []
        if self.config["cloudimg_type"] == CLOUD_IMAGE_TYPE_TAR:
            self.append = self.append + [
                "console=ttyAMA0",
                "earlyprintk=serial",
                "ro",
                "rootfstype=ext4",
                "root=LABEL=cloudimg-rootfs",
                "rootdelay=10",
            ]

    def add_boot_files(self, kernel=None, initrd=None, dtb=None):
        if kernel:
            self.params = self.params + ["-kernel", kernel]
        if initrd:
            self.params = self.params + ["-initrd", initrd]
        if dtb:
            self.params = self.params + ["-dtb", dtb]

    def add_drive(self, cloudimg):
        drive = ["-drive"]
        if self.config["qemu_disk_type"] == QEMU_DISK_TYPE_SD:
            drive = drive + ["file=%s,if=sd,cache=writeback" % (cloudimg)]
        elif self.config["qemu_disk_type"] == QEMU_DISK_TYPE_VIRTIO:
            drive = drive + ["file=%s,if=virtio" % (cloudimg)]
        elif self.config["qemu_disk_type"] == QEMU_DISK_TYPE_VIRTIO_BLK:
            drive = drive + [
                "file=%s,if=none,id=disk.%d" % (cloudimg, self.drive_id)
            ]
            drive = drive + [
                "-device",
                "virtio-blk-device,drive=disk.%d" % (self.drive_id),
            ]
        self.params = self.params + drive
        self.drive_id = self.drive_id + 1

    def get_params(self):
        params = self.params
        if self.append:
            params = params + ["-append", '"%s"' % (" ".join(self.append))]
        return params


class KVMTest(object):

    def __init__(self, image=None, timeout=500, debug_file=None):
        self.image = image
        self.timeout = timeout
        self.debug_file = debug_file
        self.arch = check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True
        ).strip()
        self.qemu_config = QEMU_ARCH_CONFIG[self.arch]
        self.release = get_codename_to_test()

    def url_to_path(self, image_path):
        """
        Test the provided image path to determine if it's a URL or or a simple
        file path
        """
        url = urlparse(image_path)
        if url.scheme == "" or url.scheme == "file":
            # Gives us path wheter we specify a filesystem path or a file URL
            logging.debug("Cloud image exists locally at %s" % url.path)
            return url.path
        elif url.scheme == "http" or url.scheme == "ftp":
            # Gives us the stuff needed to build the URL to download the image
            return self.download_image(image_path)

    def get_image_name_and_url(self, image_url=None):
        """
        Build a URL for official Ubuntu images hosted either at
        cloud-images.ubuntu.com or on a maas server hosting a mirror of
        cloud-images.ubuntu.com
        """

        def _construct_filename(alt_pattern=None, initial_url=None):
            if self.qemu_config["cloudimg_type"] == CLOUD_IMAGE_TYPE_TAR:
                cloud_iso = "%s-server-cloudimg-%s.tar.gz" % (
                    self.release,
                    self.qemu_config["cloudimg_arch"],
                )
            elif alt_pattern == "modern":
                # LP 1635345 - yakkety and beyond have a new naming scheme
                cloud_iso = "%s-server-cloudimg-%s.img" % (
                    self.release,
                    self.qemu_config["cloudimg_arch"],
                )
            elif self.qemu_config["cloudimg_type"] == CLOUD_IMAGE_TYPE_DISK:
                cloud_iso = "%s-server-cloudimg-%s-disk1.img" % (
                    self.release,
                    self.qemu_config["cloudimg_arch"],
                )
            elif initial_url:
                # LP 1662580 - if we pass a full URL, assume the last piece is
                # the filname and return that.
                cloud_iso = initial_url.split("/")[-1]
            else:
                logging.error("Unknown cloud image type")
                sys.exit(1)

            return cloud_iso

        def _construct_url(initial_url, cloud_iso):
            return "/".join((initial_url, cloud_iso))

        def _test_cloud_url(url):
            # test our URL to make sure it's reachable
            try:
                ret = requests.head(url)
            except OSError as e:
                logging.error("Unable to connect to {}".format(url))
                logging.error(" * Message: {}".format(e.with_traceback(None)))
                return False

            if ret.status_code != 200:
                return False
            else:
                return True

        if image_url is None:
            # If we have not specified a URL to get our images from, default
            # to ubuntu.com
            cloud_iso = _construct_filename()
            initial_url = "/".join(
                ("http://cloud-images.ubuntu.com", self.release, "current")
            )
            full_url = _construct_url(initial_url, cloud_iso)
            # Test our URL and rebuild with alternate name
            if not _test_cloud_url(full_url):
                logging.warn("Cloud Image URL not valid: %s" % full_url)
                logging.warn(
                    " * This means we could not reach the remote "
                    "file. Retrying with a different filename "
                    "schema."
                )
                cloud_iso = _construct_filename("modern")
                full_url = _construct_url(initial_url, cloud_iso)
                # retest one more time then exit if it still fails
                if not _test_cloud_url(full_url):
                    logging.error("Cloud URL is not valid: %s" % full_url)
                    logging.error(
                        " * It appears that there is a problem "
                        "finding the expected file.  Check the URL "
                        "noted above."
                    )
                    sys.exit(1)
        else:
            url = urlparse(image_url)
            if (
                url.path.endswith("/")
                or url.path == ""
                or not (
                    url.path.endswith(".img") or url.path.endswith(".tar.gz")
                )
            ):
                # If we have a relative URL (local copies of official images)
                # http://192.168.0.1/ or http://192.168.0.1/images/
                cloud_iso = _construct_filename()
                full_url = _construct_url(image_url.rstrip("/"), cloud_iso)
                if not _test_cloud_url(full_url):
                    logging.warn("Cloud Image URL not valid: %s" % full_url)
                    logging.warn(
                        " * This means we could not reach the remote "
                        "file. Retrying with a different filename "
                        "schema."
                    )
                    cloud_iso = _construct_filename("modern")
                    full_url = _construct_url(image_url.rstrip("/"), cloud_iso)
                    if not _test_cloud_url(full_url):
                        logging.error("Cloud URL is not valid: %s" % full_url)
                        logging.error(
                            " * It appears that there is a problem "
                            "finding the expected file.  Check the "
                            "URL noted above."
                        )
                        sys.exit(1)
            else:
                # Assume anything else is an absolute URL to a remote server
                if not _test_cloud_url(image_url):
                    logging.error("Cloud Image URL invalid: %s" % image_url)
                    logging.error(" * Check the URL and ensure it is correct")
                    sys.exit(1)
                else:
                    full_url = image_url
                    cloud_iso = _construct_filename(initial_url=full_url)

        return full_url, cloud_iso

    def download_image(self, image_url=None):
        """
        Downloads Cloud image for same release as host machine
        """
        if image_url is None:
            full_url, cloud_iso = self.get_image_name_and_url()
        else:
            full_url, cloud_iso = self.get_image_name_and_url(image_url)
        logging.debug("Acquiring cloud image from: {}".format(full_url))

        # Attempt download
        try:
            urllib.request.urlretrieve(full_url, cloud_iso)
        except (
            IOError,
            OSError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as exception:
            logging.error(
                "Failed download of image from %s: %s", image_url, exception
            )
            return False

        # Unpack img file from tar
        if self.qemu_config["cloudimg_type"] == CLOUD_IMAGE_TYPE_TAR:
            cloud_iso_tgz = tarfile.open(cloud_iso)
            cloud_iso = cloud_iso.replace("tar.gz", "img")
            cloud_iso_tgz.extract(cloud_iso)

        if not os.path.isfile(cloud_iso):
            return False

        return cloud_iso

    def boot_image(self, data_disk):
        """
        Attempts to boot the newly created qcow image using
        the config data defined in config.iso
        """

        logging.debug("Attempting boot for:{}".format(data_disk))

        qemu = QemuRunner(self.arch)

        # Assume that a tar type image is not self-bootable, so
        # therefore requires explicit bootfiles (otherwise, why
        # not just use the disk format directly?
        if self.qemu_config["cloudimg_type"] == CLOUD_IMAGE_TYPE_TAR:
            for dir in ["/boot", "/"]:
                kernel = os.path.join(dir, "vmlinuz")
                initrd = os.path.join(dir, "initrd.img")
                if os.path.isfile(kernel):
                    qemu.add_boot_files(kernel=kernel, initrd=initrd)
                    break

        qemu.add_drive(data_disk)

        # Should we attach the cloud config disk
        if os.path.isfile("seed.iso"):
            logging.debug("Attaching Cloud config disk")
            qemu.add_drive("seed.iso")

        params = qemu.get_params()
        logging.debug("Using params:{}".format(" ".join(params)))

        logging.info(
            "Storing VM console output in {}".format(
                os.path.realpath(self.debug_file)
            )
        )
        # Open VM STDERR/STDOUT log file for writing
        try:
            file = open(self.debug_file, "w")
        except IOError:
            logging.error("Failed creating file:{}".format(self.debug_file))
            return False

        # Start Virtual machine
        self.process = Popen(
            params,
            stdin=PIPE,
            stderr=file,
            stdout=file,
            universal_newlines=True,
            shell=False,
        )

    def create_cloud_disk(self):
        """
        Generate Cloud meta data and creates an iso object
        to be mounted as virtual device to instance during boot.
        """
        for file in ["user-data", "meta-data"]:
            logging.debug("Creating cloud %s", file)
            with open(file, "wt") as data_file:
                os.fchmod(data_file.fileno(), 0o777)
                data_file.write(vars()[file.replace("-", "_")])

        # Create Data ISO hosting user & meta cloud config data
        try:
            check_output(
                [
                    "genisoimage",
                    "-output",
                    "seed.iso",
                    "-volid",
                    "cidata",
                    "-joliet",
                    "-rock",
                    "user-data",
                    "meta-data",
                ],
                universal_newlines=True,
            )
        except CalledProcessError:
            logging.exception("Cloud data disk creation failed")

    def log_check(self, stream):
        if "CERTIFICATION BOOT COMPLETE" in stream:
            return 0
        else:
            return 1

    def start(self):
        if self.arch == "arm64":
            # lp:1548539 - For arm64, we need to make sure we're using qemu
            # later than 2.0.0 to enable gic_version functionality
            logging.debug("Checking QEMU version for arm64 arch")
            cmd = "apt-cache policy qemu-system-arm | grep Installed"
            installed_version = (
                check_output(["/bin/bash", "-c", cmd])
                .decode()
                .split(":", 1)[1]
                .strip()
            )

            cmd = 'dpkg --compare-versions "2.0.0" "lt" "{}"'.format(
                installed_version
            )
            retcode = call(["/bin/bash", "-c", cmd])
            if retcode != 0:
                logging.error(
                    "arm64 needs qemu-system version later than " "2.0.0"
                )
                return 1

        logging.debug("Starting KVM Test")
        status = 1
        # Create temp directory:

        date = time.strftime("%b_%d_%Y_")
        with tempfile.TemporaryDirectory("_kvm_test", date) as temp_dir:

            os.chmod(temp_dir, 0o744)
            os.chdir(temp_dir)
            if not self.image:
                logging.debug("No image specified, downloading one now.")
                # Download cloud image
                self.image = self.download_image()
            else:
                logging.debug(
                    "Cloud image location specified: %s" % self.image
                )
                self.image = self.url_to_path(self.image)

            if self.image and os.path.isfile(self.image):

                if "cloud" in self.image:
                    # Will assume we need to supply cloud meta data
                    # for instance boot to be successful
                    self.create_cloud_disk()

                # Boot Virtual Machine
                self.boot_image(self.image)

                # If running in console, reset console window to regain
                # control from VM Serial I/0
                if sys.stdout.isatty():
                    call("reset")
                # Check to be sure VM boot was successful
                self.elapsed_time = 0
                status = 1
                while self.elapsed_time <= self.timeout:
                    # Check log every 30 seconds to see if the VM boots
                    with open(self.debug_file, "r") as debug_file:
                        status = self.log_check(debug_file.read())
                        if status == 0:
                            logging.info("Booted successfully.")
                            break
                        else:
                            # Sleep 30 seconds and log check again
                            time.sleep(30)
                            self.elapsed_time += 30
                else:
                    # Finally, if we didn't get the Success message by now try
                    # one more time and return 1 if we still haven't booted
                    if status != 0:
                        with open(self.debug_file, "r") as debug_file:
                            stream = debug_file.read()
                            status = self.log_check(stream)
                            if status == 0:
                                logging.info("Booted successfully.")
                            else:
                                logging.error("KVM instance failed to boot.")
                                logging.error("Console output".center(72, "="))
                                logging.error(stream)
                self.process.terminate()
            elif not self.image:
                logging.error("Could not find downloaded image")
            else:
                logging.error("Could not find: {}".format(self.image))

        return status


class RunCommand(object):
    """
    Runs a command and can return all needed info:
    * stdout
    * stderr
    * return code
    * original command

    Convenince class to avoid the same repetitive code to run shell commands.
    """

    def __init__(self, cmd=None):
        self.stdout = None
        self.stderr = None
        self.returncode = None
        self.cmd = cmd
        self.run(self.cmd)

    def run(self, cmd):
        proc = Popen(
            shlex.split(cmd),
            stdout=PIPE,
            stderr=PIPE,
            stdin=DEVNULL,
            universal_newlines=True,
        )
        self.stdout, self.stderr = proc.communicate()
        self.returncode = proc.returncode


class LXDTest:
    """This class represents a LXD container instance test."""

    def __init__(self, template=None, rootfs=None):
        self.image_url = rootfs
        self.template_url = template
        self.image_tarball = None
        self.template_tarball = None
        self.name = "testbed"
        self.image_alias = uuid4().hex
        self.default_remote = "ubuntu:"
        self.os_version = get_release_to_test()
        self.release = get_codename_to_test()

    def run_command(
        self, cmd: str, log_stderr: bool = True, on_guest: bool = False
    ):
        """Runs a shell command."""
        if on_guest:
            cmd = f"lxc exec {self.name} -- {cmd}"
        task = RunCommand(cmd)
        if task.returncode != 0:
            logging.error(
                "Command %s returned a code of %d", task.cmd, task.returncode
            )
            logging.error(" STDOUT: %s", task.stdout)
            if log_stderr:
                logging.error(" STDERR: %s", task.stderr)
            return False

        logging.debug("Command %s:", task.cmd)
        if task.stdout:
            logging.debug(" STDOUT: %s", task.stdout)
        if task.stderr and log_stderr:
            logging.debug(" STDERR: %s", task.stderr)
        if not task.stderr and not task.stdout:
            logging.debug(" Command returned no output")
        return True

    def init_lxd(self):
        """Initializes LXD."""
        logging.debug("Attempting to initialize LXD")
        if self.run_command("lxd waitready --timeout 5", log_stderr=False):
            logging.debug("LXD already initialized")
            return True

        if not self.run_command("lxd init --auto"):
            logging.debug("Error encountered while initializing LXD")
            return False

        return True

    def retrieve_template(self):
        """Retrieves LXD template image."""
        if self.template_url:
            logging.debug("Downloading template.")
            targetfile = urlparse(self.template_url).path.split("/")[-1]
            filename = os.path.join("/tmp", targetfile)
            if not os.path.isfile(filename):
                self.template_tarball = self.download_images(
                    self.template_url, filename
                )
                if not self.template_tarball:
                    logging.error(
                        "Unable to download %s from %s",
                        targetfile,
                        self.template_url,
                    )
                    return False
            else:
                logging.debug(
                    "Template file %s already exists. Skipping Download.",
                    filename,
                )
                self.template_tarball = filename

        return True

    def retrieve_image(self):
        """Retrieve LXD image."""
        if self.image_url:
            logging.debug("Downloading image.")
            targetfile = urlparse(self.image_url).path.split("/")[-1]
            filename = os.path.join("/tmp", targetfile)
            if not os.path.isfile(filename):
                self.image_tarball = self.download_images(
                    self.image_url, filename
                )
                if not self.image_tarball:
                    logging.error(
                        "Unable to download %s from %s",
                        targetfile,
                        self.image_url,
                    )
                    logging.error("Aborting")
                    return False
            else:
                logging.debug(
                    "Image file %s already exists. Skipping Download.",
                    filename,
                )
                self.image_tarball = filename

        return True

    def insert_images(self):
        """Insert LXD images."""
        if self.template_tarball and self.image_tarball:
            logging.debug("Importing images into LXD")
            cmd = (
                f"lxc image import {self.template_tarball} "
                f"rootfs {self.image_tarball} --alias {self.image_alias}"
            )
            if not self.run_command(cmd):
                logging.error(
                    "Error encountered while attempting to import images into LXD"
                )
                return False
            return True

        logging.debug(
            "No local image available, attempting to import from default remote."
        )
        retries = 2
        cmd = (
            f"lxc image copy {self.default_remote}{self.os_version} "
            f"local: --alias {self.image_alias}"
        )
        for _ in range(retries):
            if self.run_command(cmd):
                break
            logging.error(
                "Error encountered while attempting to import images from default remote"
            )
            logging.error("Attempting up to %d times.", retries)
        else:
            return False

        return True

    def setup(self):
        """Sets up LXD."""
        # Initialize LXD
        if not self.init_lxd():
            return False

        # Retrieve LXD images
        if not self.retrieve_template() or not self.retrieve_image():
            return False

        # Insert LXD images
        if not self.insert_images():
            return False

        return True

    def add_gpu_device(self, gpu_vendor: str, gpu_pci: Optional[str] = None):
        """Adds a GPU device to the instance."""
        logging.debug("Passing through GPU device")
        cmd = f"lxc config device add {self.name} gpu gpu gputype=physical"
        if gpu_pci:
            cmd += f" pci={gpu_pci}"
        return self.run_command(cmd)

    def configure_gpu_device(
        self, gpu_vendor: str, gpu_pci: Optional[str] = None
    ):
        """Performs additional GPU configuration on instance."""
        if gpu_vendor == "nvidia":
            logging.debug("Passing NVIDIA runtime through to instance")
            cmd = f"lxc config set {self.name} nvidia.runtime=true"
            if not self.run_command(cmd):
                logging.error("Failed to pass NVIDIA runtime to instance")
                return False
        elif gpu_vendor == "amd":
            logging.debug("Passing AMD Kernel Fusion Driver through")
            cmd = f"lxc config device add {self.name} kfd unix-char path=/dev/kfd"
            if not self.run_command(cmd):
                logging.error("Failed to pass AMD KFD to instance")
                return False

        return True

    def add_apt_repo(
        self,
        name: str,
        repo_line: str,
        gpg_url: str,
        gpg_fingerprint: str,
        pinfile: Optional[str] = None,
    ):
        """Adds an APT repository to the instance."""
        logging.debug("Downloading GPG key from %s", gpg_url)
        gpg_dest = f"/usr/share/keyrings/{name}.gpg"
        cmds = [
            "set -e",
            f"wget -O {name}.gpg '{gpg_url}'",
            f"gpg --no-default-keyring --keyring ./tmp.gpg --import {name}.gpg",
            f"gpg --no-default-keyring --keyring ./tmp.gpg --fingerprint {gpg_fingerprint}",
            f"gpg --yes --no-default-keyring --keyring ./tmp.gpg --export --output {gpg_dest}",
            f"rm ./tmp.gpg ./tmp.gpg~ ./{name}.gpg",
        ]
        cmd = f"bash -c \"{'; '.join(cmds)}\""
        if not self.run_command(cmd, on_guest=True):
            logging.error("Failed to import GPG key from %s", gpg_url)
            return False

        # Create/download pinfile.
        if pinfile:
            pinfile_dest = f"/etc/apt/preferences.d/{name}-pin-600"
            if pinfile.startswith("http"):
                logging.debug("Downloading pinfile")
                cmd = f"wget -O {pinfile_dest} {pinfile}"
            else:
                logging.debug("Creating pinfile")
                cmd = f"bash -c \"echo -e '{pinfile}' | tee {pinfile_dest}\""
            if not self.run_command(cmd, on_guest=True):
                logging.error("Failed to create/download pinfile")
                return False

        logging.debug("Setting up APT repository: %s", name)
        repo_dest = f"/etc/apt/sources.list.d/{name}.list"
        list_file = f"deb [signed-by={gpg_dest}] {repo_line}"
        cmd = f"bash -c \"echo '{list_file}' | tee {repo_dest}\""
        if not self.run_command(cmd, on_guest=True):
            logging.error("Failed to create APT repository")
            return False

        logging.debug("Updating APT cache")
        if not self.run_command("apt-get -q update", on_guest=True):
            logging.error("Failed to update APT cache")
            return False

        return True

    def build_vgpu_test(self, gpu_vendor: str, gpu_pci: Optional[str] = None):
        """Fetches and builds the vGPU test on the instance."""
        test_name = ""
        cmake_cmd = "cmake ../mixbench-{test_name}"

        # Depending on the GPU vendor:
        #   * Install dependencies
        #   * Set the mixbench test name
        #   * (If needed) Add env vars or parameters to cmake command
        if gpu_vendor == "nvidia":
            logging.debug("Adding NVIDIA CUDA repository to instance")
            osrelease = f"ubuntu{self.os_version.replace('.', '')}"
            arch = os.uname().machine
            repo_url = f"https://developer.download.nvidia.com/compute/cuda/repos/{osrelease}/{arch}"
            if not self.add_apt_repo(
                "cuda",
                f"{repo_url} /",
                gpg_url=f"{repo_url}/3bf863cc.pub",
                gpg_fingerprint="EB693B3035CD5710E231E123A4B469963BF863CC",
                pinfile=f"{repo_url}/cuda-{osrelease}.pin",
            ):
                return False

            logging.debug("Installing CUDA toolkit on instance")
            cmd = "apt-get -q install -y --no-install-recommends build-essential cmake cuda-toolkit"
            if not self.run_command(cmd, on_guest=True):
                logging.error("CUDA toolkit installation failed")
                return False

            logging.debug("Finding CUDA capability for GPU")
            cuda_arch = "native"
            cmd = f"lxc exec {self.name} -- nvidia-smi --query-gpu=compute_cap --format=csv,noheader"
            proc = subprocess.run(
                shlex.split(cmd), check=False, capture_output=True, text=True
            )
            if proc.returncode == 0:
                cuda_arch = proc.stdout.strip().replace(".", "")
            logging.debug("Using CUDA architecture '%s'", cuda_arch)

            test_name = "cuda"
            nvcc_path = "/usr/local/cuda/bin/nvcc"
            cmake_cmd = f"CUDACXX={nvcc_path} {cmake_cmd} -DCMAKE_CUDA_ARCHITECTURES={cuda_arch}"
        elif gpu_vendor == "amd":
            # TODO: Test if hardcoding v6.2 works on older LTS releases
            gpg_url = "https://repo.radeon.com/rocm/rocm.gpg.key"
            gpg_fingerprint = "CA8BB4727A47B4D09B4EE8969386B48A1A693C5C"
            amd_version = "6.2"
            amd_repo = f"https://repo.radeon.com/amdgpu/{amd_version}/ubuntu"
            rocm_repo = f"https://repo.radeon.com/rocm/apt/{amd_version}"
            if not self.add_apt_repo(
                "amdgpu",
                f"{amd_repo} {self.release} main",
                gpg_url=gpg_url,
                gpg_fingerprint=gpg_fingerprint,
            ) or not self.add_apt_repo(
                "rocm",
                f"{rocm_repo} {self.release} main",
                gpg_url=gpg_url,
                gpg_fingerprint=gpg_fingerprint,
                pinfile="Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600",
            ):
                return False

            logging.debug("Installing ROCm on instance")
            cmd = "apt-get -q install -y --no-install-recommends cmake build-essential rocm"
            if not self.run_command(cmd, on_guest=True):
                logging.error("ROCm installation failed")
                return False

            test_name = "hip"
        else:
            logging.error("Unsupported GPU vendor %s", gpu_vendor)
            return False

        logging.debug("Fetching and compiling vGPU test on instance")
        cmds = [
            "set -e",
            "git clone https://github.com/ekondis/mixbench.git",
            f"mkdir mixbench/build-{test_name}",
            f"cd mixbench/build-{test_name}",
            cmake_cmd.format(test_name=test_name),
            "make",
            f"ln -s ~/mixbench/build-{test_name}/mixbench-{test_name} ~/vgpu-test",
        ]
        cmd = f"bash -c \"{'; '.join(cmds)}\""
        return self.run_command(cmd, on_guest=True)

    def download_images(self, url, filename):
        """Downloads LXD files for same release as host machine."""
        # TODO: Clean this up to use a non-internet simplestream on MAAS server
        logging.debug("Attempting download of %s from %s", filename, url)
        try:
            urllib.request.urlretrieve(url, filename)
        except (
            IOError,
            OSError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as exception:
            logging.error(
                "Failed download of image from %s: %s", url, exception
            )
            return False
        except ValueError as verr:
            logging.error("Invalid URL %s", url)
            logging.exception(verr)
            return False

        if not os.path.isfile(filename):
            logging.warning("Can not find %s", filename)
            return False

        return filename

    def cleanup(self):
        """Cleans up test files and instances created."""
        logging.debug("Cleaning up images and instance created during test")
        cmd = f"lxc image delete {self.image_alias}"
        self.run_command(cmd, log_stderr=False)
        self.run_command(f"lxc delete --force {self.name}", log_stderr=False)

    def launch(self):
        """Sets up and creates the container."""
        if not self.setup():
            logging.error("One or more setup stages failed.")
            return False

        logging.debug("Launching container")
        if not self.run_command(f"lxc launch {self.image_alias} {self.name}"):
            return False

        logging.debug("Container listing:")
        if not self.run_command("lxc list type=container"):
            return False

        return True

    def test(self):
        """Creates a LXD container and performs the test."""
        if not self.launch():
            return False

        logging.debug("Testing container")
        cmd = "dd if=/dev/urandom of=testdata.txt bs=1024 count=1000"
        if not self.run_command(cmd, on_guest=True):
            return False

        return True

    def test_vgpu(
        self,
        gpu_vendor: str,
        gpu_pci: Optional[str] = None,
        run_count: int = VGPU_RUNS,
        threshold_sec: float = VGPU_THRESHOLD_SEC,
    ):
        """Creates a container and performs the vGPU test."""
        if gpu_vendor not in GPU_VENDORS:
            logging.error("Unrecognized GPU vendor %s", gpu_vendor)
            return False

        if not self.launch():
            return False

        if not self.add_gpu_device(gpu_vendor, gpu_pci):
            logging.error("Failed to add GPU device to instance")
            return False

        logging.debug("Wait for network to be up")
        time.sleep(20)

        # Configure GPU device
        if not self.configure_gpu_device(gpu_vendor, gpu_pci):
            logging.error("One or more steps of GPU configuration failed")
            return False

        logging.debug("Restarting instance")
        if not self.run_command(f"lxc restart {self.name}"):
            return False

        logging.debug("Wait for network to be up")
        time.sleep(20)

        logging.debug("Building vGPU test")
        if not self.build_vgpu_test(gpu_vendor, gpu_pci):
            return False

        logging.debug("Testing container %d times", run_count)
        total_runtime = 0.0
        result = True
        for i in range(run_count):
            tic = time.time()
            if not self.run_command("./vgpu-test", on_guest=True):
                logging.error("vGPU test failed")
                return False
            toc = time.time()
            runtime = toc - tic
            total_runtime += runtime
            logging.debug("Runtime #%d (sec): %f", i, runtime)

        avg_runtime = total_runtime / run_count
        logging.info("Average runtime (sec): %f", avg_runtime)
        result = avg_runtime < threshold_sec
        if not result:
            logging.error(
                "Average runtime %fs greater than threshold %fs",
                avg_runtime,
                threshold_sec,
            )
        return result


class LXDTest_vm(LXDTest):
    """This class represents a LXD VM instance test."""

    @override
    def __init__(self, template=None, image=None, launch_options=None):
        super().__init__(template, image)
        self.launch_options = launch_options

    @override
    def insert_images(self):
        if self.template_tarball and self.image_tarball:
            logging.debug("Importing images into LXD")
            cmd = (
                f"lxc image import {self.template_tarball} {self.image_tarball} "
                f"--alias {self.image_alias}"
            )
            if not self.run_command(cmd):
                logging.error(
                    "Error encountered while attempting to import images into LXD"
                )
                return False
        return True

    @override
    def launch(self):
        if not self.setup():
            logging.error("One or more setup stages failed.")
            return False

        logging.debug("Launching virtual machine")
        if not self.image_url and not self.template_url:
            logging.debug(
                "No local image available, attempting to import from default remote."
            )
            cmd = f"lxc init {self.default_remote}{self.os_version} {self.name} --vm"
        else:
            cmd = f"lxc init {self.image_alias} {self.name} --vm"
        if self.launch_options:
            cmd = f"{cmd} {' '.join(self.launch_options)}"
        if not self.run_command(cmd):
            return False

        logging.debug("Start VM:")
        if not self.run_command(f"lxc start {self.name}"):
            return False

        logging.debug("Virtual machine listing:")
        if not self.run_command("lxc list type=virtual-machine"):
            return False

        return True

    @override
    def add_gpu_device(self, gpu_vendor: str, gpu_pci: Optional[str] = None):
        # Hot plugging is only supported on containers
        logging.debug("Stopping virtual machine to add GPU device")
        if not self.run_command(f"lxc stop --force {self.name}"):
            return False

        if not super().add_gpu_device(gpu_vendor, gpu_pci):
            return False

        logging.debug("Starting virtual machine")
        if not self.run_command(f"lxc start {self.name}"):
            return False

        return True

    @override
    def configure_gpu_device(
        self, gpu_vendor: str, gpu_pci: Optional[str] = None
    ):
        if not self.run_command("apt-get -q update -y", on_guest=True):
            return False

        if gpu_vendor == "nvidia":
            logging.debug("Installing ubuntu-drivers tool")
            cmd = "apt-get -q install -y ubuntu-drivers-common"
            if not self.run_command(cmd, on_guest=True):
                return False

            logging.debug("Installing NVIDIA drivers on VM")
            cmd = "ubuntu-drivers install"
            if not self.run_command(cmd, on_guest=True):
                return False
        elif gpu_vendor == "amd":
            logging.debug("Updating machine")
            cmd = f"bash -c \"apt-get -q update -y; apt-get -q upgrade -y\""
            if not self.run_command(cmd, on_guest=True):
                return False

            logging.debug("Installing AMD GPU drivers")
            cmd = "apt-get -q install -y xserver-xorg-video-all"
            if not self.run_command(cmd, on_guest=True):
                return False

            logging.debug("Enabling AMD sysmodules")
            cmds = [
                "set -e",
                "apt-get -q install -y linux-modules-extra-$(uname -r)",
                "modprobe amdgpu",
                "modprobe radeon",
                r"echo -e 'amdgpu\nradeon' >> /etc/modules-load.d/amdgpu.conf",
                "update-initramfs -u",
            ]
            cmd = f"bash -c \"{'; '.join(cmds)}\""
            if not self.run_command(cmd, on_guest=True):
                return False
        return True

    @override
    def test(self):
        """Creates a LXD virtual machine and performs the test."""
        if not self.launch():
            return False

        logging.debug("Wait for vm to boot")
        wait_interval = 5
        max_wait_duration = 300
        time_waited = 0
        while time_waited < max_wait_duration:
            time.sleep(wait_interval)
            if self.run_command(
                "lsb_release -a", log_stderr=False, on_guest=True
            ):
                print("VM started and booted successfully")
                return True
            logging.debug("Re-verify VM booted")
            time_waited += wait_interval

        logging.debug("testing vm failed")
        return False


def test_lxd_vm(args):
    """Performs the LXD VM test."""
    logging.debug("Executing LXD VM Test")

    template = None
    image = None

    # First in priority are environment variables.
    if "LXD_TEMPLATE" in os.environ:
        template = os.environ["LXD_TEMPLATE"]
    if "KVM_IMAGE" in os.environ:
        image = os.environ["KVM_IMAGE"]

    # Finally, highest-priority are command line arguments.
    if args.template:
        template = args.template
    if args.image:
        image = args.image

    lxd_test = LXDTest_vm(template, image)

    result = lxd_test.test()
    lxd_test.cleanup()
    if result:
        print("PASS: Virtual Machine was successfully started and checked")
        sys.exit(0)
    else:
        print("FAIL: Virtual Machine was not started and checked")
        sys.exit(1)


def test_lxd_vm_vgpu(args):
    """Performs the LXD VM vGPU test."""
    logging.debug("Executing LXD VM vGPU Test")

    template = args.template or os.getenv("LXD_TEMPLATE")
    image = args.image or os.getenv("KVM_IMAGE")
    run_count = int(args.count or os.getenv("LXD_VGPU_RUNS") or VGPU_RUNS)
    threshold_sec = float(
        args.threshold or os.getenv("LXD_VGPU_THRESHOLD") or VGPU_THRESHOLD_SEC
    )

    # Increase storage for drivers installation.
    # Disable secureboot to simplify drivers installation.
    lxd_test = LXDTest_vm(
        template,
        image,
        launch_options=["-d root,size=50GB", "-c security.secureboot=false"],
    )
    result = lxd_test.test_vgpu(
        args.gpu_vendor, args.gpu_pci, run_count, threshold_sec
    )
    lxd_test.cleanup()

    if result:
        print("PASS: Virtual machine was successfully started and checked")
        sys.exit(0)
    else:
        print("FAIL: Virtual machine was not started and checked")
        sys.exit(1)


def test_lxd(args):
    """Performs the LXD test."""
    logging.debug("Executing LXD Test")

    template = None
    rootfs = None

    # First in priority are environment variables.
    if "LXD_TEMPLATE" in os.environ:
        template = os.environ["LXD_TEMPLATE"]
    if "LXD_ROOTFS" in os.environ:
        rootfs = os.environ["LXD_ROOTFS"]

    # Finally, highest-priority are command line arguments.
    if args.template:
        template = args.template
    if args.rootfs:
        rootfs = args.rootfs

    lxd_test = LXDTest(template, rootfs)

    result = lxd_test.test()
    lxd_test.cleanup()
    if result:
        print("PASS: Container was succssfully started and checked")
        sys.exit(0)
    else:
        print("FAIL: Container was not started and checked")
        sys.exit(1)


def test_lxd_vgpu(args):
    """Performs the LXD vGPU test."""
    logging.debug("Executing LXD vGPU Test")

    template = args.template or os.getenv("LXD_TEMPLATE")
    rootfs = args.rootfs or os.getenv("LXD_ROOTFS")
    run_count = int(args.count or os.getenv("LXD_VGPU_RUNS") or VGPU_RUNS)
    threshold_sec = float(
        args.threshold or os.getenv("LXD_VGPU_THRESHOLD") or VGPU_THRESHOLD_SEC
    )

    lxd_test = LXDTest(template, rootfs)
    result = lxd_test.test_vgpu(
        args.gpu_vendor, args.gpu_pci, run_count, threshold_sec
    )
    lxd_test.cleanup()

    if result:
        print("PASS: Container was successfully started and checked")
        sys.exit(0)
    else:
        print("FAIL: Container was not started and checked")
        sys.exit(1)


def test_kvm(args):
    """Performs the KVM test."""
    logging.debug("Executing KVM Test")

    image = ""
    timeout = ""

    # First in priority are environment variables.
    if "KVM_TIMEOUT" in os.environ:
        try:
            timeout = float(os.environ["KVM_TIMEOUT"])
        except ValueError as err:
            logging.warning("TIMEOUT env variable: %s" % err)
            timeout = DEFAULT_TIMEOUT
    if "KVM_IMAGE" in os.environ:
        image = os.environ["KVM_IMAGE"]

    # Finally, highest-priority are command line arguments.
    if args.timeout:
        timeout = args.timeout
    elif not timeout:
        timeout = DEFAULT_TIMEOUT
    if args.image:
        image = args.image

    kvm_test = KVMTest(image, timeout, args.log_file)
    # If arch is ppc64el, disable smt
    if kvm_test.arch == "ppc64el":
        os.system("/usr/sbin/ppc64_cpu --smt=off")
    result = kvm_test.start()
    # If arch is ppc64el, re-enable smt
    if kvm_test.arch == "ppc64el":
        os.system("/usr/sbin/ppc64_cpu --smt=on")

    sys.exit(result)


def main():
    """Main entrypoint of the program."""
    parser = ArgumentParser(description="Virtualization Test")
    subparsers = parser.add_subparsers()

    # Main cli options
    kvm_test_parser = subparsers.add_parser(
        "kvm", help=("Run kvm virtualization test")
    )
    lxd_test_parser = subparsers.add_parser(
        "lxd", help=("Run the LXD validation test")
    )
    lxd_test_vm_parser = subparsers.add_parser(
        "lxdvm", help=("Run the LXD VM validation test")
    )
    parser.add_argument(
        "--debug",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
    )

    # Sub test options
    kvm_test_parser.add_argument("-i", "--image", type=str, default=None)
    kvm_test_parser.add_argument("-t", "--timeout", type=int)
    kvm_test_parser.add_argument(
        "-l",
        "--log-file",
        default="virt_debug",
        help="Location for debugging output log. Defaults to %(default)s.",
    )
    kvm_test_parser.set_defaults(func=test_kvm)

    # Sub test options
    lxd_test_parser.add_argument("--template", type=str, default=None)
    lxd_test_parser.add_argument("--rootfs", type=str, default=None)
    lxd_test_parser.set_defaults(func=test_lxd)
    lxd_subparsers = lxd_test_parser.add_subparsers()
    lxd_vgpu_parser = lxd_subparsers.add_parser(
        "vgpu", help="Run the LXD vGPU validation test"
    )
    lxd_vgpu_parser.add_argument(
        "--gpu-vendor", type=str, choices=GPU_VENDORS, default=GPU_VENDORS[0]
    )
    lxd_vgpu_parser.add_argument("--gpu-pci", type=str, default=None)
    lxd_vgpu_parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=None,
        help="How many times to run vGPU test.",
    )
    lxd_vgpu_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Threshold (sec) for vGPU test.",
    )
    lxd_vgpu_parser.set_defaults(func=test_lxd_vgpu)

    # Sub test options
    lxd_test_vm_parser.add_argument("--template", type=str, default=None)
    lxd_test_vm_parser.add_argument("--image", type=str, default=None)
    lxd_test_vm_parser.set_defaults(func=test_lxd_vm)
    lxd_vm_subparsers = lxd_test_vm_parser.add_subparsers()
    lxd_vm_vgpu_parser = lxd_vm_subparsers.add_parser(
        "vgpu", help="Run the LXD VM vGPU validation test"
    )
    lxd_vm_vgpu_parser.add_argument(
        "--gpu-vendor", type=str, choices=GPU_VENDORS, default=GPU_VENDORS[0]
    )
    lxd_vm_vgpu_parser.add_argument("--gpu-pci", type=str, default=None)
    lxd_vm_vgpu_parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=None,
        help="How many times to run vGPU test.",
    )
    lxd_vm_vgpu_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Threshold (sec) for vGPU test.",
    )
    lxd_vm_vgpu_parser.set_defaults(func=test_lxd_vm_vgpu)

    args = parser.parse_args()

    try:
        logging.basicConfig(level=args.log_level)
    except AttributeError:
        pass  # avoids exception when trying to run without specifying 'kvm'

    # silence normal output from requests module
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Verify args
    try:
        args.func(args)
    except AttributeError:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
