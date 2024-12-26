#!/usr/bin/env python3
"""
    This script base on network-manager. And network-manager has it own
    limitation about wifi ap mode and wifi-p2p.
    For wifi ap mode:
        Only band a and bg are supported

    For wifi-p2p:
        We are not able to validate the result even following the user
        manual of network-manager.

    Please refer to following for more details:
    [1] https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html
    [2] https://netplan.readthedocs.io/en/stable/netplan-yaml
    [3] https://bugs.launchpad.net/carmel/+bug/2080353/comments/2

"""
import argparse
import subprocess
import sys
import time
import logging
import re
import random
import string
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class WiFiManager:
    def __init__(self, **kwargs):
        """
        Initialize the WiFiManager with dynamic arguments.
        kwargs: Dictionary of configuration arguments.
        """
        self._command = "nmcli"
        self.interface = kwargs.get("interface")
        self.type = kwargs.get("type")
        self.mode = kwargs.get("mode")
        self.band = kwargs.get("band")
        self.channel = kwargs.get("channel")
        self.key_mgmt = kwargs.get("keymgmt")
        self.group = kwargs.get("group")
        self.peer = kwargs.get("peer")
        self.ssid = kwargs.get("ssid")
        self.ssid_pwd = kwargs.get("ssid_pwd")
        self.conname = "qa-test-ap"

    def init_conn(self):
        logging.info("Initializing connection")
        if self.type == "wifi":
            run_command(
                "{} c add type {} ifname {} con-name {} "
                "autoconnect no wifi.ssid {} "
                "wifi.mode {} ipv4.method shared".format(
                    self._command,
                    self.type,
                    self.interface,
                    self.conname,
                    self.ssid,
                    self.mode,
                )
            )
            self.set_band_channel()
            if self.key_mgmt:
                self.set_secured()
        elif self.type == "wifi-p2p":
            run_command(
                "{} c add type {} ifname {} con-name {} "
                "wifi-p2p.peer {}".format(
                    self._command,
                    self.type,
                    self.interface,
                    self.conname,
                    self.peer,
                )
            )
        else:
            raise ValueError("Unsupported type: {}".format(self.type))

    def set_band_channel(self):
        """
        Set band, channel and channel-width.
        If channel and channel-width in 0, run command with setting band only.
        """
        cmd = "{} c modify {} wifi.band {} ".format(
            self._command, self.conname, self.band
        )
        if self.channel:
            cmd += "wifi.channel {} ".format(self.channel)
        run_command(cmd)

    def set_secured(self):
        run_command(
            "{} c modify {} wifi-sec.key-mgmt {} wifi-sec.psk {} "
            "wifi-sec.group {}".format(
                self._command,
                self.conname,
                self.key_mgmt,
                self.ssid_pwd,
                self.group,
            )
        )

    def get_ip_addr(self):
        """
        nmcli -g IP4.ADDRESS command will return the IPv4 address of the
        interface with netmask.
        e.g. 10.102.99.224/22
        """
        ip_addr = run_command(
            "{} -g IP4.ADDRESS device show {}".format(
                self._command,
                self.interface,
            )
        )
        ip_addr = ip_addr.split("/")[0] if ip_addr.find("/") != -1 else ""
        return ip_addr

    def up_cmd(self):
        return "{} c up {}".format(self._command, self.conname)

    def up_conn(self):
        try:
            run_command(self.up_cmd())
            logging.info("Initialized connection successful!")
        except Exception:
            raise SystemError("Bring up connection failed!")
        for i in range(1, 6):
            try:
                ip_addr = self.get_ip_addr()
                if ip_addr:
                    logging.info("IP address is {}".format(ip_addr))
                    return True
            except subprocess.CalledProcessError:
                pass
            time.sleep(5)
        return False

    def del_cmd(self):
        return "{} c delete {}".format(self._command, self.conname)

    def connect_dut_cmd(self, host_if):
        connect_cmd = (
            "{} con add type wifi ifname {} con-name {} ssid {}".format(
                self._command, host_if, self.conname, self.ssid
            )
        )
        if self.key_mgmt:
            connect_cmd += " wifi-sec.key-mgmt {}" " wifi-sec.psk {}".format(
                self.key_mgmt, self.ssid_pwd
            )
        if self.mode == "adhoc":
            connect_cmd += " wifi.mode {}".format(self.mode)
        return connect_cmd

    def __enter__(self):
        self.init_conn()
        if not self.up_conn():
            raise RuntimeError("Connection initialization failed!")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info("Exiting context and cleaning up connection")
        cmd = self.del_cmd()
        run_command(cmd)


def run_command(command):
    logging.info("Run command: %s", command)
    output = subprocess.check_output(
        command, shell=True, text=True, stderr=subprocess.STDOUT
    )
    return output


def sshpass_cmd_gen(ip, user, pwd, cmd):
    return "sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} {}".format(
        pwd, user, ip, cmd
    )


def ping_cmd(ip):
    return "ping {} -c 4".format(ip)


@contextmanager
def connect_dut_from_host_via_wifi(host_net_info: dict, connect_info: dict):
    ip = host_net_info["ip"]
    user = host_net_info["user"]
    pwd = host_net_info["pwd"]
    ssid = connect_info["ssid"]
    connect_cmd = connect_info["connect_cmd"]
    del_host_conn = connect_info["delete_cmd"]
    up_host_conn = connect_info["up_cmd"]
    connected = False

    logging.info("Pinging target host first...")
    try:
        run_command(ping_cmd(ip))
        logging.info("Ping to target host %s successful.", ip)
    except Exception as e:
        raise SystemError("Unable to ping the HOST! Error: %s", str(e))
    try:
        connected = create_conn_from_host(ip, user, pwd, connect_cmd)
        if connected:
            if bring_up_conn_from_host(ip, user, pwd, up_host_conn):
                yield
    except Exception as e:
        raise SystemError(e)
    finally:
        if connected:
            try:
                run_command(sshpass_cmd_gen(ip, user, pwd, del_host_conn))
                logging.info("Deleted host connection successfully.")
            except Exception as e:
                raise SystemError(
                    "Failed to delete host connection: %s", str(e)
                )
        else:
            raise SystemError(
                "Unable to connect to DUT AP SSID %s after 10 attempts.", ssid
            )


def create_conn_from_host(ip, user, pwd, connect_cmd):
    logging.info("Attempting to create the connection configuration on HOST")
    try:
        run_command(sshpass_cmd_gen(ip, user, pwd, connect_cmd))
        logging.info("Create connection configuration successful!")
        return True
    except Exception as e:
        logging.warning(
            "Unable to create connection configuration on HOST. %s", str(e)
        )


def bring_up_conn_from_host(ip, user, pwd, up_host_conn):
    for i in range(1, 4):
        logging.info(
            "Attempting to bring up the connection on HOST (%d/%d)...", i, 3
        )
        try:
            run_command(sshpass_cmd_gen(ip, user, pwd, up_host_conn))
            logging.info("Bring up connection successful!")
            return True
        except Exception as e:
            logging.warning(
                "Unable to bring up connection on HOST. Attempt %d failed."
                " Error: %s",
                i,
                str(e),
            )
            time.sleep(10)


def ping_test(target_ip, host_net_info: dict):
    ip = host_net_info["ip"]
    user = host_net_info["user"]
    pwd = host_net_info["pwd"]
    try:
        logging.info("Attempting to ping DUT...")
        ping_result = run_command(
            sshpass_cmd_gen(ip, user, pwd, ping_cmd(target_ip))
        )

        packet_loss_match = re.search(r"(\d+)% packet loss", ping_result)
        if packet_loss_match:
            packet_loss = packet_loss_match.group(1)
            logging.info("Packet loss: %s %%", packet_loss)
            if packet_loss == "0":
                logging.info("Ping DUT passed.")
                return 0
            else:
                logging.error(
                    "Ping DUT failed with %s %% packet loss!", packet_loss
                )
        else:
            logging.error("Could not parse packet loss from ping result.")

    except Exception as e:
        logging.error("An error occurred during ping_test: %s", str(e))
    return 1


def main():
    parser = argparse.ArgumentParser(description="WiFi test")
    subparsers = parser.add_subparsers(
        dest="type",
        required=True,
        help="Type of connection. " 'Currentlly support "wifi" and "wifi-p2p"',
    )
    # Subparser for 'wifi'
    wifi_parser = subparsers.add_parser("wifi", help="WiFi configuration")
    wifi_parser.add_argument(
        "--mode",
        choices=["ap", "adhoc"],
        required=True,
        help="WiFi mode: ap or adhoc",
    )
    wifi_parser.add_argument("--band", required=True, help="WiFi band to use")
    wifi_parser.add_argument(
        "--channel", required=True, type=int, help="WiFi channel to use"
    )
    wifi_parser.add_argument(
        "--keymgmt", required=False, help="Key management method"
    )
    wifi_parser.add_argument(
        "--group", required=False, help="Group key management method"
    )
    wifi_parser.add_argument(
        "--ssid",
        default="".join(
            [random.choice(string.ascii_letters) for _ in range(10)]
        ),
        required=False,
        help="SSID for AP mode",
    )
    wifi_parser.add_argument(
        "--ssid-pwd",
        required=False,
        default="insecure",
        help="Password for SSID",
    )

    # Subparser for 'wifi-p2p'
    wifi_p2p_parser = subparsers.add_parser(
        "wifi-p2p", help="WiFi P2P configuration"
    )
    wifi_p2p_parser.add_argument(
        "--peer", required=True, help="MAC address for P2P peer"
    )
    parser.add_argument(
        "--interface", required=True, help="WiFi interface to use"
    )
    parser.add_argument(
        "--host-ip",
        required=True,
        help="IP address of the Host device to connect to."
        "The HOST is a device to access the DUT's AP.",
    )
    parser.add_argument(
        "--host-user",
        required=True,
        help="Username of the Host device for SSH connection",
    )
    parser.add_argument(
        "--host-pwd",
        required=True,
        help="Password of the Host device for SSH connection",
    )
    parser.add_argument(
        "--host-interface",
        required=True,
        help="The wifi interface name of the Host device",
    )

    args = parser.parse_args()
    config = vars(args)
    try:
        with WiFiManager(**config) as manager:
            host_net_info = {
                "ip": args.host_ip,
                "user": args.host_user,
                "pwd": args.host_pwd,
            }
            connect_info = {
                "ssid": args.ssid,
                "connect_cmd": manager.connect_dut_cmd(args.host_interface),
                "delete_cmd": manager.del_cmd(),
                "up_cmd": manager.up_cmd(),
            }
            with connect_dut_from_host_via_wifi(host_net_info, connect_info):
                ret = ping_test(manager.get_ip_addr(), host_net_info)
        sys.exit(ret)
    except SystemError as e:
        logging.error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
