#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# graphics_stress_test.py
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
#
# Authors: Alberto Milone <alberto.milone@canonical.com>
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

import errno
import logging
import os
import re
import sys
import tempfile
import time

from argparse import ArgumentParser
from subprocess import call, Popen, PIPE
from checkbox_support.contrib import xrandr


class VtWrapper(object):
    """docstring for VtWrapper"""
    def __init__(self):
        self.x_vt = self._get_x_vt()

    def _get_x_vt(self):
        '''Get the vt where X lives'''
        vt = 0
        proc = Popen(['ps', 'aux'], stdout=PIPE, universal_newlines=True)
        proc_output = proc.communicate()[0].split('\n')
        proc_line = re.compile(r'.*tty(\d+).+/usr/bin/X.*')
        for line in proc_output:
            match = proc_line.match(line)
            if match:
                vt = match.group(1).strip().lower()
        return int(vt)

    def set_vt(self, vt):
        retcode = call(['chvt', '%d' % vt])
        return retcode


class SuspendWrapper(object):
    def __init__(self):
        pass

    def can_we_sleep(self, mode):
        '''
        Test to see if S3 state is available to us.  /proc/acpi/* is old
        and will be deprecated, using /sys/power to maintine usefulness for
        future kernels.

        '''
        states_fh = open('/sys/power/state', 'r')
        try:
            states = states_fh.read().split()
        finally:
            states_fh.close()

        if mode in states:
            return True
        else:
            return False

    def get_current_time(self):
        cur_time = 0
        time_fh = open('/sys/class/rtc/rtc0/since_epoch', 'r')
        try:
            cur_time = int(time_fh.read())
        finally:
            time_fh.close()
        return cur_time

    def set_wake_time(self, time):
        '''
        Get the current epoch time from /sys/class/rtc/rtc0/since_epoch
        then add time and write our new wake_alarm time to
        /sys/class/rtc/rtc0/wakealarm.

        The math could probably be done better but this method avoids having to
        worry about whether or not we're using UTC or local time for both the
        hardware and system clocks.

        '''
        cur_time = self.get_current_time()
        logging.debug('Current epoch time: %s' % cur_time)

        wakealarm_fh = open('/sys/class/rtc/rtc0/wakealarm', 'w')

        try:
            wakealarm_fh.write('0\n')
            wakealarm_fh.flush()

            wakealarm_fh.write('+%s\n' % time)
            wakealarm_fh.flush()
        finally:
            wakealarm_fh.close()

        logging.debug('Wake alarm in %s seconds' % time)

    def do_suspend(self, mode):
        '''
        Suspend the system and hope it wakes up.
        Previously tried writing new state to /sys/power/state but that
        seems to put the system into an uncrecoverable S3 state.  So far,
        pm-suspend seems to be the most reliable way to go.

        '''
        if mode == 'mem':
            status = call('/usr/sbin/pm-suspend')
        elif mode == 'disk':
            status = call('/usr/sbin/pm-hibernate')
        else:
            logging.debug('Unknown sleep state passed')
            status == 1

        return status


class RotationWrapper(object):

    def __init__(self):
        self._rotations = {'normal': xrandr.RR_ROTATE_0,
                           'right': xrandr.RR_ROTATE_90,
                           'inverted': xrandr.RR_ROTATE_180,
                           'left': xrandr.RR_ROTATE_270}

    def _rotate_screen(self, rotation):
        # Refresh the screen. Required by NVIDIA
        screen = xrandr.get_current_screen()
        screen.set_rotation(rotation)
        return screen.apply_config()

    def do_rotation_cycle(self):
        '''Cycle through all possible rotations'''
        rots_statuses = {}

        for rot in self._rotations:
            try:
                status = self._rotate_screen(self._rotations[rot])
            except (xrandr.RRError, xrandr.UnsupportedRRError) as err:
                status = 1
                error = err
            else:
                error = 'N/A'
            # Collect the status and the error message
            rots_statuses[rot] = (status, error)
            time.sleep(4)

        # Try to set the screen back to normal
        try:
            self._rotate_screen(xrandr.RR_ROTATE_0)
        except (xrandr.RRError, xrandr.UnsupportedRRError) as error:
            print(error)

        result = 0
        for elem in rots_statuses:
            status = rots_statuses.get(elem)[0]
            error = rots_statuses.get(elem)[1]
            if status != 0:
                logging.error('Error: rotation "%s" failed with status %d: %s.'
                              % (elem, status, error))
                result = 1
        return result


class RenderCheckWrapper(object):
    """A simple class to run the rendercheck suites"""

    def __init__(self, temp_dir=None):
        self._temp_dir = temp_dir

    def _print_test_info(self, suites='all', iteration=1, show_errors=False):
        '''Print the output of the test suite'''

        main_command = 'rendercheck'
        passed = 0
        total = 0

        if self._temp_dir:
            # Use the specified path
            temp_file = tempfile.NamedTemporaryFile(dir=self._temp_dir,
                                                    delete=False)
        else:
            # Use /tmp
            temp_file = tempfile.NamedTemporaryFile(delete=False)

        if suites == all:
            full_command = [main_command, '-f', 'a8r8g8b8']
        else:
            full_command = [main_command, '-t', suites, '-f', 'a8r8g8b8']

        try:
            # Let's dump the output into file as it can be very large
            # and we don't want to store it in memory
            process = Popen(full_command, stdout=temp_file,
                            universal_newlines=True)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                logging.error('Error: please make sure that rendercheck '
                              'is installed.')
                exit(1)
            else:
                raise

        exit_code = process.wait()

        temp_file.close()

        # Read values from the file
        errors = re.compile('.*test error.*')
        results = re.compile('(.+) tests passed of (.+) total.*')

        first_error = True
        with open(temp_file.name) as temp_handle:
            for line in temp_handle:
                match_output = results.match(line)
                match_errors = errors.match(line)
                if match_output:
                    passed = int(match_output.group(1).strip())
                    total = int(match_output.group(2).strip())
                    logging.info('Results:')
                    logging.info(
                        '    %d tests passed out of %d.' % (passed, total))
                if show_errors and match_errors:
                    error = match_errors.group(0).strip()
                    if first_error:
                        logging.debug(
                            'Rendercheck %s suite errors '
                            'from iteration %d:'
                            % (suites, iteration))
                        first_error = False
                    logging.debug('    %s' % error)

        # Remove the file
        os.unlink(temp_file.name)

        return (exit_code, passed, total)

    def run_test(self, suites=[], iterations=1, show_errors=False):
        exit_status = 0
        for suite in suites:
            for it in range(iterations):
                logging.info(
                    'Iteration %d of Rendercheck %s suite...'
                    % (it + 1, suite))
                (status, passed, total) = self._print_test_info(
                    suites=suite, iteration=it + 1, show_errors=show_errors)
                if status != 0:
                    # Make sure to catch a non-zero exit status
                    logging.info(
                        'Iteration %d of Rendercheck %s suite '
                        'exited with status %d.'
                        % (it + 1, suite, status))
                    exit_status = status
                it += 1

                # exit with 1 if passed < total
                if passed < total:
                    if exit_status == 0:
                        exit_status = 1
        return exit_status

    def get_suites_list(self):
        '''Return a list of the available test suites'''
        try:
            process = Popen(['rendercheck', '--help'], stdout=PIPE,
                            stderr=PIPE, universal_newlines=True)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                logging.error('Error: please make sure that rendercheck '
                              'is installed.')
                exit(1)
            else:
                raise

        proc = process.communicate()[1].split('\n')
        found = False
        tests_pattern = re.compile('.*Available tests: *(.+).*')
        temp_line = ''
        tests = []
        for line in proc:
            if found:
                temp_line += line
            match = tests_pattern.match(line)
            if match:
                first_line = match.group(1).strip().lower()
                found = True
                temp_line += first_line
        for elem in temp_line.split(','):
            test = elem.strip()
            if elem:
                tests.append(test)
        return tests


def main():
    # Make sure that we have root privileges
    if os.geteuid() != 0:
        print('Error: please run this program as root',
              file=sys.stderr)
        exit(1)

    usage = 'Usage: %prog [OPTIONS]'
    parser = ArgumentParser(usage)
    parser.add_argument('-i', '--iterations',
                        type=int,
                        default=10,
                        help='The number of times to run the test. \
                              Default is 10')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help='Choose this to add verbose output \
                              for debug purposes')
    parser.add_argument('-b', '--blacklist',
                        nargs='+',
                        help='Name(s) of rendercheck test(s) to blacklist.')
    parser.add_argument('-o', '--output',
                        default='',
                        help='The path to the log which will be dumped. \
                              Default is stdout')
    parser.add_argument('-tp', '--temp',
                        default='',
                        help='The path where to store temporary files. \
                              Default is /tmp')
    args = parser.parse_args()

    # Set up logging to console
    format = '%(message)s'

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(format))

    # Set up the overall logger
    logger = logging.getLogger()
    # This is necessary to ensure debug messages are passed through the logger
    # to the handler
    logger.setLevel(logging.DEBUG)

    # This is what happens when -d and/or -o are passed:
    # -o ->     stdout (info)                - log (info)
    # -d ->     only stdout (info and debug) - no log
    # -d -o ->  stdout (info)                - log (info and debug)

    # Write to a log
    if args.output:
        # Write INFO to stdout
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        # Specify a log file
        logfile = args.output
        logfile_handler = logging.FileHandler(logfile)
        if args.debug:
            # Write INFO and DEBUG to a log
            logfile_handler.setLevel(logging.DEBUG)
        else:
            # Write INFO to a log
            logfile_handler.setLevel(logging.INFO)

        logfile_handler.setFormatter(logging.Formatter(format))
        logger.addHandler(logfile_handler)

    # Write only to stdout
    else:
        if args.debug:
            # Write INFO and DEBUG to stdout
            console_handler.setLevel(logging.DEBUG)
            logger.addHandler(console_handler)
        else:
            # Write INFO to stdout
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)

    status = 0

    rendercheck = RenderCheckWrapper(args.temp)
    tests = rendercheck.get_suites_list()
    for test in args.blacklist:
        if test in tests:
            tests.remove(test)

    # Switch between the tty where X lives and tty10
    vt_wrap = VtWrapper()
    target_vt = 10
    if vt_wrap.x_vt != target_vt:
        logging.info('== Vt switch test ==')
        for it in range(args.iterations):
            logging.info('Iteration %d...', it)
            retcode = vt_wrap.set_vt(target_vt)
            if retcode != 0:
                logging.error(
                    'Error: switching to tty%d failed with code %d '
                    'on iteration %d' % (target_vt, retcode, it))
                status = 1
            else:
                logging.info('Switching to tty%d: passed' % (target_vt))
            time.sleep(2)
            retcode = vt_wrap.set_vt(vt_wrap.x_vt)
            if retcode != 0:
                logging.error(
                    'Error: switching to tty%d failed with code %d '
                    'on iteration %d' % (vt_wrap.x_vt, retcode, it))
            else:
                logging.info('Switching to tty%d: passed' % (vt_wrap.x_vt))
                status = 1
    else:
        logging.error('Error: please run X on a tty other than 10')

    # Call sleep x times
    logging.info('== Sleep test ==')
    sleep_test = SuspendWrapper()
    sleep_mode = 'mem'
    # See if we can sleep
    if sleep_test.can_we_sleep(sleep_mode):
        for it in range(args.iterations):
            # Run the test
            logging.info('Iteration %d...', it + 1)
            # Set wake time
            sleep_test.set_wake_time(20)
            # Suspend to RAM
            if sleep_test.do_suspend(sleep_mode) == 0:
                logging.info('Passed')
            else:
                logging.error('Failed')
                status = 1
    else:
        # Skip the test
        logging.info('Skipped (the system does not seem to support S3')

    # Rotate the screen x times
    # The app already rotates the screen 5 times
    logging.info('== Rotation test ==')
    rotation_test = RotationWrapper()

    for it in range(args.iterations):
        logging.info('Iteration %d...', it + 1)
        if rotation_test.do_rotation_cycle() == 0:
            logging.info('Passed')
        else:
            logging.error('Failed')
            status = 1

    # Call rendercheck x times
    logging.info('== Rendercheck test ==')
    if rendercheck.run_test(tests, args.iterations,
                            args.debug) == 0:
        logging.info('Passed')
    else:
        logging.error('Failed')
        status = 1

    return status


if __name__ == '__main__':
    exit(main())
