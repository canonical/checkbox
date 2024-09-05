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

import subprocess
import threading
import argparse
import logging
import time
import json
import sys
import re
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

    def _run_command(self, cmd: list, shell=False) -> str:
        """
        use subprocess.check_output to execute command

        :param cmd: the command will be executed

        :param shell: enable shell or not

        :returns: Output of command
        """
        try:
            return subprocess.check_output(
                cmd, shell=shell, universal_newlines=True
            )

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise SystemExit(
                "Running command:{} failed due to {}".format(cmd, repr(e))
            )

    def find_card_id(self, pci_bdf: str) -> str:
        """
        use pci BDF to find card id under /sys/kernel/debug/dri

        :param pci_bdf: pci device BDF in NNNN:NN:NN.N format

        :returns: card id
        """
        pci_bdf_format = "[0-9]{4}:[0-9,a-f]{2}:[0-9,a-f]{2}.[0-9]"
        if not re.match(pci_bdf_format, pci_bdf.lower()):
            raise SystemExit("pci BDF format error")

        try:
            cmd = [
                "grep",
                "-lr",
                "--include=name",
                pci_bdf,
                "/sys/kernel/debug/dri",
            ]

            card_path = self._run_command(cmd)
            return card_path.split("/")[5]
        except IndexError as e:
            raise SystemExit("return value format error {}".format(repr(e)))

    def find_card_name(self, pci_bdf: str) -> str:
        """
        use pci BDF to find card name by lshw

        :param pci_bdf: pci device BDF in NNNN:NN:NN.N format

        :returns: card name
        """
        cmd = ["lshw", "-c", "display", "-numeric", "-json"]
        try:
            card_infos = self._run_command(cmd)
            infos = json.loads(card_infos)
            for info in infos:
                if pci_bdf in info["businfo"]:
                    return info["product"]
            raise SystemExit("Card name not found")
        except (KeyError, TypeError, json.decoder.JSONDecodeError) as e:
            raise SystemExit("return value format error {}".format(e))

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
        return self._run_command(read_clients_cmd)

    def check_offload(
        self, cmd: list, card_id: str, card_name: str, timeout: int
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

    def _find_bdf(self, card: str):
        """
        Use the /sys/kernel/debug/dri/<card id>/name to get pci BDF.

        :param card: in /sys/kernel/debug/dri/<card id>/clients format

        """
        data_in_name = self._run_command(
            ["cat", card.replace("clients", "name")]
        )
        return data_in_name.split()[1].split("=")[1]

    def find_offload(self, cmd: str, timeout: int):
        """
        Use to find provided command is executed on which GPU.

        :param cmd: command that is running

        :param timeout: timeout for command
        """
        delay = timeout / 10

        deadline = time.time() + timeout

        cmd = cmd.split()

        find_cmd = [
            "grep",
            "-lr",
            "--include=clients",
            cmd[0],
            "/sys/kernel/debug/dri",
        ]

        while time.time() < deadline:
            time.sleep(delay)
            card_path = self._run_command(find_cmd)
            if "/sys/kernel/debug/dri" in card_path:
                try:
                    # The graphic will be shown such as 0 and 128
                    # at the same time. Therefore, pick up the first one
                    first_card = card_path.splitlines()[0]
                    bdf = self._find_bdf(first_card)
                    self.logger.info("Process is running on:")
                    self.logger.info("  process:[{}]".format(cmd))
                    self.logger.info(
                        "  Card ID:[{}]".format(self.find_card_id(bdf))
                    )
                    self.logger.info(
                        "  Device Name:[{}]".format(self.find_card_name(bdf))
                    )
                    return
                except IndexError as e:
                    self.logger.info(
                        "Finding card information failed {}".format(repr(e))
                    )
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

    def _reformat_cmd_timeout(self, cmd: str, timeout: int) -> (list, int):
        """
        use to reformat the command with correct timeout setting

        :param cmd: the command will be executed

        :param timeout: timeout

        :returns: reformated command and real timeout
        """
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
        return (offload_cmd, timeout)

    def cmd_runner(self, cmd: list, env: dict = None):
        """
        use to execute command and piping the output to the screen.

        :param cmd: the command will be executed

        :param env: the environment variables for executing command

        """
        try:
            with subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            ) as runner:

                self.logger.info("running command:[{}]".format(cmd))

                # redirect command output real time
                while runner.poll() is None:
                    line = runner.stdout.readline().strip()
                    self.logger.info(line)
        except subprocess.CalledProcessError as e:
            raise SystemExit("run command failed {}".format(repr(e)))

    def cmd_finder(self, cmd: str, timeout: int):
        """
        run offload command and find it runs on which GPU

        :param cmd: command that running under prime offload

        :param timeout: timeout for offloaded command
        """
        (modified_cmd, timeout) = self._reformat_cmd_timeout(cmd, timeout)

        # use other thread to find offload
        find_thread = threading.Thread(
            target=self.find_offload, args=(cmd, timeout)
        )
        find_thread.start()
        self.cmd_runner(modified_cmd)
        find_thread.join()

        if self.check_result:
            raise SystemExit("Couldn't find process running on GPU")

    def cmd_checker(self, cmd: str, pci_bdf: str, driver: str, timeout: int):
        """
        run offload command and check it runs on correct GPU

        :param cmd: command that running under prime offload

        :param pci_bdf: pci device name in NNNN:NN:NN.N format

        :param driver: GPU driver, such as i915, amdgpu, nvidia

        :param timeout: timeout for offloaded command
        """
        card_id = self.find_card_id(pci_bdf)
        card_name = self.find_card_name(pci_bdf)

        # run offload command in other process
        dri_pci_bdf_format = re.sub("[:.]", "_", pci_bdf)

        (modified_cmd, timeout) = self._reformat_cmd_timeout(cmd, timeout)

        env = os.environ.copy()
        if driver in ("nvidia", "pcieport"):
            offload_env = {
                "__NV_PRIME_RENDER_OFFLOAD": "1",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
            }
        else:
            offload_env = {"DRI_PRIME": "pci-{}".format(dri_pci_bdf_format)}

        env.update(offload_env)
        self.logger.info("prime offload env: {}".format(offload_env))

        # if nv driver under nvidia mode, prime/reverse prime couldn't work.
        self.check_nv_offload_env()

        # use other thread to check offload is correctly or not
        check_thread = threading.Thread(
            target=self.check_offload, args=(cmd, card_id, card_name, timeout)
        )
        check_thread.start()
        self.cmd_runner(modified_cmd, env)
        check_thread.join()

        if self.check_result:
            raise SystemExit("offload to specific GPU failed")

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
            help="pci device bdf in NNNN:NN:NN.N format, such as 0000:00:02.0",
        )
        parser.add_argument(
            "-d",
            "--driver",
            type=str,
            help="Type of GPU driver, such as i915",
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

        if args.pci and args.driver:
            # cmd_checker("glxgears", "0000:00:02.0", "i915", 0)
            self.cmd_checker(args.command, args.pci, args.driver, args.timeout)
        else:
            # cmd_finder("glxgears", 0)
            self.cmd_finder(args.command, args.timeout)


if __name__ == "__main__":
    PrimeOffloader().main()
