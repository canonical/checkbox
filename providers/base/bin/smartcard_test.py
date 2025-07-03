#!/usr/bin/env python3
# Copyright 2015-2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>

from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.Exceptions import NoCardException, CardConnectionException
from smartcard.util import toHexString
from smartcard.System import readers
from time import sleep
import argparse
import logging
import sys
import re


class SmartcardObserver(CardObserver):
    def update(self, observable, actions):
        (addedcards, removedcards) = actions
        for card in addedcards:
            print("+Inserted: ", toHexString(card.atr), flush=True)
        for card in removedcards:
            print("-Removed: ", toHexString(card.atr), flush=True)


class SmartcardTest:

    logger = logging.getLogger()

    readers = None

    def __init__(self):
        self.readers = readers()

    def stringfy_reader_name(self, name: str) -> str:
        pattern = r"[^a-zA-Z0-9]+"
        return re.sub(pattern, "-", name[:40])

    def reader_filter(self, list_type: str, name: str) -> str:
        lt = list_type.lower()
        ln = name.name.lower()
        if lt == "contact":
            if "contactless" not in ln and "-cl" not in ln:
                return name
        elif lt == "contactless":
            if "contactless" in ln or "-cl" in ln:
                return name
        else:
            return name

    def list_readers(self, list_type: str):
        for r in self.readers:
            if self.reader_filter(list_type, r):
                print(
                    "smartcard_reader: {}".format(
                        self.stringfy_reader_name(r.name)
                    )
                )

    def detect_reader(self, list_type: str):
        count = 0
        for r in self.readers:
            if self.reader_filter(list_type, r):
                self.logger.info(r.name)
                count = count + 1
        if count < 1:
            raise SystemExit("There is no smartcard reader in this system")

    def get_real_reader_instance(self, reader: str):
        for r in self.readers:
            if self.stringfy_reader_name(r.name) == reader:
                return r

    def get_connection(self, reader: str):
        sc_reader = self.get_real_reader_instance(reader)
        if sc_reader:
            try:
                connection = sc_reader.createConnection()
                connection.connect()
                return connection
            except (NoCardException, CardConnectionException):
                raise SystemExit("no card inserted or card is unsupported")
            self.logger.info("[{}] connected".format(sc_reader))

    def detect_smartcard(self, reader: str):
        cardmonitor = CardMonitor()
        cardobserver = SmartcardObserver()
        cardmonitor.addObserver(cardobserver)

        self.logger.info("Please insert/remove smartcard")
        sleep(30)  # Monitor for 30 seconds
        self.logger.info("Test ended")

        cardmonitor.deleteObserver(cardobserver)  # Clean up observer

    def send_apdu_test(self, reader: str):
        sc_conn = self.get_connection(reader)
        if sc_conn:
            self.logger.info("ATR from smartcard:")
            self.logger.info(toHexString(sc_conn.getATR()))
            select = [0xA0, 0xA4, 0x00, 0x00, 0x02]
            df_telecom = [0x7F, 0x10]
            data, sw1, sw2 = sc_conn.transmit(select + df_telecom)
            if sw1 in [0x6E, 0x9F]:
                self.logger.info("Send/Receive APDU command is working")
                return
        raise SystemExit("Could not working for this smartcard reader")

    def _args_parsing(self, args=sys.argv[1:]):
        parser = argparse.ArgumentParser(
            prog="Smartcard validator",
            description="use to test smartcard reader could work",
        )

        subparsers = parser.add_subparsers(dest="test_type")
        subparsers.required = True

        # Add parser for listing smartcard readers for resource job
        parser_resources = subparsers.add_parser(
            "resources",
            help="list smartcard readers on this system to resources",
        )
        parser_resources.add_argument(
            "-t",
            "--type",
            type=str,
            default="All",
            help="""
                  List All/contact/contactless smartcard reader for testing
                  (default: %(default)s)
                 """,
        )

        # Add parser for listing smartcard readers for resource job
        parser_detect_reader = subparsers.add_parser(
            "detect_reader",
            help="count smartcard readers on this system",
        )
        parser_detect_reader.add_argument(
            "-t",
            "--type",
            type=str,
            default="All",
            help="""
                  List All/contact/contactless smartcard reader for testing
                  (default: %(default)s)
                 """,
        )

        # Add parser for detecting smartcard insert/remove
        parser_detect = subparsers.add_parser(
            "detect_card", help="Detecting smartcard insert/remove"
        )
        parser_detect.add_argument(
            "-r",
            "--reader",
            type=str,
            help="smartcard reader for testing",
        )

        # Add parser for sending/receiving APDU command to/from smartcard
        parser_send = subparsers.add_parser(
            "send", help="Sending/receiving APDU command to/from smartcard"
        )
        parser_send.add_argument(
            "-r",
            "--reader",
            type=str,
            help="smartcard reader for testing",
        )
        return parser.parse_args(args)

    def function_select(self, args):
        if args.test_type == "resources":
            # list_readers("All")
            return self.list_readers(args.type)
        elif args.test_type == "detect_reader":
            # detect_reader("Broadcom 58200")
            return self.detect_reader(args.type)
        elif args.test_type == "detect_card":
            # detect_smartcard("Broadcom 58200")
            return self.detect_smartcard(args.reader)
        elif args.test_type == "send":
            # send_apdu_test("Broadcom 58200")
            return self.send_apdu_test(args.reader)


def main():
    sc = SmartcardTest()

    # create logger formatter
    log_formatter = logging.Formatter(fmt="%(message)s")

    # set log level
    sc.logger.setLevel(logging.INFO)

    # create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # Add console handler to logger
    sc.logger.addHandler(console_handler)
    sys.exit(sc.function_select(sc._args_parsing()))


if __name__ == "__main__":
    main()
