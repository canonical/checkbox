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
    :type logger: RootLogger

    :attr check_result:
        store the result of checking offloading is ok or not.
    :type check_result: bool
    """

    logger = logging.getLogger()
    check_result = False

    def find_card_id(self, pci_name: str) -> str:
        """
        use pci name to find card id under /sys/kernel/debug/dri

        :param pci_name: pci device name in NNNN:NN:NN.N format

        :returns: card id
        """
        pci_name_format = "[0-9]{4}:[0-9,a-f]{2}:[0-9,a-f]{2}.[0-9]"
        if not re.match(pci_name_format, pci_name.lower()):
            raise SystemExit("pci name format error")

        try:
            cmd = [
                "grep",
                "-lr",
                "--include=name",
                pci_name,
                "/sys/kernel/debug/dri",
            ]

            card_path = subprocess.check_output(cmd, universal_newlines=True)
            return card_path.split("/")[5]
        except IndexError as e:
            raise SystemExit("return value format error {}".format(repr(e)))
        except subprocess.CalledProcessError as e:
            raise SystemExit("run command failed {}".format(repr(e)))

    def find_card_name(self, pci_name: str) -> str:
        """
        use pci name to find card name by lshw

        :param pci_name: pci device name in NNNN:NN:NN.N format

        :returns: card name
        """
        cmd = ["lshw", "-c", "display", "-json"]
        try:
            card_infos = subprocess.check_output(cmd, universal_newlines=True)
            infos = json.loads(card_infos)
            for info in infos:
                if pci_name in info["businfo"]:
                    return info["product"]
            raise SystemExit("Card name not found")
        except (KeyError, TypeError, json.decoder.JSONDecodeError) as e:
            raise SystemExit("return value format error {}".format(e))
        except subprocess.CalledProcessError as e:
            raise SystemExit("run command failed {}".format(repr(e)))

    def get_clients(self, card_id: str) -> str:
        """
        Use to get clients that running on specific GPU
        by reading debugfs.

        .. note::
            While setting prime offload environment such as DRI_PRIME,
            the process will be listed under kernel debug interface.
            The location of kernel debug interface is
            /sys/kernel/debug/dri/<card id>,
            and the process could be found in
            /sys/kernel/debug/dri/<card id>/clients

        :param cmd: command that running under prime offload
        """
        read_clients_cmd = [
            "cat",
            "/sys/kernel/debug/dri/{}/clients".format(card_id),
        ]
        try:
            return subprocess.check_output(
                read_clients_cmd, universal_newlines=True
            )
        except subprocess.CalledProcessError:
            self.logger.info(
                "Couldn't get clients on specific GPU{}".format(card_id)
            )

    def check_offload(
        self, cmd: list, card_id: str, card_name: str, timeout: str
    ):
        """
        Use to check provided command is executed on specific GPU.

        :param cmd: command that running under prime offload

        :param card_id: card id of dri device

        :param card_name: card name of dri device

        :param timeout: timeout for offloaded command
        """
        delay = timeout / 10

        deadline = time.time() + timeout

        while time.time() < deadline:
            time.sleep(delay)
            clients = self.get_clients(card_id)
            if clients and cmd[0] in clients:
                self.logger.info("Checking success:")
                self.logger.info("  Offload process:[{}]".format(cmd))
                self.logger.info("  Card ID:[{}]".format(card_id))
                self.logger.info("  Device Name:[{}]".format(card_name))
                return
        self.logger.info("Checking fail:")
        self.logger.info("  Couldn't find process [{}]".format(cmd))
        self.check_result = True

    def check_nv_offload_env(self):
        """
        prime offload of nvidia driver is limited.
        Only on-demand mode is supported.
        """
        # nvidia-smi ship with NVIDIA GPU display drivers on Linux
        # https://developer.nvidia.com/nvidia-system-management-interface
        # check prime-select to make sure the nv driver is included.
        # If there is no nv driver, prime offload is fine for other drivers.
        try:
            if "on-demand" not in subprocess.check_output(
                ["prime-select", "query"], universal_newlines=True
            ):
                raise SystemExit("System isn't on-demand mode")

            # prime offload couldn't running on nvlink active or inactive
            # Therefore, only return empty string is supported environment.
            nvlink = subprocess.check_output(
                ["nvidia-smi", "nvlink", "-s"], universal_newlines=True
            )
            if nvlink:
                if "error" in nvlink.lower():
                    raise SystemExit("nvidia driver error")
                raise SystemExit("NVLINK detected")
        except FileNotFoundError:
            self.logger.info(
                "No prime-select, it should be ok to run prime offload"
            )

    def run_offload_cmd(
        self, cmd: str, pci_name: str, driver: str, timeout: int
    ):
        """
        run offload command and check it runs on correct GPU

        :param cmd: command that running under prime offload

        :param pci_name: pci device name in NNNN:NN:NN.N format

        :param driver: GPU driver, such as i915, amdgpu, nvidia

        :param timeout: timeout for offloaded command
        """
        card_id = self.find_card_id(pci_name)
        card_name = self.find_card_name(pci_name)

        # run offload command in other process
        dri_pci_name_format = re.sub("[:.]", "_", pci_name)

        if "timeout" in cmd:
            raise SystemExit("Put timeout in command isn't allowed")

        cmd = cmd.split()
        if timeout > 0:
            offload_cmd = ["timeout", str(timeout)] + cmd
        else:
            # if timeout <=0 will make check_offload failed.
            # Set the timeout to the default value
            log_str = (
                "Timeout {}s is invalid,"
                " remove the timeout setting"
                " and change check_offload to run 20s".format(timeout)
            )
            self.logger.info(log_str)
            timeout = 20
            offload_cmd = cmd

        env = os.environ.copy()
        if driver in ("nvidia", "pcieport"):
            offload_env = {
                "__NV_PRIME_RENDER_OFFLOAD": "1",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
            }
        else:
            offload_env = {"DRI_PRIME": "pci-{}".format(dri_pci_name_format)}

        env.update(offload_env)
        self.logger.info("prime offload env: {}".format(offload_env))

        # if nv driver under nvidia mode, prime/reverse prime couldn't work.
        self.check_nv_offload_env()

        # use other thread to check offload is correctly or not
        check_thread = threading.Thread(
            target=self.check_offload, args=(cmd, card_id, card_name, timeout)
        )
        check_thread.start()
        try:
            with subprocess.Popen(
                offload_cmd,
                env=env,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            ) as offload:

                self.logger.info("offload command:[{}]".format(offload_cmd))

                # redirect offload command output real time
                while offload.poll() is None:
                    line = offload.stdout.readline().strip()
                    self.logger.info(line)
            check_thread.join()
            if self.check_result:
                raise SystemExit("offload to specific GPU failed")
        except subprocess.CalledProcessError as e:
            raise SystemExit("run offload command failed {}".format(repr(e)))

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
            "-c",
            "--command",
            type=str,
            default="glxgears",
            help="command to offload to specific GPU (default: %(default)s)",
        )
        parser.add_argument(
            "-p",
            "--pci",
            type=str,
            default="0000:00:02.0",
            help="pci name in NNNN:NN:NN.N format (default: %(default)s)",
        )
        parser.add_argument(
            "-d",
            "--driver",
            type=str,
            default="i915",
            help="Type of GPU driver (default: %(default)s)",
        )
        parser.add_argument(
            "-t",
            "--timeout",
            type=int,
            default=20,
            help="executing command duration in second (default: %(default)s).",  # noqa: E501
        )
        return parser.parse_args(args)

    def main(self):
        args = self.parse_args()

        # create self.logger.formatter
        log_formatter = logging.Formatter(fmt="%(message)s")

        # create logger
        self.logger.setLevel(logging.INFO)

        # create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        # Add console handler to logger
        self.logger.addHandler(console_handler)

        # run_offload_cmd("glxgears", "0000:00:02.0", "i915", 0)
        self.run_offload_cmd(args.command, args.pci, args.driver, args.timeout)


if __name__ == "__main__":
    PrimeOffloader().main()
