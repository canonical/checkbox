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

"""
lxd_provider
============

This module implements the LXD Machine and LXD Machine Provider.
LXD machines are containers that can run metabox scenarios in them.
"""
import json
import os
import sys
import time
import yaml
import subprocess
from pathlib import Path
from contextlib import contextmanager

import pkg_resources
import pylxd
from loguru import logger
from pylxd.exceptions import ClientConnectionFailed, LXDAPIException

from metabox.core.machine import MachineConfig
from metabox.core.vm.machine_factory import machine_selector
from metabox.core.lxd_execute import run_or_raise
from metabox.core.vm.vm_provider_abstract import AbstractMachineProvider

class LxdMachineProvider(AbstractMachineProvider):
    """Machine provider that uses container managed by LXD as targets."""

    LXD_CREATE_TIMEOUT = 300
    LXD_POLL_INTERVAL = 5
    LXD_INTERNAL_CONFIG_PATH = '/var/tmp/machine_config.json'
    LXD_SOURCE_MOUNT_POINT='source'
    LXD_MOUNT_DEVICE = 'sde'

    def __init__(self, session_config, effective_machine_config,
                 debug_machine_setup=False, dispose=False):
        self._session_config = session_config
        self._machine_config = effective_machine_config
        self._debug_machine_setup = debug_machine_setup
        self._owned_containers = []
        self._dispose = dispose

        # TODO: maybe add handlers for more complicated client connections
        #       like a remote LXD host and/or authenticated access
        try:
            # TODO: Find a suitable timeout value here
            self.client = pylxd.Client(timeout=None)
        except ClientConnectionFailed as exc:
            msg = f"Cannot connect to LXD. Is it installed? {exc}"
            logger.exception(msg)
            raise SystemExit(msg) from exc

    def setup(self):
        self._create_profiles()
        self._get_existing_machines()
        for config in self._machine_config:
            if config in [oc.config for oc in self._owned_containers]:
                continue
            self._create_machine(config)

    def _get_existing_machines(self):
        for container in self.client.containers.all():
            if not container.name.startswith('metabox'):
                continue
            try:
                logger.debug("Getting information about {}...", container.name)
                logger.debug("Starting {}...", container.name)
                container.start(wait=True)
                logger.debug("Retrieving config file for {}...", container.name)
                content = container.files.get(self.LXD_INTERNAL_CONFIG_PATH)
                logger.debug("Stopping {}...", container.name)
                container.stop(wait=True)
                config_dict = json.loads(content)
                config = MachineConfig(config_dict['role'], config_dict)
                logger.debug("Config: {}", repr(config))
            except Exception as e:
                logger.warning("{}: {}", container.name, e)
                continue
            if config in self._machine_config:
                logger.debug("Adding {} to list of owned containers...", repr(config))
                self._owned_containers.append(
                    machine_selector(config, container))

    def _create_profiles(self):
        profiles_path = pkg_resources.resource_filename(
            'metabox', 'lxd_profiles')
        for profile_file in os.listdir(profiles_path):
            profile_name = Path(profile_file).stem
            with open(os.path.join(profiles_path, profile_file)) as f:
                profile_dict = yaml.load(f, Loader=yaml.FullLoader)
            if self.client.profiles.exists(profile_name):
                profile = self.client.profiles.get(profile_name)
                if 'config' in profile_dict:
                    profile.config = profile_dict['config']
                if 'devices' in profile_dict:
                    profile.devices = profile_dict['devices']
                profile.save()
                logger.debug(
                    '{} LXD profile updated successfully', profile_name)
            else:
                profile = self.client.profiles.create(
                    profile_name,
                    config=profile_dict.get('config', None),
                    devices=profile_dict.get('devices', None))
                logger.debug(
                    '{} LXD profile created successfully', profile_name)

    def _create_machine(self, config):
        name = 'metabox-{}'.format(config)
        base_profiles = ["default", "checkbox"]
        alias = config.alias
        server = 'https://cloud-images.ubuntu.com/releases'
        if alias.endswith('-daily'):
            server = 'https://cloud-images.ubuntu.com/daily'
            alias = alias.replace('-daily', '')
        if config.origin == 'snap':
            base_profiles.append('snap')
        lxd_config = {
            "name": name,
            "profiles": base_profiles + config.profiles,
            "source": {
                "type": "image",
                "alias": alias,
                'protocol': 'simplestreams',
                'server': server
            }
        }
        try:
            logger.opt(colors=True).debug("[<y>creating</y>    ] {}", name)
            container = self.client.containers.create(lxd_config, wait=True)
            machine = machine_selector(config, container)
            container.start(wait=True)
            attempt = 0
            max_attempt = self.LXD_CREATE_TIMEOUT / self.LXD_POLL_INTERVAL
            while attempt < max_attempt:
                time.sleep(self.LXD_POLL_INTERVAL)
                (ret, out, err) = container.execute(
                    ['cloud-init', 'status', '--long'])
                if 'status: done' in out:
                    break
                elif ret != 0:
                    logger.error(out)
                    raise SystemExit(out)
                attempt += 1
            else:
                raise SystemExit("Timeout reached (still running cloud-init)")
            logger.opt(colors=True).debug(
                "[<y>created</y>     ] {}", container.name)
            logger.opt(colors=True).debug(
                "[<y>provisioning</y>] {}", container.name)
            self._run_transfer_commands(machine)
            self._run_setup_commands(machine)
            self._store_config(machine)
            logger.debug("Stopping container {}...", container.name)
            container.stop(wait=True)
            logger.debug("Creating 'provisioned' snapshot for {}...", container.name)
            container.snapshots.create(
                'provisioned', stateful=False, wait=True)
            logger.debug("Starting container {}...", container.name)
            container.start(wait=True)
            self._owned_containers.append(machine)
            logger.opt(colors=True).debug(
                "[<y>provisioned</y> ] {}", container.name)

        except LXDAPIException as exc:
            error = self._api_exc_to_human(exc)
            raise SystemExit(error) from exc

    def _transfer_file_preserve_mode(self, machine, src, dest):
        file_mode = os.stat(src).st_mode
        with open(src, "rb") as f:
            machine._container.files.put(dest, f.read(), mode=file_mode)

    def _mount_source(self, machine, path):
        logger.debug("Mounting dir {}", path)
        output = subprocess.check_output([
            "lxc", "config", "device", "add",
            machine._container.name, self.LXD_MOUNT_DEVICE,
            "disk", "source={}".format(path),
            "path={}".format(self.LXD_SOURCE_MOUNT_POINT)
        ], stderr=subprocess.PIPE, text=True)
        logger.debug(output)

    def _unmount_source(self, machine):
        logger.debug("Unmounting dir...")
        output = subprocess.check_output([
            "lxc", "config", "device", "remove",
            machine._container.name, self.LXD_MOUNT_DEVICE
        ], stderr=subprocess.PIPE, text=True)
        logger.debug(output)

    @contextmanager
    def _mounted_source(self, machine, path):
        self._mount_source(machine, path)
        try:
            yield ...
        finally:
            self._unmount_source(machine)

    def _run_transfer_commands(self, machine):
        provider_path = pkg_resources.resource_filename(
            'metabox', 'metabox-provider')
        # Also include the metabox providers
        metabox_dir_transfers = machine.get_early_dir_transfer() + [
            (provider_path, '/home/ubuntu/metabox-provider')]
        for src, dest in metabox_dir_transfers + machine.config.transfer:
            logger.debug("Working on {}", dest)
            with self._mounted_source(machine, src):
                # First create parent dir
                run_or_raise(
                    machine._container,
                    "sudo mkdir -p {}".format(os.path.dirname(dest)),
                    verbose=self._debug_machine_setup
                )
                # Copy the mounted dir to the desired location
                run_or_raise(
                    machine._container,
                    "sudo cp -r /{} {}".format(self.LXD_SOURCE_MOUNT_POINT, dest),
                    verbose=self._debug_machine_setup
                )
                # Own it to the correct user
                run_or_raise(
                    machine._container,
                    'sudo chown -R ubuntu:ubuntu {}'.format(dest),
                    verbose=self._debug_machine_setup)
        for src, dest in machine.get_file_transfer():
            logger.debug("Working on {}", dest)
            self._transfer_file_preserve_mode(machine, src, dest)

    def _run_setup_commands(self, machine):
        # Also install the metabox provider
        pre_cmds = machine.get_early_setup() + [
            "bash -c 'sudo python3 /home/ubuntu/metabox-provider/manage.py install'"
        ]
        post_cmds = machine.get_late_setup()
        for cmd in pre_cmds + machine.config.setup + post_cmds:
            logger.info(f"Running command: {cmd}")
            res = run_or_raise(
                machine._container, cmd,
                verbose=self._debug_machine_setup)
            if res.exit_code:
                msg = "Failed to run command in the container! Command: \n"
                msg += cmd + '\n' + res.stdout + '\n' + res.stderr
                logger.critical(msg)
                raise SystemExit()

    def _store_config(self, machine):
        machine._container.files.put(
            self.LXD_INTERNAL_CONFIG_PATH, json.dumps(machine.config.__dict__))

    def get_machine_by_config(self, config):
        for machine in self._owned_containers:
            if config == machine.config:
                return machine

    def cleanup(self, dispose=False):
        """Stop and delete (on request) all the containers."""
        for machine in self._owned_containers:
            container = machine._container
            if container.status == "Running":
                container.stop(wait=True)
                logger.opt(colors=True).debug(
                    "[<y>stopped</y>     ] {}", container.name)
            if dispose:
                container.delete(wait=True)
                logger.opt(colors=True).debug(
                    "[<y>deleted</y>     ] {}", container.name)

    def _api_exc_to_human(self, exc):
        response = json.loads(exc.response.text)
        # TODO: wrap in try/except and on wrong fields dump all info we have
        return response.get('error') or response['metadata']['err']

    def __del__(self):
        self.cleanup(self._dispose)
