#!/usr/bin/env python3
import argparse
import subprocess as sp
import re
import sys
import os
import gzip
from checkbox_support.snap_utils.snapd import Snapd


def parser_log(log, action):
    init = 0
    for line in log:
        if action == "dump":
            print(line)
        elif action == "timing":
            if re.search(r"(?:Done|seed).*\d+ms", line):
                init = init + int(re.search(r"(\d+)ms", line).groups()[0])
    if init != 0:
        return str(init / 1000)


def snapd_change_log(change_id):
    cmd = "snap debug timings " + change_id
    try:
        log = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
        return log.splitlines()
    except sp.CalledProcessError:
        exit("Error: Can't find change_id: {}".format(str(change_id)))


def find_finished_time(log, action):
    for line in log:
        if action == "dump":
            print(line)
        elif action == "timing":
            if re.search(r"Cloud-init.*finished", line) or re.search(
                "Startup finished", line
            ):
                # look up 3 kinds of log
                # first: 6min 1.700s.
                # second: 6min 700ms.
                # third: Up 998.19 seconds
                pattern_1 = r" (\d+)\.\d+ "
                pattern_2 = r"(\d+)min (\d+)\.\d+s\."
                pattern_3 = r"(\d+)min \d+ms\."
                if re.search(pattern_1, line):
                    time_sec = int(re.search(pattern_1, line).groups()[0])
                elif re.search(pattern_2, line):
                    min, sec = re.search(pattern_2, line).groups()
                    time_sec = int(min[0]) * 60 + int(sec[0])
                elif re.search(pattern_3, line):
                    min = re.search(pattern_3, line).groups()
                    time_sec = int(min[0]) * 60
                timestamp = re.search(r"(\d.)\:(\d.):(\d.)", line).groups()
                timestamp_finished = (
                    int(timestamp[0]) * 3600
                    + int(timestamp[1]) * 60
                    + int(timestamp[2])
                )
            if line == log[-1]:
                # Count the total time in second of the log
                timestamp = re.search(r"(\d.)\:(\d.):(\d.)", line).groups()
                timestamp_lastline = (
                    int(timestamp[0]) * 3600
                    + int(timestamp[1]) * 60
                    + int(timestamp[2])
                )
                time_finished = (
                    timestamp_lastline - timestamp_finished + time_sec
                )
                return str(time_finished)


def check_change_id():
    cmd = "snap changes"
    snapd_ids = {}
    try:
        log = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
    except sp.CalledProcessError:
        exit("Error: Can't execute snap changes!")
    for line in log.splitlines():
        if "Initialize system state" in line:
            snapd_ids["Initialize_system_state"] = line[:1]
        elif "Initialize device" in line:
            snapd_ids["Initialize_device"] = line[:1]
    return snapd_ids


def dump_log(file):
    if ".gz" in file:
        with gzip.open(file, "r") as f:
            log = f.read()
        return log.decode("utf-8").splitlines()
    else:
        with open(file) as f:
            log = f.readlines()
        return log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target",
        choices=["snapd", "cloud-init", "gzip-log"],
        help='Execute action in "snapd",\
                        "cloud-init" or "gzip-log"',
    )
    parser.add_argument(
        "-a",
        "--action",
        choices=["timing", "dump"],
        default=None,
        help='Execute action in "timing" or "dump"',
    )
    parser.add_argument("-f", "--file", default=None, help="File name")
    args = parser.parse_args()
    path = "/var/log/"
    snapd = Snapd().list("snapd")
    result = {
        "snapd": {"version": snapd["version"], "revision": snapd["revision"]}
    }
    if args.target == "snapd":
        snapd_id = check_change_id()
        log = {}
        if snapd_id:
            for id in snapd_id.keys():
                log[id] = snapd_change_log(str(snapd_id[id]))
            if log:
                if args.action == "timing":
                    for line in log.keys():
                        result["snapd"][line] = str(
                            parser_log(log[line], args.action)
                        )
                        print(
                            "Snapd {} takes : {} seconds".format(
                                line, result["snapd"][line]
                            )
                        )
                elif args.action == "dump":
                    for line in log.keys():
                        print("###### Snapd {} log ######".format(line))
                        parser_log(log[line], args.action)
            else:
                exit("Error: Can not found log")
        else:
            exit("Error: Can't found change ID for Snapd.")
    elif args.target == "cloud-init" and args.file != "":
        file = path + args.file
        if os.path.isfile(file):
            log = dump_log(file)
            time = find_finished_time(log, args.action)
            if args.action == "timing":
                print("Cloud-init finished Up : {} Seconds".format(time))
                result[file] = {"finished_time": time}
        else:
            exit("Error: Can't find {}".format(file))
    elif args.target == "gzip-log" and args.file != "":
        file = path + args.file
        if os.path.isfile(file):
            log = dump_log(file)
            if args.file == "install-timings.txt.gz":
                time = parser_log(log, args.action)
            elif args.file == "install-mode.log.gz":
                time = find_finished_time(log, args.action)
            if args.action == "timing":
                print("Time from {} taskes : {} seconds".format(file, time))
                result[file.replace(".gz", "")] = time
        else:
            exit("Error: Can't find {}".format(file))
    return result


if __name__ == "__main__":
    main()
