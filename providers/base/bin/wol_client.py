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
from urllib3.util import Retry
from requests import Session
from requests.adapters import HTTPAdapter
import requests
import argparse
import netifaces
import subprocess
import sys
import time


def request(method, url, retry=3, **kwargs):
    """Constructs and sends a :class:`Request <Request>`.
    Args:
        method (str):
            method for the new :class:`Request` object:
                `GET`, `OPTIONS`, `HEAD`, `POST`,
                `PUT`, `PATCH`, or `DELETE`.
        url (str): URL for the new :class:`Request` object.
        retry (int, optional):
            The maximum number of retries each connection should attempt.
            Defaults to 3.
    Returns:
        requests.Response: requests.Response
    """
    retries = Retry(total=retry)

    with Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.mount("http://", HTTPAdapter(max_retries=retries))
        logging.info("Send {} request to {}".format(method, url))
        logging.debug("Request parameter: {}".format(kwargs))

        resp = session.request(method=method, url=url, **kwargs)
        logging.debug(resp.text)
        return resp


def post(url, data=None, json=None, retry=3, **kwargs):
    """Sends a POST request
    Args:
        url (str): URL for the new :class:`Request` object.
        data (dict|list|bytes, optional):
            Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
            Defaults to None.
        json (json, optional):
            A JSON serializable Python object to send in
                the body of the :class:`Request`.
            Defaults to None.
        retry (int, optional):
            The maximum number of retries each connection should attempt.
            Defaults to 3.
    Returns:
        requests.Response: requests.Response
    """
    return request("post", url, data=data, json=json, retry=retry, **kwargs)


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
    except Exception as e:
        raise e


def get_ip_mac(interface):
    try:
        # get the mac address
        mac_a = netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]["addr"]

        # get the ip address
        ip_info = netifaces.ifaddresses(interface).get(netifaces.AF_INET)

        ip_a = ip_info[0]["addr"] if ip_info else None
        return ip_a, mac_a

    except ValueError as e:
        raise SystemExit("Error: {}".format(e))


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
    # wakeup_enabled = False
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

    try:
        # send the request to wol server
        resp = post(url, json=req, retry=3)
        result_dict = resp.json()
    except requests.exceptions.RequestException as e:
        raise SystemExit("Request error: {}".format(e))

    if resp.status_code != 200 or result_dict["result"] != "success":
        raise SystemExit(
            "get the wrong response: {}".format(result_dict["result"])
        )

    # bring up the system. The time should be delay*retry*2
    bring_up_system("rtc", delay * retry * 2)
    logging.debug(
        "set the rtcwake time: {} seconds ".format(delay * retry * 2)
    )

    # write the time stamp
    write_timestamp(args.timestamp_file)

    # s3 or s5 the system
    s3_or_s5_system(args.powertype)


if __name__ == "__main__":
    main()
