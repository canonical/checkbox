#!/usr/bin/env python3

import serial
import serial.rs485
import logging
import sys
import os
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
        with serial.Serial(serial_device, baudrate, timeout=1) as ser:
            logger.info("Serial port opened successfully.")

            # Send 'Enter Key'
            logger.info("Sending 'Enter Key'...")
            ser.write(os.linesep.encode())
            response = ser.read(size=128).decode()
            logger.info("Received response:\n'{}'".format(response))
            # ":~$" is the pattern for the DUT after logging in
            # "login:" is the pattern for the DUT before logging in
            if ":~$" in response or "login:" in response:
                logger.info("[PASS] Serial console test successful.")
            else:
                logger.info("[FAIL] Serial console test failed.")
                logger.info(
                    "Expected response should contain ':~$' or 'login:'"
                )
                raise SystemExit(1)
        logger.info("Serial port closeed successfully.")
    except Exception:
        logger.exception("Caught an exception.")
        raise SystemExit(1)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--device",
        "-d",
        default="/dev/ttyUSB0",
        help="The serial port used to connect to",
    )
    parser.add_argument(
        "--baudrate",
        "-b",
        default=115200,
        help="The baud rate for the serial port",
    )
    args = parser.parse_args()
    test_serial_console(args.device, args.baudrate)


if __name__ == "__main__":
    SystemExit(main())
