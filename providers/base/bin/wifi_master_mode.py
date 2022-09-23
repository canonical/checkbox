#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Po-Hsu Lin <po-hsu.lin@canonical.com>

import argparse
import logging
import os
import sys
import subprocess
import tempfile


class WifiMasterMode():

    """Make system to act as an 802.11 Wi-Fi Access Point."""

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--protocol', default='g',
                            choices=['a', 'b', 'g', 'ad'],
                            help="802.11 protocol, possible value: a/b/g/ad")
        parser.add_argument('--auto', action='store_true',
                            help="Run in the automated mode")
        args = parser.parse_args()

        data_dir = ""
        try:
            data_dir = os.environ['PLAINBOX_PROVIDER_DATA']
        except KeyError:
            logging.error("PLAINBOX_PROVIDER_DATA variable not set")
            return 1
        logging.info("Provider data dir: {}".format(data_dir))

        wifi_dev = "wlan0"
        try:
            wifi_dev = os.environ['WIFI_AP_DEV']
        except KeyError:
            logging.info("WIFI_AP_DEV variable not set, defaulting to wlan0")
        logging.info("Wi-Fi adapter: {}".format(wifi_dev))

        conf_in = os.path.join(data_dir, 'hostapd.conf.in')
        if not os.path.isfile(conf_in):
            logging.error("Couldn't find {}".format(conf_in))
            return 1

        with tempfile.NamedTemporaryFile(mode='w+t') as conf_file_out:
            with open(conf_in, "r") as conf_file_in:
                data_in = conf_file_in.read()
                data_out = data_in.replace("$PROTOCOL", args.protocol)
                data_out = data_out.replace("$WIFI-DEV-NAME", wifi_dev)
                conf_file_out.write(data_out)
                conf_file_out.flush()

            if args.auto:
                child = subprocess.Popen(['hostapd', '-d', conf_file_out.name],
                                         stdout=subprocess.PIPE,
                                         universal_newlines=True)
                log = ''
                while child.poll() is None:
                    output = child.stdout.readline()
                    log += output
                    if 'AP-ENABLED' in output:
                        logging.info(output)
                        logging.info("AP successfully established.")
                        child.terminate()
                if child.poll() != 0:
                    output = child.stdout.read()
                    logging.error(log + output)
                    logging.error('AP failed to start')
                return child.poll()
            else:
                # Print and flush this or it will get buffered during test
                print("Hit any key to start the Access Point, a second key " +
                      "press will stop the Access Point:")
                sys.stdout.flush()
                input()

                try:
                    child = subprocess.Popen(['hostapd', conf_file_out.name])

                    # kill the  process on input
                    input()
                finally:
                    child.terminate()


if __name__ == "__main__":
    WifiMasterMode().main()
