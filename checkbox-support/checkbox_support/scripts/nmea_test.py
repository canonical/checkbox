#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#     Jonathan Cave <jonathan.cave@canonical.com>

import argparse
import os
from stat import S_ISCHR

import pynmea2
import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('device', help='Serial port device e.g. /dev/ttyS1')
    parser.add_argument('--baudrate', default=9600, type=int)
    parser.add_argument('--bytesize', choices=[5, 6, 7, 8], type=int,
                        help='set bytesize, one of {5, 6, 7, 8}, default: 8',
                        default=8)
    parser.add_argument('--parity', choices=['N', 'E', 'O', 'S', 'M'],
                        type=lambda c: c.upper(),
                        help='set parity, one of {N E O S M}, default: N',
                        default='N')
    parser.add_argument('--stopbits', choices=[1, 2], type=int,
                        help='set stopbits, one of {1, 2}, default: 1',
                        default=1)
    args = parser.parse_args()
    print('Device name: {}'.format(args.device))
    mode = os.stat(args.device).st_mode
    if not S_ISCHR(mode):
        raise SystemExit('Expected a character device file')
    with serial.Serial(args.device,
                       baudrate=args.baudrate,
                       bytesize=args.bytesize,
                       parity=args.parity,
                       stopbits=args.stopbits,
                       timeout=1) as f_dev:
        attempts = 30
        print('Attempting to parse {} sentences:'.format(attempts))
        bad_msg_count = 0
        for _ in range(attempts):
            try:
                str_from_serial = f_dev.readline().decode('UTF-8')
            except UnicodeDecodeError:
                print(' Bad sentence: couldn\'t decode line')
                bad_msg_count += 1
                continue
            try:
                msg = pynmea2.parse(str_from_serial, check=True)
            except pynmea2.ChecksumError:
                print(' Bad sentence: checksum error')
                bad_msg_count += 1
                continue
            except pynmea2.ParseError:
                print(' Bad sentence: parse error')
                bad_msg_count += 1
                continue
            print(' Got sentence type: {}'.format(msg.sentence_type))
        print('Total bad sentences: {}'.format(bad_msg_count))
        if bad_msg_count > 3:
            raise SystemExit('Too many bad NMEA sentences')
        else:
            print('Acceptable number of bad NMEA sentences')


if __name__ == '__main__':
    main()
