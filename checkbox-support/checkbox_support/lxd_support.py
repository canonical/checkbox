"""Support interfaces related to LXD.

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

import logging
import os
import shlex
import subprocess
import urllib.request
import uuid
from typing import List, Optional
from urllib.parse import urlparse

from checkbox_support.helpers.retry import retry, run_with_retry
from plainbox.impl.decorators import cached_property

logger = logging.getLogger(__file__)
logger.addHandler(logging.StreamHandler())


class LXD:
    """This class represents a LXD instance."""

    def __init__(
        self,
        template_url: Optional[str] = None,
        image_url: Optional[str] = None,
        name: str = "testbed",
        remote: str = "ubuntu:",
        release: Optional[str] = None,
    ):
        self.template_url = template_url
        self.image_url = image_url
        self.name = name
        self.remote = remote
        self.image_alias = uuid.uuid4()
        self._release = release

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

    @cached_property
    def release(self) -> str:
        """Gets the Ubuntu release used."""
        if self._release:
            return self._release

        try:
            import distro

            if distro.id() == "ubuntu-core":
                return "{}.04".format(distro.version())
            return distro.version()
        except ImportError:
            import lsb_release  # type: ignore

            return lsb_release.get_distro_information()["RELEASE"]

    @retry(5, 2)
    def download_image(self, url, filename):
        """Downloads LXD files for same release as host machine."""
        if os.path.isfile(filename):
            return
        logger.debug("Attempting download of %s from %s", filename, url)
        urllib.request.urlretrieve(url, filename)
        if not os.path.isfile(filename):
            raise FileNotFoundError(filename)

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
            logger.debug("Command: %s", cmd)
            out = subprocess.check_output(
                shlex.split(cmd),
                stderr=stderr_pipe,
                stdin=subprocess.DEVNULL,
                universal_newlines=True,
            )
            logger.debug(" STDOUT: %s", out)
        except subprocess.CalledProcessError as e:
            logger.error("Command failed: %s", cmd)
            logger.info(" STDOUT: %s", e.stdout)
            if not ignore_errors:
                raise

    def insert_images(self):
        """Insert LXD template and image images."""
        if self.template and self.image:
            logger.debug("Importing images into LXD")
            self.run(
                "lxc image import {} rootfs {} --alias {}".format(
                    self.template, self.image, self.image_alias.hex
                )
            )
        else:
            logger.debug("No local images, attempting import from remote")
            run_with_retry(
                self.run,
                5,
                2,
                "lxc image copy {}{} local: --alias {}".format(
                    self.remote, self.release, self.image_alias.hex
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

    def launch(self, options: Optional[List[str]] = None):
        """Sets up and creates the instance."""
        cmd = ["lxc", "launch", self.image_alias.hex, self.name]
        if options:
            cmd += options
        self.run(" ".join(cmd))

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

    @retry(10, 10)
    def wait_until_running(self):
        """Waits for the instance to be up and running."""
        self.run("systemctl is-system-running --wait", on_guest=True)

    def add_device(
        self,
        device: str,
        device_type: str,
        options: Optional[List[str]] = None,
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
            logger.debug("Importing images into LXD")
            self.run(
                "lxc image import {} {} --alias {}".format(
                    self.template, self.image, self.image_alias.hex
                )
            )

    def launch(self, options: Optional[List[str]] = None):
        logger.debug("Initializing virtual machine")
        cmd = ["lxc", "init"]
        if not self.image and not self.template:
            logger.debug("No local image, importing from remote")
            cmd += ["{}{}".format(self.remote, self.release)]
        else:
            cmd += [self.image_alias.hex]
        cmd += [self.name, "--vm"]
        if options:
            cmd += options
        self.run(" ".join(cmd))

        logger.debug("Starting virtual machine")
        self.run("lxc start {}".format(self.name))

    def add_device(self, device: str, device_type: str, options=None):
        # Hot plugging is only supported on containers
        self.stop(force=True)
        super().add_device(device, device_type, options)
        self.start()
