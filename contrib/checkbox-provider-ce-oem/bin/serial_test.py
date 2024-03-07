#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Rick Wu <rick.wu@canonical.com>
#   Stanley Huang <stanley.huang@canonical.com>
#   Vincent Liao <vincent.liao@canonical.com>

"""
Whole idea of this RS485/232/422 remote test script is to connet
all RS232/422/485 that on DUT to the server. And test the
port on DUT.
"""
import sys
import argparse
import serial
import serial.rs485
import time
import logging
import os


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


class Serial:
    def __init__(
        self,
        node,
        type,
        group: list = [],
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: int = 1,
    ) -> None:
        self.node = node
        self.type = type
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.ser = self.serial_init(node)
        self.group = []
        for ser in group:
            self.group.append(self.serial_init(ser))

    def serial_init(self, node: str) -> serial.Serial:
        """Create a serial.Serial object based on the class variables"""
        ser = serial.Serial(
            node,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=1,
        )
        if self.type == "RS485":
            ser.rs485_mode = serial.rs485.RS485Settings()
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        return ser

    def send(self, data: bytes) -> None:
        try:
            self.ser.rts = True
            self.ser.write(data)
            self.ser.rts = False
            logging.info("Sent: {}".format(data.hex()))
        except Exception:
            logging.exception("Not able to send data!")

    def recv(self) -> bytes:
        rcv = ""
        try:
            self.ser.rts = False
            rcv = self.ser.read(8)
            if rcv:
                logging.info("Received: {}".format(rcv.hex()))
        except ValueError:
            logging.exception("Received unmanageable string format")
            rcv = "Error format"
        return rcv


def server_mode(ser: Serial) -> None:
    """
    Running as a server, it will be sniffing for received string.
    And it will send the same string out.
    usage:
    running on port /dev/ttyUSB0 as a server
    $ sudo ./serial_test.py /dev/ttyUSB0 --mode server --type USB
    """
    logging.info("Listening on port {} ...".format(ser.node))
    while True:
        data = ser.recv()
        if data:
            time.sleep(3)
            logging.info("Send string back ...")
            ser.send(data)
            logging.info("Listening on port {} ...".format(ser.node))


def client_mode(ser: Serial):
    """
    Running as a clinet and it will sending out a string and wait
    the string send back from server. After receive the string,
    it will check the readback is correct or not.
    Usage:
    running on port /dev/ttymxc1 as a client
    $ sudo ./serial_test.py /dev/ttymxc1 --mode client --type RS485
    """
    data = os.urandom(8)
    ser.send(data)
    for i in range(1, 6):
        logging.info("Attempting receive string... {} time".format(i))
        readback = ser.recv()
        time.sleep(3)
        if readback:
            if readback == data:
                logging.info("Received string is correct!")
                raise SystemExit(0)
            else:
                logging.error("Received string is incorrect!")
                raise SystemExit(1)
    logging.error("Not able to receive string!!")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("node", help="Serial port device node e.g. /dev/ttyS1")
    parser.add_argument(
        "--mode",
        choices=["server", "client"],
        type=str,
        help="set running mode, one if {server, client}",
        required=True,
    )
    parser.add_argument(
        "--type",
        type=str,
        help="The type of serial port (e.g. RS485, RS422, RS232, USB)",
        default="USB"
    )
    parser.add_argument(
        "--group",
        type=str,
        help="The group of serial ports that needed to be bringup also",
        nargs="?",
        const="",
        default="",
    )
    parser.add_argument("--baudrate", default=115200, type=int)
    parser.add_argument(
        "--bytesize",
        choices=[5, 6, 7, 8],
        type=int,
        help="set bytesize, one of {5, 6, 7, 8}, default: 8",
        default=8,
    )
    parser.add_argument(
        "--parity",
        choices=["N", "E", "O", "S", "M"],
        type=lambda c: c.upper(),
        help="set parity, one of {N E O S M}, default: N",
        default="N",
    )
    parser.add_argument(
        "--stopbits",
        choices=[1, 2],
        type=int,
        help="set stopbits, one of {1, 2}, default: 1",
        default=1,
    )
    args = parser.parse_args()
    init_logger()
    group = args.group.split() if args.group else []
    ser = Serial(
        args.node,
        args.type,
        group,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
    )

    if args.mode == "server":
        server_mode(ser)
    elif args.mode == "client":
        client_mode(ser)
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
