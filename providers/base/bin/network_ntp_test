#!/usr/bin/env python3
'''
Program to test that ntpdate will sync the clock with an internet time server.

Copyright (C) 2010 Canonical Ltd.

Author:
    Jeff Lane <jeffrey.lane@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to test to see whether the test system can
connect to an internet time server and sync the local clock.

It will also check to see if ntpd is running locally, and if so, stop it for
the duration of the test and restart it after the test is finished.

By default, we're hitting ntp.ubuntu.com, however you can use any valid NTP
server by passing the URL to the program via --server

'''
import sys
import os
import logging
import signal
import time
from datetime import datetime, timedelta
from subprocess import Popen, PIPE
from argparse import ArgumentParser


def SilentCall(*popenargs):
    '''
    Modified version of subprocess.call() to supress output from the command
    that is executed. Wait for command to complete, then return the returncode
    attribute.
    '''
    null_fh = open('/dev/null', 'wb', 0)
    try:
        return (Popen(*popenargs, shell=True, stdout=null_fh, stderr=null_fh)
                .wait())
    finally:
        null_fh.close()


def CheckNTPD():
    '''
    This checks to see if nptd is running or not, if so it returns a tuple
    (status,pid,command) where status is either on or off.
    '''
    ps_list = (Popen('ps axo pid,comm', shell=True, stdout=PIPE)
               .communicate()[0].splitlines())
    for item in ps_list:
        fields = item.split()
        if fields[1] == 'ntpd':
            logging.debug('Found %s with PID %s'
                          % (fields[1], fields[0]))
            break
    if fields[1] == 'ntpd':
        return ('on', fields[0], fields[1])
    else:
        return ('off', '0', '0')


def StartStopNTPD(state, pid=0):
    '''
    This is used to either start or stop ntpd if its running.
    '''
    if state == 'off':
        logging.info('Stopping ntpd process PID: %s' % pid)
        os.kill(int(pid), signal.SIGHUP)
    elif state == 'on':
        logging.info('Starting ntp process')
        SilentCall('/etc/init.d/ntp start')
        ntpd_status = CheckNTPD()

        if status == 0:
            logging.debug('ntpd restarted with PID: %s' % ntpd_status[1])
        else:
            logging.error('ntpd restart failed for some reason')
    else:
        logging.error('%s is an unknown state, unable to start/stop ntpd' %
                        state)


def SyncTime(server):
    '''
    This is used to sync time to the specified ntp server.  We use -b here as
    that syncs time faster than the slewed method that ntpdate uses by default,
    meaning we'll see something meaningful faster.
    '''
    cmd = 'ntpdate -b ' + server
    logging.debug('using %s' % server)
    sync = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    result = sync.communicate()

    if sync.returncode == 0:
        logging.info('Successful NTP update from %s' % server)
        logging.debug(result[0].strip().decode())
        return True
    else:
        logging.error('Failed to sync with %s' % server)
        logging.error(result[1].strip().decode())
        return False


def TimeCheck():
    '''
    Returns current time in a time.localtime() struct
    '''
    return time.localtime()


def SkewTime():
    '''
    Optional function. We can skew time by 1 hour if we'd like to see real sync
    changes being enforced
    '''
    TIME_SKEW = 1
    logging.info('Time Skewing has been selected. Setting clock ahead 1 hour')
    # Let's get our current time
    skewed = datetime.now() + timedelta(hours=TIME_SKEW)
    logging.info('Current time is: %s' % time.asctime())
    # Now create new time string in the form MMDDhhmmYYYY for the date program
    date_time_string = skewed.strftime('%m%d%H%M%Y')
    logging.debug('New date string is: %s' % date_time_string)
    logging.debug('Setting new system time/date')
    # This call is necessary for testing, otherwise TimeSkew() does nothing.
    SilentCall('/bin/date %s' % date_time_string)
    logging.info('Pre-sync time is: %s' % time.asctime())


def main():
    description = 'Tests the ability to skew and sync the clock with an NTP server'
    parser = ArgumentParser(description=description)
    parser.add_argument('--server',
                        action='store',
                        default='ntp.ubuntu.com',
                        help='The NTP server to sync from. The default server \
                        is %(default)s')
    parser.add_argument('--skew-time',
                        action='store_true',
                        default=False,
                        help='Setting this will change system time ahead by 1 \
                        hour to make the results of ntp syncing more dramatic \
                        and noticeable.')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        default=False,
                        help='Verbose output for debugging purposes')
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("You must run this script as root")

    # Set up logging
    format = '%(asctime)s %(levelname)-8s %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format, date_format))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    # Make sure NTP is installed
    if not os.access('/usr/sbin/ntpdate', os.F_OK):
        logging.error('NTP is not installed!')
        return 1

    # Check for and stop the ntp daemon
    ntpd_status = CheckNTPD()
    logging.debug('Pre-sync ntpd status: %s %s %s' % (ntpd_status[0],
                                                      ntpd_status[1],
                                                      ntpd_status[2]))
    if ntpd_status[0] == 'on':
        logging.debug('Since ntpd is currently running, stopping it now')
        StartStopNTPD('off', ntpd_status[1])

    if args.skew_time:
        logging.debug('Setting system time ahead one hour')
        SkewTime()
    else:
        logging.info('Pre-sync time is: %s' % time.asctime(TimeCheck()))

    sync = SyncTime(args.server)

    logging.info('Current system time is: %s' % time.asctime(TimeCheck()))

    # Restart ntp daemon
    if ntpd_status[0] == 'on':
        logging.debug('Since ntpd was previously running, starting it again')
        StartStopNTPD('on')

    if sync is True:
        return 0
    else:
        return 1

if __name__ == '__main__':
    sys.exit(main())
