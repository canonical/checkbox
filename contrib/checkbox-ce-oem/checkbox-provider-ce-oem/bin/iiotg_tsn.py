#!/usr/bin/python3

import argparse
import subprocess
import shlex
import time
import re
import os
from threading import Event
from typing import List
from contextlib import contextmanager


def clear_qdisc_settings(interface: str) -> None:
    """Clear the previous qdisc settings.

    This function clears the previous qdisc settings by running the tc
    command with the 'qdisc del' option. It may return an error if there
    is no previous settings.
    This will get errors if there is no previous settings.

    Args:
        interface (str): The name of the network interface.

    Returns:
        None
    """
    # Build the tc command to delete the root qdisc settings
    cmd = "tc qdisc del dev {} root".format(interface)

    # Run the tc command with a timeout of 1 second
    subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,  # Redirect stdout to a pipe.
        stderr=subprocess.PIPE,  # Redirect stderr to a pipe.
        timeout=1,
    )


@contextmanager
def clear_qdisc_settings_before_and_after(interface: str):
    """Clear the previous qdisc settings.

    This context manager clears the previous qdisc settings by running the
    tc command with the 'qdisc del' option. It may return an error if there
    is no previous settings.

    Args:
        interface (str): The name of the network interface.

    Yields:
        None

    Raises:
        subprocess.CalledProcessError: If the tc command fails to delete
        the root qdisc settings.
    """

    # Run the tc command to delete the root qdisc settings
    try:
        # Clear qdisc settings before the function call
        clear_qdisc_settings(interface)
        yield
    finally:
        # Clear qdisc settings after the function call
        clear_qdisc_settings(interface)


def ptp4l(interface: str, cfg: str, timeout: int = 0) -> subprocess.Popen:
    """Run ptp4l command to sync physical hardware clock between systems.

    Args:
        interface (str): The interface to set the clock on.
        cfg (str): The path to the configuration file.
        timeout (int): The time to wait for the command to complete, \
            in seconds.

    Returns:
        subprocess.Popen: A process object representing \
        the running ptp4l command.
    """
    # Build the ptp4l command with the provided parameters.
    cmd = "timeout {} ptp4l -i {} -f {} -m".format(
        timeout,
        interface,
        cfg,
    )

    # Run the ptp4l command with the provided parameters.
    # The command is run with stdout and stderr redirected to pipes.
    # Text mode is enabled to allow access to the output as text.
    process = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,  # Redirect stdout to a pipe.
        stderr=subprocess.PIPE,  # Redirect stderr to a pipe.
        text=True,  # Enable text mode, so output can be accessed as text.
    )

    # Return the process object representing the running ptp4l command.
    return process


def phc2sys(interface: str, timeout: int = 60) -> subprocess.Popen:
    """Run phc2sys command to sync system clock to physical hardware clock.

    Args:
        interface (str): The network interface to sync.
        timeout (int): The time to wait for the command to complete,
        in seconds. Defaults to 60 seconds.

    Returns:
        subprocess.Popen: A process object representing the
        running phc2sys command.
    """
    # Build the phc2sys command with the provided parameters.
    # The command uses the timeout utility to limit the execution time.
    # phc2sys is used to sync the system clock to the physical hardware clock.
    # The -s specifies the interface to sync.
    # The -O 0 flag sets the offset between system clock
    # and physical hardware clock to 0.
    # The -c specify the slave clock source.
    # The -w flag wait for ptp4l.
    # The -m flag print the messages.
    # The --step_threshold=1 flag sets the step threshold to 1.
    # The --transportSpecific=1 the transport specific field. [0-255]
    cmd = (
        "timeout {} phc2sys -s {} "
        "-O 0 -c CLOCK_REALTIME -w -m "
        "--step_threshold=1 --transportSpecific=1"
    ).format(timeout, interface)

    # Run the phc2sys command with the provided parameters.
    # The command is run with stdout and stderr redirected to pipes.
    # Text mode is enabled to allow access to the output as text.
    process = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,  # Redirect stdout to a pipe.
        stderr=subprocess.PIPE,  # Redirect stderr to a pipe.
        text=True,  # Enable text mode, so output can be accessed as text.
    )

    # Return the process object representing the running phc2sys command.
    return process


def server_mode(
    interfaces: List,
    cfg: str = "/usr/share/doc/linuxptp/configs/automotive-master.cfg",
) -> None:
    """Run ptp4l as master in every port.

    Args:
        interfaces (List): List of network interfaces.
        cfg (str, optional): Path to the configuration file.
            Defaults to
            "/usr/share/doc/linuxptp/configs/automotive-master.cfg".

    This function runs ptp4l as master in every port specified
    in the interfaces list. It terminates all running ptp4l processes on
    KeyboardInterrupt.

    Raises:
        ValueError: If the number of interfaces and server_ips is not the same.
    """

    # List to store the process objects
    processes = []

    # Iterate over each interface and run ptp4l as master
    for interface in interfaces:
        # Clear qdisc settings for the interface
        clear_qdisc_settings(interface=interface)

        # Run ptp4l as master with the provided interface and configuration
        process = ptp4l(interface=interface, cfg=cfg)
        processes.append(process)
        print("Start running ptp4l on {} as master".format(interface))

        # Get the IP address of the interface
        ip = get_interface_ip(interface)

        # Run iperf3 as a server in each port specified and each CPU
        for port, cpu in zip(range(5201, 5204), range(1, 4)):
            # Run iperf3 server
            process = subprocess.Popen(
                shlex.split(
                    "iperf3 -s -B {} -p {} -A {}".format(ip, port, cpu)
                )
            )
            processes.append(process)

        # Wait for 0.5 seconds before printing the separator
        time.sleep(0.5)

        # Print separator line
        print("===========================================================")

    # Print message to press ctrl + c to end this
    print("Press ctrl + c to end this.")

    try:
        # Wait for KeyboardInterrupt
        Event().wait()
    except KeyboardInterrupt:
        # Terminate all running ptp4l processes
        for process in processes:
            process.terminate()
        print("Terminated all ptp4l and iperf3 process")

    return


def time_sync_ptp4l(
    interface: str,
    cfg: str = "/usr/share/doc/linuxptp/configs/automotive-slave.cfg",
    timeout: int = 60,
) -> None:
    """
    Test ptp4l by running it as a subprocess and checking its output.

    Args:
        interface (str): The network interface to run ptp4l on.
        cfg (str, optional): The path to the ptp4l configuration file.
            Defaults to "/usr/share/doc/linuxptp/configs/automotive-slave.cfg".
        timeout (int, optional): The maximum time to wait for ptp4l to run.
            Defaults to 60 seconds.

    Raises:
        SystemExit: If ptp4l encounters an error or the master offset is not
        between -100 and 100.

    Prints:
        Standard Output (stdout): The output of ptp4l.
        Standard Error (stderr): The error output of ptp4l, if any.
        [PASS] Masteroffset is between -100 to 100: If the master offset is
            between -100 and 100.
        [FAIL] Masteroffset is not between -100 to 100: If the master offset
            is not between -100 and 100.
    """
    if timeout < 30:
        raise SystemExit(
            "[ERROR] timeout should be at least 30 seconds "
            "to let the time synchronized"
        )
    # Run ptp4l as a subprocess and get its output
    process = ptp4l(interface=interface, cfg=cfg, timeout=timeout)
    stdout, stderr = process.communicate()

    # Print the output of ptp4l
    print("Standard Output (stdout):")
    print(stdout)
    print("Standard Error (stderr):")
    print(stderr)

    # If ptp4l encountered an error, raise a SystemExit exception
    if stderr:
        raise SystemExit(
            "[Error] Catch error while running ptp4l on {}".format(interface)
        )

    # Check the last 10 seconds of ptp4l output
    lines = stdout.splitlines()
    for line in lines[-10:]:
        offset = int(line.split()[3])
        if not -100 < offset < 100:
            raise SystemExit("[FAIL] Masteroffset is not between -100 to 100")

    # If the master offset is between -100 and 100, print a success message
    print("[PASS] Masteroffset is between -100 to 100")


def time_sync_phc2sys(
    interface: str,
    cfg: str = "/usr/share/doc/linuxptp/configs/automotive-slave.cfg",
    timeout: int = 60,
) -> None:
    """
    Test phc2sys by running it as a subprocess and checking its output.

    Args:
        interface (str): The network interface to run phc2sys on.
        cfg (str, optional): The path to the phc2sys configuration file.
            Defaults to "/usr/share/doc/linuxptp/configs/automotive-slave.cfg".
        timeout (int, optional): The maximum time to wait for phc2sys to run.
            Defaults to 60 seconds.

    Raises:
        SystemExit: If phc2sys encounters an error or the master offset is not
            between -100 and 100, or the state is not equal to "s2" for the
            last 10 seconds, or the path delay is not equal to 0.

    Prints:
        Standard Output (stdout): The output of phc2sys.
        Standard Error (stderr): The error output of phc2sys, if any.
        [PASS] Syncing system time to physical hardware clock successfully: If
            phc2sys syncs the system time to physical hardware clock
            successfully.
    """
    if timeout < 30:
        raise SystemExit(
            "[ERROR] timeout should be at least 30 seconds "
            "to let the time synchronized"
        )
    # Run ptp4l as a subprocess and get its output
    ptp4l(interface=interface, cfg=cfg, timeout=timeout)

    # Run phc2sys as a subprocess and get its output
    process = phc2sys(interface=interface, timeout=timeout)
    stdout, stderr = process.communicate()

    # Print the output of phc2sys
    print("Standard Output (stdout):")
    print(stdout)
    print("Standard Error (stderr):")
    print(stderr)

    # If phc2sys encountered an error, raise a SystemExit exception
    if stderr:
        print(f"[Error] Catch error while running ptp4l on {interface}")
        raise SystemExit(
            "[Error] Catch error while running ptp4l on {}".format(interface)
        )

    # Check the last 10 seconds of phc2sys output
    lines = stdout.splitlines()
    for line in lines[-10:]:
        offset = int(line.split()[4])
        state = line.split()[5]
        delay = int(line.split()[9])

        # If the master offset is not between -100 and 100,
        # raise a SystemExit exception
        if not -100 < offset < 100:
            print("[FAIL] phc offset is not between -100 to 100")
            raise SystemExit(1)

        # If the state is not equal to "s2" for the last 10 seconds,
        # raise a SystemExit exception
        if state != "s2":
            raise SystemExit(
                "[FAIL] state is not equal to s2 "
                "for the last 10 seconds\n"
                "s0: unsynced\n"
                "s1: syncing\n"
                "s2: synced"
            )

        # If the path delay is not equal to 0 for the last 10 seconds,
        # raise a SystemExit exception
        if delay != 0:
            raise SystemExit(
                "[FAIL] path delay is not equal to 0\n"
                "path delay should be 0 if using hardware "
                "cross timestamping"
            )

    print("[PASS] Syncing system time to physical hardware clock successfully")


def time_based_shaper(interface: str, timeout: int = 10) -> None:
    """
    Setup a time-based shaper on the specified interface.

    Args:
        interface (str): The interface to set the shaper on.
        timeout (int): The timeout for the shaper in seconds.

    Raises:
        SystemExit: If there are more than 5% packets not within the required
            time interval.
    """

    # Add mqprio qdisc with four traffic classes
    cmd = (
        "tc qdisc add dev {} handle 8001: parent root mqprio num_tc 4 "
        "map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 queues 1@0 1@1 1@2 1@3 hw 0"
    ).format(interface)
    subprocess.run(shlex.split(cmd), timeout=1)

    # Replace parent qdisc with etf offload
    cmd = (
        "tc qdisc replace dev {} parent 8001:4 etf offload clockid CLOCK_TAI "
        "delta 500000"
    ).format(interface)
    subprocess.run(shlex.split(cmd), timeout=1)

    # Show the current qdisc settings
    cmd = "tc qdisc show dev {}".format(interface)
    subprocess.run(shlex.split(cmd), timeout=1)

    # Run udp_tai with specified parameters
    cmd = "udp_tai -c 3 -i {} -P 1000000 -p 90 -d 600000".format(interface)
    process_udp_tai = subprocess.Popen(
        shlex.split(cmd), stdout=subprocess.PIPE, text=True
    )

    # Capture packets with tcpdump and
    # check that they are within the required time interval
    cmd = (
        "tcpdump -G {} -Q out -ttt -ni {} --time-stamp-precision=nano "
        "-j adapter_unsynced port 7788 -c {}".format(
            timeout, interface, timeout * 1000
        )
    )
    process = subprocess.Popen(
        shlex.split(cmd), stdout=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout * 2)
    except subprocess.TimeoutExpired:
        process.kill()
        raise SystemExit("Reach timeout {}".format(timeout * 2))
    finally:
        process_udp_tai.kill()

    if stdout is None or stderr is not None:
        raise SystemExit("No output from tcpdump!")

    # Print the output of tcpdump
    print("Standard Output (stdout):")
    print(stdout)
    print("Standard Error (stderr):")
    print(stderr)

    lines = stdout.splitlines()
    cnt = 0
    for line in lines:
        try:
            time = int(line.split()[0].split(".")[1])
        except (IndexError, ValueError):
            raise SystemExit(
                "[ERROR] Cannot find the time in the line: {}".format(line)
            )
        if not 999500 < time < 1000500:
            cnt += 1

    # If there are more than 5% packets not within the required time interval,
    # raise a SystemExit exception
    if cnt > timeout * 1000 * 0.05:
        raise SystemExit(
            "[FAIL] There are {}/{} (more than 5%) packets not "
            "within the required time interval (999500 - 1000500)".format(
                cnt, timeout * 1000
            )
        )

    print(
        "[PASS] There are {}/{} packets (less than 5%) within "
        "the required time interval (999500 - 1000500)".format(
            cnt, timeout * 1000
        )
    )


def credit_based_shaper(
    interface: str,
    server_ip: str,
    timeout: int = 10
) -> None:
    """
    Setup a credit-based shaper on the specified interface.

    Args:
        interface (str): The interface to set the shaper on.
        server_ip (str): The IP address of the server to send traffic to.
        timeout (int): The timeout for the shaper in seconds.
    """

    # Replace the main qdisc with a multi-queue qdisc (mqprio) with four
    # traffic classes and 1 queue for each class
    # Set the queues to be associated with classes 0-3
    # and enable hardware offload
    cmd = (
        "tc qdisc replace dev {} handle 100: parent root mqprio num_tc 4 "
        "map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 "
        "queues 1@0 1@1 1@2 1@3 hw 0".format(interface)
    )
    subprocess.run(shlex.split(cmd), timeout=1)

    # Show the current qdisc settings
    cmd = "tc -g class show dev {}".format(interface)
    subprocess.run(shlex.split(cmd), timeout=1)

    # Wait for 5 seconds before replacing the parent qdisc with a credit-based
    # shaper (cbs) and configuring its parameters
    time.sleep(5)

    # Replace the parent qdisc (handle 100:) with a cbs (credit based shaper)
    # Set the low credit and high credit values
    # Set the send slope and idle slope values
    # Enable offload
    cmd = (
        "tc qdisc replace dev {} parent 100:1 cbs "
        "locredit -1350 hicredit 150 sendslope -900000 "
        "idleslope 100000 offload 1".format(interface)
    )
    subprocess.run(shlex.split(cmd), timeout=1)

    # Show the current qdisc settings
    cmd = "tc qdisc show dev {}".format(interface)
    subprocess.run(shlex.split(cmd), timeout=1)

    # Wait for 5 seconds before running iperf3 to measure the upload speed
    time.sleep(5)

    # Run iperf3 client to measure the upload speed
    process = iperf3_client(server_ip, get_interface_ip(interface), timeout)
    stdout, stderr = process.communicate()

    # Check for errors in the iperf3 output
    if stderr:
        raise SystemExit(
            "[ERROR] Found error while running iperf3:\n {}".format(stderr)
        )

    # Print the iperf3 output
    print(stdout)

    # Parse the upload speed from the iperf3 output
    speed_bits = float(stdout.split("\n")[-4].split()[6])

    # Check if the upload speed is between 90 and 100 Mbps
    if not 90 < speed_bits < 100:
        raise SystemExit(
            "[FAIL] The upload speed is not between 90 and 100 Mbps\n"
            "The upload speed is {} Mbps".format(speed_bits)
        )

    # Print the upload speed and a success message
    print(
        "[PASS] The upload speed is between 90 and 100 Mbps\n"
        "The upload speed is {} Mbps".format(speed_bits)
    )


def traffic_scheduling(
    interface: str,
    server_ip: str,
    cfg: str,
    timeout: int = 25,
) -> None:
    """
    Schedules traffic by running ptp4l command, setting qdisc,
    and managing hardware transmit queues for iperf3 instances
    using net_prio cgroups.

    Args:
        interface (str): The interface to schedule traffic on.
        server_ip (str): The IP address of the server.
        cfg (str): The configuration file path.
        timeout (int, optional): The time in seconds to wait for
        each operation. Defaults to 25.

    Returns:
        None
    """

    if timeout < 25:
        raise SystemExit("Timeout must be at least 25 seconds.")
    print("Running ptp4l on {}...".format(interface))
    ptp4l(interface, cfg, timeout)
    time.sleep(10)

    print("Setting qdisc...")
    cmd = (
        "tc qdisc add dev {} parent root handle 100 taprio "
        "num_tc 4 "
        "map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 "
        "queues 1@0 1@1 1@2 1@3 "
        "sched-entry S 01 5000000 "
        "sched-entry S 02 5000000 "
        "sched-entry S 04 5000000 "
        "sched-entry S 08 5000000 "
        "flags 0x2 "
        "txtime-delay 0".format(
            interface
        )
    )
    result = subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1,
    )
    if result.returncode:
        raise SystemExit(
            "[ERROR] Found error while setting qdisc:\n{}".format(
                result.stderr.decode()
            )
        )
    time.sleep(5)

    print(
        "Setting which hardware transmit queue "
        "each iperf3 instance using via net_prio cgroups..."
    )

    # Create /sys/fs/cgroup/net_prio
    os.makedirs("/sys/fs/cgroup/net_prio", exist_ok=True)

    # Mount /sys/fs/cgroup/net_prio
    cmd = "mount -t cgroup -onet_prio none /sys/fs/cgroup/net_prio"
    subprocess.run(shlex.split(cmd), timeout=1)

    # Create /sys/fs/cgroup/net_prio/grp{1,2,3} and write interface {1, 2, 3}
    for grp in range(1, 4):
        path = "/sys/fs/cgroup/net_prio/grp{}".format(grp)
        os.makedirs(path, exist_ok=True)
        with open(path + "/net_prio.ifpriomap", "w") as f:
            f.write("{} {}".format(interface, grp))

    # Run iperf3 client
    for port, group in zip(range(5201, 5204), range(1, 4)):
        print("Running iperf3 client on port {}...".format(port))
        process = iperf3_client(
            server_ip,
            get_interface_ip(interface),
            timeout=timeout - 15,
            port=port,
        )
        pid = str(process.pid)
        file = "/sys/fs/cgroup/net_prio/grp{}/cgroup.procs".format(group)
        print(
            "Writing iperf3 with port {} pid {} to {}".format(port, pid, file)
        )
        with open(file, "w") as f:
            f.write(pid)

    print("Showing qdisc settings after running iperf3...")
    cmd = "tc -s qdisc show dev {}".format(interface)
    before = subprocess.run(
        shlex.split(cmd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print(before.stdout)
    pattern = r"Sent (\d+) bytes"
    bytes_before = re.findall(pattern, before.stdout)
    time.sleep(timeout - 15)
    print("After {} seconds...".format(timeout - 15))
    after = subprocess.run(
        shlex.split(cmd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print(after.stdout)
    bytes_after = re.findall(pattern, before.stdout)
    # Exclude the first value because we only care about 100:1 ~ 100:4
    for before, after in zip(bytes_before[1:], bytes_after[1:]):
        # Need increasing bytes in every queue
        if int(after) - int(before) < 0:
            raise SystemExit(
                "[FAIL] Sent bytes is not increasing "
                "in every queue!\n"
                "100:1 to 100:4"
            )
    print("[PASS] Sent bytes is increasing in every queue!")


def iperf3_client(
    server_ip: str,
    client_ip,
    timeout: int = 60,
    port: int = 5201,
) -> subprocess.Popen:
    """
    Run iperf3 client to measure the upload speed
    from the client to the server.

    Args:
        server_ip (str): The IP address of the server.
        client_ip (str): The IP address of the client.
        timeout (int): The timeout for the iperf3 test in seconds.

    Returns:
        str: The output of the iperf3 client.

    Raises:
        SystemExit: If an error occurs while running iperf3.
    """
    # Construct the iperf3 command
    cmd = "iperf3 -c {} -t {} -B {} -p {} -f m".format(
        server_ip,
        timeout,
        client_ip,
        port,
    )

    # Run the iperf3 client
    process = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,  # Redirect stdout to a pipe.
        stderr=subprocess.PIPE,  # Redirect stderr to a pipe.
        text=True,  # Enable text mode, so output can be accessed as text.
    )
    # Return the process object
    return process


def get_interface_ip(interface):
    cmd = ["ip", "-4", "-o", "addr", "show", "dev", interface]
    result = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Cannot find ip address for {}: {}".format(
                interface, result.stderr.strip()
            )
        )

    for line in result.stdout.splitlines():
        tokens = line.split()
        if "inet" in tokens:
            ip_with_prefix = tokens[tokens.index("inet") + 1]
            return ip_with_prefix.split("/")[0]

    raise SystemExit("Cannot find ip address for {}".format(interface))


def parse_string(string: str):
    """It should be this format, INTERFACE1:SERVER_IP1,INTERFACE2:SERVER_IP2"""
    try:
        for eth in string.split(","):
            interface, server_ip = eth.split(":")
            print("interface: {}".format(interface))
            print("server_ip: {}".format(server_ip))
            print("")
    except Exception as err:
        raise SystemExit("[ERROR] {}".format(err))


def main():
    """
    Main function to parse command line arguments and perform the
    specified testing item or server_mode.
    """
    # Create ArgumentParser object
    parser = argparse.ArgumentParser(
        prog="TSN Testing Tool",
        description="This is a tool to help you perform the TSN testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Add arguments
    parser.add_argument(
        "--run",
        "-r",
        action="store",
        choices=[
            "server",
            "ptp4l",
            "phc2sys",
            "time_based_shaper",
            "credit_based_shaper",
            "traffic_scheduling",
        ],
        help="Run a testing item or server_mode",
    )
    parser.add_argument(
        "--parse-string",
        "-p",
        action="store",
        type=str,
        default=None,
        help="The string need to be parsed, format: "
        "INTERFACE1:SERVER_IP1,INTERFACE2:SERVER_IP2",
    )
    parser.add_argument(
        "--interfaces", "-i", nargs="+", help="TSN ethernet interfaces"
    )
    parser.add_argument(
        "--timeout",
        "-t",
        action="store",
        type=int,
        default=60,
        help="Timeout for the testing item",
    )
    parser.add_argument(
        "--master-config",
        action="store",
        type=str,
        default="/usr/share/doc/linuxptp/configs/automotive-master.cfg",
        help="gPTP config file for master",
    )
    parser.add_argument(
        "--client-config",
        action="store",
        type=str,
        default="/usr/share/doc/linuxptp/configs/automotive-slave.cfg",
        help="gPTP config file for client",
    )
    parser.add_argument(
        "--server-ip",
        action="store",
        type=str,
        help="Server IP address",
    )
    parser.add_argument(
        "--all-interfaces",
        type=str,
        help="All TSN supported network interfaces, sperated by spaces, "
        "quoted by double quotes",
    )
    # Parse command line arguments
    args = parser.parse_args()

    if args.parse_string is not None:
        parse_string(args.parse_string)
        return
    # Perform the specified testing item or server_mode
    if args.run == "server":
        # Run server_mode
        server_mode(
            args.interfaces, cfg=args.master_config
        )
        return
    elif len(args.interfaces) != 1:
        # Exit if interfaces is not a single element
        raise SystemExit("We only need one interface for testing!")

    if args.run == "ptp4l":
        # Time sync with ptp4l
        with clear_qdisc_settings_before_and_after(
            interface=args.interfaces[0]
        ):
            time_sync_ptp4l(
                args.interfaces[0],
                cfg=args.client_config,
                timeout=args.timeout,
            )
    elif args.run == "phc2sys":
        # Time sync with phc2sys
        with clear_qdisc_settings_before_and_after(
            interface=args.interfaces[0]
        ):
            time_sync_phc2sys(
                args.interfaces[0],
                cfg=args.client_config,
                timeout=args.timeout,
            )
    elif args.run == "time_based_shaper":
        # Time based shaper
        with clear_qdisc_settings_before_and_after(
            interface=args.interfaces[0]
        ):
            time_based_shaper(
                interface=args.interfaces[0],
                timeout=args.timeout,
            )
    elif args.run == "credit_based_shaper":
        # Credit based shaper
        with clear_qdisc_settings_before_and_after(
            interface=args.interfaces[0]
        ):
            credit_based_shaper(
                interface=args.interfaces[0],
                server_ip=args.server_ip,
                timeout=args.timeout,
            )
    elif args.run == "traffic_scheduling":
        # Traffic scheduling
        if args.all_interfaces is None:
            other_interfaces = []
        else:
            other_interfaces = args.all_interfaces.split()
            other_interfaces.remove(args.interfaces[0])
        with clear_qdisc_settings_before_and_after(
            interface=args.interfaces[0]
        ):
            traffic_scheduling(
                interface=args.interfaces[0],
                server_ip=args.server_ip,
                cfg=args.client_config,
                timeout=args.timeout,
            )


if __name__ == "__main__":
    main()
