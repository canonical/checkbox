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

from checkbox_support.helpers.timeout import run_with_timeout
import subprocess
import threading
import argparse
import logging
import fnmatch
import time
import json
import sys
import re
import os
import typing as T
from shlex import split as sh_split


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

    def find_file_containing_string(
        self, search_directory: str, filename_pattern: str, search_string: str
    ) -> T.Optional[str]:
        """
        Search for a file matching a specific pattern
        that contains a given string.

        :param search_directory: The directory to search through.

        :param filename_pattern: The pattern that filenames should match.

        :param search_string: The string to search for within
                              the file's contents.

        :returns: The full path of the file that contains the string,
                  or None if no file is found.
        """
        for root, dirs, files in os.walk(search_directory):
            for file_name in fnmatch.filter(files, filename_pattern):
                file_path = os.path.join(root, file_name)
                # Check if the search string is in the file
                with open(
                    file_path, "r", encoding="utf-8", errors="ignore"
                ) as file:
                    if search_string in file.read():
                        return file_path

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
            card_path = self.find_file_containing_string(
                "/sys/kernel/debug/dri", "name", pci_bdf
            )
            assert card_path, "Couldn't find a card named: {}".format(pci_bdf)
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
            card_infos = subprocess.check_output(
                cmd, shell=False, universal_newlines=True
            )
            infos = json.loads(card_infos)
            for info in infos:
                if pci_bdf in info["businfo"]:
                    return info["product"]
            raise SystemExit("Card name not found")
        except (KeyError, TypeError, json.decoder.JSONDecodeError) as e:
            raise SystemExit("return value format error {}".format(e))
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise SystemExit(
                "Running command:{} failed due to {}".format(cmd, repr(e))
            )

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

        :param card_id: card id shows in debugfs
        """
        filename = "/sys/kernel/debug/dri/{}/clients".format(card_id)
        with open(filename, "r") as f:
            return f.read()
        return ""

    def check_offload(
        self, cmd: T.List[str], card_id: str, card_name: str, timeout: int
    ):
        """
        Used to check if the provided command is executed on a specific GPU.

        :param cmd: command to be run under prime offload

        :param card_id: card ID of the DRI device

        :param card_name: card name of the DRI device

        :param timeout: timeout for the offloaded command
        """
        delay = timeout / 10

        deadline = time.time() + timeout

        while time.time() < deadline:
            time.sleep(delay)
            clients = self.get_clients(card_id)
            # The command shows in /sys/kernel/debug/dri/<card_id>/clients
            # doesn't include arguments. Therefore cmd[0] is used to search
            if clients and cmd[0] in clients:
                self.logger.info("Checking success:")
                self.logger.info("  Offload process:[{}]".format(cmd))
                self.logger.info("  Card ID:[{}]".format(card_id))
                self.logger.info("  Device Name:[{}]".format(card_name))
                return
        self.logger.info("Checking fail:")
        self.logger.info("  Couldn't find process {}".format(cmd))
        self.check_result = True

    def _find_bdf(self, card_id: str):
        """
        Use the /sys/kernel/debug/dri/<card id>/name to get pci BDF.

        :param card_id: card id shows in debugfs
        """
        filename = "/sys/kernel/debug/dri/{}/name".format(card_id)
        with open(filename, "r") as f:
            data_in_name = f.read()
        return data_in_name.split()[1].split("=")[1]

    def find_offload(self, cmd_str: str, timeout: int):
        """
        Find the card that the command is running on.
        This script looks for the card on which a specific command is running.
        It checks ten times in regular intervals if the process is running
        by looking for it in the /sys/kernel/debug/dri/<card id>/clients.
        If the timeout is reached, the function will fail

        :param cmd: command that is running

        :param timeout: timeout for command
        """
        directory = "/sys/kernel/debug/dri"

        delay = timeout / 10

        deadline = time.time() + timeout

        cmd = sh_split(cmd_str)

        while time.time() < deadline:
            time.sleep(delay)
            # The command shows in /sys/kernel/debug/dri/<card_id>/clients
            # doesn't include arguments. Therefore cmd[0] is used to search
            card_path = self.find_file_containing_string(
                directory, "clients", cmd[0]
            )

            if card_path and directory in card_path:
                try:
                    # The graphic will be shown such as 0 and 128
                    # at the same time. Therefore, pick up the first one
                    first_card = card_path.splitlines()[0]
                    card_id = first_card.split("/")[5]
                    bdf = self._find_bdf(card_id)
                    self.logger.info("Process is running on:")
                    self.logger.info("  process:[{}]".format(cmd[0]))
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
        self.logger.info("  Couldn't find process {}".format(cmd))
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

    def cmd_runner(self, cmd: T.List[str], env: T.Optional[T.Dict] = None):
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
                    # when stdout=subprocess.PIPE, stdout is not None
                    line = runner.stdout.readline().strip()  # type: ignore
                    self.logger.info(line)
        except subprocess.CalledProcessError as e:
            raise SystemExit("run command failed {}".format(repr(e)))

    def cmd_finder(self, cmd: str, timeout: int):
        """
        run offload command and find it runs on which GPU

        :param cmd: command that running under prime offload

        :param timeout: timeout for offloaded command
        """
        if "timeout" in cmd:
            raise SystemExit("Put timeout in command isn't allowed")

        # use other thread to find offload
        find_thread = threading.Thread(
            target=self.find_offload, args=(cmd, timeout)
        )
        find_thread.start()
        try:
            run_with_timeout(self.cmd_runner, timeout, cmd.split())
        except TimeoutError:
            self.logger.info("Test finished")
        find_thread.join()

        if self.check_result:
            raise SystemExit("Couldn't find process running on GPU")

    def cmd_checker(
        self, cmd_str: str, pci_bdf: str, driver: str, timeout: int
    ):
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

        if "timeout" in cmd_str:
            raise SystemExit("Put timeout in command isn't allowed")

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

        cmd = sh_split(cmd_str)
        # use other thread to check offload is correctly or not
        check_thread = threading.Thread(
            target=self.check_offload, args=(cmd, card_id, card_name, timeout)
        )
        check_thread.start()
        try:
            run_with_timeout(self.cmd_runner, timeout, cmd, env)
        except TimeoutError:
            self.logger.info("Test finished")
        check_thread.join()

        if self.check_result:
            raise SystemExit(
                "offload to specific GPU: {} failed".format(pci_bdf)
            )

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
    assert os.getuid() == 0, "This test must be run as root"
    PrimeOffloader().main()
