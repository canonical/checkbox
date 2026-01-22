#!/usr/bin/env python3
import argparse
import logging
import serial
import sys

# Define Control Characters
ENQ = b"\x05"  # Enquiry
ACK = b"\x06"  # Acknowledge
NAK = b"\x15"  # Negative Acknowledge


def test_connection(port, baudrate, parity_mode):
    """
    Test connection with specific parity settings.
    parity_mode: 'N' (None), 'E' (Even), 'O' (Odd)
    """

    # Configure serial.Serial parameters
    if parity_mode == "E":
        bytesize = serial.SEVENBITS  # 7-E-1 typically uses 7 data bits
        parity = serial.PARITY_EVEN
    elif parity_mode == "O":
        bytesize = serial.SEVENBITS
        parity = serial.PARITY_ODD
    else:
        bytesize = serial.EIGHTBITS  # 8-N-1 typically uses 8 data bits
        parity = serial.PARITY_NONE

    parity_name = (
        "None"
        if parity_mode == "N"
        else ("Even" if parity_mode == "E" else "Odd")
    )
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

    for parity in ["N", "E", "O"]:
        if test_connection(args.port, args.baudrate, parity):
            break
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
