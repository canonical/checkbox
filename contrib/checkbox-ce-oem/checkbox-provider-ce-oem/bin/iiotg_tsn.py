#!/usr/bin/env python3

import argparse
import re
import shlex
import subprocess
import sys
import time
from collections import deque
from contextlib import contextmanager
from ipaddress import ip_address
from pathlib import Path
from threading import Event


def clear_qdisc_settings(interface: str) -> None:
    """Clear the previous qdisc settings.

    This function clears the previous qdisc settings by running the tc
    command with the 'qdisc del' option.

    Args:
        interface (str): The name of the network interface.

    Returns:
        None
    """
    # Build the tc command to delete the root qdisc settings

    # Run the tc command with a timeout of 1 second
    subprocess.run(
        ["tc", "qdisc", "del", "dev", interface, "root"],
        capture_output=True,
        timeout=1,
        check=False,  # cleaning nonexistent setting will return 2
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


def ptp4l(
    interface: str,
    cfg: "Path | None" = None,
    timeout: int = 0,
    server_mode: bool = False,
    print_to_console: bool = False,
) -> "subprocess.Popen[str]":
    """Spawn a ptp4l process

    Args:
        interface (str): The interface to set the clock on.
        cfg (str): The path to the configuration file.
        timeout (int): The time to wait for the command to complete, \
            in seconds.

    Returns:
        subprocess.Popen: A process object representing \
        the running ptp4l command.
    """

    # Run the ptp4l command with the provided parameters.
    # The command is run with stdout and stderr redirected to pipes.
    # Text mode is enabled to allow access to the output as text.

    if cfg:
        print("Using ptp4l config file at", cfg, flush=True)
        process = subprocess.Popen(
            # caller is responsible for making sure config file is valid
            # i.e. options are recognized by ptp4l
            [
                "timeout",
                str(timeout),
                "ptp4l",
                "-i",
                interface,
                "-f",
                cfg,
                "-m",
            ],
            stdout=None if print_to_console else subprocess.PIPE,
            stderr=None if print_to_console else subprocess.PIPE,
            text=True,
        )
    else:
        # convenience path, you don't have to have a config file to run tests
        # this should work on most intel platforms even without rt kernel
        default_cmd = [
            "timeout",
            str(timeout),
            "ptp4l",
            "-i",
            interface,
            "-m",  # print msg to stdout
            # anycast, allows auto server discovery
            "--network_transport=L2",
            "--tx_timestamp_timeout=5",
            # comes from the default config
            # both server and client needs to have this
            # /usr/share/doc/linuxptp/configs/automotive-slave.cfg
            "--transportSpecific=1",
        ]
        if not server_mode:
            # client only mode
            default_cmd.append("-s")
            # force 'master offset' output to appear in stdout
            default_cmd.append("--summary_interval=-4")
        else:
            default_cmd.extend(
                # print more logs basically
                ["--logAnnounceInterval=0", "--logSyncInterval=-3"]
            )
            # print a warning message that we are using --transportSpecific=1
            # clients must also specify --transportSpecific=1
            # or their packets will be dropped silently
            print("=" * 80)
            print(
                "Launching default ptp4l grandmaster",
                "with --transportSpecific=1",
            )
            print(
                "All clients must also specify --transportSpecific=1",
                "to prevent their packets from being dropped",
            )
            print(
                "You can override this by specifying a config file.",
                "See /usr/share/doc/linuxptp/configs/automotive-master.cfg",
                "for an example",
            )
            print("=" * 80)

        process = subprocess.Popen(
            default_cmd,
            stdout=None if print_to_console else subprocess.PIPE,
            stderr=None if print_to_console else subprocess.PIPE,
            text=True,
        )

    # caller decides how to consume stdout and stderr
    return process


def phc2sys(interface: str, timeout: int = 60) -> "subprocess.Popen[str]":
    """Run phc2sys command to sync system clock to physical hardware clock.

    Args:
        interface (str): The network interface to sync.
        timeout (int): The time to wait for the command to complete,
        in seconds. Defaults to 60 seconds.

    Returns:
        subprocess.Popen: A process object representing the
        running phc2sys command.
    """

    process = subprocess.Popen(
        [
            "timeout",
            str(timeout),
            "phc2sys",
            "-s",  # the interface to sync
            interface,
            "-O",  # -O 0 sets the offset between system clock
            "0",  # and physical hardware clock to 0
            "-c",  # client clock source is CLOCK_REALTIME
            "CLOCK_REALTIME",
            "-w",  # wait for ptp4l to be ready
            "-m",  # print the messages to stdout
            "--step_threshold=1",
            "--transportSpecific=1",  # see ptp4l()
        ],
        stdout=subprocess.PIPE,  # Redirect stdout to a pipe.
        stderr=subprocess.PIPE,  # Redirect stderr to a pipe.
        text=True,  # Enable text mode, so output can be accessed as text.
    )

    # Return the process object representing the running phc2sys command.
    return process


def server_mode(
    interfaces: "list[str]",
    cfg: "Path | None" = None,
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

    processes = []  # type: list[subprocess.Popen[str]]

    # Iterate over each interface and run ptp4l as master
    for interface in interfaces:
        # Clear qdisc settings for the interface
        clear_qdisc_settings(interface=interface)

        # Run ptp4l as master with the provided interface and configuration
        process = ptp4l(interface=interface, cfg=cfg, server_mode=True)
        processes.append(process)
        print(f"Start running ptp4l on {interface} as grandmaster")

        # Get the IP address of the interface
        ip = get_interface_ip(interface)

        # Run iperf3 as a server in each port specified and each CPU
        for port, cpu in zip(range(5201, 5204), range(1, 4)):
            # Run iperf3 server
            process = subprocess.Popen(
                ["iperf3", "-s", "-B", ip, "-p", str(port), "-A", str(cpu)],
                text=True,
            )
            processes.append(process)

        # Wait for 0.5 seconds before printing the separator
        time.sleep(0.5)

        # Print separator line
        print("===========================================================")

    print("Press ctrl + c to stop the server")

    try:
        # Wait for KeyboardInterrupt
        Event().wait()
    except KeyboardInterrupt:
        # Terminate all running ptp4l processes
        for process in processes:
            process.terminate()
        print("Terminated all ptp4l and iperf3 process")


def time_sync_ptp4l(
    interface: str,
    cfg: "Path | None" = None,
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
        [PASS] Master offset is between -100 to 100: If the master offset is
            between -100 and 100.
        [FAIL] Master offset is not between -100 to 100: If the master offset
            is not between -100 and 100.
    """
    if timeout < 30:
        raise SystemExit(
            "[ERROR] timeout should be at least 30 seconds "
            + f"for a successful time sync (got {timeout})"
        )
    # Run ptp4l as a subprocess and get its output
    process = ptp4l(interface=interface, cfg=cfg, timeout=timeout)
    # discard the ones already printed to stdout
    last_10_lines = deque(maxlen=10)  # type: deque[str]

    # they should be io.TextIO objects
    assert process.stdout and process.stderr
    for raw_line in process.stdout:
        line = str(raw_line).strip()
        print(line, flush=True)
        last_10_lines.append(line)

    process.wait()

    stderr = str(process.stderr.read()).strip()
    if stderr:
        # a successful & clean run of ptp4l shows no errors
        # NOTE: if the error mentions deleting files in /var/run
        # NOTE: that means a previous ptp4l run was force killed / crashed
        # NOTE: re-run the test and those lines won't appear
        print("Standard Error (stderr):", file=sys.stderr)
        print(stderr, file=sys.stderr)
        raise SystemExit(
            f"[Error] Caught error while running ptp4l on {interface}"
        )

    # now we check the last 10 lines of ptp4l's output
    # a successful output looks like this:
    #
    # ptp4l[11408.871]: master offset -5 s2 freq +7652 path delay 12
    #
    # we want to check the master_offset = -5 value from that line
    # if abs(master_offset) < 100, then the test passes
    # a failed run usually has very large numbers instead of -5
    for line in last_10_lines:
        try:
            master_offset = int(line.split()[3])
            if not -100 < master_offset < 100:
                raise SystemExit(
                    "[FAIL] Master offset is not between -100 to 100"
                )
        except ValueError:
            # print the entire line before raising
            # or we get a cryptic "'as' cannot be converted to int" message
            print(
                "Failed to parse offset int from line:", line, file=sys.stderr
            )
            raise  # now we print the actual call trace

    # If the master offset is between -100 and 100, print a success message
    print("[PASS] Master offset is between -100 to 100")


def time_sync_phc2sys(
    interface: str,
    cfg: "Path | None" = None,
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
            + f"for a successful time sync (got {timeout})"
        )

    # the timeout will cleanup the process for us
    # so we don't have to explicitly call Process.terminate()
    ptp4l(interface=interface, cfg=cfg, timeout=timeout, print_to_console=True)

    phc2sys_proc = phc2sys(interface=interface, timeout=timeout)
    last_10_lines = deque(maxlen=10)  # type: deque[str]
    assert phc2sys_proc.stdout and phc2sys_proc.stderr

    for raw_line in phc2sys_proc.stdout:
        line = str(raw_line).strip()
        print(line, flush=True)
        last_10_lines.append(line)

    phc2sys_proc.wait()

    stderr = str(phc2sys_proc.stderr.read()).strip()
    if stderr:
        print("Standard Error (stderr):", file=sys.stderr)
        print(stderr, file=sys.stderr)
        raise SystemExit(
            f"[Error] Caught error while running phc2sys on {interface}"
        )

    for line in last_10_lines:
        offset = int(line.split()[4])
        state = line.split()[5]
        delay = int(line.split()[9])

        if not -100 < offset < 100:
            print("[FAIL] phc offset is not between -100 to 100")
            raise SystemExit(1)

        if state != "s2":
            raise SystemExit(
                "[FAIL] state is not equal to s2 for the last 10 seconds\n"
                + "s0: unsynced\n"
                + "s1: syncing\n"
                + "s2: synced"
            )

        if delay != 0:
            raise SystemExit(
                "[FAIL] path delay is not equal to 0\n"
                + "path delay should be 0 if using hardware cross timestamping"
            )

    print("[PASS] Synced system time to physical hardware clock successfully")


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
    # https://man7.org/linux/man-pages/man8/tc-mqprio.8.html
    cmd = (
        # create a new Queueing Discipline at <interface> with handle 8001:
        ["tc", "qdisc", "add", "dev", interface, "handle", "8001:"]
        # attach this Discipline to the root
        # use the multi queue priority scheme (mqprio)
        # and create 4 unique traffic classes
        + ["parent", "root", "mqprio", "num_tc", "4"]
        + [
            "map",  # assign each of the 16 prio bands to the traffic classes
            "0",  # band 0 to class 0
            "1",  # band 1 to class 1
            "2",  # band 2 to class 2
            *(["3"] * (16 - 3)),  # dump all remaining bands to class 3
        ]
        # all traffic classes start with exactly 1 queue
        + ["queues", "1@0", "1@1", "1@2", "1@3"]
        # disable hw offloading
        + ["hw", "0"]
    )
    subprocess.run(cmd, timeout=1, check=False)

    # configure Earliest TxTime First
    # https://man7.org/linux/man-pages/man8/tc-etf.8.html
    cmd = (
        # Replace parent qdisc with etf offload
        ["tc", "qdisc", "replace", "dev", interface]
        # specifically, replace the 4th queue
        + ["parent", "8001:4"]
        + ["etf", "offload", "clockid", "CLOCK_TAI", "delta", "500000"]
    )
    subprocess.run(cmd, timeout=1, check=False)

    # show the current qdisc settings
    subprocess.run(
        ["tc", "qdisc", "show", "dev", interface], timeout=1, check=False
    )

    # spawn udp_tai. To get this command, compile from
    # https://gist.github.com/tomli380576/73529ee1449106eaa7d289ef0253c9ed
    process_udp_tai = subprocess.Popen(
        ["udp_tai", "-c", "3", "-i", interface]
        + ["-P", "1000000", "-p", "90", "-d", "600000"],
        stdout=subprocess.PIPE,
        text=True,
    )

    # capture packets with tcpdump and
    # check that they are within the required time interval
    cmd = [
        "tcpdump",
        "-G",  # rotate output file every <timeout> seconds
        str(timeout),  # since we write to stdout, tcpdump stops after 10s
        "-Q",
        "out",  # only check outgoing packets
        "-ttt",  # print time delta for each packet
        "-ni",  # do not resolve ip
        interface,  # and listen on this interface
        "--time-stamp-precision=nano",
        "-j",  # specify timestamp type
        "adapter_unsynced",
        "port",  # check this port only
        "7788",
        "-c",  # stop after this many packets
        str(timeout * 1000),
    ]
    tcp_dump_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    try:
        stdout, stderr = tcp_dump_proc.communicate(timeout=timeout * 2)
    except subprocess.TimeoutExpired:
        tcp_dump_proc.kill()
        raise SystemExit(f"Reached timeout {timeout * 2}s")
    finally:
        process_udp_tai.kill()

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
                f"[ERROR] Cannot find the time in the line: {line}"
            )
        if not 999500 < time < 1000500:
            cnt += 1

    # If there are more than 5% packets not within the required time interval,
    # raise a SystemExit exception
    if cnt > timeout * 1000 * 0.05:
        raise SystemExit(
            f"[FAIL] There are {cnt}/{timeout * 1000} (more than 5%) packets "
            + "not within the required time interval (999500 - 1000500)"
        )

    print(
        "[PASS] There are",
        f"{cnt}/{timeout * 1000}",
        "packets (less than 5%) within",
        "the required time interval (999500 - 1000500)",
    )


def credit_based_shaper(
    interface: str, server_ip: str, timeout: int = 10
) -> None:
    """
    Setup a credit-based shaper on the specified interface.

    Args:
        interface (str): The interface to set the shaper on.
        server_ip (str): The IP address of the server to send traffic to.
        timeout (int): The timeout for the shaper in seconds.
    """
    # quick sanity check and make sure server is reachable
    print(
        "Make sure we can reach the iperf sever at",
        server_ip,
        "through interface",
        interface,
    )
    subprocess.run(["ping", "-I", interface, "-c", "5", server_ip], check=True)

    # this is mostly the same as time based shaper
    # except it uses a different handle
    # https://man7.org/linux/man-pages/man8/tc-mqprio.8.html
    cmd = (
        # create a new Queueing Discipline at <interface> with handle 8001:
        ["tc", "qdisc", "add", "dev", interface, "handle", "100:"]
        # attach this Discipline to the root
        # use the multi queue priority scheme (mqprio)
        # and create 4 unique traffic classes
        + ["parent", "root", "mqprio", "num_tc", "4"]
        + [
            "map",  # assign each of the 16 prio bands to the traffic classes
            "0",  # band 0 to class 0
            "1",  # band 1 to class 1
            "2",  # band 2 to class 2
            *(["3"] * (16 - 3)),  # dump all remaining bands to class 3
        ]
        # all traffic classes start with exactly 1 queue
        + ["queues", "1@0", "1@1", "1@2", "1@3"]
        # disable hw offloading
        + ["hw", "0"]
    )
    subprocess.run(cmd, timeout=1, check=False)

    # Show the current qdisc settings
    subprocess.run(
        ["tc", "-g", "class", "show", "dev", interface], timeout=1, check=False
    )

    # Wait for 5 seconds before replacing the parent qdisc with a credit-based
    # shaper (cbs) and configuring its parameters
    time.sleep(5)

    # Replace the parent qdisc (handle 100:) with a cbs (credit based shaper)
    # Set the low credit and high credit values
    # Set the send slope and idle slope values
    # Enable offload
    # cmd = (
    cmd = ["tc", "qdisc", "replace", "dev", interface, "parent", "100:1"] + [
        "cbs",  # configure credit based shaping (cbs)
        "locredit",  # min credit
        "-1350",
        "hicredit",  # max credit
        "150",
        "sendslope",
        "-900000",  # comes from idleslope - link_speed
        # NOTE: this value is picked specifically for 1Gbps ports
        "idleslope",
        "100000",  # reserve 100Mbps bandwidth
        "offload",
        "1",  # enable hardware offload
    ]

    subprocess.run(cmd, timeout=1, check=False)

    # Show the current qdisc settings
    subprocess.run(
        ["tc", "qdisc", "show", "dev", interface], timeout=1, check=False
    )

    # Wait for 5 seconds before running iperf3 to measure the upload speed
    time.sleep(5)

    # Run iperf3 client to measure the upload speed
    print(
        "Starting iperf3 client at",
        interface,
        "to measure upload speed",
        f"(will run for {timeout} seconds)",
        flush=True,
    )
    iperf_process = iperf3_client(
        server_ip, get_interface_ip(interface), timeout
    )
    assert iperf_process.stdout and iperf_process.stderr

    iperf_stdout_lines = deque(maxlen=10)  # type: deque[str]
    for raw_line in iperf_process.stdout:
        line = str(raw_line).strip()
        iperf_stdout_lines.append(line)
        print(line, flush=True)

    iperf_process.wait()
    iperf_stderr = str(iperf_process.stderr.read()).strip()
    # Check for errors in the iperf3 output
    if iperf_stderr:
        raise SystemExit(
            f"[ERROR] Found error while running iperf3:\n{iperf_stderr}"
        )

    # Parse the upload speed from the iperf3 output
    speed_bits = float(iperf_stdout_lines[-4].split()[6])

    # Check if the upload speed is between 90 and 100 Mbps
    if not 90 < speed_bits < 100:
        raise SystemExit(
            "[FAIL] The upload speed is not between 90 and 100 Mbps\n"
            + f"The upload speed is {speed_bits} Mbps"
        )

    # Print the upload speed and a success message
    print(
        "[PASS] The upload speed",
        speed_bits,
        "Mbps",
        "is between 90 and 100 Mbps!",
    )


def traffic_scheduling(
    interface: str,
    server_ip: str,
    cfg: "Path | None" = None,
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
        raise SystemExit(
            "Traffic scheduling timeout must be at least 25 seconds. "
            + f"(got {timeout})"
        )

    print(f"Running ptp4l on {interface}...", flush=True)
    ptp4l(interface, cfg, timeout, print_to_console=True)

    print(
        "Letting ptp4l sync for 10 seconds before starting the test",
        flush=True,
    )
    time.sleep(10)

    print("Setting qdisc...", flush=True)
    cmd = (
        f"tc qdisc add dev {interface} parent root handle 100 taprio "
        "num_tc 4 "
        "map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 "
        "queues 1@0 1@1 1@2 1@3 "
        "sched-entry S 01 5000000 "
        "sched-entry S 02 5000000 "
        "sched-entry S 04 5000000 "
        "sched-entry S 08 5000000 "
        "flags 0x2 "
        "txtime-delay 0"
    )
    result = subprocess.run(
        shlex.split(cmd),
        capture_output=True,
        timeout=1,
        check=True,
    )
    if result.returncode:
        raise SystemExit(
            "[ERROR] Found error while setting qdisc:\n"
            + result.stderr.decode()
        )
    time.sleep(5)

    print(
        "Setting which hardware transmit queue",
        "each iperf3 instance using via net_prio cgroups...",
        flush=True,
    )

    # Create and mount /sys/fs/cgroup/net_prio
    sys_fs_cgroup_net_prio = Path("/sys/fs/cgroup/net_prio")
    sys_fs_cgroup_net_prio.mkdir(exist_ok=True)
    mount_result = subprocess.run(
        [
            "mount",
            "-t",
            "cgroup",
            "-onet_prio",
            "none",
            str(sys_fs_cgroup_net_prio),
        ],
        timeout=1,
        check=False,
    )
    if mount_result.returncode not in (0, 32):
        # 32 means it's already mounted, explicitly ignore it
        # otherwise let check_returncode panic and print the err for us
        mount_result.check_returncode()

    # Create /sys/fs/cgroup/net_prio/grp{1,2,3} and write interface {1, 2, 3}
    for grp in range(1, 4):
        grp_path = sys_fs_cgroup_net_prio / f"grp{grp}"
        grp_path.mkdir(exist_ok=True)
        with (grp_path / "net_prio.ifpriomap").open("w") as f:
            # example: enp1s1 1
            f.write(f"{interface} {grp}")

    # Run iperf3 client
    for port, group in zip(range(5201, 5204), range(1, 4)):
        print(f"Running iperf3 client on port {port}...", flush=True)
        process = iperf3_client(
            server_ip,
            get_interface_ip(interface),
            timeout=timeout - 15,
            port=port,
        )
        pid = str(process.pid)
        file = sys_fs_cgroup_net_prio / f"grp{group}" / "cgroup.procs"
        print(
            f"Adding iperf3 process (port={port} pid={pid}) to {file}",
            flush=True,
        )
        with file.open("w") as f:
            f.write(pid)

    print("Showing qdisc settings after running iperf3...", flush=True)
    before = subprocess.run(
        ["tc", "-s", "qdisc", "show", "dev", interface],
        check=True,
        capture_output=True,
        text=True,
    )
    print(before.stdout, flush=True)
    pattern = r"Sent (\d+) bytes"
    bytes_before = re.findall(pattern, before.stdout)

    time.sleep(timeout - 15)

    print("After", timeout - 15, "seconds...", flush=True)
    after = subprocess.run(
        ["tc", "-s", "qdisc", "show", "dev", interface],
        check=True,
        capture_output=True,
        text=True,
    )
    print(after.stdout, flush=True)
    bytes_after = re.findall(pattern, before.stdout)

    # Exclude the first value because we only care about 100:1 ~ 100:4
    for before, after in zip(bytes_before[1:], bytes_after[1:]):
        # Need increasing bytes in every queue
        if int(after) - int(before) < 0:
            raise SystemExit(
                "[FAIL] Sent bytes is not increasing in every queue!\n"
                + "100:1 to 100:4"
            )
    print("[PASS] Sent bytes is increasing in every queue!")


def iperf3_client(
    server_ip: str,
    client_ip: str,
    timeout: int = 60,
    port: int = 5201,
    print_to_console: bool = False,
) -> "subprocess.Popen[str]":
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

    return subprocess.Popen(
        [
            "iperf3",
            "--client",  # run in client mode
            server_ip,  # connect to this server
            "--time",  # stop after <timeout> seconds
            str(timeout),
            "--bind",  # iperf should only listen on the port associated with..
            client_ip,  # this ip
            "--format",  # print the speed in
            "m",  # megabits
        ],
        stdout=None if print_to_console else subprocess.PIPE,
        stderr=None if print_to_console else subprocess.PIPE,
        text=True,
    )


def get_interface_ip(interface: str):
    result = subprocess.run(
        ["ip", "-4", "-o", "addr", "show", "dev", interface],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"Cannot find ip address for {interface}: {result.stderr.strip()}"
        )

    for line in result.stdout.splitlines():
        tokens = line.split()
        if "inet" in tokens:
            ip_with_prefix = tokens[tokens.index("inet") + 1]
            return ip_with_prefix.split("/")[0]

    raise SystemExit(f"Cannot find ip address for {interface}")


def parse_string(string: str):
    """It should be this format, INTERFACE1:SERVER_IP1,INTERFACE2:SERVER_IP2"""
    interface_ip_pairs = string.strip().split(",")
    if len(interface_ip_pairs) == 0:
        raise SystemExit(f"Found no INTERFACE:SERVER_IP pairs in '{string}'")

    for pair in interface_ip_pairs:
        words = pair.strip().split(":")
        if len(words) != 2:
            raise SystemExit(f"Expected INTERFACE:SERVER_IP, but got '{pair}'")
        interface, server_ip = words
        if not (Path("/sys/class/net/") / interface).exists():
            raise SystemExit(
                f"Parsed interface '{interface}', "
                + "but it doesn't exist under /sys/class/net"
            )
        # this will raise ValueError for us if addr invalid
        ip_address(server_ip)

        print("interface:", interface)
        print("server_ip:", server_ip)


def parse_args() -> argparse.Namespace:
    """
    we have 3 subcommands
    - server: this should be run on a peer dut
    - client: the actual TSN tests
    - validate-string: only used for the resource job,
        validates TSN_DEVICE_IP_LIST
    """
    parser = argparse.ArgumentParser(
        prog="TSN Testing Tool",
        description=(
            "This is a tool to help you test TSN (Time Sensitive Networking)"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser(
        "server",
        help="Spawn the TSN test server (ptp4l master and iperf3 servers)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    server_parser.add_argument(
        "--interfaces",
        "-i",
        nargs="+",
        required=True,
        help=(
            "TSN ethernet interfaces to serve. "
            "ptp4l will run on these interfaces."
        ),
    )
    server_parser.add_argument(
        "--master-config",
        type=str,
        help=(
            "Optional ptp4l config file for the server. "
            "This is directly passed to ptp4l."
        ),
    )

    client_parser = subparsers.add_parser(
        "client",
        help=(
            "Run a TSN test on the client. "
            "Specify a subcommand then -h to see usage."
        ),
    )
    client_subparsers = client_parser.add_subparsers(
        dest="test", required=True
    )

    # shared by every client test
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--interface",
        "-i",
        required=True,
        help="TSN ethernet interface to test",
    )
    common_parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=60,
        help="Timeout for the current test in seconds",
    )

    gptp_parser = argparse.ArgumentParser(
        add_help=False, parents=[common_parser]
    )
    gptp_parser.add_argument(
        "--client-config",
        type=str,
        help=(
            "Config file for client. "
            "They are passed to the corresponding test commands with -f <file>"
        ),
    )

    client_subparsers.add_parser(
        "ptp4l",
        parents=[gptp_parser],
        help="Time sync test with ptp4l",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    client_subparsers.add_parser(
        "phc2sys",
        parents=[gptp_parser],
        help="Time sync test with phc2sys",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    credit_based_shaper_parser = client_subparsers.add_parser(
        "credit-based-shaper",
        parents=[common_parser],
        help="Credit-Based Shaper test",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    credit_based_shaper_parser.add_argument(
        "--server-ip",
        type=str,
        required=True,
        help="Server IP address",
    )

    traffic_scheduling_parser = client_subparsers.add_parser(
        "traffic-scheduling",
        parents=[gptp_parser],
        help="Traffic scheduling test",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    traffic_scheduling_parser.add_argument(
        "--server-ip",
        type=str,
        required=True,
        help="Server IP address",
    )

    validate_parser = subparsers.add_parser(
        "validate-string",
        help="Validate an INTERFACE:SERVER_IP resource string",
    )
    validate_parser.add_argument(
        "string",
        type=str,
        help=(
            "The string to validate, format: "
            "INTERFACE1:SERVER_IP1,INTERFACE2:SERVER_IP2"
        ),
    )

    return parser.parse_args()


def run_client(args: argparse.Namespace) -> None:
    with clear_qdisc_settings_before_and_after(interface=args.interface):
        if args.test == "ptp4l":
            time_sync_ptp4l(
                args.interface,
                cfg=args.client_config,
                timeout=args.timeout,
            )
        elif args.test == "phc2sys":
            time_sync_phc2sys(
                args.interface,
                cfg=args.client_config,
                timeout=args.timeout,
            )
        elif args.test == "credit-based-shaper":
            credit_based_shaper(
                interface=args.interface,
                server_ip=args.server_ip,
                timeout=args.timeout,
            )
        elif args.test == "traffic-scheduling":
            traffic_scheduling(
                interface=args.interface,
                server_ip=args.server_ip,
                cfg=args.client_config,
                timeout=args.timeout,
            )


def main():
    args = parse_args()

    if args.command == "server":
        server_mode(args.interfaces, cfg=args.master_config)
    elif args.command == "client":
        run_client(args)
    elif args.command == "validate-string":
        parse_string(args.string)


if __name__ == "__main__":
    main()
