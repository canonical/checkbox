#!/usr/bin/env python3

import os
import sys
import time

from optparse import OptionParser
from subprocess import Popen, PIPE


COMMAND_FORMAT = "pgrep -f %(options)s %(process)s"


def process_pids(process, *options):
    options_string = " ".join(options)
    command = COMMAND_FORMAT % {"options": options_string, "process": process}

    # Exclude this process and the pgrep process
    subprocess = Popen(
        command, stdout=PIPE, shell=True, universal_newlines=True)
    exclude_pids = [os.getpid(), os.getppid(), subprocess.pid]

    pids_string = subprocess.communicate()[0]
    pids = [int(pid) for pid in pids_string.split()]

    result = set(pids).difference(exclude_pids)
    return list(result)


def process_count(*args):
    return len(process_pids(*args))


def main(args):
    default_sleep = 1

    usage = "Usage: %prog PROCESS [PROCESS...]"
    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--sleep",
        type="int",
        default=default_sleep,
        help="Number of seconds to sleep between checks.")
    parser.add_option("-t", "--timeout",
        type="int",
        help="Number of seconds to timeout from sleeping.")
    parser.add_option("-u", "--uid",
        help="Effective user name or id of the running processes")
    (options, processes) = parser.parse_args(args)

    process_args = []
    if options.uid is not None:
        process_args.extend(["-u", options.uid])

    while True:
        for process in processes:
            if process_count(process, *process_args):
                break
        else:
            break

        if options.timeout is not None:
            if options.timeout <= 0:
                return 1
            else:
                options.timeout -= options.sleep

        time.sleep(options.sleep)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
