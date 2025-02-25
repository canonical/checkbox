#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Eugene Wu <eugene.wu@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import logging
import urllib
import urllib.request
import argparse
import subprocess
import sys
import time
import json
import socket
import fcntl
import struct


def send_request_to_wol_server(url, data=None, retry=3):
    # Convert data to JSON format
    data_encoded = json.dumps(data).encode("utf-8")

    # Construct request
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data_encoded, headers=headers)

    attempts = 0
    while attempts < retry:
        try:
            with urllib.request.urlopen(req) as response:
                logging.info("in the urllib request.")
                response_data = json.loads(response.read().decode("utf-8"))
                logging.debug(
                    "Response message: {}".format(response_data["message"])
                )
                status_code = response.status
                logging.debug("Status code: {}".format(status_code))
                if status_code == 200:
                    logging.info(
                        "Send request to Wake-on-lan server successful."
                    )
                    return
                else:
                    logging.error(
                        "Failded to send request to Wkae-on-lan server."
                    )
        except Exception as e:
            logging.error("An unexpected error occurred: {}".format(e))

        attempts += 1
        time.sleep(1)  # Wait for a second before retrying
        logging.debug("Retrying... ({}/{})".format(attempts, retry))

    raise SystemExit(
        "Failed to send request to WOL server. "
        "Please ensure the WOL server setup correctlly."
    )


def check_wakeup(interface):
    wakeup_file = "/sys/class/net/{}/device/power/wakeup".format(interface)
    try:
        with open(wakeup_file, "r") as f:
            wakeup_status = f.read().strip()

        logging.info(
            "Wakeup status for {}: {}".format(interface, wakeup_status)
        )

        if wakeup_status == "enabled":
            return True
        elif wakeup_status == "disabled":
            return False
        else:
            raise ValueError(
                "Unexpected wakeup status: {}".format(wakeup_status)
            )

    except FileNotFoundError:
        raise FileNotFoundError(
            "The network interface {} does not exist.".format(interface)
        )


def __get_ip_address(interface):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip_addr = fcntl.ioctl(
            s.fileno(),
            0x8915,
            struct.pack("256s", interface[:15].encode("utf-8")),
        )
        return socket.inet_ntoa(ip_addr[20:24])
    except IOError:
        return None


def __get_mac_address(interface):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mac_addr = fcntl.ioctl(
            s.fileno(),
            0x8927,
            struct.pack("256s", interface[:15].encode("utf-8")),
        )
        return ":".join("%02x" % b for b in mac_addr[18:24])
    except IOError:
        raise SystemExit("Error: Unable to retrieve MAC address")


def get_ip_mac(interface):
    ip_a = __get_ip_address(interface)
    mac_a = __get_mac_address(interface)

    return ip_a, mac_a


# set the rtc wake time to bring up system in case the wake-on-lan failed
def set_rtc_wake(wake_time):
    """
    Set the RTC (Real-Time Clock) to wake the system after a specified time.
    Parameters:
       wake_time (int): The time to wake up the system once wake on lan failed.
    """
    command = ["rtcwake", "-m", "no", "-s", str(wake_time)]

    try:
        subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "Failed to set RTC wake: {}".format(e.output.decode().strip())
        )
    except Exception as e:
        raise SystemExit("An unexpected error occurred: {}".format(e))


# try to suspend(s3) or power off(s5) the system
def s3_or_s5_system(type):
    """
    Suspends or powers off the system using systemctl.
    Args:
        type: String, either "s3" for suspend or "s5" for poweroff.
    Raises:
        RuntimeError: If the type is invalid or the command fails.
    """
    commands = {
        "s3": ["systemctl", "suspend"],
        "s5": ["systemctl", "poweroff"],
    }

    if type not in commands:
        raise RuntimeError(
            "Error: type should be s3 or s5(provided: {})".format(type)
        )

    try:
        subprocess.check_output(commands[type], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Try to enter {} failed: {}".format(type, e))


# bring up the system by rtc or any other ways in case the wake-on-lan failed
def bring_up_system(way, time):
    # try to wake up the system by rtc
    if way == "rtc":
        set_rtc_wake(time)
        logging.debug("set the rtcwake time: {} seconds ".format(time))
    else:
        # try to wake up the system other than RTC which not support
        raise SystemExit(
            "we don't have the way {} to bring up the system,"
            "Some error happened.".format(way)
        )


# write the time stamp to a file to record the test start time
def write_timestamp(timestamp_file):
    with open(timestamp_file, "w") as f:
        f.write(str(time.time()))
        f.flush()


def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description="Parse command line arguments."
    )

    parser.add_argument(
        "--interface", required=True, help="The network interface to use."
    )
    parser.add_argument(
        "--target", required=True, help="The target IP address or hostname."
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=60,
        help="Delay between attempts (in seconds).",
    )
    parser.add_argument(
        "--retry", type=int, default=3, help="Number of retry attempts."
    )
    parser.add_argument(
        "--waketype",
        default="g",
        help="Type of wake operation.eg 'g' for magic packet",
    )
    parser.add_argument("--powertype", type=str, help="Type of s3 or s5.")
    parser.add_argument(
        "--timestamp_file",
        type=str,
        help="The file to store the timestamp of test start.",
    )

    return parser.parse_args(args)


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format="%(levelname)s: %(message)s",
    )

    logging.info("wake-on-LAN test started.")
    logging.info("Test network interface: {}".format(args.interface))

    wakeup_enabled = check_wakeup(args.interface)
    if not wakeup_enabled:
        raise SystemExit(
            "wake-on-LAN of {} is disabled!".format(args.interface)
        )

    delay = args.delay
    retry = args.retry

    ip, mac = get_ip_mac(args.interface)

    logging.info("IP: {}, MAC: {}".format(ip, mac))

    if ip is None:
        raise SystemExit("Error: failed to get the ip address.")

    url = "http://{}".format(args.target)
    req = {
        "DUT_MAC": mac,
        "DUT_IP": ip,
        "delay": args.delay,
        "retry_times": args.retry,
        "wake_type": args.waketype,
    }

    send_request_to_wol_server(url, data=req, retry=3)

    bring_up_system("rtc", delay * retry * 2)

    # write the time stamp
    write_timestamp(args.timestamp_file)

    # s3 or s5 the system
    s3_or_s5_system(args.powertype)


if __name__ == "__main__":
    main()
