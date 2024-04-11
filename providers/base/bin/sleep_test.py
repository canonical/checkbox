#!/usr/bin/env python3
"""
Program to automate system entering and resuming from sleep states

Copyright (C) 2010-2014 Canonical Ltd.

Author:
    Jeff Lane <jeffrey.lane@canonical.com>
    Daniel Manrique <roadmr@ubuntu.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import os
import re
import sys
import syslog

from optparse import OptionParser, OptionGroup
from subprocess import call


class ListDictHandler(logging.StreamHandler):
    """
    Extends logging.StreamHandler to handle list, tuple and dict objects
    internally, rather than through external code, mainly used for debugging
    purposes.

    """

    def emit(self, record):
        if isinstance(
            record.msg,
            (
                list,
                tuple,
            ),
        ):
            for msg in record.msg:
                logger = logging.getLogger(record.name)
                new_record = logger.makeRecord(
                    record.name,
                    record.levelno,
                    record.pathname,
                    record.lineno,
                    msg,
                    record.args,
                    record.exc_info,
                    record.funcName,
                )
                logging.StreamHandler.emit(self, new_record)
        elif isinstance(record.msg, dict):
            for key, val in record.msg.items():
                logger = logging.getLogger(record.name)
                new_msg = "%s: %s" % (key, val)
                new_record = logger.makeRecord(
                    record.name,
                    record.levelno,
                    record.pathname,
                    record.lineno,
                    new_msg,
                    record.args,
                    record.exc_info,
                    record.funcName,
                )
                logging.StreamHandler.emit(self, new_record)
        else:
            logging.StreamHandler.emit(self, record)


class SuspendTest:
    """
    Creates an object to handle the actions necessary for suspend/resume
    testing.

    """

    def __init__(self):
        self.wake_time = 0
        self.current_time = 0
        self.last_time = 0

    def CanWeSleep(self, mode):
        """
        Test to see if S3 state is available to us.  /proc/acpi/* is old
        and will be deprecated, using /sys/power to maintain usefulness for
        future kernels.

        """
        states_fh = open("/sys/power/state", "rb", 0)
        try:
            states = states_fh.read().decode("ascii").split()
        finally:
            states_fh.close()
        logging.debug("The following sleep states were found:")
        logging.debug(states)

        if mode in states:
            return True
        else:
            return False

    def GetCurrentTime(self):

        time_fh = open("/sys/class/rtc/rtc0/since_epoch", "rb", 0)
        try:
            time = int(time_fh.read().decode("ascii"))
        finally:
            time_fh.close()
        return time

    def SetWakeTime(self, time):
        """
        Get the current epoch time from /sys/class/rtc/rtc0/since_epoch
        then add time and write our new wake_alarm time to
        /sys/class/rtc/rtc0/wakealarm.

        The math could probably be done better but this method avoids having to
        worry about whether or not we're using UTC or local time for both the
        hardware and system clocks.

        """
        self.last_time = self.GetCurrentTime()
        logging.debug("Current epoch time: %s" % self.last_time)

        wakealarm_fh = open("/sys/class/rtc/rtc0/wakealarm", "wb", 0)

        try:
            wakealarm_fh.write("0\n".encode("ascii"))
            wakealarm_fh.flush()

            wakealarm_fh.write("+{}\n".format(time).encode("ascii"))
            wakealarm_fh.flush()
        finally:
            wakealarm_fh.close()

        logging.debug("Wake alarm in %s seconds" % time)

    def DoSuspend(self, mode):
        """
        Suspend the system and hope it wakes up.
        Previously tried writing new state to /sys/power/state but that
        seems to put the system into an uncrecoverable S3 state.  So far,
        pm-suspend seems to be the most reliable way to go.

        """
        # Set up our start and finish markers
        self.time_stamp = self.GetCurrentTime()
        self.start_marker = "CHECKBOX SLEEP TEST START %s" % self.time_stamp
        self.end_marker = "CHECKBOX SLEEP TEST STOP %s" % self.time_stamp
        self.MarkLog(self.start_marker)

        if mode == "mem":
            status = call("/usr/sbin/pm-suspend")
        elif mode == "disk":
            status = call("/usr/sbin/pm-hibernate")
        else:
            logging.debug("Unknown sleep state passed: %s" % mode)
            status == 1

        if status == 0:
            logging.debug("Successful suspend")
        else:
            logging.debug("Error while running pm-suspend")
        self.MarkLog(self.end_marker)

    def GetResults(self, mode, perf):
        """
        This will parse /var/log/messages for our start and end markers. Then
        it'll find a few key phrases that are part of the sleep and resume
        process, grab their timestamps, Bob's your Uncle and return a
        three-tuple consisting of: (PASS/FAIL,Sleep elapsed time, Resume
        elapsed time)
        """
        # figure out our elapsed time
        logfile = "/var/log/syslog"
        log_fh = open(logfile, "r")
        line = ""
        run_complete = "Fail"
        sleep_start_time = 0.0
        sleep_end_time = 0.0
        resume_start_time = 0.0
        resume_end_time = 0.0

        while self.start_marker not in line:
            line = log_fh.readline()
            if self.start_marker in line:
                logging.debug("Found Start Marker")
                loglist = log_fh.readlines()

        if perf:
            for idx in range(0, len(loglist)):
                if "PM: Syncing filesystems" in loglist[idx]:
                    sleep_start_time = re.split(r"[\[\]]", loglist[idx])[
                        1
                    ].strip()
                    logging.debug("Sleep started at %s" % sleep_start_time)
                if "ACPI: Low-level resume complete" in loglist[idx]:
                    sleep_end_time = re.split(r"[\[\]]", loglist[idx - 1])[
                        1
                    ].strip()
                    logging.debug("Sleep ended at %s" % sleep_end_time)
                    resume_start_time = re.split(r"[\[\]]", loglist[idx])[
                        1
                    ].strip()
                    logging.debug("Resume started at %s" % resume_start_time)
                    idx += 1
                if "Restarting tasks" in loglist[idx]:
                    resume_end_time = re.split(r"[\[\]]", loglist[idx])[
                        1
                    ].strip()
                    logging.debug("Resume ended at %s" % resume_end_time)
                if self.end_marker in loglist[idx]:
                    logging.debug(
                        "End Marker found, run appears to " "have completed"
                    )
                    run_complete = "Pass"
                    break

            sleep_elapsed = float(sleep_end_time) - float(sleep_start_time)
            resume_elapsed = float(resume_end_time) - float(resume_start_time)
            logging.debug("Sleep elapsed: %.4f seconds" % sleep_elapsed)
            logging.debug("Resume elapsed: %.4f seconds" % resume_elapsed)
        else:
            if self.end_marker in loglist:
                logging.debug(
                    "End Marker found, " "run appears to have completed"
                )
                run_complete = "Pass"
            sleep_elapsed = None
            resume_elapsed = None

        return (run_complete, sleep_elapsed, resume_elapsed)

    def MarkLog(self, marker):
        """
        Write a stamped marker to syslogd (will appear in /var/log/messages).
        This is used to calculate the elapsed time for each iteration.
        """
        syslog.syslog(syslog.LOG_INFO, "---" + marker + "---")

    def CheckAlarm(self, mode):
        """
        A better method for checking if system woke via rtc alarm IRQ. If the
        system woke via IRQ, then alarm_IRQ will be 'no' and wakealarm will be
        an empty file.  Otherwise, alarm_IRQ should still say yes and wakealarm
        should still have a number in it (the original alarm time), indicating
        the system did not wake by alarm IRQ, but by some other means.
        """
        rtc = {}
        rtc_fh = open("/proc/driver/rtc", "rb", 0)
        alarm_fh = open("/sys/class/rtc/rtc0/wakealarm", "rb", 0)
        try:
            rtc_data = rtc_fh.read().decode("ascii").splitlines()
            for item in rtc_data:
                rtc_entry = item.partition(":")
                rtc[rtc_entry[0].strip()] = rtc_entry[2].strip()
        finally:
            rtc_fh.close()

        try:
            alarm = int(alarm_fh.read().decode("ascii"))
        except ValueError:
            alarm = None
        finally:
            alarm_fh.close()

        logging.debug("Current RTC entries")
        logging.debug(rtc)
        logging.debug("Current wakealarm %s" % alarm)

        # see if there's something in wakealarm or alarm_IRQ
        # Return True indicating the alarm is still set
        # Return False indicating the alarm is NOT set.
        # This is currently held up by a bug in PM scripts that
        # does not reset alarm_IRQ when waking from hibernate.
        # https://bugs.launchpad.net/ubuntu/+source/linux/+bug/571977
        if mode == "mem":
            if (alarm is not None) or (rtc["alarm_IRQ"] == "yes"):
                logging.debug("alarm is %s" % alarm)
                logging.debug("rtc says alarm_IRQ: %s" % rtc["alarm_IRQ"])
                return True
            else:
                logging.debug("alarm was cleared")
                return False
        else:
            # This needs to be changed after we get a way around the
            # hibernate bug.  For now, pretend that the alarm is unset for
            # hibernate tests.
            logging.debug("mode is %s so we're skipping success check" % mode)
            return False


def main():
    usage = "Usage: %prog [OPTIONS]"
    parser = OptionParser(usage)
    group = OptionGroup(
        parser,
        "This will not work for hibernat testing due"
        " to a kernel timestamp bug when doing an S4 "
        "(hibernate/resume) sleep cycle",
    )
    group.add_option(
        "-p",
        "--perf",
        action="store_true",
        default=False,
        help="Add some output that tells you how long it "
        "takes to enter a sleep state and how long it "
        "takes to resume.",
    )
    parser.add_option(
        "-i",
        "--iterations",
        action="store",
        type="int",
        metavar="NUM",
        default=1,
        help="The number of times to run the suspend/resume "
        "loop. Default is %default",
    )
    parser.add_option(
        "-w",
        "--wake-in",
        action="store",
        type="int",
        metavar="NUM",
        default=60,
        dest="wake_time",
        help="Sets wake up time (in seconds) in the future "
        "from now. Default is %default.",
    )
    parser.add_option(
        "-s",
        "--sleep-state",
        action="store",
        default="mem",
        metavar="MODE",
        dest="mode",
        help="Sets the sleep state to test. Passing mem will "
        "set the sleep state to Suspend-To-Ram or S3.  Passing "
        "disk will set the sleep state to Suspend-To-Disk or S4 "
        "(hibernate). Default sleep state is %default",
    )
    parser.add_option(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Choose this to add verbose output for debug \
                      purposes",
    )
    parser.add_option_group(group)
    (options, args) = parser.parse_args()
    options_dict = vars(options)

    if not (os.geteuid() == 0):
        parser.error("Must be run as root.")
        return 1

    # Set up logging handler
    format = "%(message)s"
    handler = ListDictHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(format))
    handler.setLevel(logging.INFO)

    # Set up the logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    if options.debug:
        handler.setLevel(logging.DEBUG)

    logger.addHandler(handler)
    logging.debug("Running with these options")
    logging.debug(options_dict)

    suspender = SuspendTest()
    run_result = {}
    run_count = 0
    fail_count = 0

    # Chcek fo the S3 state availability
    if not suspender.CanWeSleep(options.mode):
        logging.error("%s sleep state not supported" % options.mode)
        return 1
    else:
        logging.debug(
            "%s sleep state supported, continuing test" % options.mode
        )

    # We run the following for the number of iterations requested
    for iteration in range(0, options.iterations):
        # Set new alarm time and suspend.
        suspender.SetWakeTime(options.wake_time)
        suspender.DoSuspend(options.mode)
        run_count += 1
        run_result[run_count] = suspender.GetResults(
            options.mode, options.perf
        )
        if suspender.CheckAlarm(options.mode):
            logging.debug("The alarm is still set")

    if options.perf:
        sleep_total = 0.0
        resume_total = 0.0
        logging.info("=" * 20 + " Test Results " + "=" * 20)
        logging.info(run_result)

        for k in run_result.keys():
            sleep_total += run_result[k][1]
            resume_total += run_result[k][2]
        sleep_avg = sleep_total / run_count
        resume_avg = resume_total / run_count
        logging.info("Average time to sleep: %.4f" % sleep_avg)
        logging.info("Average time to resume: %.4f" % resume_avg)
    for run in run_result.keys():
        if "Fail" in run_result[run]:
            fail_count += 1

    if fail_count > 0:
        logging.error("%s sleep/resume test cycles failed" % fail_count)
        logging.error(run_result)
        return 1
    else:
        logging.info(
            "Successfully completed %s sleep iterations" % options.iterations
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
