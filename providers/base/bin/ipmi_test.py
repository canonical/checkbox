#!/usr/bin/env python3
"""
Copyright (C) 2020 Canonical Ltd.

Authors
  Adrian Lane <adrian.lane@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Tests IPMI subsystem on SUT.
"""

import re
import os
import shutil
import sys
import argparse
import logging
from subprocess import (
    Popen,
    check_call,
    PIPE,
    TimeoutExpired,
    SubprocessError)


class IpmiTest(object):
    def __init__(self):
        # paths to kernel_module binaries
        self._path_lsmod = self._get_path('lsmod')
        self._path_modprobe = self._get_path('modprobe')
        # kernel modules to load/verify
        self._kernel_modules = (
            'ipmi_si',
            'ipmi_devintf',
            'ipmi_powernv',
            'ipmi_ssif',
            'ipmi_msghandler')
        # paths to freeipmi tools
        self._path_ipmi_chassis = self._get_path('ipmi-chassis')
        self._path_ipmi_config = self._get_path('ipmi-config')
        self._path_bmc_info = self._get_path('bmc-info')
        self._path_ipmi_locate = self._get_path('ipmi-locate')
        # function subprocess commands
        self._cmd_kernel_mods = [
            'sudo', self._path_lsmod]
        self._cmd_ipmi_chassis = [
            'sudo', self._path_ipmi_chassis, '--get-status']
        self._cmd_ipmi_channel = [
            'sudo', self._path_ipmi_config, '--checkout',
            '--lan-channel-number']
        self._cmd_bmc_info = [
            'sudo', self._path_bmc_info]
        self._cmd_ipmi_locate = [
            'sudo', self._path_ipmi_locate]
        # min. ipmi version to pass
        self._ipmi_ver = 2.0
        # subprocess call timeout (s)
        self._subproc_timeout = 10
        # raised subproc exceptions to handle
        self._sub_proc_excs = (
            TimeoutExpired,
            SubprocessError,
            OSError,
            TypeError)

    # get absolute path
    def _get_path(self, binary):
        try:
            path_full = shutil.which(binary)
            return path_full
        except (self._sub_proc_excs[-2:-1]):
            logging.info('* Unable to stat path via shutil lib!')
            logging.info('* Using relative paths...')
            return binary

    # subprocess stdin/stderr handling
    def _subproc_logging(self, cmd):
        process = Popen(
            cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        output, error = process.communicate(timeout=self._subproc_timeout)
        logging.debug('## Debug Output: ##')
        if (len(output) > 0):
                        # padding
            logging.debug('   [Stdout]\n')
            logging.debug(f'{output}\n')
        if (len(error) > 0):
                        # padding
            logging.debug('   [Stderr]\n')
            logging.debug(f'{error}\n')
        logging.debug('## End Debug Output ##\n')
        return output

    # post-process exception handling
    def _proc_exc(self, exc, test_method):
        if (type(exc) == TimeoutExpired):
            logging.info(
                f'* Timeout calling {test_method}!'
                f' ({self._subproc_timeout}s)\n')
        elif (type(exc) == TypeError):
            logging.info(
                f'* Error calling {test_method}!'
                ' Check your paths!\n')
        else:
            logging.info(f'* Error calling {test_method}!\n')

    # kernel_mods() helper function to call modprobe
    def _modprobe_hlpr(self, module):
        try:
            check_call(
                [self._path_modprobe, module],
                stderr=PIPE, timeout=self._subproc_timeout)
        except self._sub_proc_excs:
            logging.info(f'* Unable to load module {module}!')
            logging.info('  **********************************************')
            logging.info(f'  Warning: proceeding, but in-band IPMI may fail')
            logging.info('  **********************************************')
        else:
            logging.info(f'- Successfully loaded module {module}')

    # check (and load) kernel modules
    def kernel_mods(self):
        logging.info('-----------------------')
        logging.info('Verifying kernel modules:')
        try:
            output = self._subproc_logging(self._cmd_kernel_mods)
            for module in self._kernel_modules:
                if module in output:
                    logging.info(f'- {module} already loaded')
                else:
                    self._modprobe_hlpr(module)
            logging.info('')
        except self._sub_proc_excs as exc:
            self._proc_exc(exc, self.kernel_mods.__qualname__)

    # get ipmi chassis data
    # pass if called w/o error
    def impi_chassis(self):
        logging.info('-----------------------')
        logging.info('Fetching chassis status:')
        try:
            self._subproc_logging(self._cmd_ipmi_chassis)
        except self._sub_proc_excs as exc:
            self._proc_exc(exc, self.impi_chassis.__qualname__)
            return 1
        else:
            logging.info('- Fetched chassis status!\n')
            return 0

    # get power status via ipmi chassis data
    # pass if called w/o error & system power field present
    def pwr_status(self):
        logging.info('-----------------------')
        logging.info('Fetching power status:')
        regex = re.compile('^System Power')
        try:
            output = self._subproc_logging(self._cmd_ipmi_chassis)
            for line in output.rstrip().split('\n'):
                if re.search(regex, line):
                    logging.info('- Fetched power status!\n')
                    return 0
            else:
                logging.info('* Unable to retrieve power status via IPMI.\n')
                return 1
        except self._sub_proc_excs as exc:
            self._proc_exc(exc, self.pwr_status.__qualname__)
            return 1

    # call bmc-info
    # pass if called w/o error
    def bmc_info(self):
        logging.info('-----------------------')
        logging.info('Fetching BMC information:')
        try:
            self._subproc_logging(self._cmd_bmc_info)
        except self._sub_proc_excs as exc:
            self._proc_exc(exc, self.bmc_info.__qualname__)
            return 1
        else:
            logging.info('- Fetched BMC information!\n')
            return 0

    # ipmi driver discovery loop
    def _ipmi_version_hlpr(self):
        regex = re.compile('^IPMI Version')
        output = self._subproc_logging(self._cmd_bmc_info)
        for line in output.rstrip().split('\n'):
            if re.search(regex, line):
                version = (line.split(':'))[1].strip()
                return version

    # fetch ipmi version via bmc-info sdout
    # pass if ipmi version >= self._ipmi_ver
    def ipmi_version(self):
        logging.info('-----------------------')
        logging.info('Validating IPMI version:')
        try:
            version = self._ipmi_version_hlpr()
            logging.info(f'- IPMI version: {version}')
        except self._sub_proc_excs as exc:
            self._proc_exc(exc, self.ipmi_version.__qualname__)
            return 1
        else:
            if (float(version) < float(self._ipmi_ver)):
                logging.info(f'* IPMI version below {self._ipmi_ver}!\n')
                return 1
            else:
                logging.info(f'  IPMI version compliant!\n')
                return 0

    # ipmi_channel discovery loop
    def _ipmi_channel_hlpr(self, i, channel):
        regex = re.compile('Section User')
        cmd = self._cmd_ipmi_channel
        if (len(cmd) > 4):
            cmd.pop(-1)
        cmd.append(str(i))
        output = self._subproc_logging(cmd)
        for line in output.rstrip().split('\n'):
            if re.search(regex, line):
                channel.append(i)
                return channel

    # get ipmi channel(s) in use
    # pass if user data returns after calling ipmi-config
    def ipmi_channel(self):
        logging.info('-----------------------')
        logging.info('Fetching IPMI channels:')
        # support multiple channels
        channel = []
        # test channels 0 - 15
        for i in range(16):
            try:
                self._ipmi_channel_hlpr(i, channel)
            except self._sub_proc_excs as exc:
                self._proc_exc(exc, self.ipmi_channel.__qualname__)
                return 1
        else:
            if (len(channel) > 0):
                logging.info(f'- Found {len(channel)} channel(s)!')
                logging.info(f'  IPMI channel(s): {channel}\n')
                return 0
            else:
                logging.info('* Unable to fetch IPMI channel!\n')
                return 1

    # ipmi driver discovery loop
    def _ipmi_locate_hlpr(self, ipmi_drivers):
        regex = re.compile('driver:')
        output = self._subproc_logging(self._cmd_ipmi_locate)
        for line in output.rstrip().split('\n'):
            if re.search(regex, line):
                driver = (line.split(':'))[1].lstrip()
                ipmi_drivers.append(driver)
        else:
            return ipmi_drivers

    # call ipmi-locate
    # pass if drivers are loaded
    def ipmi_locate(self):
        logging.info('-----------------------')
        logging.info('Locating IPMI drivers:')
        # support multiple driver types
        ipmi_drivers = []
        try:
            self._ipmi_locate_hlpr(ipmi_drivers)
        except self._sub_proc_excs as exc:
            self._proc_exc(exc, self.ipmi_locate.__qualname__)
            return 1
        else:
            if (len(ipmi_drivers) > 0):
                logging.info(f'- Found {len(ipmi_drivers)} IPMI driver(s)!')
                logging.info(f'  IPMI driver(s) loaded: {ipmi_drivers}\n')
                return 0
            else:
                logging.info('* Unable to locate IPMI driver(s)!\n')
                return 1

    # initialize kernel modules, run ipmi tests
    def run_test(self):
        # load/val kernel modules
        self.kernel_mods()
        results = [self.impi_chassis(),
                   self.pwr_status(),
                   self.bmc_info(),
                   self.ipmi_version(),
                   self.ipmi_channel(),
                   self.ipmi_locate()]
        return results


def main():
    # instantiate argparse as parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true',
                        help='debug/verbose output (stdout/stderr)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='suppress output')
    args = parser.parse_args()
    # init logging
    if ((not args.quiet) or args.debug):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
    if (not args.quiet):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    # instantiate IpmiTest as ipmi_test
    ipmi_test = IpmiTest()
    # run tests, return in [results]
    results = ipmi_test.run_test()
    results_dict = {'Chassis': results[0],
                    'Power': results[1],
                    'BMC': results[3],
                    'IPMI Version': results[4],
                    'Channel': results[2],
                    'IPMI Locate': results[5]}
    # tally results
    if (sum(results) > 0):
        print('-----------------------')
        print('## IPMI tests failed! ##')
        print(f'## {results_dict} ##')
        return 1
    else:
        print('-----------------------')
        print('## IPMI tests passed! ##')
        return 0


# call main()
if __name__ == '__main__':
    sys.exit(main())
