#!/usr/bin/env python3
import argparse
import logging
import serial
import sys

# Define Control Characters
ENQ = b"\x05"  # Enquiry
ACK = b"\x06"  # Acknowledge
NAK = b"\x15"  # Negative Acknowledge


def test_connection(port, baudrate, bytesize, parity):
    """
    Test connection with specific serial settings.
    """

    parity_name = {
        serial.PARITY_NONE: "None",
        serial.PARITY_EVEN: "Even",
        serial.PARITY_ODD: "Odd",
    }[parity]

    logging.info(
        "Testing config: Baud=%s, DataBits=%s, Parity=%s ... ",
        baudrate,
        bytesize,
        parity_name,
    )

    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=serial.STOPBITS_ONE,
            timeout=5,
        ) as ser:

            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Send ENQ
            ser.write(ENQ)

            # Read response
            response = ser.read(1)

            if response == ACK:
                logging.info(
                    "[SUCCESS] Received ACK (0x06)! Settings are correct."
                )
                return True
            elif response == NAK:
                logging.error(
                    "Received NAK (0x15). Device rejected request "
                    "(Possible Parity Error or Protocol Mismatch)."
                )
                return False
            elif response:
                logging.error(
                    "Received unknown data: %s", response.hex().upper()
                )
                return False
            else:
                logging.error("No response")
                return False

    except serial.SerialException:
        logging.error("[ERROR] Cannot open port")
        return False


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    parser = argparse.ArgumentParser(
        description="Credit Card Reader connection test tool"
    )

    parser.add_argument(
        "-p", "--port", type=str, required=True, help="Serial Port path"
    )
    parser.add_argument(
        "-b", "--baudrate", type=int, default=115200, help="Baudrate"
    )

    args = parser.parse_args()

    logging.info(
        "Attempting to connect to credit card reader on port %s...\n",
        args.port,
    )

    """
    Accroding to the SPCE of verifone's credit card reader. It support
    6 different conbinations of parity and bytesize.
    And it use 8 bits and parity None as default setting. We use it as
    our test configuration at the moment.
    ref: https://drive.google.com/file/d/1UCR0FuF6qbdXMUrc9MrFCFSOYj_FYX-f/view?usp=drive_link
    """
    configs = [
        (serial.EIGHTBITS, serial.PARITY_NONE),
        (serial.EIGHTBITS, serial.PARITY_EVEN),
        (serial.EIGHTBITS, serial.PARITY_ODD),
        (serial.SEVENBITS, serial.PARITY_EVEN),
        (serial.SEVENBITS, serial.PARITY_ODD),
        (serial.SEVENBITS, serial.PARITY_NONE),
    ]

    for bytesize, parity in configs:
        if test_connection(args.port, args.baudrate, bytesize, parity):
            break
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
