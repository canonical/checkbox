# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hector Cao <hector.cao@canonical.com>
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

import json
import os
import sys
import time
import yaml
import textwrap
import subprocess
import yaml
import pkg_resources

from pathlib import Path
from loguru import logger

from metabox.core.vm.vm_provider_abstract import AbstractMachineProvider
from metabox.core.machine import MachineConfig
from metabox.core.vm.machine_factory import machine_selector
from metabox.core.vm.docker_machine import ContainerDockerMachine

class DockerMachineProvider(AbstractMachineProvider):
    """Machine provider that uses container managed by Docker as targets."""

    def __init__(self, session_config, effective_machine_config,
                 debug_machine_setup=False, dispose=False):
        self._session_config = session_config
        self._machine_config = effective_machine_config
        self._debug_machine_setup = debug_machine_setup
        self._dispose = dispose

        self.compose_conf = {'services': {}}

    def docker_image(self, config):
        """
        tag : <checkbox-version>-<ubuntu-release>
        example : 2.6-jammy
        """
        checkbox_version = '2.6'
        ubuntu_release = config.alias
        return f'hectorcao84/checkbox:{checkbox_version}-{ubuntu_release}'

    def docker_devel_mode(self, config, compose):
        """
        Bind the checkbox source into the machine 
        """
        machine_name = str(config)
        if config.origin == 'source':
            if compose.get('volumes') is not None:
                compose['volumes'].append('$PWD:/tmp/checkbox')
            else:
                compose['volumes'] = [ '$PWD:/tmp/checkbox' ]

    def docker_compose_service(self, config):
        machine_name = str(config)
        image_name = self.docker_image(config)
        docker_compose = yaml.safe_load(textwrap.dedent(f"""
                image: {image_name}
                command: /usr/sbin/init
                container_name: "{machine_name}"
                entrypoint: ""
                environment:
                    - HOME=/root/
                ports:
                    - '18871:18871'
        """))
        self.docker_devel_mode(config, docker_compose)
        self.compose_conf['services'][machine_name] = docker_compose
        with open('/tmp/docker-compose.yaml','w') as f:
            yaml.dump(self.compose_conf, f, default_flow_style=False)
        subprocess.check_call(['docker-compose',
                            '-f',
                            '/tmp/docker-compose.yaml',
                            'up',
                            '-d'])

    def docker_compose(self, config):
        machine_name = str(config)
        image_name = self.docker_image(config)
        docker_compose = yaml.safe_load(textwrap.dedent(f"""
                image: {image_name}
                command: /usr/sbin/init
                container_name: "{machine_name}"
                entrypoint: ""
                environment:
                    - HOME=/home/ubuntu/
        """))
        self.docker_devel_mode(config, docker_compose)
        self.compose_conf['services'][machine_name] = docker_compose
        with open('/tmp/docker-compose.yaml','w') as f:
            yaml.dump(self.compose_conf, f, default_flow_style=False)
        subprocess.check_call(['docker-compose',
                                '-f',
                                '/tmp/docker-compose.yaml',
                                'up',
                                '-d'])

    def setup(self):
        """
        Start docker containers from config.
        Config can contain one or several docker machine/container
        (Typically for remote mode, we will have 2 machines : master & slave)
        """
        for config in self._machine_config:
            self._create_machine(config)

    def _create_machine(self, config):
        """
        Create docker machine
        """
        machine = machine_selector(config, None)
        logger.info(f'Create machine {machine.config} - role={machine.config.role}')
        # role == [local|service|remote]
        if machine.config.role == 'service':
            self.docker_compose_service(config)
        else:
            self.docker_compose(config)
        self._run_transfer_commands(machine)
        self._run_setup_commands(machine)
        # commit
        machine_name = str(machine.config)
        subprocess.check_call(['docker', 'commit',
                                machine_name, f'{machine_name}-test'])
        self.compose_conf['services'][machine_name]['image'] = f'{machine_name}-test'

    def _run_transfer_commands(self, machine):
        machine_name = str(machine.config)
        provider_path = pkg_resources.resource_filename(
            'metabox', 'metabox-provider')
        metabox_dir_transfers = machine.get_early_dir_transfer() + [
            (provider_path, '/var/tmp/checkbox-providers/')]
        for src, dest in metabox_dir_transfers + machine.config.transfer:
            machine.copy(src, dest)
        for src, dest in machine.get_file_transfer():
            machine.copy(src, dest)

    def _run_setup_commands(self, machine):
        pre_cmds = machine.get_early_setup()
        post_cmds = machine.get_late_setup()
        for cmd in pre_cmds + machine.config.setup + post_cmds:
            machine.execute(cmd)

    def get_machine_by_config(self, config):
        machine = ContainerDockerMachine(config, None)
        return machine

    def cleanup(self, dispose=False):
        """
        Stop and delete (dispose==True) all machines
        Called at each scenario end
        """
        with open('/tmp/docker-compose.yaml','w') as f:
            yaml.dump(self.compose_conf, f, default_flow_style=False)
        subprocess.check_call(['docker-compose',
                               '-f',
                               '/tmp/docker-compose.yaml',
                               'down',
                               '--remove-orphans'])
        # so far
        subprocess.check_call(['docker-compose',
                               '-f',
                                '/tmp/docker-compose.yaml',
                                'up',
                                '-d'])

    def _api_exc_to_human(self, exc):
        response = json.loads(exc.response.text)
        # TODO: wrap in try/except and on wrong fields dump all info we have
        return response.get('error') or response['metadata']['err']

    def __del__(self):
        self.cleanup(self._dispose)
