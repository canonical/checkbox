# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
import itertools
import os.path
import re
import time
from pathlib import Path
import textwrap
from contextlib import suppress

import pylxd.exceptions
from loguru import logger
from metabox.core.lxd_execute import interactive_execute
from metabox.core.lxd_execute import run_or_raise


class MachineConfig:
    def __init__(self, role, config):
        self.role = role
        self.alias = config["alias"]
        self.origin = config["origin"]
        self.uri = config.get("uri", "")
        self.profiles = config.get("profiles", [])
        self.transfer = config.get("transfer", [])
        self.setup = config.get("setup", [])
        self.checkbox_core_snap = config.get("checkbox_core_snap", {})
        self.checkbox_snap = config.get("checkbox_snap", {})
        self.snap_name = config.get("name", "")
        self.revision = config.get("revision", "current")
        if not self.snap_name:
            self.snap_name = "checkbox"

    def _slug_revision(self):
        # make revision a valid name str
        # avoid slash, not valid in lxd names
        return self.revision.replace("/", "-")

    def __members(self):
        return (
            self.role,
            self.alias,
            self.origin,
            self.snap_name,
            self.uri,
            self.revision,
            " ".join(self.profiles),
            " ".join(itertools.chain(*self.transfer)),
            " ".join(self.setup),
        )

    def __repr__(self):
        return "<{} alias:{!r} origin:{!r} revision: {!r}>".format(
            self.role, self.alias, self.origin, self.revision
        )

    def __str__(self):
        return "{}-{}-{}-{}".format(
            self.role, self.alias, self.origin, self._slug_revision()
        )

    def __hash__(self):
        return hash(self.__members())

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__members() == other.__members()
        else:
            return False


class ContainerBaseMachine:
    """Base implementation of Machine using LXD container as the backend."""

    CHECKBOX = "checkbox-cli "  # mind the trailing space !

    def __init__(self, config, container):
        self.config = config
        self._container = container
        self._checkbox_wrapper = self.CHECKBOX

    def execute(self, cmd, env={}, verbose=False, timeout=0):
        return run_or_raise(
            self._container, self._checkbox_wrapper + cmd, env, verbose, timeout
        )

    def interactive_execute(self, cmd, env={}, verbose=False, timeout=0):
        return interactive_execute(
            self._container, self._checkbox_wrapper + cmd, env, verbose, timeout
        )

    def rollback_to(self, savepoint):
        if self._container.status != "Stopped":
            self._container.stop(wait=True)
        self._container.restore_snapshot(savepoint, wait=True)
        self._container.start(wait=True)
        logger.opt(colors=True).debug("[<y>restored</y>    ] {}", self._container.name)
        if self.config.role == "service":
            attempts_left = 60
            out = ""
            while attempts_left and out.rstrip() not in (
                "starting",
                "running",
                "degraded",
            ):
                time.sleep(1)
                (ret, out, err) = self._container.execute(
                    ["systemctl", "is-system-running"]
                )
                attempts_left -= 1
            if not attempts_left:
                raise SystemExit("Rollback failed (systemd not ready)")

    def put(self, filepath, data, mode=None, uid=1000, gid=1000):
        try:
            self._container.files.put(filepath, data, mode, uid, gid)
        except pylxd.exceptions.LXDAPIException:
            logger.error("Failed to create {}", filepath)
            raise

    def get_connecting_cmd(self):
        return "lxc exec {} -- sudo --user ubuntu --login".format(self._container.name)

    @property
    def address(self):
        addresses = self._container.state().network["eth0"]["addresses"]
        return addresses[0]["address"]

    def get_early_dir_transfer(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def get_file_transfer(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def get_early_setup(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def get_late_setup(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def start_remote(self, host, launcher, cmd_args="", interactive=False, timeout=0):
        assert self.config.role == "remote"

        if interactive:
            # Return a PTS object to interact with
            return self.interactive_execute(
                "remote {} {} {}".format(cmd_args, host, launcher), verbose=True, timeout=timeout
            )
        else:
            # Return an ExecuteResult named tuple
            return self.execute(
                "remote {} {} {}".format(cmd_args, host, launcher), verbose=True, timeout=timeout
            )

    def start(self, cmd=None, env={}, interactive=False, timeout=0):
        assert self.config.role == "local"
        if interactive:
            # Return a PTS object to interact with
            return self.interactive_execute(cmd, env=env, verbose=True, timeout=timeout)
        else:
            # Return an ExecuteResult named tuple
            return self.execute(cmd, env=env, verbose=True, timeout=timeout)

    def run_cmd(self, cmd, env={}, interactive=False, timeout=0):
        verbose = True
        if interactive:
            # Return a PTS object to interact with
            return interactive_execute(self._container, cmd, env, verbose, timeout)
        else:
            # Return an ExecuteResult named tuple
            return run_or_raise(self._container, cmd, env, verbose, timeout)

    def start_service(self, force=False):
        """
        .. note:: You should override this method in your subclass.
        """
        pass

    def stop_service(self):
        """
        .. note:: You should override this method in your subclass.
        """
        pass

    def reboot(self, timeout=0):
        verbose = True
        return run_or_raise(self._container, "sudo reboot", verbose, timeout)

    def is_service_active(self):
        """
        .. note:: You should override this method in your subclass.
        """
        pass

    def start_user_session(self):
        assert self.config.role in ("service", "local")
        # Start a set of ubuntu-user-owned processes to fake an active GDM user
        # session (A virtual framebuffer and a pulseaudio server with a dummy
        # output)
        interactive_execute(
            self._container,
            "DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority "
            "XDG_SESSION_TYPE=x11 /usr/bin/Xvfb -screen 0 1280x1024x24",
        )
        # Note: running the following commands as part of standard setup does
        # not make them persistent as after restoring snapshots user/1000
        # is gone from /run
        pulseaudio_setup_cmds = [
            "sudo mkdir -v -p /run/user/1000/pulse",
            "sudo chown -R ubuntu:ubuntu /run/user/1000/",
            "pulseaudio --start --exit-idle-time=-1 --disallow-module-loading",
        ]
        env = {"XDG_RUNTIME_DIR": "/run/user/1000"}
        for cmd in pulseaudio_setup_cmds:
            run_or_raise(self._container, cmd, env)

    def switch_off_networking(self):
        return run_or_raise(self._container, "sudo ip link set eth0 down")

    def switch_on_networking(self):
        return run_or_raise(self._container, "sudo ip link set eth0 up")


class ContainerSourceMachine(ContainerBaseMachine):
    """
    Machine using LXD container as the backend and running checkbox from
    source code repository.
    """

    def __init__(self, config, container):
        super().__init__(config, container)
        self._pts = None  # Keep a pointer to started pts for easy kill

    def get_early_dir_transfer(self):
        dirs = [(self.config.uri, "/home/ubuntu/checkbox")]
        return dirs

    def _get_install_dependencies_cmds(self):
        # We need any pip version >20 because we use pyproject.toml
        if self.config.alias in ["xenial", "bionic"]:
            # Use <21 to get the latest 20 as 21+ is not supported here
            return [
                "bash -c 'sudo python3 -m pip install -U \"pip<21\"'",
            ]
        if self.config.alias not in ["focal", "jammy"]:
            logger.warning("Unknown revision dependencies version, installing latest")
        return [
            "bash -c 'sudo python3 -m pip install -U \"pip>20\"'",
        ]

    def _get_install_source_cmds(self):
        if self.config.alias in ["xenial", "bionic"]:
            # pip<20 does not support editable install without a setup.py file
            return [
                (
                    "bash -c 'pushd /home/ubuntu/checkbox/checkbox-ng ; "
                    'echo "from setuptools import setup; setup()" > setup.py;'
                    "sudo python3 -m pip install -e .'"
                ),
                (
                    "bash -c 'pushd /home/ubuntu/checkbox/checkbox-support ; "
                    'echo "from setuptools import setup; setup()" > setup.py;'
                    "sudo python3 -m pip install -e .'"
                ),
                # ensure these two are at the correct version to support xenial
                "bash -c 'sudo python3 -m pip install importlib_metadata==1.0.0 \"zipp<2\"'",
            ]
        if self.config.alias not in ["focal", "jammy"]:
            logger.warning("Unknown revision dependencies version, installing latest")
        return [
            (
                "bash -c 'pushd /home/ubuntu/checkbox/checkbox-ng ; "
                "sudo python3 -m pip install -e .'"
            ),
            (
                "bash -c 'pushd /home/ubuntu/checkbox/checkbox-support ; "
                "sudo python3 -m pip install -e .'"
            ),
        ]

    def _get_provider_setup_cmds(self):
        # This installs the providers. This is based on the fact
        # that each provider dir (that is in `checkbox/providers`)
        # has a manage.py script that will install the provider
        # if called with the install parameter.
        # This lists all manage.py in these locations and calls
        # them as sudo with an install parameter
        return [
            "bash -c 'sudo mkdir -p /usr/local/share/plainbox-providers-1/'",
            (
                "bash -c 'ls /home/ubuntu/checkbox/providers/*/manage.py"
                "| xargs -I{} -n1 sudo python3 {} install'"
            ),
        ]

    def get_early_setup(self):
        """
        Installation from source and, if required, creation of systemd service.
        """
        commands = (
            self._get_install_dependencies_cmds()
            + self._get_install_source_cmds()
            + self._get_provider_setup_cmds()
        )

        if self.config.role in ("remote", "service"):
            commands += [
                "sudo bash -c 'systemctl daemon-reload'",
                "sudo bash -c 'systemctl enable checkbox-ng.service --now'",
            ]
            service_content = textwrap.dedent(
                """
                [Unit]
                Description=Checkbox Remote Service
                Wants=network.target

                [Service]
                ExecStart=/usr/local/bin/checkbox-cli service
                SyslogIdentifier=checkbox-ng.service
                Environment="XDG_CACHE_HOME=/var/cache/"
                Restart=on-failure
                TimeoutStopSec=30
                Type=simple

                [Install]
                WantedBy=multi-user.target
                """
            ).lstrip()
            self.run_cmd(
                "sudo mkdir -p '/usr/lib/systemd/system'"
            )
            self.put(
                "/usr/lib/systemd/system/checkbox-ng.service",
                service_content,
                uid=0,
                gid=0,
            )

        return commands

    def start_service(self, force=False):
        assert self.config.role in ("remote", "service")
        if force:
            return run_or_raise(
                self._container, "sudo systemctl start checkbox-ng.service"
            )

    def stop_service(self):
        assert self.config.role in ("remote", "service")
        return run_or_raise(self._container, "sudo systemctl stop checkbox-ng.service")

    def reboot_service(self):
        assert self.config.role == "service"
        verbose = True
        return run_or_raise(self._container, "sudo reboot", verbose)

    def is_service_active(self):
        assert self.config.role in ("remote", "service")
        return (
            run_or_raise(
                self._container, "systemctl is-active checkbox-ng.service"
            ).stdout
            == "active"
        )


class ContainerPPAMachine(ContainerBaseMachine):
    """
    Machine using LXD container as the backend and running checkbox
    from PPA.
    """

    def __init__(self, config, container):
        super().__init__(config, container)

    def get_early_setup(self):
        if self.config.setup:
            return []
        if self.config.role == "remote":
            deb = "checkbox-ng"
        else:
            deb = "canonical-certification-client"
        return [
            "sudo add-apt-repository {}".format(self.config.uri),
            "sudo apt-get update",
            "sudo apt-get install -y --no-install-recommends {}".format(deb),
        ]

    def start_service(self, force=False):
        assert self.config.role == "service"
        if force:
            return run_or_raise(
                self._container, "sudo systemctl start checkbox-ng.service"
            )

    def stop_service(self):
        assert self.config.role == "service"
        return run_or_raise(self._container, "sudo systemctl stop checkbox-ng.service")

    def is_service_active(self):
        assert self.config.role == "service"
        return (
            run_or_raise(
                self._container, "systemctl is-active checkbox-ng.service"
            ).stdout
            == "active"
        )


class ContainerSnapMachine(ContainerBaseMachine):
    """
    Machine using LXD container as the backend and running checkbox
    from a snap.
    """

    CHECKBOX_CORE_SNAP_MAP = {
        "xenial": "checkbox",
        "bionic": "checkbox18",
        "focal": "checkbox20",
        "jammy": "checkbox22",
    }
    CHECKBOX_SNAP_TRACK_MAP = {
        "xenial": "16.04",
        "bionic": "18.04",
        "focal": "20.04",
        "jammy": "22.04",
    }

    def __init__(self, config, container):
        super().__init__(config, container)
        self._snap_name = self.config.snap_name
        self._checkbox_wrapper = "{}.{}".format(self._snap_name, self.CHECKBOX)

    def get_file_transfer(self):
        file_tranfer_list = []
        if self.config.checkbox_core_snap.get("uri"):
            core_filename = Path(self.config.checkbox_core_snap.get("uri")).expanduser()
            self.core_dest = Path("/home", "ubuntu", core_filename.name)
            file_tranfer_list.append((core_filename, self.core_dest))
        if self.config.checkbox_snap.get("uri"):
            filename = Path(self.config.checkbox_snap.get("uri")).expanduser()
            self.dest = Path("/home", "ubuntu", filename.name)
            file_tranfer_list.append((filename, self.dest))
        return file_tranfer_list

    def get_early_setup(self):
        cmds = []
        # First install the checkbox core snap if the related section exists
        if self.config.checkbox_core_snap:
            if self.config.checkbox_core_snap.get("uri"):
                cmds.append(f"sudo snap install {self.core_dest} --dangerous")
            else:
                core_snap = self.CHECKBOX_CORE_SNAP_MAP[self.config.alias]
                channel = f"latest/{self.config.checkbox_core_snap['risk']}"
                cmds.append(f"sudo snap install {core_snap} --channel={channel}")
        # Then install the checkbox snap
        confinement = "devmode"
        if self.config.origin == "classic-snap":
            confinement = "classic"
        if self.config.checkbox_snap.get("uri"):
            cmds.append(f"sudo snap install {self.dest} --{confinement} --dangerous")
        else:
            try:
                track_map = self.config.checkbox_snap["track_map"]
            except KeyError:
                track_map = self.CHECKBOX_SNAP_TRACK_MAP
            channel = "{}/{}".format(
                track_map[self.config.alias], self.config.checkbox_snap["risk"]
            )
            cmds.append(
                "sudo snap install {} --channel={} --{}".format(
                    self._snap_name, channel, confinement
                )
            )
        return cmds

    def start_service(self, force=False):
        assert self.config.role == "service"
        if force:
            return run_or_raise(
                self._container,
                "sudo systemctl start snap.{}.service.service".format(self._snap_name),
            )

    def stop_service(self):
        assert self.config.role == "service"
        return run_or_raise(
            self._container,
            "sudo systemctl stop snap.{}.service.service".format(self._snap_name),
        )

    def is_service_active(self):
        assert self.config.role == "service"
        return (
            run_or_raise(
                self._container,
                "systemctl is-active snap.{}.service.service".format(self._snap_name),
            ).stdout
            == "active"
        )


def machine_selector(config, container):
    if config.origin in ("snap", "classic-snap"):
        return ContainerSnapMachine(config, container)
    elif config.origin == "ppa":
        return ContainerPPAMachine(config, container)
    elif config.origin == "source":
        return ContainerSourceMachine(config, container)
