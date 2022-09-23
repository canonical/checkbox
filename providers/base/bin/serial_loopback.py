#!/usr/bin/env python3
# Copyright 2018 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Vinay Simha BN <vinaysimha@inforcecomputing.com>
#    Jonathan Cave <jonathan.cave@canonical.com>

import argparse

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('device', help='Serial port device e.g. /dev/ttyS1')
    parser.add_argument('--baudrate', default=115200, type=int)
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
    print("Test parameters:", vars(args))
    with serial.Serial(args.device,
                       baudrate=args.baudrate,
                       bytesize=args.bytesize,
                       parity=args.parity,
                       stopbits=args.stopbits,
                       timeout=1) as ser:
        test_str = 'loopback\n'
        ser.write(test_str.encode('UTF-8'))
        rcv = ser.readline().decode('UTF-8')
        print("Sent:", repr(test_str))
        print("Received:", repr(rcv))
        if rcv != test_str:
            raise SystemExit('SERIAL LOOPBACK TEST FAILED')
        print("SERIAL LOOPBACK TEST PASSED")


if __name__ == '__main__':
    main()
