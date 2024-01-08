#!/usr/bin/env python3

import argparse
import ctypes
import os
import socket
import sys
import time
import datetime
import logging
from socketcan_socket import CANSocket, prepare_can_link


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


def start_echo_server(interface, fd_mode, delay=0.001):
    """
    Start CAN Echo server

    Args:
        interface (str):    network interface of SocketCAN, e.g. can0
        fd_mode (bool):     FD mode enable
        delay (float):      The time delay before echo CAN frame
    """
    logging.info("Initial CAN Link object with %s", interface)
    with prepare_can_link(interface, fd_mode):
        logging.info('Start SocketCAN echo server')
        can_socket = CANSocket(interface, fd_mode)
        while True:
            recv_pkt = can_socket.recv()
            recv_id, recv_data = can_socket.destruct_packet(recv_pkt)
            logging.info('Received packet')
            logging.info('  ID  : %s', '{:x}'.format(recv_id))
            logging.info('  Data: %s', recv_data.hex())
            time.sleep(delay)
            if recv_id > 2047:
                id_flags = socket.CAN_EFF_FLAG
            else:
                id_flags = 0

            client_fd_mode = True if len(recv_data) == 64 else False
            logging.info('Echo data back...')
            try:
                can_pkt = can_socket.struct_packet(
                    recv_id, recv_data, id_flags, fd_frame=client_fd_mode)
                can_socket.send(can_pkt)
            except OSError as e:
                logging.error(e)
                if e.errno == 90:
                    raise SystemExit(
                        'ERROR: interface does not support FD Mode')
                else:
                    raise SystemExit('ERROR: OSError on attempt to send')


def _random_can_data(can_id, eff_flag, data_size):
    """
    Generate CAN frame data with specific data length

    Args:
        can_id (str):       CAN ID
        eff_flag (bool):    EFF CAN ID Enable
        data_size (int):    The data length

    Return:
        can_id_int (int):   CAN ID
        data_bytes (byte):  Random data with byte format
        id_flag (int):      CAN ID Flag. 0 means SFF, 1 means EFF
    """
    # ID conversion and size check
    logging.debug('Using source ID: %s', can_id)
    can_id_int = int(can_id, 16)
    if can_id_int > 2047 and eff_flag is False:
        raise SystemExit('ERROR: CAN ID to high for SFF')

    id_flag = 0
    if eff_flag:
        logging.debug('Setting EFF CAN ID flag')
        id_flag = ctypes.c_ulong(socket.CAN_EFF_FLAG).value

    data_bytes = os.urandom(data_size)

    return can_id_int, data_bytes, id_flag


def _validate_packet_data(socket_obj, src_packet, recv_packet):

    if socket_obj.destruct_packet(recv_packet) != \
       socket_obj.destruct_packet(src_packet):

        logging.error("Received data is unexpected!")
        logging.error("Received data: %s", recv_packet)
        logging.error("Expected data: %s", src_packet)

        return False
    return True


def echo_test(interface, can_id, eff_flag, fd_mode):
    """
    Perform the echo test through SocketCAN bus

    Args:
        interface (str): network interface of SocketCAN, e.g. can0
        can_id (str):       CAN ID
        eff_flag (bool):    EFF CAN ID Enable
        fd_mode (bool):     FD mode enable

    Raises:
        SystemExit: if received CAN frame data is not correct
    """
    data_size = 64 if fd_mode else 8
    can_id_i, data_b, id_flags = _random_can_data(
                        can_id, eff_flag, data_size)
    logging.info('Sending data: %s', data_b.hex())
    logging.info("Initial CAN Link object with %s", interface)
    with prepare_can_link(interface, fd_mode):
        can_socket = CANSocket(interface, fd_mode)
        can_pkt = can_socket.struct_packet(
            can_id_i, data_b, id_flags, fd_frame=fd_mode)
        can_socket.send(can_pkt, timeout=5)

        can_recv_pkt = can_socket.recv(5)

        if _validate_packet_data(can_socket, can_pkt,
                                 can_recv_pkt):
            logging.info('\nPASSED')
        else:
            raise SystemExit('ERROR: ID/Data received does not match sent')


def stress_echo_test(interface, can_id, eff_flag, fd_mode, count=30):
    """
    Perform the echo stress test through SocketCAN bus

    Args:
        interface (str): network interface of SocketCAN, e.g. can0
        can_id (str):       CAN ID
        eff_flag (bool):    EFF CAN ID Enable
        fd_mode (bool):     FD mode enable
        count (int):        Stress test cycle

    Raises:
        SystemExit: if received CAN frames is not expected
    """
    # Due to the timestamp data is 8 bytes
    # So we need to generate extra random data (56 bytes)
    data_size = 56 if fd_mode else 0

    can_id_i, prefix_data, id_flags = _random_can_data(
                        can_id, eff_flag, data_size)

    logging.info("Initial CAN Link object with %s", interface)
    with prepare_can_link(interface, fd_mode):
        can_socket = CANSocket(interface, fd_mode)

        logging.info("Generate data for stress tests")
        original_records = [
            can_socket.struct_packet(
                can_id_i,
                b"".join([
                    prefix_data,
                    bytes.fromhex(
                        str(int(datetime.datetime.now().timestamp()*1000000)))
                ]),
                id_flags,
                fd_frame=fd_mode
            ) for _ in range(count)
        ]

        time_format = "%Y-%m-%d %H:%M:%S"
        recv_records = []

        start_time = datetime.datetime.now()
        logging.info(
            "# Start stress echo string test at %s",
            start_time.strftime(time_format)
        )
        for can_pkt in original_records:
            can_socket.send(can_pkt, timeout=5)
            recv_records.append(can_socket.recv(5))
            if recv_records[-1] is None:
                logging.error(
                    "Stop testing due to failed to receive packet"
                )
                logging.error(
                    "Received %d packets from CAN echo server",
                    len(recv_records)
                )
                raise SystemExit("CAN ECHO Stress test failed")

        end_time = datetime.datetime.now()
        logging.info("# End stress echo string test at {}".format(
            end_time.strftime(time_format)
        ))

        elapsed_time = end_time - start_time
        logging.info(
            "received %s frames in %s", len(recv_records), elapsed_time)

        if len(recv_records) == count:
            logging.info("# Checking the data in received frames")
            failed_count = 0
            for index, data in enumerate(original_records):
                # validate data field in CAN packet only
                if _validate_packet_data(can_socket, data,
                                         recv_records[index]):
                    failed_count += 1

            if failed_count > 0:
                logging.error("Found %s incorrect data frames", failed_count)
                raise SystemExit("CAN ECHO Stress test failed")
            else:
                logging.info("CAN ECHO Stress test passed")

        else:
            logging.error(
                "%s frames is received, but %s is expected",
                len(recv_records),
                count
            )
            raise SystemExit("CAN ECHO Stress test failed")


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='SocketCAN Tests')
    parser.add_argument(
        "-d", "--device",
        required=True,
        help="CAN network interface"
    )
    parser.add_argument(
        "-f", "--fd-mode",
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )

    subparsers = parser.add_subparsers(
        dest="mode",
        required=True
    )
    server_parser = subparsers.add_parser("server")
    server_parser.add_argument(
        "-t", "--time-delay",
        type=float,
        default=0.001
    )

    client_parser = subparsers.add_parser("client")
    client_parser.add_argument(
        "-x", "--execute-test",
        type=str,
        choices=["stress-echo", "echo"],
        default="stress-echo"
    )
    client_parser.add_argument(
        "-c", "--can-id",
        type=str,
        required=True
    )
    client_parser.add_argument(
        "-e", "--eff-mode",
        action="store_true",
        default=False
    )
    client_parser.add_argument(
        "-l", "--loop",
        type=int,
        default=30
    )

    args = parser.parse_args()
    return args


def main():

    args = register_arguments()
    print(args)

    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.mode == "server":
        start_echo_server(args.device, args.fd_mode, args.time_delay)
    elif args.mode == "client":
        if args.execute_test == "stress-echo":
            stress_echo_test(
                args.device, args.can_id, args.eff_mode,
                args.fd_mode, args.loop
            )
        elif args.execute_test == "echo":
            echo_test(
                args.device, args.can_id, args.eff_mode, args.fd_mode
            )


if __name__ == "__main__":
    main()
