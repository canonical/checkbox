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
        raise SystemError("An unexpected error occurred: {}".format(e))


def get_interfaces() -> List[Tuple[str, str]]:
    output = run_command(["iw", "dev"])
    device_pattern = r"phy#(\d+).*?Interface (\S+)"
    if output:
        matches = re.findall(device_pattern, output, re.DOTALL)
        return [
            (device_id, interface_name)
            for device_id, interface_name in matches
        ]
    raise SystemExit(0)


def get_wiphy_info() -> List[Tuple[str, List[str]]]:
    # We can not use command "iw phy0 info" to get the infomation of sepcific
    # interface.
    # Because of "phy0" in command could be other pattern like "mwiphy0".
    # And such pattern as "mwiphy0" will only show in the output of command
    # "iw phy".
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


def print_supported_modes() -> str:
    interfaces = get_interfaces()
    wiphy_info = get_wiphy_info()
    for wiphy_index, modes in wiphy_info:
        for device_index, interface in interfaces:
            if wiphy_index == device_index:
                for mode in modes:
                    print("{}_{}: supported".format(interface, mode))


def main():
    print_supported_modes()


if __name__ == "__main__":
    main()
