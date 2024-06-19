#!/usr/bin/env python3

import glob
import argparse
import subprocess
import shlex


def runcmd(command):
    ret = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        timeout=1,
    )
    return ret


def detect_spi_node(exit_with_notice=False):
    spi_devices = glob.glob("/dev/spidev*")
    if spi_devices:
        for device in spi_devices:
            print("device: {}".format(device))
            print()
    elif exit_with_notice:
        raise SystemExit("No SPI devices found under /dev/")


def test_spi_content_consistency(spi_path):
    """
    Test the consistency of the SPI communication.

    Args:
        spi_path (str): The path to the SPI device.

    Raises:
        SystemExit: If no output is reported or
        if the content is not consistent.
    """

    # Construct the command to run the SPI test
    cmd = "spidev_test -D {} -p 'Canonical SPI Test' -v".format(spi_path)
    print(f"Run command: {cmd}\n")

    # Run the command and capture the output
    spi_ret = runcmd(cmd)
    print(spi_ret.stdout)

    # Split the output into packets
    packets = spi_ret.stdout.split("\n")

    # Check if any output is reported
    if not len(packets):
        raise SystemExit("ERROR: no any output be reported")

    # Check if the content is consistent between TX and RX
    for rx, tx in zip(packets[-2:-1], packets[-3:-2]):
        tx_content = tx.split("|")[2]
        rx_content = rx.split("|")[2]

        if tx_content != rx_content:
            raise SystemExit(
                "ERROR: the content is not consistent between TX and RX"
            )


def main():
    parser = argparse.ArgumentParser(
        prog="SPI Testing Tool",
        description="This is a tool to help you test "
        "Serial Peripheral Interface (SPI)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--detect",
        "-d",
        action="store_true",
        help="Detect SPI node in the system, will raise error if not found",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List SPI node in the system, will not raise error if not found",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Test SPI content consistency",
    )
    parser.add_argument(
        "--path",
        "-p",
        action="store",
        default="/dev/spidev0.0",
        help="SPI path",
    )
    args = parser.parse_args()

    if args.detect:
        detect_spi_node(exit_with_notice=True)
    elif args.list:
        detect_spi_node(exit_with_notice=False)
    elif args.test:
        test_spi_content_consistency(args.path)


if __name__ == "__main__":
    main()
