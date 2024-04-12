#!/usr/bin/env python3

import re
from subprocess import check_output


def parse_iw_dev_output():
    """
    Parses the output of 'iw dev' to extract PHY and interface mappings.
    """
    cmd = "iw dev"
    output = check_output(cmd, shell=True, universal_newlines=True)
    iw_dev_ptn = r"(phy.*)[\s\S]*?Interface (\w+)"
    iw_dev_compile = re.compile(iw_dev_ptn)
    return iw_dev_compile.findall(output)


def parse_phy_info_output(output):
    """
    Parses the output of 'iw phy info' to extract bands and STA support.
    """
    bands_data = output.split("Supported commands:")[0]
    bands = {}
    for band in bands_data.split("Band "):
        if band:
            band_ptn = r"(\d+):\s+([\s\S]*)"
            band_compile = re.compile(band_ptn)
            band_res = band_compile.match(band)
            if band_res:
                band_num = band_res.groups()[0]
                band_content = band_res.groups()[1]
                freqs_raw = band_content.split("Frequencies:")[1]
                freq_ptn = r"(\d+ MHz.*)"
                freq_compile = re.compile(freq_ptn)
                freqs = [freq for freq in freq_compile.findall(freqs_raw)
                         if "disabled" not in freq]
                bands[band_num] = freqs
    return bands


def check_sta_support(phy_info_output):
    """
    Checks if supported STAs (BE, AX, AC) are present based on keywords in
    the output.
    """
    # Supported STAs and their keywords
    supported_stas = {"BE": "EHT", "AX": "HE RX MCS", "AC": "VHT RX MCS"}

    sta_supported = {sta: "supported" if sta_keyword in phy_info_output
                     else "unsupported"
                     for sta, sta_keyword in supported_stas.items()}
    return sta_supported


def check_freq_support(bands):
    """
    Checks if supported frequency (2.4GHz, 5GHz, 6GHz) are present based on
    band number
    """
    supported_freqs = {"2.4GHz": "1", "5GHz": "2", "6GHz": "4"}

    freq_supported = {
        freq: "supported"
        if band in bands and len(bands[band]) > 0 else "unsupported"
        for freq, band in supported_freqs.items()
    }
    return freq_supported


def create_phy_interface_mapping(phy_interface):
    """
    Creates a mapping between interfaces and their PHY, bands, and STA support.
    """
    phy_interface_mapping = {}
    for phy, interface in phy_interface:
        cmd = "iw {} info".format(phy)
        phy_info_output = check_output(cmd, shell=True,
                                       universal_newlines=True)
        bands = parse_phy_info_output(phy_info_output)
        freq_supported = check_freq_support(bands)
        sta_supported = check_sta_support(phy_info_output)
        phy_interface_mapping[interface] = {
            "PHY": phy,
            "Bands": bands,
            "FREQ_Supported": freq_supported,
            "STA_Supported": sta_supported
        }
    return phy_interface_mapping


def main():
    # Read and parse 'iw dev' output
    phy_interface = parse_iw_dev_output()

    # Create mapping with interface, PHY, bands, and supported STAs
    phy_interface_mapping = create_phy_interface_mapping(phy_interface)

    # Print interface summary with detailed information on separate lines
    for interface, content in phy_interface_mapping.items():
        for freq, ret in content["FREQ_Supported"].items():
            print("{}_{}: {}".format(interface, freq, ret))
        for sta, ret in content["STA_Supported"].items():
            print("{}_{}: {}".format(interface, sta.lower(), ret))


if __name__ == "__main__":
    main()
