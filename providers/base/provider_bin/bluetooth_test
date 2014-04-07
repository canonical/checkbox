#!/usr/bin/env python3

from subprocess import CalledProcessError, check_output, STDOUT
from tempfile import TemporaryDirectory
import argparse
import logging
import os
import re
import sys
import time

OBEX_RESPONSE_CODE = {
    0x10: "Continue",
    0x20: "OK, Success",
    0x21: "Created",
    0x22: "Accepted",
    0x23: "Non-Authoritative Information",
    0x24: "No Content",
    0x25: "Reset Content",
    0x26: "Partial Content",
    0x30: "Multiple Choices",
    0x31: "Moved Permanently",
    0x32: "Moved temporarily",
    0x33: "See Other",
    0x34: "Not modified",
    0x35: "Use Proxy",
    0x40: "Bad Request - server couldn't understand request",
    0x41: "Unauthorized",
    0x42: "Payment required",
    0x43: "Forbidden - operation is understood but refused",
    0x44: "Not Found",
    0x45: "Method not allowed",
    0x46: "Not Acceptable",
    0x47: "Proxy Authentication required",
    0x48: "Request Time Out",
    0x49: "Conflict",
    0x4A: "Gone",
    0x4B: "Length Required",
    0x4C: "Precondition failed",
    0x4D: "Requested entity too large",
    0x4E: "Request URL too large",
    0x4F: "Unsupported media type",
    0x50: "Internal Server Error",
    0x51: "Not Implemented",
    0x52: "Bad Gateway",
    0x53: "Service Unavailable",
    0x54: "Gateway Timeout",
    0x55: "HTTP version not supported",
    0x60: "Database Full",
    0x61: "Database Locked"
}


class ObexFTPTest:
    def __init__(self, path, btaddr):
        self._file = path
        self._filename = os.path.basename(path)
        self._filesize = os.path.getsize(path)
        self._btaddr = btaddr

    def _error_helper(self, pattern, **extra):
        # obexftp 0.23 version returns 255 on success, see:
        # http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=549623
        if 'exception' in extra:
            exception = extra.get('exception')
            if re.search(pattern, exception.output):
                logging.info("PASS")
                return 0
            else:
                logging.error(exception.output.strip())
                if exception.returncode in OBEX_RESPONSE_CODE:
                    logging.error(OBEX_RESPONSE_CODE.get(exception.returncode))
                return exception.returncode
        elif 'output' in extra:
            output = extra.get('output')
            if re.search(pattern, output):
                logging.info("PASS")
                return 0
            else:
                logging.error(output)
                return 1

    def _run_command(self, command, expected_pattern, cwd=None):
        try:
            output = check_output(command, stderr=STDOUT,
                                  universal_newlines=True, cwd=cwd)
            return self._error_helper(expected_pattern, output=output)
        except OSError as e:
            logging.error(e)
            logging.error("Binary not found, "
                          "maybe obexftp is not installed")
        except CalledProcessError as e:
            return self._error_helper(expected_pattern, exception=e)
        finally:
            # Let the Bluetooth stack enough time to close the connection
            # before doing another test
            time.sleep(5)

    def send(self):
        logging.info("[ Send test ]".center(80, '='))
        logging.info("Using {} as a test file".format(self._filename))
        logging.info("Sending {} to {}".format(self._file, self._btaddr))
        return self._run_command(["obexput", "-b", self._btaddr, self._file],
                                 "Sending.*?done")

    def browse(self):
        logging.info("[ Browse test ]".center(80, '='))
        logging.info("Checking {} for {}".format(self._btaddr, self._file))
        logging.info("Will check for a filesize of {}".format(self._filesize))
        return self._run_command(["obexftp", "-b", self._btaddr, "-l"],
                                 '{}.*?size="{}"'.format(self._filename,
                                                         self._filesize))

    def remove(self):
        logging.info("[ Remove test ]".center(80, '='))
        logging.info("Removing {} from {}".format(self._filename,
                                                  self._btaddr))
        return self._run_command(
            ["obexrm", "-b", self._btaddr, self._filename],
            "Sending.*?done")

    def get(self):
        with TemporaryDirectory() as tmpdirname:
            logging.info("[ Get test ]".center(80, '='))
            logging.info("Getting file {} from {}".format(self._filename,
                                                          self._btaddr))
            # Dont trust "get" returncode, it's always 0...
            return self._run_command(
                ["obexget", "-b", self._btaddr, self._filename],
                "Receiving.*?done", cwd=tmpdirname)


def main():
    description = "Bluetooth tests using ObexFTP"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('file', type=argparse.FileType('rb'))
    parser.add_argument('btaddr', help='bluetooth mac address')
    parser.add_argument('action', choices=['send', 'browse', 'remove', 'get'])
    args = parser.parse_args()
    args.file.close()
    # Configure logging as requested
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='%(levelname)s: %(message)s')
    return getattr(ObexFTPTest(args.file.name, args.btaddr), args.action)()

if __name__ == "__main__":
    sys.exit(main())
