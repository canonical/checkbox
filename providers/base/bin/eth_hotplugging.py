#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
"""Check if hotplugging works on an ethernet port."""

import sys
import os
import time
import glob
import yaml
import subprocess as sp

from gateway_ping_test import perform_ping_test

NETPLAN_CFG_PATHS = ("/etc/netplan", "/lib/netplan", "/run/netplan")


def netplan_renderer():
    """
    Check the renderer used by netplan on the system if it is networkd or
    NetworkManager.
    This function looks for the renderer used in the yaml files located in the
    NETPLAN_CFG_PATHS directories, and returns the first renderer found.
    If the renderer is not found, it defaults to "networkd".
    If the netplan file is not found, it defaults to "NetworkManager".
    """
    netplan_file_exist = False
    for basedir in NETPLAN_CFG_PATHS:
        if os.path.exists(basedir):
            files = glob.glob(os.path.join(basedir, "*.yaml"))
            for f in files:
                netplan_file_exist = True
                with open(f, "r") as file:
                    data = yaml.safe_load(file)
                    if "renderer" in data["network"]:
                        return data["network"]["renderer"]
    if netplan_file_exist:
        return "networkd"
    return "NetworkManager"


def get_interface_info(interface, renderer):
    """
    Get the interface information (state and gateway) from the renderer.
    """
    if renderer == "networkd":
        cmd = "networkctl status --no-pager --no-legend {}".format(interface)
        key_map = {"State": "state", "Gateway": "gateway"}
    elif renderer == "NetworkManager":
        cmd = "nmcli device show {}".format(interface)
        key_map = {"GENERAL.STATE": "state", "IP4.GATEWAY": "gateway"}
    else:
        raise ValueError("Unknown renderer: {}".format(renderer))

    return _get_cmd_info(cmd, key_map, renderer)


def _get_cmd_info(cmd, key_map, renderer):
    info = {}
    try:
        output = sp.check_output(cmd, shell=True)
        for line in output.decode(sys.stdout.encoding).splitlines():
            # Skip lines that don't have a "key: value" format
            if ":" not in line:
                continue
            key, val = line.strip().split(":", maxsplit=1)
            key = key.strip()
            val = val.strip()
            if key in key_map:
                info[key_map[key]] = val
    except sp.CalledProcessError as e:
        print("Error running {} command: {}".format(renderer, e))
    return info


def _check_routable_state(interface, renderer):
    """
    Check if the interface is in a routable state depending on the renderer
    """
    routable = False
    state = ""
    info = get_interface_info(interface, renderer)
    state = info.get("state", "")
    if renderer == "networkd":
        routable = "routable" in state
    elif renderer == "NetworkManager":
        routable = "connected" in state and "disconnected" not in state
    return (routable, state)


def wait_for_routable_state(
    interface, renderer, do_routable=True, max_wait=30
):
    attempts = 0
    routable_msg = "routable" if do_routable else "NOT routable"
    while attempts <= max_wait:
        attempts += 1
        (routable, _) = _check_routable_state(interface, renderer)
        if routable == do_routable:
            print("Reached {} state".format(routable_msg))
            return
        time.sleep(1)
    raise SystemExit("Failed to reach {} state!".format(routable_msg))


def has_cable(iface):
    """Check if cable is inserted in the ethernet port identified by iface."""
    path = "/sys/class/net/{}/carrier".format(iface)
    with open(path) as carrier:
        return carrier.read()[0] == "1"


def wait_for_cable_state(iface, do_cable=True, max_wait=30):
    """Wait for the cable state to be True or False."""
    attempts = 0
    cable_msg = "plugged" if do_cable else "unplugged"
    while attempts <= max_wait:
        attempts += 1
        if has_cable(iface) == do_cable:
            print("Detected cable state: {}".format(cable_msg))
            return
        time.sleep(1)
    raise SystemExit("Failed to detect {}!".format(cable_msg))


def help_wait_cable_and_routable_state(iface, do_check=True):
    if do_check:
        do_cable = True
        do_routable = True
    else:
        do_cable = False
        do_routable = False

    renderer = netplan_renderer()
    print(
        "Waiting for cable to get {}.".format(
            "connected" if do_cable else "disconnected"
        ),
        flush=True,
    )
    wait_for_cable_state(iface, do_cable, 60)

    print(
        "Waiting for networkd/NetworkManager {}.".format(
            "routable" if do_routable else "NOT routable"
        )
    )
    wait_for_routable_state(iface, renderer, do_routable, 60)

    print("Cable {}!".format("connected" if do_cable else "disconnected"))
    print("Network {}!".format("routable" if do_routable else "NOT routable"))


def main():
    """Entry point to the program."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage {} INTERFACE_NAME".format(sys.argv[0]))
    iface = sys.argv[1]
    # sanity check of the interface path
    try:
        has_cable(iface)
    except Exception as exc:
        msg = "Could not check the cable for '{}': {}".format(iface, exc)
        raise SystemExit(msg) from exc
    print(
        (
            "Press enter and unplug the ethernet cable "
            "from the port {} of the System."
        ).format(iface)
    )
    print("After 15 seconds plug it back in.")
    print("Checkbox session may be interrupted but it should come back up.")
    input()

    help_wait_cable_and_routable_state(iface, False)

    print("\n\nPlease plug the cable back in.\n\n")

    help_wait_cable_and_routable_state(iface, True)

    print("Pinging gateway...")
    ping_state = perform_ping_test([iface])
    if ping_state == 0:
        print("PASS: Ping to gateway successful")
    else:
        raise SystemExit("FAIL: Ping to gateway failed")


if __name__ == "__main__":
    main()
