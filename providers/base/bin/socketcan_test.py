#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import ctypes
import os
import socket
import struct
import sys
import textwrap
import threading
import time


class CANSocket():

    # struct module format strings for CAN packets
    # Normal format:
    #   <   little-endian
    #   I   unsigned int (4)    : CAN-ID + EFF/RTR/ERR Flags
    #   B   unsigned char (1)   : Data length
    #   3x  padding (3 * 1)     : -
    #   8s  char array (8 * 1)  : Data
    FORMAT = "<IB3x8s"
    # Flexible Data (FD) rate format:
    #   <    little-endian
    #   I    unsigned int (4)    : CAN-ID + EFF/RTR/ERR Flags
    #   B    unsigned char (1)   : Data length
    #   B    unsigned char (1)   : FD Flags
    #   2x   padding (2 * 1)     : -
    #   64s  char array (64 * 1) : Data
    FD_FORMAT = "<IBB2x64s"

    CAN_MTU = struct.Struct(FORMAT).size
    CANFD_MTU = struct.Struct(FD_FORMAT).size

    # Socket options from <linux/can/raw.h>
    CAN_RAW_FILTER = 1         # set 0 .. n can_filter(s)
    CAN_RAW_ERR_FILTER = 2     # set filter for error frames
    CAN_RAW_LOOPBACK = 3       # local loopback (default:on)
    CAN_RAW_RECV_OWN_MSGS = 4  # receive my own msgs (default:off)
    CAN_RAW_FD_FRAMES = 5      # allow CAN FD frames (default:off)
    CAN_RAW_JOIN_FILTERS = 6   # all filters must match to trigger

    def __init__(self, interface=None, fdmode=False, loopback=True):
        self.sock = socket.socket(socket.PF_CAN,  # protocol family
                                  socket.SOCK_RAW,
                                  socket.CAN_RAW)
        self._fdmode = fdmode
        self._loopback = loopback
        if interface is not None:
            self._bind(interface)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.sock.close()

    def _bind(self, interface):
        self.sock.bind((interface,))
        if self._fdmode:  # default is off
            self.sock.setsockopt(socket.SOL_CAN_RAW, self.CAN_RAW_FD_FRAMES, 1)
        if not self._loopback:  # default is on
            self.sock.setsockopt(socket.SOL_CAN_RAW, self.CAN_RAW_LOOPBACK, 0)

    def send(self, can_id, data, id_flags=0, fd_flags=0):
        can_id = can_id | id_flags
        if self._fdmode:
            can_pkt = struct.pack(self.FD_FORMAT, can_id, len(data), fd_flags,
                                  data)
        else:
            can_pkt = struct.pack(self.FORMAT, can_id, len(data), data)
        self.sock.send(can_pkt)

    def recv(self):
        can_pkt = self.sock.recv(self.CANFD_MTU)
        nbytes = len(can_pkt)
        if nbytes == self.CANFD_MTU:
            can_id, length, fd_flags, data = struct.unpack(self.FD_FORMAT,
                                                           can_pkt)
        else:
            can_id, length, data = struct.unpack(self.FORMAT, can_pkt)
        can_id &= socket.CAN_EFF_MASK
        return (can_id, data[:length])


def echo_test(args):
    # ID conversion and size check
    print('Using source ID: {}'.format(args.can_id))
    can_id_i = int(args.can_id, 16)
    if can_id_i > 2047 and not args.effid:
        raise SystemExit('ERROR: CAN ID to high for SFF')
    id_flags = 0
    if args.effid:
        print('Setting EFF CAN ID flag')
        id_flags = ctypes.c_ulong(socket.CAN_EFF_FLAG).value

    # Whether to enable local loopback, required for local only test
    # but only want to parse packets from other end if remote
    loopback = not args.remote

    # Default data size is 8 bytes but if testing FD Mode use 64
    data_size = 8
    if args.fdmode:
        data_size = 64
    data_b = os.urandom(data_size)
    print('Sending data: {}'.format(data_b.hex()))

    recv_id_i = None
    recv_data_b = None

    def receive():
        nonlocal recv_id_i
        nonlocal recv_data_b
        print('Opening read socket on {}'.format(args.interface))
        with CANSocket(args.interface, fdmode=args.fdmode,
                       loopback=loopback) as recv_s:
            recv_id_i, recv_data_b = recv_s.recv()

    # Create a receive thread
    recv_t = threading.Thread(target=receive, daemon=True)
    recv_t.start()
    time.sleep(1)

    print('Opening send socket on {}'.format(args.interface))
    # Open socket, will raise OSError on failure
    with CANSocket(args.interface, fdmode=args.fdmode,
                   loopback=loopback) as send_s:
        print('Sending data...', flush=True)
        try:
            send_s.send(can_id_i, data_b, id_flags=id_flags)
        except OSError as e:
            print(e, file=sys.stderr)
            if e.errno == 90:
                raise SystemExit('ERROR: interface does not support FD Mode')
            else:
                raise SystemExit('ERROR: OSError on attempt to send')

    recv_t.join(10)
    if recv_t.is_alive():
        raise SystemExit('ERROR: Timeout waiting to receive data')

    print('Received packet')
    print('  ID  : {:x}'.format(recv_id_i))
    print('  Data: {}'.format(recv_data_b.hex()))
    if recv_id_i != can_id_i or recv_data_b != data_b:
        raise SystemExit('ERROR: ID/Data received does not match sent')

    print('\nPASSED')


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='SocketCAN Tests',
        epilog=textwrap.dedent('''
        Examples:
            socketcan_test.py can0 123
            socketcan_test.py can0 212 --remote
            socketcan_test.py can0 FA123 --effid
            socketcan_test.py can0 E407DB --effid --fdmode''').lstrip())
    parser.add_argument('interface', type=str, help='Interface name e.g. can0')
    parser.add_argument('can_id', type=str, help=textwrap.dedent('''
        CAN ID of source in Hex, max of 11 bits using Standard Frame
        Format (SFF). Specifying use of Extended Frame Format (EFF)
        allows the use of up to 29 bit IDs.''').lstrip())
    parser.add_argument('--remote', action='store_true',
                        help='Expect a remote device to echo the test packet')
    parser.add_argument('--effid', action='store_true',
                        help='Use EFF ID (CAN 2.0 B)')
    parser.add_argument('--fdmode', action='store_true',
                        help='Attempt to send 64 bytes of data i.e. FD mode')
    parser.set_defaults(func=echo_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
