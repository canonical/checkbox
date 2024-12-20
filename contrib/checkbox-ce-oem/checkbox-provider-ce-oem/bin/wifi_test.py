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
        self.key_mgmt = kwargs.get("key_mgmt")
        self.group = kwargs.get("group")
        self.peer = kwargs.get("peer")
        self.ssid = kwargs.get("ssid", "qa-test-ssid")
        self.ssid_pwd = kwargs.get("ssid_pwd", "insecure")
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
            if self.key_mgmt is not None:
                self.set_secured()
        elif self.type == "wifi-p2p":
            run_command(
                "{} c add type {} ifname {} con-name {} \
                    wifi-p2p.peer {}".format(
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
            "{} c modify {} wifi-sec.key-mgmt {} wifi-sec.psk {}\
                  wifi-sec.group {}".format(
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

    def up_conn(self):
        try:
            run_command("{} c up {}".format(self._command, self.conname))
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

    def del_conn(self):
        run_command("{} c delete {}".format(self._command, self.conname))

    def connect_dut(self):
        connect_cmd = "{} d wifi c {}".format(self._command, self.ssid)
        if self.key_mgmt != "none":
            connect_cmd += " password {}".format(self.ssid_pwd)
        if self.mode == "adhoc":
            connect_cmd += " wifi.mode {}".format(self.mode)
        return connect_cmd

    def __enter__(self):
        self.init_conn()
        if not self.up_conn():
            raise RuntimeError("Connection initialization failed!")

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info("Exiting context and cleaning up connection")
        self.del_conn()


def run_command(command):
    logging.info("Run command: %s", command)
    output = subprocess.check_output(
        command, shell=True, stderr=subprocess.STDOUT
    )
    return output.decode()


def sshpass_cmd_gen(ip, user, pwd, cmd):
    return "sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} {}".format(
        pwd, user, ip, cmd
    )


def ping_cmd(ip):
    return "ping {} -c 4".format(ip)


def connect_host_device(manager, ip, user, pwd):
    connect_cmd = manager.connect_dut()
    ssid = manager.ssid
    logging.info("Ping target Host first ...")
    try:
        run_command(ping_cmd(ip))
        logging.info("Ping target Host %s successful...", ip)
        logging.info("Attempting to connect DUT AP %s...", ssid)
        for i in range(1, 11):
            logging.info("Attempting to connect DUT AP %s %d time...", ssid, i)
            try:
                run_command(sshpass_cmd_gen(ip, user, pwd, connect_cmd))
                logging.info("Connect successful!")
                return True
            except Exception:
                logging.warning("Not able to found SSID %s", ssid)
            time.sleep(10)
        logging.error("Not able to connect to DUT AP SSID %s", ssid)
    except Exception:
        logging.error("Not able to ping the HOST!")


def ping_test(manager, ip, user, pwd):
    try:
        logging.info("Attempting to ping DUT...")
        ping_result = run_command(
            sshpass_cmd_gen(ip, user, pwd, ping_cmd(manager.get_ip_addr()))
        )
        packet_loss = re.search(r"(\d+)% packet loss", ping_result).group(1)
        logging.info("Packet loss: %s %%", packet_loss)
        if packet_loss == "0":
            logging.info("Ping DUT pass")
            exit_code = 0
        else:
            logging.error("Ping DUT fail with %s %% packet loss!", packet_loss)
            exit_code = 1
    except Exception as e:
        logging.error("An error occurred during ping_test: %s", str(e))
        exit_code = 1
    finally:
        del_host_conn = "{} c delete {}".format(manager._command, manager.ssid)
        try:
            run_command(sshpass_cmd_gen(ip, user, pwd, del_host_conn))
            logging.info("Deleted host connection successfully.")
        except Exception as e:
            logging.error("Failed to delete host connection: %s", str(e))
        sys.exit(exit_code)


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
        "--ssid-pwd", required=False, help="Password for SSID"
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

    args = parser.parse_args()
    config = vars(args)
    manager = WiFiManager(**config)
    with manager:
        if connect_host_device(
            manager, args.host_ip, args.host_user, args.host_pwd
        ):
            ping_test(manager, args.host_ip, args.host_user, args.host_pwd)


if __name__ == "__main__":
    main()
