#!/usr/bin/env python3
from subprocess import check_output
import re
from typing import List, Tuple, Dict


def get_interfaces() -> List[Tuple[str, str]]:
    output = check_output(["iw", "dev"], universal_newlines=True)
    device_pattern = r"phy#(\d+).*?Interface (\S+)"
    if output:
        matches = re.findall(device_pattern, output, re.DOTALL)
        return [
            (device_id, interface_name)
            for device_id, interface_name in matches
        ]
    raise SystemExit(0)


def get_wiphy_info() -> Dict[int, List[str]]:
    # We can not use command "iw phy0 info" to get the infomation of sepcific
    # interface.
    # Because of "phy0" in command could be other pattern like "mwiphy0".
    # And such pattern as "mwiphy0" will only show in the output of command
    # "iw phy".
    output = check_output(["iw", "phy"], universal_newlines=True)
    if not output:
        return []

    interfaces_info = (info.strip() for info in output.split("Wiphy"))
    # drop empty sections
    interfaces_info = filter(bool, interfaces_info)
    index_re = re.compile(r"phy(\d+)")
    wiphy_info = {}
    supported_modes_re = re.compile(
        r"Supported interface modes:\s*((?:\s*\*\s*[\w/-]+\s*)+)"
    )
    for interface_info in interfaces_info:
        interface_id = index_re.search(interface_info).group(1)
        match_modes = supported_modes_re.search(interface_info).group(1)

        supported_modes = map(str.strip, match_modes.split("*"))
        # remove first element because it is spaces before the first *
        _ = next(supported_modes)
        wiphy_info[interface_id] = list(supported_modes)
    return wiphy_info


def print_supported_modes() -> str:
    interfaces = get_interfaces()
    wiphy_info = get_wiphy_info()
    for wiphy_index, modes in wiphy_info.items():
        interface = interfaces[int(wiphy_index)][1]
        print("interface: {}".format(interface))
        for mode in modes:
            print(
                "{}: supported".format(
                    mode.replace("-", "_").replace("/", "_")
                )
            )
        print()


def main():
    print_supported_modes()


if __name__ == "__main__":
    main()
