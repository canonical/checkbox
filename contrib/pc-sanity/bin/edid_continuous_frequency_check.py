#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import argparse


def is_laptop():
    with open("/sys/class/dmi/id/chassis_type", "r") as fobj:
        chassis_type = fobj.read().replace("\n", "")
        if chassis_type == "10" or chassis_type == "9" or chassis_type == "13":
            return True
    print("Not laptop, notebook or AIO platform, abort EDID check.")
    return False


def find_internal_panel_edid():
    """Find internal panel edid"""
    drmdir = "/sys/class/drm/"
    for i in "card0-eDP-1", "card1-eDP-1", "card0-LVDS-1", "card1-LVDS-1":
        for edid_file_path in glob.glob(drmdir + i):
            edid_file = edid_file_path + "/edid"
            if os.path.isfile(edid_file):
                print(edid_file)
                return edid_file
    raise SystemExit("Can not find edid from sysfs !")


def read_edid(edid_fobj, address, bytelen):
    """Read edid number of bytelen bytes from specified address"""
    edid_fobj.seek(address)
    rbytes = edid_fobj.read(bytelen)
    # print("0x%X: 0x%s" % (address, rbytes.hex()))
    return rbytes


def is_continuous_frequency_display(value_of_18h):
    """Is bit 0 at address 18h set to 1"""
    if (int.from_bytes(value_of_18h, byteorder="big") & 0x01) == 0x01:
        return True
    else:
        return False


def get_edid_version(value_of_12h, value_of_13h):
    """Get edid version"""
    version = int.from_bytes(value_of_12h, byteorder="big")
    revision = int.from_bytes(value_of_13h, byteorder="big")
    return version, revision


def get_horizontal_addressable_video_in_pixels(data_block_of_DTD):
    """Get Horizontal Addressable Video in pixels from Detailed Timing Definition # noqa: E501
    Address: 0x36h
    Size: 18 bytes
    """
    havip = bytearray((data_block_of_DTD[4] >> 4).to_bytes(1, byteorder="big"))
    havip.append(data_block_of_DTD[2])
    # print("DTD: Horizontal Addressable Video in Pixels: %d" % int.from_bytes(havip, byteorder='big') ) # noqa: E501
    return int.from_bytes(havip, byteorder="big")


def maximum_horizontal_active_pixels(byte12, byte13):
    return 8 * (byte13 + 256 * (0x03 & byte12))


def check_display_range_limits_descriptor(
    data_block_of_DRLD, horizontal_address_video_in_pixels
):  # noqa: E501
    """Check Display Range Limits Descriptor with CVT support
    Address: 0x48h
    Size: 18 bytes
    """
    # Debug dump DRLD
    # print("DRLD: Dump: %02X" %  int.from_bytes(data_block_of_DRLD, byteorder='big'))# noqa: E501

    # check tag 0xFD
    if data_block_of_DRLD[3] == 0xFD:
        if data_block_of_DRLD[10] == 0x04:
            if (data_block_of_DRLD[5] < data_block_of_DRLD[6]) and (
                data_block_of_DRLD[7] < data_block_of_DRLD[8]
            ):  # noqa: E501
                if (
                    horizontal_address_video_in_pixels
                    == maximum_horizontal_active_pixels(
                        data_block_of_DRLD[12], data_block_of_DRLD[13]
                    )
                ):  # noqa: E501
                    return True
                else:
                    print(
                        "horizontal_address_video_in_pixels != maximum_horizontal_active_pixels "
                    )  # noqa: E501
            else:
                print("Minimum/Maximum Vertical/Horizontal Freq value error")
        else:
            print("CVT not support")
    else:
        print("0xFD is an optional field in EDID 1.4")
        print("https://glenwing.github.io/docs/VESA-EEDID-A2.pdf page 38")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--edid", help="path of a EDID file from /sys/class/drm/", type=str
    )  # noqa: E501
    args = parser.parse_args()
    if not is_laptop():
        return 0

    if args.edid is None:
        edidfile = find_internal_panel_edid()
    else:
        edidfile = args.edid

    with open(edidfile, "rb") as fobj:
        version, revision = get_edid_version(
            read_edid(fobj, 0x12, 1), read_edid(fobj, 0x13, 1)
        )  # noqa: E501
        if version == 1 and revision >= 4:
            if is_continuous_frequency_display(read_edid(fobj, 0x18, 1)):
                if check_display_range_limits_descriptor(
                    read_edid(fobj, 0x48, 18),
                    get_horizontal_addressable_video_in_pixels(
                        read_edid(fobj, 0x36, 18)
                    ),
                ):  # noqa: E501
                    print("EDID Display Range Limits Descriptor checke: pass")
                else:
                    raise SystemExit(
                        "EDID Display Range Limits Descriptor check failed!"
                    )  # noqa: E501
            else:
                print("Display is noncontinuous frequency")
        else:
            print("EDID version: %d.%d < 1.4" % (version, revision))
    return 0


if __name__ == "__main__":
    main()
