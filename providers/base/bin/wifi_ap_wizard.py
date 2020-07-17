#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>

"""This program talks to wifi-ap.setup-wizard and sets up predefined AP"""

from checkbox_support.interactive_cmd import InteractiveCommand
import select
import subprocess
import sys


class InteractiveCommandWithShell(InteractiveCommand):
    # this exists only to everride how subprocess.Popen is called (the addition
    # of shell=True. If InteractiveCommand gets this as default, or an option
    # this class won't be needed
    def start(self):
        self._proc = subprocess.Popen(
            self._args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, shell=True)
        self._is_running = True
        self._poller = select.poll()
        self._poller.register(self._proc.stdout, select.POLLIN)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(
            'Usage: wifi_ap_wizard.py WLAN_INTERFACE SHARED_INTERFACE')
    wlan_iface = sys.argv[1]
    shared_iface = sys.argv[2]

    with InteractiveCommandWithShell('wifi-ap.setup-wizard') as wizard:
        steps = [
            ('Which SSID you want to use for the access point',
                'Ubuntu_Wizard'),
            ('Do you want to protect your network with a WPA2 password', 'y'),
            ('Please enter the WPA2 passphrase', 'Test1234'),
            ('Insert the Access Point IP address', '192.168.42.1'),
            ('How many host do you want your DHCP pool to hold to', '100'),
            ('Do you want to enable connection sharing?', 'y'),
            ('Which network interface you want to use for connection sharing?',
                shared_iface),
            ('Do you want to enable the AP now?', 'y'),
        ]
        iface_choice_prompt = "Which wireless interface"
        wizard.wait_for_output()
        first_prompt = wizard.read_all()

        if iface_choice_prompt in first_prompt:
            wizard.writeline(wlan_iface)
        else:
            # the prompt is already consumed, so let's write a response
            wizard.writeline(steps[0][1])
            # and proceed with next steps
            steps = steps[1:]

        for prompt, response in steps:
            if wizard.wait_until_matched(prompt, 1) is None:
                raise SystemExit('Did not get prompted ("{}")'.format(prompt))
            wizard.writeline(response)


if __name__ == '__main__':
    main()
