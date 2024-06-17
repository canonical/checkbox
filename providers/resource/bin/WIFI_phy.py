#!/usr/bin/env python3

# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>

import re
from subprocess import check_output
from typing import Dict, List, Tuple


def parse_iw_dev_output() -> List[Tuple[str, str]]:
    """
    Parses the output of "iw dev" to extract PHY and interface mappings.
    """
    output = check_output(["iw", "dev"], universal_newlines=True)
    iw_dev_ptn = r"(phy.*)[\s\S]*?Interface (\w+)"
    return re.findall(iw_dev_ptn, output)


def parse_phy_info_output(output: str) -> Dict[str, List[str]]:
    """
    Parses the output of "iw phy info" to extract bands and STA support.
    """
    bands_data = output.split("Supported commands:")[0]
    bands = {}
    for band in bands_data.split("Band "):
        if not band:
            continue
        band_ptn = r"(\d+):"
        band_res = re.match(band_ptn, band)
        if not band_res:
            continue
        band_num, band_content = band.split(":", 1)
        # get Frequencies paragraph
        freqs_raw = band_content.split("Frequencies:", 1)[1].split(":", 1)[0]
        freqs = [
            freq.strip()
            for freq in freqs_raw.split("*")
            if "disabled" not in freq and "MHz" in freq
        ]
        bands[band_num] = freqs
    return bands


def check_sta_support(phy_info_output: str) -> Dict[str, str]:
    """
    Checks if supported STAs (BE, AX, AC) are present based on keywords in
    the output.
    """
    # Supported STAs and their keywords
    supported_stas = {"BE": "EHT", "AX": "HE RX MCS", "AC": "VHT RX MCS"}

    sta_supported = {
        sta: "supported" if sta_keyword in phy_info_output else "unsupported"
        for sta, sta_keyword in supported_stas.items()
    }
    return sta_supported


def check_freq_support(bands: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Checks if supported frequency (2.4GHz, 5GHz, 6GHz) are present based on
    band number
    """
    # Ex. the frequency 2.4GHz is band 1, 5GHz is band 2, 6GHz is band 4
    # so if bands[1] is not empty, the device supports 2.4GHz.
    supported_freqs = {"2.4GHz": "1", "5GHz": "2", "6GHz": "4"}

    freq_supported = {
        freq: ("supported" if bands.get(band) else "unsupported")
        for freq, band in supported_freqs.items()
    }
    return freq_supported


def create_phy_interface_mapping(phy_interface: List[Tuple[str, str]]) -> Dict:
    """
    Creates a mapping between interfaces and their PHY, bands, and STA support.
    """
    phy_interface_mapping = {}
    for phy, interface in phy_interface:
        phy_info_output = check_output(
            ["iw", phy, "info"], universal_newlines=True
        )
        bands = parse_phy_info_output(phy_info_output)
        freq_supported = check_freq_support(bands)
        sta_supported = check_sta_support(phy_info_output)
        phy_interface_mapping[interface] = {
            "PHY": phy,
            "Bands": bands,
            "FREQ_Supported": freq_supported,
            "STA_Supported": sta_supported,
        }
    return phy_interface_mapping


def main():
    # Read and parse "iw dev" output
    phy_interface = parse_iw_dev_output()

    # Create mapping with interface, PHY, bands, and supported STAs
    phy_interface_mapping = create_phy_interface_mapping(phy_interface)

    # Print interface summary with detailed information on separate lines
    for interface, content in phy_interface_mapping.items():
        for freq, ret in content["FREQ_Supported"].items():
            # replace . with _ to support resource expressions for 2.4GHz
            # as . is not a valid character in resource expression names
            # i.e.: wifi.wlan0_2_4GHz is valid, wifi.wlan0_2.4GHz is not
            print("{}_{}: {}".format(interface, freq.replace(".", "_"), ret))
        for sta, ret in content["STA_Supported"].items():
            print("{}_{}: {}".format(interface, sta.lower(), ret))


if __name__ == "__main__":
    main()
