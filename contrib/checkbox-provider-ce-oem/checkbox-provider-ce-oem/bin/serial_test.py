#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Rick Wu <rick.wu@canonical.com>
#   Stanley Huang <stanley.huang@canonical.com>

"""
Whole idea of this RS485/232/422 remote test script is to connet
all rs485/232/422 that on DUT to the server(RPi 3). And test the
port on DUT.
"""
import sys
import argparse
import serial
import time
import string
import random
import logging


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


def str_generator(size):
    chars = []
    chars.extend(string.ascii_uppercase)
    chars.extend(string.ascii_lowercase)
    chars.extend(string.digits)
    chars.extend(string.punctuation)

    return "".join(random.choices(chars, k=size))


def serial_init(device, **kwargs):
    ser = serial.Serial(
        device,
        baudrate=kwargs.get("baudrate", 115200),
        bytesize=kwargs.get("bytesize", 8),
        parity=kwargs.get("parity", "N"),
        stopbits=kwargs.get("stopbits", 1),
        timeout=1,
        write_timeout=1,
        xonxoff=True
    )
    return ser


def sender(ser, test_str):
    try:
        ser.write(test_str.encode("utf-8"))
        logging.info("Sent: {}".format(test_str))
    except Exception:
        logging.error("Not able to send data!")


def receiver(ser):
    """
    If trying to receive string between two different protocols
    (e.g. RS485 with RS232). Then it will receive the string
    that is not able to decode. So we can handle that kind of
    an exception to filter out the string from the different protocols.
    """
    rcv = ""
    try:
        rcv = ser.readline().decode("utf-8")
        if rcv:
            logging.info("Received: {}".format(rcv))
    except ValueError:
        logging.error("Received unmanageable string format")
        rcv = "Error format"
    return rcv


def server_mode(ser):
    """
    Running as a server, it will be sniffing for received string.
    And it will send the same string out.
    usage:
    running on port /dev/ttyUSB0 as a server
    $ sudo ./rs485-remote.py /dev/ttyUSB0 --mode server
    """
    logging.info("Listening on port {} ...".format(ser._port))
    while True:
        re_string = receiver(ser)
        if re_string:
            time.sleep(3)
            logging.info("Send string back ...")
            sender(ser, re_string)
            logging.info("Listening on port {} ...".format(ser._port))
            ser.reset_input_buffer()


def client_mode(ser, data_length):
    """
    Running as a clinet and it will sending out a string and wait
    the string send back from server. After receive the string,
    it will check the readback is correct or not.
    Usage:
    running on port /dev/ttymxc1 as a client
    $ sudo ./rs485-remotr.py /dev/ttymxc1 --mode client
    """
    test_str = "{}-{}".format(ser._port, str_generator(data_length))
    sender(ser, test_str)
    for i in range(1, 6):
        logging.info("Attempting receive string... {} time".format(i))
        time.sleep(3)
        readback = receiver(ser)
        if readback:
            if readback == test_str:
                logging.info("Received string is correct!")
                raise SystemExit(0)
            else:
                logging.error("Received string is incorrect!")
                raise SystemExit(1)
    logging.error("Not able to receive string!!")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('device', help='Serial port device e.g. /dev/ttyS1')
    parser.add_argument(
        "--mode",
        choices=["server", "client"],
        type=str,
        help="set running mode, one if {server, client}",
        required=True,
    )
    parser.add_argument("--size", default=16, type=int)
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
    ser = serial_init(
        args.device,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
    )

    if args.mode == "server":
        server_mode(ser)
    else:
        client_mode(ser, args.size)


if __name__ == "__main__":
    main()
