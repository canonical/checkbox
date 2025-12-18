#!/usr/bin/env python3

import os
import re
import shlex
import textwrap
from pathlib import Path
from itertools import chain
from subprocess import check_output, CalledProcessError

rootdir_pattern = re.compile(r"^.*?/devices")

# NOTE: If raid_types changes, also change it in disk_smart script!
raid_types = ["megaraid", "cciss", "3ware", "areca"]


def device_state(name):
    """Follow pmount policy to find if a device is removable or internal."""

    path = rootdir_pattern.sub("", os.readlink("/sys/block/%s" % name))
    hotplug_buses = ("usb", "ieee1394", "mmc", "pcmcia", "firewire")
    for bus in hotplug_buses:
        if os.path.exists("/sys/bus/%s" % bus):
            for device_bus in os.listdir("/sys/bus/%s/devices" % bus):
                device_link = rootdir_pattern.sub(
                    "",
                    os.readlink("/sys/bus/%s/devices/%s" % (bus, device_bus)),
                )
                if re.search(device_link, path):
                    return "removable"

    return "internal"


def usb_support(name, version):
    """Check the USB specification number for both hub port and device."""
    path = rootdir_pattern.sub("", os.readlink("/sys/block/%s" % name))

    # Remove the usb config.interface part of the path
    m = re.match(r"((.*usb\d+).*\/)\d-[\d\.:\-]+\/.*", path)
    if m:
        device_path = m.group(1)
        hub_port_path = m.group(2)

        # Check the highest version of USB the device supports
        with open("/sys/devices/%s/version" % device_path, "rt") as f:
            if float(f.readline()) < version:
                return "unsupported"

        # Check the highest version of USB the hub supports
        with open("/sys/devices/%s/version" % hub_port_path, "rt") as f:
            if float(f.readline()) < version:
                return "unsupported"

        return "supported"

    return "unsupported"


def device_rotation(name):
    """
    Check the device queue/rotational parameter to determine if it's a spinning
    device or a non-spinning device, which indicates it's an SSD.
    """
    path = "/sys/block/{0}/device/block/{0}/queue/rotational".format(name)
    if not os.path.exists(path):
        return "no"
    with open(path, "rt") as f:
        if f.read(1) == "1":
            return "yes"

    return "no"


def smart_supporting_diskinfo(diskinfo) -> bool:
    # if a diskinfo line contains any of the following (all on one line)
    # assume the disk supports SMART
    # ex. SMART support is: Avaliable
    indicators = [("SMART support is", "Available"), ("SMART", "test result")]

    def contains_indicator(line):
        return any(
            all(indicator_segment in line for indicator_segment in indicator)
            for indicator in indicators
        )

    return any(contains_indicator(line) for line in diskinfo)


def smart_support_raid(name, raid_type):
    """Check for availability of SMART support in a RAID device.

    See also count_raid_disks() in disk_smart script.
    :param name:
        disk device filename within /dev (e.g., sda)
    :param raid_type:
        type of raid device (e.g., megaraid, 3ware, etc. -- codes used
                             by smartctl)
    :returns:
        'True' or 'False' as string (for return to Checkbox)
    """
    disk_num = 0
    # Loop through all disks in array to verify that SMART is available on
    # at least one of them. Note that if there's a mix of supported and
    # unsupported, this test returns 'True', which will result in a failure
    # of disk_smart. This is by design, since such a mix is likely an assembly
    # error by the manufacturer.
    while True:
        command = "smartctl -x /dev/{} -d {},{}".format(
            name, raid_type, disk_num
        )
        try:
            diskinfo = check_output(
                shlex.split(command), universal_newlines=True
            ).splitlines()
            if smart_supporting_diskinfo(diskinfo):
                return "True"

            disk_num += 1
        except CalledProcessError:
            return "False"


def smart_support(name):
    """Check for availability of SMART support in the device.

    See also count_raid_disks() in disk_smart script.
    :param name:
        disk device filename within /dev (e.g., sda)
    :returns:
        'True' or 'False' as string (for return to Checkbox)
    """
    # Check with smartctl to see if SMART is available and enabled on the disk
    command = "smartctl -x /dev/%s" % name
    try:
        diskinfo = check_output(
            shlex.split(command), universal_newlines=True
        ).splitlines()
    except CalledProcessError:
        return "False"

    # First check if the current name supports SMART
    if smart_supporting_diskinfo(diskinfo):
        return "True"
    # Try to check if the disk is in a raid configuration
    for type in raid_types:
        if any("-d {},N".format(type) in s for s in diskinfo):
            return smart_support_raid(name, type)
    return "False"


def main():
    sys_block = Path("/sys/block")
    # match the name any dir in sys block that has a subdirectory device or dm
    disk_names = (
        path.parent.name
        for path in chain(sys_block.glob("*/device"), sys_block.glob("*/dm"))
    )
    for disk_name in disk_names:
        state = device_state(disk_name)
        usb2 = usb_support(disk_name, 2.00)
        usb3 = usb_support(disk_name, 3.00)
        rotation = device_rotation(disk_name)
        smart = smart_support(disk_name)
        resource_text = textwrap.dedent(
            """
            name: {disk_name}
            state: {state}
            usb2: {usb2}
            usb3: {usb3}
            rotation: {rotation}
            smart: {smart}
            """.format(
                disk_name=disk_name,
                state=state,
                usb2=usb2,
                usb3=usb3,
                rotation=rotation,
                smart=smart,
            )
        ).lstrip()
        print(resource_text)


if __name__ == "__main__":
    main()
