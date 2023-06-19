#!/usr/bin/env python3
"""prime offload test module."""
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
from enum import IntEnum


class PrimeOffloaderError(IntEnum):
    """
    A class used to define PrimeOffloader Error code

    :attr NO_ERROR: process success
    :type NO_ERROR: int

    :attr NO_CARD_ID: couldn't find card id
    :type NO_CARD_ID: int

    :attr NO_CARD_NAME: couldn't find card name
    :type NO_CARD_NAME: int

    :attr OFFLOAD_FAIL: couldn't find process on specific GPU
    :type OFFLOAD_FAIL: int

    :attr NOT_SUPPORT_NV_PRIME: this system couldn't support nv prime offload
    :type NOT_SUPPORT_NV_PRIME: int

    :attr NV_DRIVER_ERROR: some errors form nvidia driver
    :type NV_DRIVER_ERROR: int

    """

    NO_ERROR = 0
    NO_CARD_ID = -1
    NO_CARD_NAME = -2
    OFFLOAD_FAIL = -3
    NOT_SUPPORT_NV_PRIME = -4
    NV_DRIVER_ERROR = -5


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

    check_result = PrimeOffloaderError.OFFLOAD_FAIL

    def find_card_id(self, pci_name):
        """
        use pci name to find card id under /sys/kernel/debug/dri

        :param pci_name: pci device name in NNNN:NN:NN.N format
        :type card_name: str
        """
        cmd = "sudo grep -lr --include=name \"{}\""  \
              " /sys/kernel/debug/dri 2>/dev/null".format(pci_name)
        try:
            if not re.match("[0-9]{4}:[0-9]{2}:[0-9]{2}.[0-9]", pci_name):
                return PrimeOffloaderError.NO_CARD_ID

            card_path = subprocess.run(cmd, shell=True,
                                       stdout=subprocess.PIPE,
                                       universal_newlines=True)
            card_id = card_path.stdout.split('/')[5]
            return card_id
        except (ValueError, IndexError, AttributeError):
            return PrimeOffloaderError.NO_CARD_ID

    def find_card_name(self, pci_name):
        """
        use pci name to find card name by lshw

        :param pci_name: pci device name in NNNN:NN:NN.N format
        :type card_name: str
        """
        cmd = 'sudo lshw -c display -json'
        try:
            card_infos = subprocess.run(cmd, shell=True,
                                        stdout=subprocess.PIPE,
                                        universal_newlines=True)
            infos = json.loads(card_infos.stdout)
            for info in infos:
                if pci_name in info['businfo']:
                    return info['product']
        except (ValueError, IndexError, TypeError):
            return None

    def check_offload(self, cmd, card_id, card_name):
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
        :type cmd: str

        :param card_id: card id of dri device
        :type card_id: str

        :param card_name: card name of dri device
        :type card_name: str
        """
        cmd_without_args = cmd.split(' ')[0]
        for index in range(1, 11):
            time.sleep(2)
            try:
                read_clients_cmd = \
                    "sudo cat /sys/kernel/debug/dri/{}/clients".format(card_id)
                clients = subprocess.run(read_clients_cmd, shell=True,
                                         stdout=subprocess.PIPE,
                                         universal_newlines=True)
                if cmd_without_args in clients.stdout:
                    self.logger.info("Checking success:")
                    self.logger.info("  Offload process:[{}]".format(cmd))
                    self.logger.info("  Card ID:[{}]".format(card_id))
                    self.logger.info("  Device Name:[{}]".format(card_name))
                    self.check_result = PrimeOffloaderError.NO_ERROR
                    return
                self.check_result = PrimeOffloaderError.OFFLOAD_FAIL
            except (OSError, TypeError):
                # Missing file or permissions?
                self.logger.info("Couldn't open file for"
                                 "reading clients of dri device")
                self.check_result = PrimeOffloaderError.OFFLOAD_FAIL
                return
        self.logger.info("Checking fail:")
        self.logger.info("  Couldn't find process [{}]".format(cmd) +
                         " running after check {} times".format(index))
        self.check_result = PrimeOffloaderError.OFFLOAD_FAIL

    def check_nv_offload_env(self):
        """
        prime offload of nvidia driver is limited.
        Only on-demand mode is supported.
        """
        # nvidia-smi ship with NVIDIA GPU display drivers on Linux
        # https://developer.nvidia.com/nvidia-system-management-interface
        # check prime-select to make sure system with nv driver.
        # If there is no nv driver, prime offload is fine for other drivers.
        ps = subprocess.run("whereis prime-select | cut -d ':' -f 2",
                            shell=True,
                            stdout=subprocess.PIPE,
                            universal_newlines=True)
        if 'prime-select' not in ps.stdout:
            return PrimeOffloaderError.NO_ERROR

        # prime offload could running on on-demand mode only
        mode = subprocess.run("prime-select query",
                              shell=True,
                              stdout=subprocess.PIPE,
                              universal_newlines=True)
        if "on-demand" not in mode.stdout:
            self.logger.info("System isn't on-demand mode")
            return PrimeOffloaderError.NOT_SUPPORT_NV_PRIME

        # prime offload couldn't running on nvlink active or inactive
        # Therefore, only return empty string is supported environment.
        nvlink = subprocess.run("nvidia-smi nvlink -s",
                                shell=True,
                                stdout=subprocess.PIPE,
                                universal_newlines=True)
        if len(nvlink.stdout) != 0:
            if re.search('error', nvlink.stdout, re.IGNORECASE):
                self.logger.info("nvidia driver error")
                return PrimeOffloaderError.NV_DRIVER_ERROR
            self.logger.info("NVLINK detected")
            return PrimeOffloaderError.NOT_SUPPORT_NV_PRIME

        return PrimeOffloaderError.NO_ERROR

    def run_offload_cmd(self, cmd, pci_name, driver, timeout):
        """
        run offload command and check it runs on correct GPU

        :param cmd: command that running under prime offload
        :type cmd: str

        :param pci_name: pci device name in NNNN:NN:NN.N format
        :type pci_name: str

        :param driver: GPU driver, such as i915, amdgpu, nvidia
        :type driver: str
        """
        card_id = self.find_card_id(pci_name)
        if card_id == PrimeOffloaderError.NO_CARD_ID:
            self.logger.info("Couldn't find card id,"
                             " please check your pci name")
            return PrimeOffloaderError.NO_CARD_ID

        card_name = self.find_card_name(pci_name)
        if card_name is None:
            self.logger.info("Couldn't find card name,"
                             " please check your pci name")
            return PrimeOffloaderError.NO_CARD_NAME

        # run offload command in other process
        dri_pci_name_format = re.sub("[:.]", "_", pci_name)

        if timeout > 0:
            tmp_cmd = "timeout {} {}".format(timeout, cmd)
        else:
            tmp_cmd = cmd

        if driver in ('nvidia', 'pcieport'):
            offload_cmd = "__NV_PRIME_RENDER_OFFLOAD=1" \
                          " __GLX_VENDOR_LIBRARY_NAME=nvidia {}" \
                          .format(tmp_cmd)
        else:
            offload_cmd = "DRI_PRIME=pci-{} {}" \
                          .format(dri_pci_name_format, tmp_cmd)

        # if nv driver under nvidia mode, prime/reverse prime couldn't work.
        if self.check_nv_offload_env() \
           == PrimeOffloaderError.NOT_SUPPORT_NV_PRIME:
            self.logger.info("Couldn't use nv prime offload"
                             " on this system environment")
            offload_cmd = tmp_cmd
            # Couldn't work, always return NO_ERROR
            self.check_result = PrimeOffloaderError.NO_ERROR
        else:
            # use other thread to check offload is correctly or not
            check_thread = threading.Thread(target=self.check_offload,
                                            args=(cmd, card_id, card_name))
            check_thread.start()

        offload = subprocess.Popen(offload_cmd,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   universal_newlines=True)

        self.logger.info("offload command:[{}]".format(offload_cmd))

        # redirect offload command output real time
        while offload.poll() is None:
            line = offload.stdout.readline().strip()
            self.logger.info(line)
        return PrimeOffloaderError.NO_ERROR

    def main(self) -> int:
        """
        main function for command line processing
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

        args = parser.parse_args()

        # create self.logger.formatter
        log_formatter = logging.Formatter(fmt='%(message)s')

        # create logger
        self.logger.setLevel(logging.INFO)

        # create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        # Add console handler to logger
        self.logger.addHandler(console_handler)

        # run_offload_cmd("glxgears", "0000:00:02.0", "i915", 0)
        self.run_offload_cmd(args.command, args.pci, args.driver, args.timeout)

        return self.check_result


if __name__ == "__main__":
    sys.exit(PrimeOffloader().main())
