#!/usr/bin/env python3
"""
Copyright (C) 2012-2015 Canonical Ltd.

Authors
  Jeff Marcom <jeff.marcom@canonical.com>
  Daniel Manrique <roadmr@ubuntu.com>
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
"""

from argparse import (
    ArgumentParser,
    RawTextHelpFormatter
)
import datetime
import fcntl
import ipaddress
import logging
import math
import os
import re
import shlex
import socket
import struct
import subprocess
import tempfile
import threading
from subprocess import (
    CalledProcessError,
    check_call,
    check_output,
    STDOUT
)
import sys
import time

# Global results[] variable to pass results from multiple threads....
results = []


class IPerfPerformanceTest(object):
    """Measures performance of interface using iperf client
    and target. Calculated speed is measured against theorectical
    throughput of selected interface"""

    def __init__(
            self,
            interface,
            target,
            fail_threshold,
            cpu_load_fail_threshold,
            iperf3,
            num_threads,
            reverse,
            protocol="tcp",
            data_size="1",
            run_time=None,
            scan_timeout=3600,
            iface_timeout=120):

        self.iface = Interface(interface)
        self.target = target
        self.protocol = protocol
        self.fail_threshold = fail_threshold
        self.cpu_load_fail_threshold = cpu_load_fail_threshold
        self.iperf3 = iperf3
        self.num_threads = num_threads
        self.data_size = data_size
        self.run_time = run_time
        self.scan_timeout = scan_timeout
        self.iface_timeout = iface_timeout
        self.reverse = reverse

    def run_one_thread(self, cmd, port_num):
        """Run a single test thread, storing the output in the global results[]
        variable."""
        cmd = cmd + " -p {}".format(port_num)
        logging.debug("Executing command {}".format(cmd))
        logging.info("Connecting to port {} on server....".format(port_num))
        try:
            iperf_return = check_output(
                shlex.split(cmd), stderr=subprocess.STDOUT,
                universal_newlines=True)
        except CalledProcessError as iperf_exception:
            if iperf_exception.returncode != 124:
                # timeout command will return 124 if iperf timed out, so any
                # other return value means something did fail
                if "unable to connect to server" in iperf_exception.output:
                    logging.error("Unable to connect to server on port {}".
                                  format(port_num))
                    if port_num == 5202:
                        # 5202 is 2nd port in high-speed configs
                        logging.warning("Your iperf3 server is not configured")
                        logging.warning("for high-speed network testing. See")
                        logging.warning("the Self-Test Guide's 'Network")
                        logging.warning("Performance Tuning' appendix for")
                        logging.warning("more information.")
                else:
                    # Unknown error; log it....
                    logging.error("Failed executing iperf on port {}.".
                                  format(port_num))
                    logging.error("Output is '{}'".
                                  format(iperf_exception.output))
                return iperf_exception.returncode
            else:
                # this is normal so we "except" this exception and we
                # "pass through" whatever output iperf did manage to produce.
                # When confronted with SIGTERM iperf should stop and output
                # a partial (but usable) result.
                logging.warning("iperf timed out - this should be OK")
                iperf_return = iperf_exception.output
        results.append(iperf_return)

    def summarize_speeds(self):
        """Search the global results[] variable, computing the throughput for
        each thread and returning the total throughput for all threads."""
        total_throughput = 0
        n = 0
        for run in results:
            logging.debug(run)
            # iperf3 provides "sender" and "receiver" summaries; remove them
            run = re.sub(r".*(sender|receiver)", "", run)
            speeds = list(map(float, re.findall(r"([\w\.]+)\sMbits/sec",
                                                run)))
            if (len(speeds) > 0):
                total_throughput = total_throughput + sum(speeds)/len(speeds)
                logging.debug("Throughput for thread {} is {}".
                              format(n, sum(speeds)/len(speeds)))
                logging.debug("Min Transfer speed for thread {}: {} Mb/s".
                              format(n, min(speeds)))
                logging.debug("Max Transfer speed for thread {}: {} Mb/s".
                              format(n, max(speeds)))
                n = n + 1
        return total_throughput

    def summarize_cpu(self):
        """Return the average CPU load of all the threads, as reported by
        iperf3. (Version 2 of iperf does not return CPU loads, in which case
        this function returns 0.)"""
        sum_cpu = 0.0
        avg_cpu = 0.0
        n = 0
        for thread_results in results:
            # "CPU Utilization" line present only in iperf3 output
            new_cpu = re.findall(r"CPU Utilization.*local/sender\s([\w\.]+)",
                                 thread_results)
            if new_cpu:
                float_cpu = float(new_cpu[0])
                logging.debug("CPU load for thread {}: {}%".
                              format(n, float_cpu))
                sum_cpu = sum_cpu + float_cpu
                n = n + 1
            if n > 0:
                avg_cpu = sum_cpu / n
        return avg_cpu

    def run(self):
        # if max_speed is 0, assume it's wifi and move on
        if self.iface.max_speed == 0:
            logging.warning("No max speed detected, assuming Wireless device "
                            "and continuing with test.")

        # Set the correct binary to run
        if (self.iperf3):
            self.executable = "iperf3 -V"
        else:
            self.executable = "iperf"

        # Determine number of parallel threads
        if self.num_threads == -1:
            # Below is a really crude guesstimate based on our
            # initial testing. It's likely possible to improve
            # this method of setting the number of threads.
            threads = math.ceil(self.iface.link_speed / 10000)
        else:
            threads = self.num_threads

        if threads == 1:
            logging.info("Using 1 thread.")
        else:
            logging.info("Using {} threads.".format(threads))

        # Alter variables for iperf (2) vs. iperf3 -- Use iperf (2)'s own
        # built-in threading, vs. this script's threading for iperf3. (Note
        # that even with iperf 2, this script creates one separate thread
        # for running iperf -- but only one; within that thread, iperf 2's
        # own multi-threading handles that detail.)
        if self.iperf3:
            start_port = 5201
            iperf_threads = 1
            python_threads = threads
        else:
            start_port = 5001
            iperf_threads = threads
            python_threads = 1

        # If we set run_time, use that instead to build the command.
        if self.run_time is not None:
            cmd = "{} -c {} -t {} -i 1 -f m -P {}".format(
                self.executable, self.target, self.run_time, iperf_threads)
            if self.reverse:
                cmd += " -R"
        else:
            # Because we can vary the data size, we need to vary the timeout as
            # well.  It takes an estimated 15 minutes to send 1GB over 10Mb/s.
            # 802.11b is 11 Mb/s.  So we'll assume 1.2x15 minutes or 18 minutes
            # or 1080 seconds per Gigabit. This will allow for a long period of
            # time without timeout to catch devices that slow down, and also
            # not prematurely end iperf on low-bandwidth devices.
            self.timeout = 1080*int(self.data_size)
            cmd = "timeout -k 1 {} {} -c {} -n {}G -i 1 -f -m -P {}".format(
                self.timeout, self.executable, self.target, self.data_size,
                iperf_threads)

        # Handle threading -- start Python threads (even if just one is
        # used), then use join() to wait for them all to complete....
        t = []
        results.clear()
        for thread_num in range(0, python_threads):
            port_num = start_port + thread_num
            t.append(threading.Thread(target=self.run_one_thread,
                                      args=(cmd, port_num)))
            t[thread_num].start()
        for thread_num in range(0, python_threads):
            t[thread_num].join()

        throughput = self.summarize_speeds()
        invalid_speed = False
        try:
            percent = throughput / int(self.iface.max_speed) * 100
        except (ZeroDivisionError, TypeError):
            # Catches a condition where the interface functions fine but
            # ethtool fails to properly report max speed. In this case
            # it's up to the reviewer to pass or fail.
            percent = 0
            invalid_speed = True
        logging.info("Avg Transfer speed: {} Mb/s".format(throughput))
        if invalid_speed:
            # If we have no link_speed (e.g. wireless interfaces don't
            # report this), then we shouldn't penalize them because
            # the transfer may have been reasonable. So in this case,
            # we'll exit with a pass-warning.
            logging.warning("Unable to obtain maximum speed.")
            logging.warning("Considering the test as passed.")
            return 0
        # Below is guaranteed to not throw an exception because we'll
        # have exited above if it did.
        logging.info("{:03.2f}% of theoretical max {} Mb/s".
                     format(percent, int(self.iface.max_speed)))

        if self.iperf3:
            cpu_load = self.summarize_cpu()
            logging.info("Average CPU utilization: {}%".
                         format(round(cpu_load, 1)))
        else:
            cpu_load = 0
        if percent < self.fail_threshold or \
                cpu_load > self.cpu_load_fail_threshold:
            logging.warning("The network test against {} failed because:".
                            format(self.target))
            if percent < self.fail_threshold:
                logging.error("  Transfer speed: {} Mb/s".format(throughput))
                logging.error(
                    "  {:03.2f}% of theoretical max {} Mb/s\n".format(
                        percent, int(self.iface.max_speed)))
            if cpu_load > self.cpu_load_fail_threshold:
                logging.error("  CPU load: {}%".format(cpu_load))
                logging.error(
                    "  CPU load is above {}% maximum\n".format(
                        self.cpu_load_fail_threshold))
            return 30

        logging.debug("Passed benchmark against {}".format(self.target))


class StressPerformanceTest:

    def __init__(self, interface, target, iperf3):
        self.interface = interface
        self.target = target
        self.iperf3 = iperf3

    def run(self):
        if self.iperf3:
            iperf_cmd = 'timeout -k 1 320 iperf3 -c {} -t 300'.format(
                self.target)
        else:
            iperf_cmd = 'timeout -k 1 320 iperf -c {} -t 300'.format(
                self.target)
        print("Running iperf...")
        iperf = subprocess.Popen(shlex.split(iperf_cmd))

        ping_cmd = 'ping -I {} {}'.format(self.interface, self.target)
        ping = subprocess.Popen(shlex.split(ping_cmd), stdout=subprocess.PIPE)
        iperf.communicate()

        ping.terminate()
        (out, err) = ping.communicate()

        if iperf.returncode != 0:
            return iperf.returncode

        print("Running ping test...")
        result = 0
        time_re = re.compile('(?<=time=)[0-9]*')
        for line in out.decode().split('\n'):
            time = time_re.search(line)

            if time and int(time.group()) > 2000:
                print(line)
                print("ICMP packet was delayed by > 2000 ms.")
                result = 1
            if 'unreachable' in line.lower():
                print(line)
                result = 1

        return result


class Interface(socket.socket):
    """
    Simple class that provides network interface information.
    """

    def __init__(self, interface):

        super(Interface, self).__init__(
            socket.AF_INET, socket.IPPROTO_ICMP)

        self.interface = interface

        self.dev_path = os.path.join("/sys/class/net", self.interface)

    def _read_data(self, type):
        try:
            return open(os.path.join(self.dev_path, type)).read().strip()
        except OSError:
            logging.warning("%s: Attribute not found", type)

    @property
    def ipaddress(self):
        freq = struct.pack('256s', self.interface[:15].encode())

        try:
            nic_data = fcntl.ioctl(self.fileno(), 0x8915, freq)
        except IOError:
            logging.error("No IP address for %s", self.interface)
            return None
        return socket.inet_ntoa(nic_data[20:24])

    @property
    def netmask(self):
        freq = struct.pack('256s', self.interface.encode())

        try:
            mask_data = fcntl.ioctl(self.fileno(), 0x891b, freq)
        except IOError:
            logging.error("No netmask for %s", self.interface)
            return None
        return socket.inet_ntoa(mask_data[20:24])

    @property
    def link_speed(self):
        return int(self._read_data("speed"))

    @property
    def max_speed(self):
        speeds = [0]
        # parse ethtool output, look for things like:
        # 100baseSX, 40000baseNX, 10000baseT
        try:
            ethinfo = check_output(['ethtool', self.interface],
                                   universal_newlines=True,
                                   stderr=STDOUT).split(' ')
            expression = r'(\\d+)(base)([A-Z]+)|(\d+)(Mb/s)'

            regex = re.compile(expression)
            if ethinfo:
                for i in ethinfo:
                    hit = regex.search(i)
                    if hit:
                        speeds.append(int(re.sub(r"\D", "", hit.group(0))))
        except CalledProcessError as e:
            logging.error('ethtool returned an error!')
            logging.error(e.output)
        except FileNotFoundError:
            logging.warning('ethtool not found! Trying mii-tool')
            # Parse mii-tool data for max speed
            # search for numbers in the line starting with 'capabilities'
            # return largest number as max_speed
            try:
                info = check_output(['mii-tool', '-v',  self.interface],
                                    universal_newlines=True,
                                    stderr=STDOUT).split('\n')
                regex = re.compile(r'(\d+)(base)([A-Z]+)')
                speeds = [0]
                for line in filter(lambda l: 'capabilities' in l, info):
                    for s in line.split(' '):
                        hit = regex.search(s)
                        if hit:
                            speeds.append(int(re.sub(r"\D", "", hit.group(0))))
            except FileNotFoundError:
                logging.warning('mii-tool not found! Unable to get max speed')
            except CalledProcessError as e:
                logging.error('mii-tool returned an error!')
                logging.error(e.output)
        return max(speeds)

    @property
    def macaddress(self):
        return self._read_data("address")

    @property
    def duplex_mode(self):
        return self._read_data("duplex")

    @property
    def status(self):
        return self._read_data("operstate")

    @property
    def device_name(self):
        return self._read_data("device/label")


def get_test_parameters(args, environ):
    # Decide the actual values for test parameters, which can come
    # from one of two possible sources: command-line
    # arguments, or environment variables.
    # - If command-line args were given, they take precedence
    # - Next come environment variables, if set.

    params = {"test_target_iperf": None}

    # See if we have environment variables
    for key in params.keys():
        params[key] = os.environ.get(key.upper(), "")

    # Finally, see if we have the command-line arguments that are the ultimate
    # override.
    if args.target:
        params["test_target_iperf"] = args.target

    return params


def can_ping(the_interface, test_target):
    working_interface = False
    num_loops = 0
    while (not working_interface) and (num_loops < 48):
        working_interface = True

        try:
            with open(os.devnull, 'wb') as DEVNULL:
                check_call(["ping", "-I", the_interface,
                            "-c", "1", test_target],
                           stdout=DEVNULL, stderr=DEVNULL)
        except CalledProcessError:
            working_interface = False

        if not working_interface:
            time.sleep(5)
            num_loops += 1

    return working_interface


def run_test(args, test_target):
    # Ensure that interface is fully up by waiting until it can
    # ping the test server
    logging.info("Testing {} against {}".format(args.interface, test_target))
    if can_ping(args.interface, test_target):
        logging.info("Have successfully pinged {} on {}".
                     format(test_target, args.interface))
    else:
        logging.error("Can't ping test server {} on {}".format(test_target,
                                                               args.interface))
        return 1

    # Execute requested networking test
    if args.test_type.lower() == "iperf":
        error_number = 0
        iperf_benchmark = IPerfPerformanceTest(args.interface, test_target,
                                               args.fail_threshold,
                                               args.cpu_load_fail_threshold,
                                               args.iperf3, args.num_threads,
                                               args.reverse)
        if args.datasize:
            iperf_benchmark.data_size = args.datasize
        if args.runtime:
            iperf_benchmark.run_time = args.runtime
        run_num = 0
        while not error_number and run_num < args.num_runs:
            run_num += 1
            logging.info(" Test Run Number %s ".center(60, "-"), run_num)
            error_number = iperf_benchmark.run()
            logging.info('')
    elif args.test_type.lower() == "stress":
        stress_benchmark = StressPerformanceTest(args.interface,
                                                 test_target, args.iperf3)
        error_number = stress_benchmark.run()
    else:
        logging.error("Unknown test type {}".format(args.test_type))
        return 10
    return error_number


def make_target_list(iface, test_targets, log_warnings):
    """Convert comma-separated string of test targets into a list form.

    Converts test target list in string form into Python list form, omitting
    entries that are not on the current network segment.
    :param iface:
        Name of network interface device (eth0, etc.)
    :param test_targets:
        Input test targets as string of comma-separated IP addresses or
        hostnames
    :param emit_warnings:
        Whether to log warning messages
    :returns:
        List form of input string, minus invalid values
    """
    test_targets_list = test_targets.split(",")
    try:
        net = ipaddress.IPv4Network("{}/{}".format(Interface(iface).ipaddress,
                                                   Interface(iface).netmask),
                                    False)
    except ipaddress.AddressValueError as e:
        logging.error("Device {}: Invalid IP Address".format(iface))
        logging.error("  {}".format(e))
        logging.error("Aborting test now")
        sys.exit(1)
    first_addr = net.network_address + 1
    last_addr = first_addr + net.num_addresses - 2
    return_list = list(test_targets_list)
    for test_target in test_targets_list:
        try:
            test_target_ip = socket.gethostbyname(test_target)
        except OSError:
            test_target_ip = test_target
        if (test_target_ip != "0.0.0.0"):
            try:
                target = ipaddress.IPv4Address(test_target_ip)
                if (target < first_addr) or (target > last_addr):
                    if log_warnings:
                        logging.warning("Removing iperf server {} ({}) from ".
                                        format(test_target, target))
                        logging.warning("test list since it's not within {}.".
                                        format(net))
                    return_list.remove(test_target)
            except ValueError:
                if log_warnings:
                    logging.warning("Invalid address: {}; skipping".
                                    format(test_target))
                return_list.remove(test_target)
    return_list.reverse()
    if (return_list == ['']):
        del(return_list[0])
    return return_list


# Wait until the specified interface comes up, or until iface_timeout.
def wait_for_iface_up(iface, timeout):
    isdown = True
    deadline = time.time() + timeout
    while (time.time() < deadline) and isdown:
        try:
            link_status = check_output(["ip", "link", "show", "dev",
                                        iface]).decode("utf-8")
        except CalledProcessError as interface_failure:
            logging.error("Failed to check %s:%s", iface, interface_failure)
            return 1
        if ("state UP" in link_status):
            logging.debug("Interface {} is up!".format(iface))
            isdown = False
        else:
            logging.debug("Interface {} not yet up; waiting....".format(iface))
        # Sleep whether or not interface is up because sometimes the IP
        # address gets assigned after "ip" claims it's up.
        time.sleep(5)


def interface_test(args):
    if not ("test_type" in vars(args)):
        return

    # Get the actual test data from one of two possible sources
    test_parameters = get_test_parameters(args, os.environ)

    if (args.test_type.lower() == "iperf" or
            args.test_type.lower() == "stress"):
        test_targets = test_parameters["test_target_iperf"]
        test_targets_list = make_target_list(args.interface, test_targets,
                                             True)

    # Validate that we got reasonable values
    if not test_targets_list or "example.com" in test_targets:
        # Default values found in config file
        logging.error("Valid target server has not been supplied.")
        logging.error("Configuration settings can be configured 3 different "
                      "ways:")
        logging.error("1- If calling the script directly, pass the --target "
                      "option")
        logging.error("2- Define the TEST_TARGET_IPERF environment variable")
        logging.error("3- If running the test via checkbox/plainbox, define "
                      "the ")
        logging.error("target in /etc/xdg/canonical-certification.conf")
        logging.error("Please run this script with -h to see more details on "
                      "how to configure")
        sys.exit(1)

    # Testing begins here!
    #
    # Make sure that the interface is indeed connected
    try:
        check_call(["ip", "link", "set", "dev", args.interface, "up"])
    except CalledProcessError as interface_failure:
        logging.error("Failed to use %s:%s", args.interface, interface_failure)
        return 1

    # Check for an underspeed link and abort if found, UNLESS --underspeed-ok
    # option was used or max_speed is 0 (which indicates a probable WiFi link)
    iface = Interface(args.interface)
    if iface.link_speed < iface.max_speed and iface.max_speed != 0 and \
            not args.underspeed_ok:
        logging.error("Detected link speed ({}) is lower than detected max "
                      "speed ({})".format(iface.link_speed, iface.max_speed))
        logging.error("Check your device configuration and try again.")
        logging.error("If you want to override and test despite this "
                      "under-speed link, use")
        logging.error("the --underspeed-ok option.")
        sys.exit(1)

    # Back up routing table, since network down/up process
    # tends to trash it....
    temp = tempfile.TemporaryFile()
    try:
        check_call(["ip", "route", "save", "table", "all"], stdout=temp)
    except CalledProcessError as route_error:
        logging.warning("Unable to save routing table: %s", route_error)

    error_number = 0
    # Stop all other interfaces
    if not args.dont_toggle_ifaces:
        extra_interfaces = \
            [iface for iface in os.listdir("/sys/class/net")
             if iface != "lo" and iface != args.interface and
             not iface.startswith("virbr") and not iface.startswith("lxdbr")]

        for iface in extra_interfaces:
            logging.debug("Shutting down interface:%s", iface)
            try:
                check_call(["ip", "link", "set", "dev", iface, "down"])
            except CalledProcessError as interface_failure:
                logging.error("Failed to shut down %s:%s",
                              iface, interface_failure)
                error_number = 3

    if error_number == 0:
        start_time = datetime.datetime.now()
        first_loop = True
        # Keep testing until a success or we run out of both targets and time
        while test_targets_list:
            test_target = test_targets_list.pop().strip()
            error_number = run_test(args, test_target)
            elapsed_seconds = (datetime.datetime.now() - start_time).seconds
            if (elapsed_seconds > args.scan_timeout and not first_loop) or \
                    not error_number:
                break
            if not test_targets_list:
                logging.warning(" Exhausted test target list; trying again "
                                .center(60, "="))
                test_targets_list = make_target_list(args.interface,
                                                     test_targets,
                                                     False)
                time.sleep(30)   # Wait to give server(s) time to come online
                first_loop = False

    if not args.dont_toggle_ifaces:
        for iface in extra_interfaces:
            logging.debug("Restoring interface:%s", iface)
            try:
                check_call(["ip", "link", "set", "dev", iface, "up"])
                wait_for_iface_up(iface, args.iface_timeout)
            except CalledProcessError as interface_failure:
                logging.error(
                    "Failed to restore %s:%s", iface, interface_failure)
                error_number = 3

    # Restore routing table to original state
    temp.seek(0)
    try:
        # Harmless "RTNETLINK answers: File exists" messages on stderr
        with open(os.devnull, 'wb') as DEVNULL:
            check_call(["ip", "route", "restore"], stdin=temp,
                       stderr=DEVNULL)
    except CalledProcessError:
        # This always errors out -- but it works!
        # The problem is virbr0, which has the "linkdown" flag, which the
        # "ip route restore" command can't handle.
        pass
    temp.close()

    return error_number


def interface_info(args):

    info_set = ""
    if "all" in vars(args):
        info_set = args.all

    for key, value in vars(args).items():
        if value is True or info_set is True:
            key = key.replace("-", "_")
            try:
                print(
                    key + ":", getattr(Interface(args.interface), key),
                    file=sys.stderr)
            except AttributeError:
                pass


def main():

    intro_message = """
Network module

This script provides benchmarking and information for a specified network
interface.

Example NIC information usage:
network.py info -i eth0 --max-speed

For running iperf test:
network.py test -i eth0 -t iperf --target 192.168.0.1
NOTE: The iperf test requires an iperf server running on the same network
segment that the test machine is running on.

Also, you can use iperf3 rather than iperf2 by specifying the -3 or --iperf3
option like so:

network.py test -i eth0 -t iperf -3 --target 192.168.0.1

Configuration
=============

Configuration can be supplied in three different ways, with the following
priorities:

1- Command-line parameters (see above).
2- Environment variables (example will follow).
3- If run via checkbox/plainbox, /etc/xdg/checkbox-certification.conf
   can have the below-mentioned environment variables defined in the
   [environment] section. An example file is provided and can be simply
   modified with the correct values.

Environment variables
=====================
The variables are:
TEST_TARGET_IPERF

example config file
===================
[environment]
TEST_TARGET_IPERF = iperf-server.example.com


**NOTE**

"""

    parser = ArgumentParser(
        description=intro_message, formatter_class=RawTextHelpFormatter)
    subparsers = parser.add_subparsers()

    # Main cli options
    test_parser = subparsers.add_parser(
        'test', help=("Run network performance test"))
    info_parser = subparsers.add_parser(
        'info', help=("Gather network info"))

    # Sub test options
    action = test_parser.add_mutually_exclusive_group()

    test_parser.add_argument(
        '-i', '--interface', type=str, required=True)
    test_parser.add_argument(
        '-t', '--test_type', type=str,
        choices=("iperf", "stress"), default="iperf",
        help=("[iperf *Default*]"))
    test_parser.add_argument(
        '-3', '--iperf3', default=False, action="store_true",
        help=("Tells the script to use iperf3 for testing, rather than the "
              "default of iperf2"))
    test_parser.add_argument('--target', type=str)
    action.add_argument(
        '--datasize', type=str,
        default="1",
        help=("CANNOT BE USED WITH --runtime. Amount of data to send.  For "
              "iperf tests this will direct iperf to send DATASIZE GB of "
              "data to the target."))
    action.add_argument(
        '--runtime', type=int,
        default=60,
        help=("CANNOT BE USED WITH --datasize. Send data for *runtime* "
              "seconds.  For iperf tests, this will send data for the amount "
              "of time indicated, rather than until a certain file size is "
              "reached."))
    test_parser.add_argument(
        '--scan-timeout', type=int,
        default=60,
        help=("Sets the maximum time, in seconds, the test will scan for "
              "iperf servers before giving up."))
    test_parser.add_argument(
        '--iface-timeout', type=int,
        default=120,
        help=("Sets the maximum time, in seconds, the test will wait for "
              "an interface to come up after a test before giving up."))
    test_parser.add_argument(
        '--config', type=str,
        default="/etc/checkbox.d/network.cfg",
        help="Supply config file for target/host network parameters")
    test_parser.add_argument(
        '--fail-threshold', type=int,
        default=40,
        help=("IPERF Test ONLY. Set the failure threshold (Percent of maximum "
              "theoretical bandwidth) as a number like 80.  (Default is "
              "%(default)s)"))
    test_parser.add_argument(
        '--cpu-load-fail-threshold', type=int,
        default=100,
        help=("(IPERF Test ONLY and meaningful ONLY with --iperf3. Set the "
              "failure threshold (above which the CPU load must not rise) as "
              "a number like 80. (Default is %(default)s)"))
    test_parser.add_argument(
        '--num_runs', type=int,
        default=1,
        help=("Number of times to run the test. (Default is %(default)s)"))
    test_parser.add_argument(
        '--debug', default=False, action="store_true",
        help="Turn on verbose output")
    test_parser.add_argument(
        '--underspeed-ok', default=False, action="store_true",
        help="Run test even if an underspeed 1ink is detected")
    test_parser.add_argument(
        '--num-threads', type=int, default=-1,
        help=("Number of threads to use in the test. "
              "(Default is computed based on network speed.)"))
    test_parser.add_argument(
        '--reverse', default=False, action="store_true",
        help="Run in reverse mode (server sends, client receives)")
    test_parser.add_argument(
        '--dont-toggle-ifaces', default=False, action="store_true",
        help="Do not turn of other interfaces while testing.")

    # Sub info options
    info_parser.add_argument(
        '-i', '--interface', type=str, required=True)
    info_parser.add_argument(
        '--all', default=False, action="store_true")
    info_parser.add_argument(
        '--duplex-mode', default=False, action="store_true")
    info_parser.add_argument(
        '--link-speed', default=False, action="store_true")
    info_parser.add_argument(
        '--max-speed', default=False, action="store_true")
    info_parser.add_argument(
        '--ipaddress', default=False, action="store_true")
    info_parser.add_argument(
        '--netmask', default=False, action="store_true")
    info_parser.add_argument(
        '--device-name', default=False, action="store_true")
    info_parser.add_argument(
        '--macaddress', default=False, action="store_true")
    info_parser.add_argument(
        '--status', default=False, action="store_true",
        help=("displays connection status"))
    info_parser.add_argument(
        '--debug', default=False, action="store_true",
        help="Turn on verbose output")

    test_parser.set_defaults(func=interface_test)
    info_parser.set_defaults(func=interface_info)

    args = parser.parse_args()
    if (args.func.__name__ is interface_test and
       not args.cpu_load_fail_threshold != 100 and
       not args.iperf3):
        parser.error('--cpu-load-fail-threshold can only be set with '
                     '--iperf3.')

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if 'func' not in args:
        parser.print_help()
    else:
        return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
