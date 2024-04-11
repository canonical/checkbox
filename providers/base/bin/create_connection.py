#!/usr/bin/env python3

import sys
import os
import time

from subprocess import check_call, check_output, CalledProcessError

try:
    from subprocess import DEVNULL  # >= python3.3
except ImportError:
    DEVNULL = open(os.devnull, "wb")

from uuid import uuid4
from argparse import ArgumentParser

CONNECTIONS_PATH = "/etc/NetworkManager/system-connections/"


def wifi_connection_section(ssid, uuid):

    if not uuid:
        uuid = uuid4()

    connection = """
[connection]
id=%s
uuid=%s
type=802-11-wireless
    """ % (
        ssid,
        uuid,
    )

    wireless = """
[802-11-wireless]
ssid=%s
mode=infrastructure""" % (
        ssid
    )

    return connection + wireless


def wifi_security_section(security, key):
    # Add security field to 802-11-wireless section
    wireless_security = """
security=802-11-wireless-security

[802-11-wireless-security]
    """

    if security.lower() == "wpa":
        wireless_security += (
            """
key-mgmt=wpa-psk
auth-alg=open
psk=%s
        """
            % key
        )

    elif security.lower() == "wep":
        wireless_security += (
            """
key-mgmt=none
wep-key=%s
        """
            % key
        )

    return wireless_security


def wifi_ip_sections():
    ip = """
[ipv4]
method=auto

[ipv6]
method=auto
    """

    return ip


def mobilebroadband_connection_section(name, uuid, connection_type):
    if not uuid:
        uuid = uuid4()

    connection_section = """
[connection]
id={name}
uuid={uuid}
type={type}
autoconnect=false
    """.format(
        name=name, uuid=uuid, type=connection_type
    )

    return connection_section


def mobilebroadband_type_section(
    connection_type, apn, username, password, pin
):
    number = "*99#" if connection_type == "gsm" else "#777"
    type_section = """
[{type}]
number={number}
""".format(
        type=connection_type, number=number
    )

    if apn:
        type_section += "\napn={apn}".format(apn=apn)
    if username:
        type_section += "\nusername={username}".format(username=username)
    if password:
        type_section += "\npassword={password}".format(password=password)
    if pin:
        type_section += "\npin={pin}".format(pin=pin)

    return type_section


def mobilebroadband_ppp_section():
    return """
[ppp]
lcp-echo-interval=4
lcp-echo-failure=30
    """


def mobilebroadband_ip_section():
    return """
[ipv4]
method=auto
    """


def mobilebroadband_serial_section():
    return """
[serial]
baud=115200
    """


def block_until_created(connection, retries, interval):
    while retries > 0:
        try:
            nmcli_con_list = check_output(
                ["nmcli", "con", "list"],
                stderr=DEVNULL,
                universal_newlines=True,
            )
        except CalledProcessError:
            check_call(["nmcli", "con", "reload"])
            nmcli_con_list = check_output(
                ["nmcli", "con", "show"],
                stderr=DEVNULL,
                universal_newlines=True,
            )

        if connection in nmcli_con_list:
            print("Connection %s registered" % connection)
            break

        time.sleep(interval)
        retries = retries - 1

    if retries <= 0:
        print("Failed to register %s." % connection, file=sys.stderr)
        sys.exit(1)
    else:
        try:
            check_call(["nmcli", "con", "up", "id", connection])
            print("Connection %s activated." % connection)
        except CalledProcessError as error:
            print("Failed to activate %s." % connection, file=sys.stderr)
            sys.exit(error.returncode)


def write_connection_file(name, connection_info):
    try:
        connection_file = open(CONNECTIONS_PATH + name, "w")
        connection_file.write(connection_info)
        os.fchmod(connection_file.fileno(), 0o600)
        connection_file.close()
    except IOError:
        print(
            "Can't write to "
            + CONNECTIONS_PATH
            + name
            + ". Is this command being run as root?",
            file=sys.stderr,
        )
        sys.exit(1)


def create_wifi_connection(args):
    wifi_connection = wifi_connection_section(args.ssid, args.uuid)

    if args.security:
        # Set security options
        if not args.key:
            print(
                "You need to specify a key using --key "
                "if using wireless security.",
                file=sys.stderr,
            )
            sys.exit(1)

        wifi_connection += wifi_security_section(args.security, args.key)
    elif args.key:
        print(
            "You specified an encryption key "
            "but did not give a security type "
            "using --security.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        check_call(["rfkill", "unblock", "wlan", "wifi"])
    except CalledProcessError:
        print(
            "Could not unblock wireless " "devices with rfkill.",
            file=sys.stderr,
        )
        # Don't fail the script if unblock didn't work though

    wifi_connection += wifi_ip_sections()

    # NetworkManager replaces forward-slashes in SSIDs with asterisks
    name = args.ssid.replace("/", "*")
    write_connection_file(name, wifi_connection)

    return name


def create_mobilebroadband_connection(args):
    name = args.name

    mobilebroadband_connection = mobilebroadband_connection_section(
        name, args.uuid, args.type
    )
    mobilebroadband_connection += mobilebroadband_type_section(
        args.type, args.apn, args.username, args.password, args.pin
    )

    if args.type == "cdma":
        mobilebroadband_connection += mobilebroadband_ppp_section()

    mobilebroadband_connection += mobilebroadband_ip_section()
    mobilebroadband_connection += mobilebroadband_serial_section()

    write_connection_file(name, mobilebroadband_connection)
    return name


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(help="sub command help")

    wifi_parser = subparsers.add_parser(
        "wifi", help="Create a Wifi connection."
    )
    wifi_parser.add_argument("ssid", help="The SSID to connect to.")
    wifi_parser.add_argument(
        "-S",
        "--security",
        choices=["wpa", "wep"],
        help=(
            "The type of security to be used by the "
            "connection. No security will be used if "
            "nothing is specified."
        ),
    )
    wifi_parser.add_argument(
        "-K", "--key", help="The encryption key required by the router."
    )
    wifi_parser.set_defaults(func=create_wifi_connection)

    mobilebroadband_parser = subparsers.add_parser(
        "mobilebroadband",
        help="Create a " "mobile " "broadband " "connection.",
    )
    mobilebroadband_parser.add_argument(
        "type", choices=["gsm", "cdma"], help="The type of connection."
    )
    mobilebroadband_parser.add_argument(
        "-n", "--name", default="MobileBB", help="The name of the connection."
    )
    mobilebroadband_parser.add_argument(
        "-a", "--apn", help="The APN to connect to."
    )
    mobilebroadband_parser.add_argument(
        "-u",
        "--username",
        help="The username required by the " "mobile broadband access point.",
    )
    mobilebroadband_parser.add_argument(
        "-p",
        "--password",
        help="The password required by the " "mobile broadband access point.",
    )
    mobilebroadband_parser.add_argument(
        "-P", "--pin", help="The PIN of the SIM " "card, if set."
    )
    mobilebroadband_parser.set_defaults(func=create_mobilebroadband_connection)

    parser.add_argument(
        "-U",
        "--uuid",
        help="""The uuid to assign to the connection for use by
                                NetworkManager. One will be generated if not
                                specified here.""",
    )
    parser.add_argument(
        "-R",
        "--retries",
        help="""The number of times to attempt bringing up the
                                connection until it is confirmed as active.""",
        default=5,
    )
    parser.add_argument(
        "-I",
        "--interval",
        help=(
            "The time to wait between attempts to detect "
            "the registration of the connection."
        ),
        default=2,
    )
    args = parser.parse_args()

    # Call function to create the appropriate connection type
    connection_name = args.func(args)
    # Make sure we don't exit until the connection is fully created
    block_until_created(connection_name, args.retries, args.interval)


if __name__ == "__main__":
    main()
