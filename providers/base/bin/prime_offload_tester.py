#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

import sys
import threading
import subprocess
import time
import re
import json
import argparse
import logging
import os


class PrimeOffloader:
    """
    A class used to execute process to specific GPU.
    Have to run this as root.

    :attr logger: console logger
    :type logger: obj

    :attr check_result:
        store the result of checking offloading is ok or not.
    :type check_result: int
    """

    logger = logging.getLogger()
    check_result = False

    def find_card_id(self, pci_name):
        """
        use pci name to find card id under /sys/kernel/debug/dri

        :param pci_name: pci device name in NNNN:NN:NN.N format
        :type card_name: str

        : returns : card id
        : rtype : str
        """
        if not re.match("[0-9]{4}:[0-9]{2}:[0-9]{2}.[0-9]", pci_name):
            raise RuntimeError("pci name format error")

        try:
            cmd = ["grep",
                   "-lr",
                   "--include=name",
                   pci_name,
                   "/sys/kernel/debug/dri"]

            card_path = subprocess.check_output(cmd,
                                                universal_newlines=True)
            return card_path.split('/')[5]
        except (IndexError, AttributeError) as e:
            raise RuntimeError("return value format error {}".format(e))
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e)

    def find_card_name(self, pci_name):
        """
        use pci name to find card name by lshw

        :param pci_name: pci device name in NNNN:NN:NN.N format
        :type card_name: str

        : returns : card name
        : rtype : str
        """
        cmd = ["lshw", "-c", "display", "-json"]
        try:
            card_infos = subprocess.check_output(cmd,
                                                 universal_newlines=True)
            infos = json.loads(card_infos)
            for info in infos:
                if pci_name in info['businfo']:
                    return info['product']
            raise RuntimeError("Card name not found")
        except (KeyError, TypeError, json.decoder.JSONDecodeError) as e:
            raise RuntimeError("return value format error {}".format(e))
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e)

    def check_for_kernel_bug(self, b, a):
        """
        for 6.5 kernel, a bug of dir debugfs should be fixed.
        before that, we have to check the difference
        https://warthogs.atlassian.net/browse/OEMQA-3459

        :param b: clients before test
        :type b: str

        :param a: clients after test
        :type a: str

        : returns : check result
        : rtype : Boolean
        """
        line_b = b.strip().splitlines()
        line_a = a.strip().splitlines()

        len_b = len(line_b)
        len_a = len(line_a)

        if (len_b == (len_a - 1)
           and any(x in line_a[len_a - 1] for x in ('Xorg', 'Xwayland'))):
            return True
        return False

    def check_offload(self, cmd, card_id, card_name, timeout):
        """
        Use to check provided command is executed on specific GPU.

        .. note::
            While setting prime offload environment such as DRI_PRIME,
            the process will be listed under kernel debug interface.
            The location of kernel debug interface is
            /sys/kernel/debug/dri/<card id>,
            and the process could be found in
            /sys/kernel/debug/dri/<card id>/clients

        :param cmd: command that running under prime offload
        :type cmd: list

        :param card_id: card id of dri device
        :type card_id: str

        :param card_name: card name of dri device
        :type card_name: str

        :param timeout: timeout for offloaded command
        :type timeout: int
        """
        if timeout == 0:
            delay = 2
        else:
            delay = timeout / 10

        pre_test_clients = ""

        for index in range(1, 11):
            time.sleep(delay)
            try:
                read_clients_cmd = ["cat",
                                    "/sys/kernel/debug/dri/{}/clients"
                                    .format(card_id)]
                clients = subprocess.check_output(read_clients_cmd,
                                                  universal_newlines=True)
                if not pre_test_clients:
                    pre_test_clients = clients
                    continue
                if cmd[0] in clients:
                    self.logger.info("Checking success:")
                    self.logger.info("  Offload process:[{}]".format(cmd))
                    self.logger.info("  Card ID:[{}]".format(card_id))
                    self.logger.info("  Device Name:[{}]".format(card_name))
                    return
                elif self.check_for_kernel_bug(pre_test_clients, clients):
                    self.logger.info("correct for 6.5 kernel bug only")
                    self.logger.info("Checking success:")
                    self.logger.info("  Offload process:[{}]".format(cmd))
                    self.logger.info("  Card ID:[{}]".format(card_id))
                    self.logger.info("  Device Name:[{}]".format(card_name))
                    return
            except (subprocess.CalledProcessError, OSError, TypeError) as e:
                # Missing file or permissions?
                self.logger.info(e)
                self.check_result = True
        self.logger.info("Checking fail:")
        self.logger.info("  Couldn't find process [{}]".format(cmd) +
                         " running after check {} times".format(index))
        self.check_result = True

    def check_nv_offload_env(self):
        """
        prime offload of nvidia driver is limited.
        Only on-demand mode is supported.
        """
        # nvidia-smi ship with NVIDIA GPU display drivers on Linux
        # https://developer.nvidia.com/nvidia-system-management-interface
        # check prime-select to make sure system with nv driver.
        # If there is no nv driver, prime offload is fine for other drivers.
        try:
            ps = subprocess.check_output(["which", "prime-select"],
                                         universal_newlines=True)

            if 'prime-select' in ps:
                # prime offload could running on on-demand mode only
                mode = subprocess.check_output(["prime-select", "query"],
                                               universal_newlines=True)
                if "on-demand" not in mode:
                    raise RuntimeError("System isn't on-demand mode")
            else:
                self.logger.info(
                    "No prime-select, it should be ok to run prime offload")
                return
        except subprocess.CalledProcessError:
            self.logger.info(
                "No prime-select, it should be ok to run prime offload")
            return

        # prime offload couldn't running on nvlink active or inactive
        # Therefore, only return empty string is supported environment.
        nvlink = subprocess.check_output(["nvidia-smi", "nvlink", "-s"],
                                         universal_newlines=True)
        if nvlink:
            if 'error' in nvlink.lower():
                raise RuntimeError("nvidia driver error")
            raise RuntimeError("NVLINK detected")

    def run_offload_cmd(self, cmd, pci_name, driver, timeout):
        """
        run offload command and check it runs on correct GPU

        :param cmd: command that running under prime offload
        :type cmd: str

        :param pci_name: pci device name in NNNN:NN:NN.N format
        :type pci_name: str

        :param driver: GPU driver, such as i915, amdgpu, nvidia
        :type driver: str

        :param timeout: timeout for offloaded command
        :type timeout: int
        """
        card_id = self.find_card_id(pci_name)
        card_name = self.find_card_name(pci_name)

        # run offload command in other process
        dri_pci_name_format = re.sub("[:.]", "_", pci_name)

        if "timeout" in cmd:
            raise RuntimeError("Put timeout in command isn't allowed")

        cmd = cmd.split()
        if timeout:
            offload_cmd = ["timeout", str(timeout)] + cmd
        else:
            offload_cmd = cmd

        env = os.environ.copy()
        if driver in ('nvidia', 'pcieport'):
            offload_env ={"__NV_PRIME_RENDER_OFFLOAD": "1",
                         "__GLX_VENDOR_LIBRARY_NAME": "nvidia"}
        else:
            offload_env = {"DRI_PRIME": "pci-{}".format(dri_pci_name_format)}

        env.update(offload_env)
        self.logger.info("prime offload env: {}".format(offload_env))

        # if nv driver under nvidia mode, prime/reverse prime couldn't work.
        self.check_nv_offload_env()

        # use other thread to check offload is correctly or not
        check_thread = threading.Thread(target=self.check_offload,
                                        args=(cmd, card_id,
                                              card_name,
                                              timeout))
        check_thread.start()
        # sleep 5 seconds for waiting check_offload thread get clients before testing
        time.sleep(5)
        try:
            with subprocess.Popen(offload_cmd, env=env,
                                  stdout=subprocess.PIPE,
                                  universal_newlines=True) as offload:

                self.logger.info("offload command:[{}]".format(offload_cmd))

                # redirect offload command output real time
                while offload.poll() is None:
                    line = offload.stdout.readline().strip()
                    self.logger.info(line)
            check_thread.join()
            if self.check_result:
                raise RuntimeError("offload failed")
        except subprocess.CalledProcessError as e:
            self.logger.info(e)
            raise RuntimeError("run offload command failed")

    def parse_args(self, args=sys.argv[1:]):
        """
        command line arguments parsing

        :param args: arguments from sys
        :type args: sys.argv
        """
        parser = argparse.ArgumentParser(
            prog="Prime offload tester",
            description="Test prime offload feature",
        )

        parser.add_argument(
            "-c", "--command", type=str, default='glxgears',
            help='command to offload to specific GPU (default: %(default)s)'
        )
        parser.add_argument(
            "-p", "--pci", type=str, default='0000:00:02.0',
            help='pci name in NNNN:NN:NN.N format (default: %(default)s)'
        )
        parser.add_argument(
            "-d", "--driver", type=str, default='i915',
            help='Type of GPU driver (default: %(default)s)'
        )
        parser.add_argument(
            "-t", "--timeout", type=int, default=0,
            help='executing command duration in second (default: %(default)s).'
                 ' If provide 0, then the command will be executed'
                 ' without timeout.'
        )
        return parser.parse_args(args)


if __name__ == "__main__":
    po = PrimeOffloader()

    args = po.parse_args()

    # create self.logger.formatter
    log_formatter = logging.Formatter(fmt='%(message)s')

    # create logger
    po.logger.setLevel(logging.INFO)

    # create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # Add console handler to logger
    po.logger.addHandler(console_handler)

    # run_offload_cmd("glxgears", "0000:00:02.0", "i915", 0)
    try:
        po.run_offload_cmd(args.command,
                           args.pci,
                           args.driver,
                           args.timeout)
        sys.exit(0)
    except RuntimeError as e:
        po.logger.info(e)
        sys.exit(1)
