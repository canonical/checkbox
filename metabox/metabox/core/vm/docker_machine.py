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

import subprocess
import pexpect
import re
import time

from loguru import logger

import metabox.core.keys as keys
from metabox.core.vm.base_machine import ContainerBaseMachine

class InteractiveCmd():
    def __init__(self, machine, cmd):
        # defining the dimensions of the pty is necessary
        self.child = pexpect.spawn(cmd,
                                   dimensions=(50,160),
                                   encoding='utf-8',
                                   codec_errors='ignore')
        self.machine = machine
        self.stdout_data_full = bytearray()

    def expect(self, data, timeout=0.0):
        # limit the timeout value
        if timeout >= 5:
            timeout = 5
        machine_name = str(self.machine.config)
        logger.info(f'[{machine_name}] expect: {data} - timeout={timeout}')
        try:
            if (type(data) == str):
                # use string matching instead of regular expression
                self.child.expect_exact(data, timeout=timeout)
            else:
                pattern = re.compile(data._raw_pattern)
                self.child.expect(pattern, timeout=timeout)
        except Exception as e:
            logger.warning(f'[{machine_name}] expect: {data} - FAILED')
            #logger.warning(self.child.before)
            # stop the scenario
            raise TimeoutError
        return True

    def send(self, payload, binary=False):
        machine_name = str(self.machine.config)
        data_str = payload.decode('utf-8')
        logger.info(f'[{machine_name}] send: {data_str}')
        self.child.send(data_str)

    def select_test_plan(self, data, timeout=0):
        """
        To select a test plan interactively
        KeyDown + Space to select, wait until the wanted plan is selected (X character)
        NB: the difficulty is after sending KEY_DOWN, we should wait for the terminal to be updated
            before sending the KEY_SPACE to select the next plan
        """
        found = False
        selected_data = f'(X) {data} '
        self.send('i'.encode('utf-8'), binary=True)
        # KEYDOWN -> get the cursor active so PAGEDOWN will always place
        # the cursor at the end of the end of the page
        self.send(keys.KEY_DOWN.encode('utf-8'), binary=True)
        for _ in range(0,100):
            self.send(keys.KEY_PAGEDOWN.encode('utf-8'), binary=True)
            try:
                self.child.expect_exact(data, timeout=1)
                found = True
                break 
            except Exception as e:
                pass

        if not found:
            return False
        found = False

        for _ in range(0,1000):
            self.send(keys.KEY_SPACE.encode('utf-8'), binary=True)
            try:
                self.child.expect_exact(selected_data, timeout=1)
                #self.child.interact()
                return True
            except Exception as e:
                pass
            self.send(keys.KEY_UP.encode('utf-8'), binary=True)
        return False

class ContainerDockerMachine(ContainerBaseMachine):
    """
    Machine using LXD container as the backend and running checkbox from
    source code repository.
    """

    def __init__(self, config, container):
        super().__init__(config, container)
        self._pts = None  # Keep a pointer to started pts for easy kill

    def start_user_session(self):
        pass

    def execute(self, cmd, env={}, verbose=False, timeout=0):
        """
        Execute a command
        NB: for now, force a timeout value to 10s to prevent blocking situation with
            some tests that can not be run on docker
        """
        machine_name = str(self.config)
        cmd = self._checkbox_wrapper + cmd
        env_arg = ' '.join(f'{k}={v}' for k,v in env.items())
        if len(env_arg) > 0:
            env_arg = f'-e {env_arg}'
        cmd = cmd.replace('\n','')
        cmd = f'docker exec {env_arg} -it {machine_name} {cmd}'
        cmd = cmd.split()
        process = subprocess.Popen(cmd,
                                   stderr=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=10)
            exit_code = process.returncode
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
            logger.info(f'[{machine_name}] execute : {cmd}, timeout={timeout}')
            #logger.info(f'[{machine_name}] output : {stdout_str}')
        except Exception as e:
            logger.error(f'[{machine_name}] execute : {cmd} : FAILED {e}')
            exit_code = 1
            stdout_str = ''
            stderr_str = ''
        return exit_code, stdout_str, stderr_str
    
    def interactive_execute(self, cmd, env={}, verbose=False, timeout=0):
        cmd = self._checkbox_wrapper + cmd
        env_arg = ' '.join(f'{k}={v}' for k,v in env.items())
        machine_name = str(self.config)
        logger.info(f'[{machine_name}] interactive execute : {cmd}')
        pts = InteractiveCmd(self, f'docker exec -it {machine_name} {cmd}')
        return pts

    def rollback_to(self, savepoint):
        pass

    def put(self, filepath, data, mode=None, uid=1000, gid=1000):
        machine_name = str(self.config)
        logger.info(f'[{machine_name}] put : {filepath} -- {data}')
        with open('/tmp/file', 'w') as f:
            f.write(data)
            f.flush()
            subprocess.check_call(f'docker cp /tmp/file {machine_name}:{filepath}', shell=True)

    def copy(self, src, dest):
        machine_name = str(self.config)
        logger.info(f'[{machine_name}] cp : {src} -> {dest}')
        subprocess.check_call(f'docker cp {src} {machine_name}:{dest}', shell=True)

    def get_early_dir_transfer(self):
        """
        Called at the machine creation stage (only once for each test run)
        Return list of files to transfer to the machine
        """
        dirs = []
        return dirs

    def get_early_setup(self):
        """
        Called at the machine creation stage (only once for each test run)
        Return list of commands to be executed on the machine
        """
        cmds = []
        return cmds

    def run_cmd(self, cmd, env={}, interactive=False, timeout=0):
        machine_name = str(self.config)
        logger.info(f'[{machine_name}] run : {cmd}')
        env_arg = ' '.join(f'{k}={v}' for k,v in env.items())
        cmd = f'docker exec -e {env_arg} -it {machine_name} {cmd}'
        cmd = cmd.split()
        process = subprocess.Popen(cmd,
                                   stderr=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        process.wait()

    def start_service(self, force=False):
        """
        Called to start the checkbox service in the machine
        Only applicable in remote mode
        """
        machine_name = str(self.config)
        logger.info(f'[{machine_name}] start checkbox service')
        # not necessary because the machine is restarted and cleaned, but still ...
        self.run_cmd('rm -rf /var/tmp/checkbox-ng/sessions/*')
        process = subprocess.Popen(['docker', 'exec', machine_name, 'checkbox-cli', 'service'],
                                   stderr=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        # important to wait for the service availability
        time.sleep(1)

    def stop_service(self):
        pass

    def reboot_service(self):
        pass

    def is_service_active(self):
        pass

    @property
    def address(self):
        machine_name = str(self.config)
        process = subprocess.Popen(['docker',
                                    'inspect',
                                    '-f',
                                    '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                                    machine_name],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        process.wait()
        stdout,stderr = process.communicate()
        return stdout.decode('utf-8')
