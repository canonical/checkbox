#!/usr/bin/env python3
import sys
import argparse
import subprocess


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "interface", help="Interface which will be used to ping"
    )
    parser.add_argument(
        "--threshold",
        "-t",
        help="Maximum percentage of lost of packets to mark the test as ok",
        default="90",
    )
    return parser.parse_args(argv)


def network_available(interface, threshold):
    print("Testing", interface)
    ping_output = subprocess.check_output(
        ["ping", "-I", interface, "-c", "10", "1.1.1.1"],
        universal_newlines=True,
    )
    print(ping_output)
    if "% packet loss" not in ping_output:
        raise SystemExit(
            "Unable to determine the % packet loss from the output"
        )
    perc_packet_loss = ping_output.rsplit("% packet loss", 1)[0].rsplit(
        maxsplit=1
    )[1]
    if float(perc_packet_loss) > float(threshold):
        raise SystemExit(
            "Detected packet loss ({}%) is higher than threshold ({}%)".format(
                perc_packet_loss, threshold
            )
        )
    print(
        "Detected packet loss ({}%) is lower than threshold ({}%)".format(
            perc_packet_loss, threshold
        )
    )


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    network_available(args.interface, args.threshold)


if __name__ == "__main__":
    main()
