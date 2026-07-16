#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Authors:
#   Zhongning Li <zhongning.li@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
Source code of ethtool:
https://git.kernel.org/pub/scm/network/ethtool/ethtool.git
This python program re-implements this function:
https://git.kernel.org/pub/scm/network/ethtool/ethtool.git/tree/ethtool.c#n4986
"""

import ctypes
import fcntl
import os
import socket
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
# these 2 are used to make same ioctl request as ethtool
# https://github.com/torvalds/linux/blob/3b029c035b34bbc693405ddf759f0e9b920c27f1/include/uapi/linux/sockios.h#L102
SIOCETHTOOL = 0x8946
# https://github.com/torvalds/linux/blob/3b029c035b34bbc693405ddf759f0e9b920c27f1/include/uapi/linux/ethtool.h#L1940
ETHTOOL_GET_TS_INFO = 0x00000041

# yes this is actually how it's spelled
# https://github.com/torvalds/linux/blob/3b029c035b34bbc693405ddf759f0e9b920c27f1/include/uapi/linux/if.h#L33
IFNAMSIZ = 16


# the main struct of interest
# for the purpose of finding PTP capable interfaces we only need phc_index
# we also need to specify .cmd to indicate that we want to do ETHTOOL_GET_TS_INFO
# https://github.com/torvalds/linux/blob/3b029c035b34bbc693405ddf759f0e9b920c27f1/include/uapi/linux/ethtool.h#L1739
class ethtool_ts_info(ctypes.Structure):
    _fields_ = [
        ("cmd", ctypes.c_uint32),
        ("so_timestamping", ctypes.c_uint32),
        ("phc_index", ctypes.c_int32),
        ("tx_types", ctypes.c_uint32),
        ("tx_reserved", ctypes.c_uint32 * 3),
        ("rx_filters", ctypes.c_uint32),
        ("rx_reserved", ctypes.c_uint32 * 3),
    ]

    def __str__(self) -> str:
        words = []  # type: list[str]
        for field in self._fields_:
            name = field[0]
            value = getattr(self, name)
            if isinstance(value, ctypes.Array):
                value = list(value)
            words.append("{}={}".format(name, value))
        return "ethtool_ts_info({})".format(", ".join(words))


# this is only used to make the SIOCETHTOOL ioctl request
# we don't need any of the field values in this struct
# https://github.com/torvalds/linux/blob/3b029c035b34bbc693405ddf759f0e9b920c27f1/include/uapi/linux/if.h#L234-L256
class ifreq(ctypes.Structure):
    _fields_ = [
        ("ifr_name", ctypes.c_char * IFNAMSIZ),
        ("ifr_data", ctypes.c_void_p),
        # https://github.com/torvalds/linux/blob/3b029c035b34bbc693405ddf759f0e9b920c27f1/include/uapi/linux/if.h#L234-L256
        # the rest of the ifreq struct is a 24 byte union
        # because the largest member is the ifmap struct
        # which has (long*2 + short + char*3)
        # therefore this padding should be 16 bytes
        (
            "_ifr_padding",
            ctypes.c_byte
            * (
                ctypes.sizeof(ctypes.c_long) * 2
                + ctypes.sizeof(ctypes.c_short)
                + ctypes.sizeof(ctypes.c_char) * 3
                + 3  # in the ifmap struct, it says "3 bytes to spare"
                # make sure to account for ifr_data
                - ctypes.sizeof(ctypes.c_void_p)
            ),
        ),
    ]


def _is_ethernet_interface(interface: str) -> bool:
    """Check whether the given interface is a physical ethernet device

    :param interface: interface name like enp1s1 or wlp194s0
    :return: True if the interface is a real device
             (not wifi, not loopback, not vpn, etc.)
    """

    try:
        sys_class_net_interface = Path("/sys/class/net/") / interface

        # check for ARPHRD_ETHER
        if not (sys_class_net_interface / "type").read_text().strip() == "1":
            return False
        # skip everything not associated with a physical device
        if not (sys_class_net_interface / "device").exists():
            return False
        # wifi interfaces (16.04+)
        if (sys_class_net_interface / "phy80211").exists():
            return False

        return True
    except OSError:
        # assume false if failed to read any of the paths above
        return False


def get_ts_info(interface: str) -> ethtool_ts_info:
    """
    The main entry point of getting ts_info for the given interface

    :param interface: interface name like enp1s1
    :return: the ethtool_ts_info struct. The main attr we need is the phc_index
             because it directly maps to /dev/ptpX
    """
    if not _is_ethernet_interface(interface):
        logger.warning(
            "{} is not a physical ethernet interface".format(interface)
        )

    info = ethtool_ts_info()
    info.cmd = ETHTOOL_GET_TS_INFO

    ifr = ifreq()
    ifr.ifr_name = interface.encode()
    ifr.ifr_data = ctypes.cast(ctypes.pointer(info), ctypes.c_void_p)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        fcntl.ioctl(sock.fileno(), SIOCETHTOOL, ifr, True)

    return info


def is_ptp_capable(interface: str) -> bool:
    """Checks if <interface> supports PTP

    This is equivalent to checking the "PTP Hardware Clock" line in ethtool
    and testing if the corresponding device node exists

    :param interface: the interface to check
    :return: if kernel says the interface supports ptp
             AND The /dev/ptpX device exists
    """
    try:
        info = get_ts_info(interface)
        phc_index = int(info.phc_index)
        expected_ptp_device_path = "/dev/ptp{}".format(phc_index)

        return phc_index >= 0 and os.path.exists(expected_ptp_device_path)
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    print(get_ts_info("enx5c925ed71416"))
