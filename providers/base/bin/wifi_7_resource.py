#! /usr/bin/env python3
import os
import subprocess as sp


def get_wpa_supplicant_version() -> "tuple[int, int]":
    """
    (manually verified on ubuntu16 ~ 24 including ubuntu core)
    The output of "wpa_supplicant -v" always looks like the following

    wpa_supplicant v2.10
    Copyright (c) 2003-2022, Jouni Malinen <j@w1.fi> and contributors

    :return: the sys.version style tuple like (2, 10)
    """
    wpa_supplicant_version_output = sp.check_output(
        ["wpa_supplicant", "-v"], universal_newlines=True
    )

    # take the 1st line, 2nd word, remove the 'v'
    clean_version_str = wpa_supplicant_version_output.splitlines()[0].split()[
        1
    ][1:]
    # Example: clean_version_str == '2.11'
    # Now convert to a sys.version style tuple
    version_tuple = tuple(
        map(
            int,
            clean_version_str.split(".", maxsplit=1),
        ),
    )
    assert len(version_tuple) == 2

    return version_tuple


def get_kernel_version() -> "tuple[int, int]":
    # kernel version string format is consistent
    # https://askubuntu.com/questions/843197/what-are-kernel-version-number-components-w-x-yy-zzz-called # noqa: E501
    version_str = os.uname().release
    # '6.14.0-32-generic'
    # '6.14.0-1012-oem'
    major, minor, _ = version_str.split("-", maxsplit=1)[0].split(".")
    return (int(major), int(minor))


def main():
    # workaround: we need to produce true/false in the resource job since
    # pxu resource expressions only support string comparison,
    # which means the only predictable comparator is '=='

    # TODO: if the pxu engine supports rich comparison in the future,
    # move these comparisons to the pxu files to make job requirements more
    # explicit

    print(
        "wpa_supplicant_at_least_2_11: {}".format(
            get_wpa_supplicant_version() >= (2, 11)
        )
    )
    print("kernel_at_least_6_14: {}".format(get_kernel_version() >= (6, 14)))
    # TODO: this is only used during the transition period when not all 
    # the labs have a MLO AP. Remove it once MLO_SSID is filled in for all the 
    # labs on C3
    print("mlo_ssid_specified: {}".format("MLO_SSID" in os.environ))


if __name__ == "__main__":
    main()
