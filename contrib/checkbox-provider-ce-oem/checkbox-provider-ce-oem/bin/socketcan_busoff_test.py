#!/usr/bin/env python3

import sys
import os
import argparse
import logging
import time
from datetime import datetime
from socketcan_socket import CANSocket, CANLinkState, prepare_can_link


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


def monitor_can_state(can_link, expected_states, timeout):
    """
    Monitor CAN current state until it becomes expected state

    Args:
        can_dev (str):          CAN device name
        expected_state (list):  a list of CAN states
        timeout (int):          timeout
    """
    result = False
    start_time = datetime.now()

    expected_states = [state.value for state in expected_states]
    logging.info("Expected CAN state: %s", expected_states)

    while True:
        can_link.get_link_info()
        can_state = can_link.state
        logging.info("Current CAN state: %s", can_state)

        if can_state in expected_states:
            result = True
            break
        cur_time = datetime.now()

        if (cur_time - start_time).total_seconds() > timeout:
            logging.error("CAN current state is not match")
            break

        time.sleep(1)

    return result


def can_bus_off_test(can_dev, timeout):
    """
    CAN BUS-OFF test

    Args:
        can_dev (str):  CAN device name
        timeout (int):  timeout

    Raises:
        SystemExit:     Test failed with description
    """

    logging.info("Initial CAN Link object with %s", can_dev)
    with prepare_can_link(can_dev) as can_link:
        # the state must not be BUS-OFF and STOPPED before testing
        logging.info("Check current state for %s interface", can_dev)
        expected_state = monitor_can_state(
            can_link,
            [
                CANLinkState.ERROR_ACTIVE,
                CANLinkState.ERROR_PASSIVE,
                CANLinkState.ERROR_WARNING
            ],
            timeout
        )

        if expected_state:
            print("Short CAN_H and CAN_L for {} interface".format(can_dev))
            print("And press Enter..")
            input()

            can_socket = CANSocket(can_dev, False)
            can_pkt = can_socket.struct_packet(
                222,
                os.urandom(8),
                0,
                fd_frame=False
            )
            for _ in range(10):
                can_socket.send(can_pkt, timeout=5)

            if monitor_can_state(can_link, [CANLinkState.BUS_OFF], timeout):
                print("The state of {} interface is BUS-OFF".format(can_dev))

                print("Remove short connector from {} intf".format(can_dev))
                print("And press Enter..")
                input()
                if monitor_can_state(
                    can_link,
                    [
                        CANLinkState.ERROR_ACTIVE,
                        CANLinkState.ERROR_PASSIVE,
                        CANLinkState.ERROR_WARNING
                    ],
                    timeout
                ):
                    logging.info("CAN state is recovered from BUS-OFF state")
            else:
                raise SystemExit("the CAN state is not BUS-OFF")
        else:
            raise SystemExit("Initial CAN current state is not expected.")


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='SocketCAN BUS-OFF Tests')
    parser.add_argument(
        "-d", "--device",
        required=True,
        help="CAN network interface"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=60
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )

    args = parser.parse_args()
    return args


def main():
    args = register_arguments()
    print(args)

    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    can_bus_off_test(args.dev, args.timeout)


if __name__ == "__main__":
    main()
