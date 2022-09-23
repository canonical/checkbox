#!/usr/bin/env python3
"""
Check that it's possible to establish a http connection against
ubuntu.com
"""
from argparse import ArgumentParser
import http.client
import urllib.request
import urllib.error
import urllib.parse
import sys


def check_url(url):
    """
    Open URL and return True if no exceptions were raised
    """
    try:
        urllib.request.urlopen(url)
    except (urllib.error.URLError, http.client.InvalidURL):
        return False

    return True


def main():
    """
    Check HTTP and connection
    """
    parser = ArgumentParser()
    parser.add_argument('-u', '--url',
                        action='store',
                        default='http://cdimage.ubuntu.com',
                        help='The target URL to try. Default is %(default)s')
    parser.add_argument('-a', '--auto',
                        action='store_true',
                        default=False,
                        help='Runs in Automated mode, with no visible output')

    args = parser.parse_args()

    url = {"http": args.url}

    results = {}
    for protocol, value in url.items():
        results[protocol] = check_url(value)

    bool2str = {True: 'Success', False: 'Failed'}
    message = ("HTTP connection: %(http)s\n"
               % dict([(protocol, bool2str[value])
                       for protocol, value in results.items()]))

    if not args.auto:
        if all(results.values()):
            print(message)
        else:
            print(message, file=sys.stderr)

    if any(results.values()):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
