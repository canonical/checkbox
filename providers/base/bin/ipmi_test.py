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
    SubprocessError,
    TimeoutExpired,
    SubprocessError)


class IpmiTest(object):

    def __init__(self):
        self.path_lsmod = shutil.which('lsmod')
        self.path_modprobe = shutil.which('modprobe')
        self.kernel_modules = (
            'ipmi_si',
            'ipmi_devintf',
            'ipmi_powernv',
            'ipmi_ssif',
            'ipmi_msghandler')
        self.path_ipmi_chassis = shutil.which('ipmi-chassis')
        self.path_ipmi_config = shutil.which('ipmi-config')
        self.path_bmc_info = shutil.which('bmc-info')
        self.path_ipmi_locate = shutil.which('ipmi-locate')
        # min. ipmi version to pass
        self.ipmi_ver = 2.0
        # subprocess call timeout (s)
        self.subproc_timeout = 10

    def run_test(self):
        # load/val kernel modules
        self.kernel_mods()
        # tally results
        results = [self.impi_chassis(),
                   self.pwr_status(),
                   self.ipmi_channel(),
                   self.bmc_info(),
                   self.ipmi_version(),
                   self.ipmi_locate()]
        return results

    def subproc_logging(self, cmd):
        process = Popen(
            cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        output, error = process.communicate(timeout=self.subproc_timeout)
        logging.debug('## Debug Output: ##')
        if len(output) > 0:
                        # padding
            logging.debug('   [Stdout]\n')
            logging.debug(f'{output}\n')
        if len(error) > 0:
                        # padding
            logging.debug('   [Stderr]\n')
            logging.debug(f'{error}\n')
        logging.debug('## End Debug Output ##\n')
        return output

    def proc_ex(self, subtest):
        if TimeoutExpired:
            logging.info(
                f'Timeout calling {subtest}!'
                f' ({self.subproc_timeout}s)\n')
        else:
            logging.info(f'Error calling {subtest}!\n')

    def modprobe_hlpr(self, module):
        cmd = [self.path_modprobe, module]
        try:
            check_call(
                [self.path_modprobe, module],
                stderr=PIPE, timeout=self.subproc_timeout)
        except (TimeoutExpired, SubprocessError, OSError):
            logging.info(f'* Unable to load module {module}!')
            logging.info('  **********************************************')
            logging.info(f'  Warning: proceeding, but in-band IPMI may fail')
            logging.info('  **********************************************')
        else:
            logging.info(f'- Successfully loaded module {module}')

    def kernel_mods(self):
        logging.info('-----------------------')
        logging.info('Verifying kernel modules:')
        cmd = [self.path_lsmod]
        try:
            output = self.subproc_logging(cmd)
            for module in self.kernel_modules:
                if module in output:
                    logging.info(f'- {module} already loaded')
                else:
                    self.modprobe_hlpr(module)
            logging.info('')
        except (TimeoutExpired, SubprocessError, OSError):
            self.proc_ex('lsmod')

    def impi_chassis(self):
        logging.info('-----------------------')
        logging.info('Fetching chassis status:')
        cmd = [self.path_ipmi_chassis, '--get-status']
        try:
            self.subproc_logging(cmd)
        except (TimeoutExpired, SubprocessError, OSError):
            self.proc_ex('ipmi_chassis()')
            return 1
        else:
            logging.info('Fetched chassis status!\n')
            return 0

    def pwr_status(self):
        logging.info('-----------------------')
        logging.info('Fetching power status:')
        regex = re.compile('^System Power')
        cmd = [self.path_ipmi_chassis, '--get-status']
        try:
            output = self.subproc_logging(cmd)
            for line in output.rstrip().split('\n'):
                if re.search(regex, line):
                    logging.info('Fetched power status!\n')
                    return 0
            else:
                logging.info('Unable to retrieve power status via IPMI.\n')
                return 1
        except (TimeoutExpired, SubprocessError, OSError):
            self.proc_ex('pwr_status()')
            return 1

    def ipmi_channel(self):
        logging.info('-----------------------')
        logging.info('Fetching IPMI channel:')
        regex = re.compile('Section User')
        matches = 0
        # support multiple channels
        channel = []
        cmd = [self.path_ipmi_config, '--checkout',
               '--lan-channel-number', channel]
        # test channels 0 - 15
        try:
            for i in range(16):
                del cmd[(len(cmd) - 1)]
                cmd.append(str(i))
                output = self.subproc_logging(cmd)
                for line in output.rstrip().split('\n'):
                    if re.search(regex, line):
                        matches += 1
                        channel.append(i)
                        break
        except (TimeoutExpired, SubprocessError, OSError):
            self.proc_ex('ipmi_channel()')
            return 1
        else:
            if matches > 0:
                logging.info(f'IPMI Channel(s): {channel}\n')
                return 0
            else:
                logging.info('Unable to fetch IPMI channel!\n')
                return 1

    def bmc_info(self):
        logging.info('-----------------------')
        logging.info('Fetching BMC information:')
        cmd = [self.path_bmc_info]
        try:
            self.subproc_logging(cmd)
        except (SubprocessError, OSError, TimeoutExpired):
            self.proc_ex('bmc_info()')
            return 1
        else:
            logging.info('Fetched BMC information!\n')
            return 0

    def ipmi_version(self):
        logging.info('-----------------------')
        logging.info('Testing IPMI version:')
        cmd = [self.path_bmc_info]
        try:
            output = self.subproc_logging(cmd)
            # Prefer .index() over .find() for exception handling
            res_index = output.index('IPMI Version')
            version = output[(res_index + 24):(res_index + 27)]
            logging.info(f'IPMI Version: {version}\n')
            if float(version) < self.ipmi_ver:
                logging.info(f'IPMI Version below {self.ipmi_ver}!\n')
                return 1
            else:
                return 0
        except (TimeoutExpired, SubprocessError, OSError,):
            self.proc_ex('ipmi_version()')
            return 1

    def ipmi_locate(self):
        logging.info('-----------------------')
        logging.info('Testing ipmi-locate:')
        regex = re.compile('driver:')
        cmd = [self.path_ipmi_locate]
        try:
            output = self.subproc_logging(cmd)
            if re.search(regex, output):
                logging.info('Located IPMI driver!\n')
                return 0
            else:
                logging.info('Unable to locate IPMI driver!\n')
                return 1
        except (TimeoutExpired, SubprocessError, OSError):
            self.proc_ex('ipmi_locate()')
            return 1


def main():
    # instantiate argparse as parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Debug/verbose output (stdout/stderr)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress output.')
    args = parser.parse_args()

    # logging subsystem
    if not args.quiet or args.debug:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        format = ''

    if not args.quiet:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(format, ))
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    # instantiate IpmiTest as results for post-processing
    ipmi_test = IpmiTest()
    results = ipmi_test.run_test()
    # tally results
    if sum(results) > 0:
        print ('-----------------------')
        print ('## IPMI tests failed! ##')
        print (
            f'## Chassis: {results[0]}  Power: {results[1]}  ',
            f'Channel: {results[2]}  BMC: {results[3]}  ',
            f'IPMI Version: {results[4]}  IPMI Locate: {results[5]} ##')
        return 1
    else:
        print ('-----------------------')
        print ('## IPMI tests passed! ##')
        return 0


# call main()
if __name__ == '__main__':
    sys.exit(main())
