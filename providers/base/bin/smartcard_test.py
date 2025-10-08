#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>

from smartcard.Exceptions import (
    NoCardException,
    CardConnectionException,
)
from smartcard.pcsc.PCSCReader import PCSCReader as SCReader
from checkbox_support.helpers.slugify import slugify
from checkbox_support.helpers.timeout import timeout
from smartcard.CardRequest import CardRequest
from smartcard.util import toHexString
from smartcard.System import readers
import argparse
import logging
import sys


class SmartcardTest:
    """
    A class used to test smartcard reader

    :attr logger: console logger
    :type logger: RootLogger

    :attr readers:
        Store the smart card readers detected in this system
    :type readers: list
    """

    logger = logging.getLogger()

    readers = None

    # https://www.eftlab.com/knowledge-base/complete-list-of-apdu-responses
    sw1_list = [
        0x61,
        0x62,
        0x63,
        0x64,
        0x65,
        0x66,
        0x67,
        0x68,
        0x69,
        0x6A,
        0x6B,
        0x6C,
        0x6D,
        0x6E,
        0x6F,
        0x90,
        0x91,
        0x92,
        0x93,
        0x94,
        0x95,
        0x96,
        0x97,
        0x98,
        0x99,
        0x9A,
        0x9D,
        0x9E,
        0x9F,
    ]

    def __init__(self):
        """
        Store the smart card reader object in a private variable
        """
        self.readers = readers()

    def slugify_reader_name(self, name: str) -> str:
        """
        Replacing the illegal character with "-"

        :param name: real name of smartcard reader
        """
        return slugify(name[:40])

    def reader_filter(self, list_type: str, name: SCReader) -> SCReader:
        """
        Filter the smart card reader as contact, contactless, or unfiltered

        :param list_type: contact/contactless/all

        :param name: real name of smartcard reader
        """
        ln = name.name.lower()
        if list_type == "contact":
            if "contactless" not in ln and "-cl" not in ln:
                return name
        elif list_type == "contactless":
            if "contactless" in ln or "-cl" in ln:
                return name
        else:
            return name

    def list_readers(self, list_type: str):
        """
        List smart card readers in stringified format for the resource job

        :param list_type: contact/contactless/all

        """
        for r in self.readers:
            if self.reader_filter(list_type, r):
                print(
                    "smartcard_reader: {}".format(
                        self.slugify_reader_name(r.name)
                    )
                )

    def detect_reader(self, list_type: str):
        """
        Detect smart card readers

        :param list_type: contact/contactless/all

        """
        count = 0
        for r in self.readers:
            if self.reader_filter(list_type, r):
                self.logger.info(r.name)
                count = count + 1
        if count < 1:
            raise SystemExit("There is no smartcard reader in this system")

    def get_real_reader_instance(self, reader: str):
        """
        Using the stringified smartcard reader name
        to get the actual reader instance

        :param reader: Stringified smart card reader name
        """
        for r in self.readers:
            if self.slugify_reader_name(r.name) == reader:
                return r

    def get_connection(self, reader: str):
        """
        Connect to the smartcard reader

        :param reader: Stringified smart card reader name
        """
        sc_reader = self.get_real_reader_instance(reader)
        if sc_reader:
            try:
                connection = sc_reader.createConnection()
                connection.connect()
                self.logger.info("[{}] connected".format(sc_reader))
                return connection
            except (NoCardException, CardConnectionException):
                raise SystemExit("no card inserted or card is unsupported")
        raise SystemExit("no smartcard reader")

    @timeout(30)
    def detect_smartcard(self, reader: str):
        """
        Detect smartcard insertion and removal in the smartcard reader

        :param reader: Stringified smart card reader name
        """
        real_reader = self.get_real_reader_instance(reader)
        if real_reader is None:
            raise SystemExit(
                "No real reader was found matching this name: {}".format(
                    reader
                )
            )

        self.logger.info(
            "Smartcard insertion and removal detection test is starting"
        )
        self.logger.info(
            "Please insert and remove the smartcard within 30 seconds.\n"
        )

        cardrequest = CardRequest(timeout=30, newcardonly=True)
        cards = []  # list[smartcard.Card]
        while len(cards) == 0:
            currentcards = cardrequest.waitforcardevent()
            for card in currentcards:
                if (
                    card not in cards
                    and isinstance(card.reader, str)
                    and real_reader.name == card.reader
                ):
                    cards.append(card)
                    self.logger.info("Smart card insertion detected:")
                    self.logger.info(card)
                    self.logger.info(
                        "\nPlease remove it to test the removal detection\n"
                    )
                    break

        cardrequest = CardRequest(timeout=30, newcardonly=False)
        while True:
            currentcards = cardrequest.waitforcardevent()
            for card in cards:
                if card not in currentcards:
                    cards.remove(card)
                    self.logger.info("Smart card removal detected:")
                    self.logger.info(card)
                    return

    def send_apdu_test(self, reader: str):
        """
        Send the APDU command to the smart card and verify the response.

        :param reader: Stringified smart card reader name
        """
        sc_conn = self.get_connection(reader)
        if sc_conn:
            self.logger.info("ATR from smartcard:")
            self.logger.info(toHexString(sc_conn.getATR()))
            # This is a sample APDU command
            SELECT = [0xA0, 0xA4, 0x00, 0x00, 0x02]
            DF_TELECOM = [0x7F, 0x10]
            data, sw1, sw2 = sc_conn.transmit(SELECT + DF_TELECOM)
            if sw1 in self.sw1_list:
                self.logger.info("Send/Receive APDU command is working")
                return
        raise SystemExit("Could not working for this smartcard reader")

    def _args_parsing(self, args=sys.argv[1:]):
        """
        command line arguments parsing

        :param args: arguments from sys
        :type args: sys.argv
        """
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
            default="all",
            choices=["contact", "contactless", "all"],
        )

        # Add parser for listing smartcard readers for resource job
        parser_detect_reader = subparsers.add_parser(
            "detect_reader",
            help="count smartcard readers on this system",
        )
        parser_detect_reader.add_argument(
            "-t",
            "--type",
            default="all",
            choices=["contact", "contactless", "all"],
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
            # list_readers("all")
            return self.list_readers(args.type)
        elif args.test_type == "detect_reader":
            # detect_reader("all")
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
