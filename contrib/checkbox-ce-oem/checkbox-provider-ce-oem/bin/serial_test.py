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
import time
import logging
import os
import random
import string
import serial.rs485


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
        type: str = None,
        group: list = None,
        baudrate: int = None,
        bytesize: int = None,
        parity: str = None,
        stopbits: int = None,
        timeout: int = None,
        datasize: int = None,
        rs485_settings: dict = None,
    ) -> None:
        self.node = node
        self.type = type if type else "USB"
        self.baudrate = baudrate if baudrate else 115200
        self.bytesize = bytesize if bytesize else serial.EIGHTBITS
        self.parity = parity if parity else serial.PARITY_NONE
        self.stopbits = stopbits if stopbits else serial.STOPBITS_ONE
        self.timeout = timeout if timeout else 3
        self.datasize = datasize if datasize else 1024
        """
        Assign default config since no addtional RS485 config that
        input by user.
        """
        self.rs485_settings = (
            rs485_settings
            if rs485_settings
            else {
                "rts_level_for_tx": True,
                "rts_level_for_rx": False,
                "delay_before_tx": 0.0,
                "delay_before_rx": 0.0,
            }
        )
        group = group if group else []
        self.ser = self.serial_init(node)
        self.group = []
        for ser in group:
            try:
                self.group.append(self.serial_init(ser))
            except Exception:
                raise SystemError("Failed to init serial port: {}".format(ser))

    def serial_init(self, node: str) -> serial.Serial:
        """Create a serial.Serial object based on the class variables"""
        ser = serial.Serial(
            node,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
        )
        if self.type == "RS485":
            """
            Mapping RS485 node with specific RS485 settings to
            handle different rts_level.
            """
            if node in self.rs485_settings:
                ser.rs485_mode = serial.rs485.RS485Settings(
                    rts_level_for_tx=self.rs485_settings[node].get(
                        "rts_level_for_tx"
                    )
                    == "True",
                    rts_level_for_rx=self.rs485_settings[node].get(
                        "rts_level_for_rx"
                    )
                    == "True",
                    delay_before_tx=float(
                        self.rs485_settings[node].get("delay_before_tx")
                    ),
                    delay_before_rx=float(
                        self.rs485_settings[node].get("delay_before_rx")
                    ),
                )
            else:
                """
                Use default RS485 setting if node does not have it own config
                """
                ser.rs485_mode = serial.rs485.RS485Settings(
                    rts_level_for_tx=self.rs485_settings.get(
                        "rts_level_for_tx"
                    ),
                    rts_level_for_rx=self.rs485_settings.get(
                        "rts_level_for_rx"
                    ),
                    delay_before_tx=self.rs485_settings.get("delay_before_tx"),
                    delay_before_rx=self.rs485_settings.get("delay_before_rx"),
                )
            logging.info(
                "Init port %s with RS485 config "
                "rts_level_for_tx: %s "
                "rts_level_for_rx: %s "
                "delay_befor_tx: %s "
                "delay_befor_rx: %s ",
                node,
                ser.rs485_mode.rts_level_for_tx,
                ser.rs485_mode.rts_level_for_rx,
                ser.rs485_mode.delay_before_tx,
                ser.rs485_mode.delay_before_rx,
            )
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        return ser

    def send(self, data: bytes) -> None:
        try:
            self.ser.write(data)
            logging.info("Sent: {}".format(data.decode()))
        except Exception:
            logging.exception("Not able to send data!")

    def recv(self) -> bytes:
        rcv = ""
        try:
            rcv = self.ser.read(self.datasize)
            if rcv:
                logging.info("Received: {}".format(rcv.decode()))
        except Exception:
            logging.exception(
                "Received unmanageable string format {}".format(rcv)
            )
            return None
        return rcv


def generate_random_string(length):
    """Generate random ascii string"""
    letters = string.ascii_letters + string.digits + string.punctuation
    return "".join(random.choice(letters) for _ in range(length))


def parse_rs485_config(rs485_conf: str = None):
    rs485_conf_lists = {}
    """
    Parse RS485 config,
    e.g.
    Input:
    RS485_CONFIG = "/dev/ttySC0:True:False:0.0:0.0
    /dev/ttySC2:True:False:0.0:0.0"

    Output:
    rs485_conf_lists = {
        "/dev/ttySC0": {
            "rts_level_for_tx": True,
            "rts_level_for_rx": False,
            "delay_before_tx: 0.0,
            "delay_before_rx: 0.0,
        }
        "/dev/ttySC2": {
            "rts_level_for_tx": True,
            "rts_level_for_rx": False,
            "delay_before_tx: 0.0,
            "delay_before_rx: 0.0,
        }
    }
    """
    for rs485_conf_list in rs485_conf.split():
        node, rts_tx, rts_rx, delay_tx, delay_rx = rs485_conf_list.split(":")
        rs485_conf_lists[node] = {
            "rts_level_for_tx": rts_tx,
            "rts_level_for_rx": rts_rx,
            "delay_before_tx": delay_tx,
            "delay_before_rx": delay_rx,
        }
    return rs485_conf_lists


def server_mode(
    node,
    type=None,
    group=None,
    baudrate=None,
    bytesize=None,
    parity=None,
    stopbits=None,
    timeout=None,
    datasize=None,
    rs485_settings=None,
) -> None:
    """
    Running as a server, it will be sniffing for received string.
    And it will send the same string out.
    usage:
    running on port /dev/ttyUSB0 as a server
    $ sudo ./serial_test.py /dev/ttyUSB0 --mode server --type USB
    """
    ser = Serial(
        node,
        type,
        group,
        baudrate,
        bytesize,
        parity,
        stopbits,
        timeout,
        datasize,
        rs485_settings,
    )
    logging.info("Listening on port {} ...".format(ser.node))
    while True:
        data = ser.recv()
        if data:
            time.sleep(3)
            logging.info("Send string back ...")
            ser.send(data)
            logging.info("Listening on port {} ...".format(ser.node))


def client_mode(
    node,
    type=None,
    group=None,
    baudrate=None,
    bytesize=None,
    parity=None,
    stopbits=None,
    timeout=None,
    datasize=1024,
    rs485_settings=None,
):
    """
    Running as a clinet and it will sending out a string and wait
    the string send back from server. After receive the string,
    it will check the readback is correct or not.
    Usage:
    running on port /dev/ttymxc1 as a client
    $ sudo ./serial_test.py /dev/ttymxc1 --mode client --type RS485
    """
    ser = Serial(
        node,
        type,
        group,
        baudrate,
        bytesize,
        parity,
        stopbits,
        timeout,
        datasize,
        rs485_settings,
    )

    # clean up the garbage in the serial before test
    while ser.recv():
        continue

    random_string = generate_random_string(datasize)
    ser.send(random_string.encode())
    for i in range(1, 6):
        logging.info("Attempting receive string... {} time".format(i))
        readback = ser.recv()
        time.sleep(3)
        if readback:
            if readback.decode() == random_string:
                logging.info("[PASS] Received string is correct!")
                raise SystemExit(0)
            else:
                logging.error("[FAIL] Received string is incorrect!")
                raise SystemExit(1)
    logging.error("[FAIL] Not able to receive string!!")
    raise SystemExit(1)


def console_mode(
    node,
    type=None,
    group=None,
    baudrate=None,
    bytesize=None,
    parity=None,
    stopbits=None,
    timeout=None,
    datasize=None,
    rs485_settings=None,
):
    """
    Test the serial port when it is in console mode
    This test requires DUT to loop back it self.
    For example: connect the serial console port to the USB port via
    serial to usb dongle
    """
    ser = Serial(
        node,
        type,
        group,
        baudrate,
        bytesize,
        parity,
        stopbits,
        timeout,
        datasize,
        rs485_settings,
    )
    try:
        # Send 'Enter Key'
        logging.info("Sending 'Enter Key'...")
        ser.send(os.linesep.encode())
        response = ser.recv().decode()
        # ":~$" is the pattern for the DUT after logging in
        # "login:" is the pattern for the DUT before logging in
        if ":~$" in response or "login:" in response:
            logging.info("[PASS] Serial console test successful.")
        else:
            logging.error("[FAIL] Serial console test failed.")
            logging.error("Expected response should contain ':~$' or 'login:'")
            raise SystemExit(1)
    except Exception:
        logging.exception("Caught an exception.")
        raise SystemExit(1)


def create_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("node", help="Serial port device node e.g. /dev/ttyS1")
    parser.add_argument(
        "--mode",
        choices=["server", "client", "console"],
        type=str,
        help="Running mode",
        required=True,
    )
    parser.add_argument(
        "--type",
        type=str,
        help="The type of serial port (e.g. RS485, RS422, RS232, USB)",
        default="USB",
    )
    parser.add_argument(
        "--group",
        type=str,
        help="The group of serial ports that needed to be brought up also",
        nargs="*",
        default=[],
    )
    parser.add_argument(
        "--baudrate",
        help="Baud rate for the serial ports",
        default=115200,
        type=int,
    )
    parser.add_argument(
        "--bytesize",
        choices=[
            serial.FIVEBITS,
            serial.SIXBITS,
            serial.SEVENBITS,
            serial.EIGHTBITS,
        ],
        type=int,
        help="Bytesize",
        default=serial.EIGHTBITS,
    )
    parser.add_argument(
        "--parity",
        choices=[
            serial.PARITY_NONE,
            serial.PARITY_EVEN,
            serial.PARITY_ODD,
            serial.PARITY_MARK,
            serial.PARITY_SPACE,
        ],
        type=lambda c: c.upper(),
        help="Parity",
        default=serial.PARITY_NONE,
    )
    parser.add_argument(
        "--stopbits",
        choices=[serial.STOPBITS_ONE, serial.STOPBITS_TWO],
        type=int,
        help="Stopbits",
        default=serial.STOPBITS_ONE,
    )
    parser.add_argument(
        "--datasize",
        type=int,
        help="Data size to send and receive",
        default=1024,
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout to receive",
        default=3,
    )
    parser.add_argument(
        "--rs485-config",
        type=str,
        help="RS485 configuration",
    )
    return parser


def main():
    parser = create_args()
    args = parser.parse_args()

    init_logger()
    if args.rs485_config:
        rs485_settings = parse_rs485_config(args.rs485_config)
    else:
        rs485_settings = None

    if args.mode == "server":
        server_mode(
            args.node,
            args.type,
            args.group,
            args.baudrate,
            args.bytesize,
            args.parity,
            args.stopbits,
            args.timeout,
            args.datasize,
            rs485_settings,
        )
    elif args.mode == "client":
        client_mode(
            args.node,
            args.type,
            args.group,
            args.baudrate,
            args.bytesize,
            args.parity,
            args.stopbits,
            args.timeout,
            args.datasize,
            rs485_settings,
        )
    elif args.mode == "console":
        console_mode(
            args.node,
            args.type,
            args.group,
            args.baudrate,
            args.bytesize,
            args.parity,
            args.stopbits,
            args.timeout,
            args.datasize,
            rs485_settings,
        )
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
