#!/usr/bin/env python3

import argparse

from checkbox_support.ethtool.ts_info import find_ptp_device


def parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that a network interface supports hardware PTP"
    )
    parser.add_argument("interface", help="network interface, e.g. eth0")
    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None):
    args = parse_args(argv)
    ptp_device = find_ptp_device(args.interface)
    if ptp_device is None:
        raise SystemExit(f"'{args.interface}' does not support hardware PTP")
    print(f"[ OK ] PTP device '{ptp_device}' exists for '{args.interface}'")


if __name__ == "__main__":
    main()
