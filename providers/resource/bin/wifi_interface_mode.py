#!/usr/bin/env python3
import subprocess
import re
from typing import List, Tuple


def run_command(command: List[str]) -> str:
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.stdout.decode("utf-8")
    except Exception as e:
        raise SystemError("An unexpected error occurred: {}", e)


def get_interfaces() -> List[Tuple[str, str]]:
    output = run_command(["iw", "dev"])
    interface_pattern = r"phy#(\d+).*?Interface (\S+)"
    if output:
        matches = re.findall(interface_pattern, output, re.DOTALL)
        return [(phy, interface) for phy, interface in matches]
    return []


def get_wiphy_info() -> List[Tuple[str, List[str]]]:
    output = run_command(["iw", "phy"])
    if output:
        contents = re.split(r"Wiphy\s+", output)
        index_pattern = r"phy(\d+)"
        wiphy_info = []
        for content in contents:
            if content.strip():
                match_index = re.search(
                    index_pattern, content, re.DOTALL
                ).group(1)
                supported_mode_pattern = (
                    r"Supported interface modes:\s*((?:\s*\*\s*[\w/-]+\s*)+)"
                )
                match_modes = re.search(
                    supported_mode_pattern, content, re.DOTALL
                )
                if match_modes:
                    modes = re.findall(r"\*\s*([\w/-]+)", match_modes.group(1))

                    wiphy_info.append((match_index, modes))
    return wiphy_info


def print_supported_modes(
    interfaces: List[Tuple[str, str]], wiphy_info: List[Tuple[str, List[str]]]
) -> str:
    for wiphy_index, modes in wiphy_info:
        for interface_index, interface in interfaces:
            if wiphy_index == interface_index:
                for mode in modes:
                    print("{}_{}: supported".format(interface, mode))


def main():
    interfaces = get_interfaces()
    if not interfaces:
        print("")
        return
    wiphy_info = get_wiphy_info()
    print_supported_modes(interfaces, wiphy_info)


if __name__ == "__main__":
    main()
