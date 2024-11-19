#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class WiFiManager:
    def __init__(
        self,
        interface,
        type,
        mode,
        band,
        channel,
        key_mgmt,
        group,
        peer,
        ssid,
        ssid_pwd,
    ):
        self._command = "nmcli"
        self.interface = interface
        self.type = type
        self.mode = mode
        self.band = band
        self.channel = channel
        self.key_mgmt = key_mgmt
        self.group = group
        self.ssid = ssid if ssid is not None else "qa-test-ssid"
        self.ssid_pwd = ssid_pwd if ssid_pwd is not None else "insecure"
        self.peer = peer
        self.conname = "qa-test-ap"

    def run_command(self, command):
        try:
            output = subprocess.check_output(
                command, shell=True, stderr=subprocess.STDOUT
            )
            return output.decode()
        except subprocess.CalledProcessError as e:
            logging.error("Command failed: %s", e.output.decode())
            raise

    def init_conn(self):
        logging.info("Initializing connection")
        if self.type == "wifi":
            self.run_command(
                "{} c add type {} ifname {} con-name {} \
                    autoconnect no wifi.ssid {} wifi.mode \
                    {} ipv4.method shared".format(
                    self._command,
                    self.type,
                    self.interface,
                    self.conname,
                    self.ssid,
                    self.mode,
                )
            )
        if self.type == "wifi-p2p":
            self.run_command(
                "{} c add type {} ifname {} con-name {} wifi-p2p.peer {}".format(
                    self._command,
                    self.type,
                    self.interface,
                    self.conname,
                    self.peer,
                )
            )

    def set_band_channel(self):
        self.run_command(
            "{} c modify {} wifi.band {} wifi.channel {}".format(
                self._command, self.conname, self.band, self.channel
            )
        )

    def set_secured(self):
        self.run_command(
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
        try:
            ip_addr = self.run_command(
                "{} -g IP4.ADDRESS device show {}".format(
                    self._command,
                    self.interface,
                )
            ).split("/")[0]
            return ip_addr
        except Exception:
            logging.warning("Not able to get IP address!")
            raise

    def up_conn(self):
        try:
            self.run_command("{} c up {}".format(self._command, self.conname))
            logging.info("Initialized connection successful!")
        except Exception:
            raise SystemError("Bring up connection failed!")
        for i in range(1, 6):
            try:
                ip_addr = self.get_ip_addr()
                if ip_addr:
                    logging.info("IP address is {}".format(ip_addr))
                    return True
            except Exception:
                pass
            time.sleep(5)
        return False

    def del_conn(self):
        self.run_command("{} c delete {}".format(self._command, self.conname))

    def __enter__(self):
        self.init_conn()
        if self.type == "wifi":
            self.set_band_channel()

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info("Exiting context and cleaning up connection")
        self.del_conn()


def sshpass_cmd_gen(ip, user, pwd, cmd):
    return "sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} {}".format(
        pwd, user, ip, cmd
    )


def ping_cmd(ip):
    return "ping {} -c 4".format(ip)


def connect_host_device(manager, ip, user, pwd):
    connect_cmd = "{} d wifi c {}".format(manager._command, manager.ssid)
    if manager.key_mgmt != "none":
        connect_cmd += " password {}".format(manager.ssid_pwd)
    if manager.mode == "adhoc":
        connect_cmd += " wifi.mode {}".format(manager.mode)
    logging.info("Ping target Host first ...")
    manager.run_command(ping_cmd(ip))
    logging.info("Ping target Host %s successful...", ip)
    logging.info("Attempting to connect DUT AP %s...", manager.ssid)
    for i in range(1, 11):
        logging.info(
            "Attempting to connect DUT AP %s %d time...", manager.ssid, i
        )
        try:
            manager.run_command(sshpass_cmd_gen(ip, user, pwd, connect_cmd))
            logging.info("Connect successful!")
            return True
        except Exception:
            logging.warning("Not able to found SSID {}".format(manager.ssid))
        time.sleep(10)
    logging.error("Not able to connect to DUT AP SSID {}".format(manager.ssid))
    sys.exit(1)


def ping_test(manager, ip, user, pwd):
    try:
        logging.info("Attempting to ping DUT...")
        ping_result = manager.run_command(
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
            manager.run_command(sshpass_cmd_gen(ip, user, pwd, del_host_conn))
            logging.info("Deleted host connection successfully.")
        except Exception as e:
            logging.error("Failed to delete host connection: %s", str(e))
        sys.exit(exit_code)


def main():
    parser = argparse.ArgumentParser(description="WiFi test")

    parser.add_argument(
        "--type", required=False, default="wifi", help="Connection type."
    )
    parser.add_argument(
        "--mode",
        choices=["ap", "adhoc"],
        required=False,
        help="WiFi mode: ap or adhoc",
    )
    parser.add_argument(
        "--interface", required=False, help="WiFi interface to use"
    )
    parser.add_argument("--band", required=False, help="WiFi band to use")
    parser.add_argument(
        "--channel", required=False, help="WiFi channel to use"
    )
    parser.add_argument(
        "--keymgmt", required=False, help="Key management method"
    )
    parser.add_argument(
        "--group", required=False, help="Group key management method"
    )
    parser.add_argument("--ssid", required=False, help="SSID for AP mode")
    parser.add_argument("--ssid-pwd", required=False, help="Password for SSID")
    parser.add_argument(
        "--peer", required=False, help="MAC address for p2p peer"
    )
    parser.add_argument(
        "--host-ip",
        required=False,
        help="IP address of the Host device to connect to"
        "The HOST is a device to access the DUT' AP.",
    )
    parser.add_argument(
        "--host-user",
        required=False,
        help="Username of the Host device for SSH connection",
    )
    parser.add_argument(
        "--host-pwd",
        required=False,
        help="Password of the Host device for SSH connection",
    )
    parser.add_argument(
        "--manual", action="store_true", help="Manual test (default is False)"
    )

    args = parser.parse_args()

    if not args.manual:
        if not args.host_ip or not args.host_user or not args.host_pwd:
            parser.error(
                "--host-ip, --host-user, and --host-pwd are required "
                "if not a manual test."
            )

    manager = WiFiManager(
        args.interface,
        args.type,
        args.mode,
        args.band,
        args.channel,
        args.keymgmt,
        args.group,
        args.peer,
        args.ssid,
        args.ssid_pwd,
    )
    with manager:
        if args.keymgmt is not None:
            manager.set_secured()
        if not manager.up_conn():
            raise RuntimeError("Connection initialization failed!")
        if not args.manual:
            connect_host_device(
                manager, args.host_ip, args.host_user, args.host_pwd
            )
            ping_test(manager, args.host_ip, args.host_user, args.host_pwd)
        else:
            input("Press Enter to exit after manual test finished...")


if __name__ == "__main__":
    main()
