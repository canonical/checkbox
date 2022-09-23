#!/usr/bin/env python3
"""
Copyright (C) 2020 Canonical Ltd.

Authors
  Adrian Lane <adrian.lane@canonical.com>
  Jeff Lane <jeff@ubuntu.com>
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
import shutil
import sys
import platform
import argparse
import logging
from subprocess import (
    Popen,
    check_call,
    PIPE,
    TimeoutExpired,
    SubprocessError)


class FreeIpmiTest:

    def __init__(self):
        def get_path(binary):
            """Get absolute path of FreeIPMI/nix binary,
            warn upon failure.
            """
            path_full = shutil.which(binary)
            if path_full:
                return path_full
            else:
                logging.info(
                    '* Unable to stat absolute path for %s!'
                    % binary)
                return binary

        # paths to load_kernel_module() binaries
        self._path_lsmod = get_path('lsmod')
        self._path_modprobe = get_path('modprobe')
        # ipmi kernel modules to load/verify
        self._kernel_modules = (
            'ipmi_si',
            'ipmi_devintf',
            'ipmi_powernv',
            'ipmi_ssif',
            'ipmi_msghandler')
        # method subprocess commands (FreeIPMI)
        self._cmd_ipmi_chassis = [
            get_path('ipmi-chassis'), '--get-status']
        self._cmd_ipmi_channel = [
            get_path('ipmi-config'), '--checkout',
            '--lan-channel-number']
        self._cmd_get_bmc_info = [
            get_path('bmc-info')]
        self._cmd_ipmi_locate = [
            get_path('ipmi-locate')]
        # min. ipmi version to pass
        self._ipmi_ver = 2.0
        # subprocess call timeout (s)
        self._subproc_timeout = 15
        # raised subproc exceptions to handle
        # (decoupled from self._process_exc())
        self._sub_process_excs = (
            TimeoutExpired,
            SubprocessError,
            OSError,
            TypeError,
            FileNotFoundError)

    def _subproc_logging(self, cmd):
        """Subprocess stdin/stderr handling."""
        process = Popen(
            cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        output, error = process.communicate(timeout=self._subproc_timeout)
        logging.debug('## Debug Output: ##')
        if output:
            logging.debug('   [Stdout]\n')
            logging.debug('%s\n' % output)
        if error:
            logging.debug('   [Stderr]\n')
            logging.debug('%s\n' % error)
        logging.debug('## End Debug Output ##\n')
        # ignore stderr
        return output

    def _process_exc(self, exc, test_method):
        """Allows for bundling of exception handling for all
        methods within this class.
        """
        if type(exc) is TimeoutExpired:
            logging.info(
                '* Timeout calling %s! (%ss)\n' %
                (test_method, self._subproc_timeout))
        elif type(exc) is FileNotFoundError:
            logging.info(
                '* Error calling %s! Check cmds/paths.\n' % test_method)
        else:
            logging.info('* Error calling %s!\n' % test_method)

    def _modprobe_hlpr(self, module):
        """load_kernel_mods() helper function to call modprobe."""
        try:
            check_call(
                [self._path_modprobe, module],
                stderr=PIPE, timeout=self._subproc_timeout)
        except self._sub_process_excs:
            logging.info('* Unable to load module %s!' % module)
            logging.info('  **********************************************')
            logging.info('  Warning: proceeding, but in-band IPMI may fail')
            logging.info('  **********************************************')
        else:
            logging.info('- Successfully loaded module %s' % module)

    def load_kernel_mods(self):
        """Check (and load) kernel modules."""
        logging.info('-----------------------')
        logging.info('Verifying kernel modules:')
        try:
            output = self._subproc_logging(self._path_lsmod)
            for module in self._kernel_modules:
                if module in output:
                    logging.info('- %s already loaded' % module)
                else:
                    if (module == 'ipmi_powernv' and
                            platform.machine() != 'ppc64le'):
                        logging.info(' * Skipping module %s, incorrect '
                                     'system architecture' % module)
                    else:
                        self._modprobe_hlpr(module)
            logging.info('')
        except self._sub_process_excs as exc:
            self._process_exc(exc, self.load_kernel_mods.__qualname__)
            return False

    def get_impi_chassis(self):
        """Get ipmi chassis data, pass if called w/o error."""
        logging.info('-----------------------')
        logging.info('Fetching chassis status:')
        try:
            self._subproc_logging(self._cmd_ipmi_chassis)
        except self._sub_process_excs as exc:
            self._process_exc(exc, self.get_impi_chassis.__qualname__)
            return False
        else:
            logging.info('- Fetched chassis status!\n')
            return True

    def get_pwr_status(self):
        """Get power status via ipmi chassis data,
        pass if called w/o error & system power field present.
        """
        logging.info('-----------------------')
        logging.info('Fetching power status:')
        regex = re.compile('^System Power')
        try:
            output = self._subproc_logging(self._cmd_ipmi_chassis)
            for line in output.rstrip().split('\n'):
                if re.search(regex, line):
                    logging.info('- Fetched power status!\n')
                    return True
            logging.info('* Unable to retrieve power status via IPMI.\n')
            return False
        except self._sub_process_excs as exc:
            self._process_exc(exc, self.get_pwr_status.__qualname__)
            return False

    def get_bmc_info(self):
        """Call bmc-info, pass if called w/o error."""
        logging.info('-----------------------')
        logging.info('Fetching BMC information:')
        try:
            self._subproc_logging(self._cmd_get_bmc_info)
        except self._sub_process_excs as exc:
            self._process_exc(exc, self.get_bmc_info.__qualname__)
            return False
        else:
            logging.info('- Fetched BMC information!\n')
            return True

    def _ipmi_version_hlpr(self):
        """Ipmi version discovery loop."""
        regex = re.compile('^IPMI Version')
        output = self._subproc_logging(self._cmd_get_bmc_info)
        for line in output.rstrip().split('\n'):
            if re.search(regex, line):
                version = (line.split(':'))[1].strip()
                return float(version)

    def chk_ipmi_version(self):
        """Fetch ipmi version via bmc-info sdout,
        pass if ipmi version >= self._ipmi_ver.
        """
        logging.info('-----------------------')
        logging.info('Validating IPMI version:')
        try:
            version = self._ipmi_version_hlpr()
            logging.info('- IPMI version: %.1f' % version)
        except self._sub_process_excs as exc:
            self._process_exc(exc, self.chk_ipmi_version.__qualname__)
            return False
        else:
            if version < float(self._ipmi_ver):
                logging.info('* IPMI version below %d!\n' % self._ipmi_ver)
                return False
            else:
                logging.info('  IPMI version compliant!\n')
                return True

    def _ipmi_channel_hlpr(self, i, regex, channel):
        """get_ipmi_channel discovery loop."""
        cmd = self._cmd_ipmi_channel
        if len(cmd) > 3:
            cmd.pop(-1)
        cmd.append(str(i))
        output = self._subproc_logging(cmd)
        for line in output.rstrip().split('\n'):
            if re.search(regex, line):
                channel.append(i)
                return channel

    def get_ipmi_channel(self):
        """Get ipmi channel(s) in use,
        pass if user data returns after calling ipmi-config.
        """
        logging.info('-----------------------')
        logging.info('Fetching IPMI channels:')
        # support multiple channels
        channel = []
        regex = re.compile('Section User')
        # test channels 0 - 15
        for i in range(16):
            # channel 12, 13 are invalid channels, skip
            if i == (12 | 13):
                continue
            try:
                self._ipmi_channel_hlpr(i, regex, channel)
            except self._sub_process_excs as exc:
                self._process_exc(exc, self.get_ipmi_channel.__qualname__)
                return False
        if channel:
            logging.info('- Found %d channel(s)!' % len(channel))
            logging.info('  IPMI channel(s): %s\n' % channel)
            return True
        else:
            logging.info('* Unable to fetch IPMI channel!\n')
            return False

    def run_test(self):
        """Initialize kernel modules, run ipmi tests."""
        # load/val kernel modules
        self.load_kernel_mods()
        results = [self.get_impi_chassis(),
                   self.get_pwr_status(),
                   self.get_bmc_info(),
                   self.chk_ipmi_version(),
                   self.get_ipmi_channel()]
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
    if not args.quiet or args.debug:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
    if not args.quiet:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    print('## Running IPMI Tests ##')
    # instantiate FreeIpmiTest as f_ipmi_test
    f_ipmi_test = FreeIpmiTest()
    results = f_ipmi_test.run_test()
    results_dict = {'Chassis': results[0],
                    'Power': results[1],
                    'BMC': results[2],
                    'Version': results[3],
                    'Channel': results[4]}
    # tally results
    if sum(results) < len(results):
        # transpose readable values into results_dict
        for test, result in results_dict.items():
            if result:
                results_dict[test] = 'Pass'
            else:
                results_dict[test] = 'Fail'
        print('-----------------------')
        print('## IPMI tests failed! ##')
        print('## %r ##' % results_dict)
        return 1
    else:
        print('-----------------------')
        print('## IPMI tests passed! ##')
        return 0


if __name__ == '__main__':
    sys.exit(main())
