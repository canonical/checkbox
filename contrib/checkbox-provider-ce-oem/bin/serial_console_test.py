#!/usr/bin/env python3

import serial
import serial.rs485
import logging
import sys
from argparse import ArgumentParser

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger = logging.getLogger("serial-test")
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def test_serial_console(serial_device, baudrate):
    """Test the serial port when it is in console mode"""
    try:
        # Open serial port
        ser = serial.Serial(serial_device, baudrate, timeout=1)
        logger.info("Serial port opened successfully.")

        # Send 'Enter Key'
        logger.info("Sending 'Enter Key'")
        ser.write("\n".encode())
        response = ser.read(size=128).decode()
        print("Received response:\n'{}'".format(response))
        # ":~$" is the pattern for the DUT after logging in
        # "login:" is the pattern for the DUT before logging in
        if ":~$" in response or "login:" in response:
            print("[PASS] Serial console test successful.")
        else:
            print("[FAIL] Serial console test failed.")
            print("Expected response should contain ':~$' or 'login:'")
            raise SystemExit(1)
        # Close serila port
        ser.close()
        logger.info("Serial port closeed successfully.")
    except Exception:
        logger.exception("Caught an exception.")
        raise SystemExit(1)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--device",
        "-d",
        nargs="+",
        default=["/dev/ttyUSB0"],
        help="The serial port used to connect to",
    )
    parser.add_argument(
        "--baudrate",
        "-b",
        default=115200,
        help="The baud rate for the serial port",
    )
    args = parser.parse_args()
    if len(args.device) != 1:
        logger.error("Wrong port count. Should be 1.")
        raise SystemExit(1)
    test_serial_console(args.device[0], args.baudrate)


if __name__ == "__main__":
    SystemExit(main())
