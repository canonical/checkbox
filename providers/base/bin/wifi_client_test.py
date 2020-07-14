#!/usr/bin/env python3
# Copyright 2015 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Gavin Lin <gavin.lin@canonical.com>

"""
This script will run wireless network test automatically.

To see how to use, please run "./wifi_client_test.py --help"
"""
import argparse
import os
import subprocess
import sys
import time


# Configuration file path
CFG_PATH = '/etc/network/interfaces.d/plainbox_wifi_client_test'

# Use ping to check connection? (yes/no)
PING_TEST = 'no'

# Use DHCP to get ip address? (yes/no) (This may be required for ping test)
DHCP_IP = 'no'

# Read arguments
parser = argparse.ArgumentParser(
    description=('This script will test wireless network in client mode.'))
parser.add_argument(
    '-i', '--interface', type=str, help=(
        'The interface which will be tested, default is wlan0'),
    default='wlan0')
parser.add_argument(
    '-s', '--ssid', type=str, help=(
        'SSID of target network, this is required argument'),
    required=True)
parser.add_argument(
    '-k', '--psk', type=str, help=(
        'Pre-shared key of target network, this is optional argument,'
        ' only for PSK protected network'))
if PING_TEST == 'yes':
    parser.add_argument(
        '-p', '--ping', type=str, help=(
            'Server in target network which respond to ping,'
            ' default is ubuntu.com'),
        default='ubuntu.com')
args = parser.parse_args()

# Create wireless network configuration file
wifi_cfg_file = open(CFG_PATH, 'w', encoding='utf-8')
# DHCP or static ip
if DHCP_IP == 'yes':
    wifi_cfg_file.write('iface ' + args.interface + ' inet dhcp\n')
else:
    wifi_cfg_file.write('iface ' + args.interface + ' inet static\n')
    wifi_cfg_file.write('    address 192.168.1.1\n')
# SSID
wifi_cfg_file.write('    wpa-ssid ' + '\"' + args.ssid + '\"\n')
# Opened network or PSK protected network
if not args.psk:
    wifi_cfg_file.write('    wpa-key-mgmt NONE\n')
else:
    wifi_cfg_file.write('    wpa-psk ' + '\"' + args.psk + '\"\n')
wifi_cfg_file.close()

# Bring up the interface
subprocess.call(['ip', 'link', 'set', args.interface, 'up'])
time.sleep(15)
subprocess.call(['ifdown', args.interface])
time.sleep(15)
subprocess.call(['ifup', args.interface])
time.sleep(15)

# Check connection
if PING_TEST == 'yes':
    test_result = subprocess.call([
        'ping', '-c', '5', '-I', args.interface, args.ping])
    if not test_result:
        print('Connection test passed')
        exit_code = 0
    else:
        print('Connection test failed')
        exit_code = 1
else:
    test_result = subprocess.check_output([
        'iw', args.interface, 'link']).decode()
    if test_result.find('SSID') != -1:
        print('Connection test passed')
        exit_code = 0
    else:
        print('Connection test failed')
        exit_code = 1

# Bring down the interface and remove configuration file after test
subprocess.call(['ifdown', args.interface])
time.sleep(15)
os.remove(CFG_PATH)
sys.exit(exit_code)
