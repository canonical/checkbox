#!/usr/bin/env python3
import socket
import argparse
import threading
import logging
import time
import string
import random
from datetime import datetime, timedelta
from enum import Enum


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


class StatusEnum(Enum):
    SUCCESS = 0
    ERROR = 1
    FAIL = 2


def generate_random_string(length):
    letters_and_digits = string.ascii_letters + string.digits
    random_string = "".join(
        random.choice(letters_and_digits) for _ in range(length)
    )
    return random_string


def sorting_data(dict_status):
    list_times = []
    fail_records = []
    for value in dict_status.values():
        list_times.append(value.get("time"))
        if not value.get("status"):
            fail_records.append(value)
    return list_times, fail_records


def format_output(port, message="", dict_status={}):
    result = {
        "port": port,
        "status": StatusEnum.SUCCESS,
        "message": None,
        "fail": None,
        "port_period": None,
        "avg_period": None,
        "max_period": None,
        "min_period": None,
    }
    times = records = None
    if message:
        result["status"] = StatusEnum.ERROR
        result["message"] = message
    elif dict_status:
        times, records = sorting_data(dict_status)
        if records:
            result["fail"] = records
            result["status"] = StatusEnum.FAIL
            result["message"] = "Received payload incorrect!"
        else:
            result["message"] = "Received payload correct!"
        result["port_period"] = sum(times, timedelta())
        result["avg_period"] = result["port_period"] / len(times)
        result["max_period"] = max(times)
        result["min_period"] = min(times)
    return result


def check_result(results):
    final = 0
    for port in results:
        if port["status"] == StatusEnum.FAIL:
            final = 1
            logging.error("Fail on port %s: %s", port["port"], port["message"])
            logging.error("Detail:")
            for value in port["fail"]:
                logging.error(
                    "Period: %s, Status: %s", value["time"], value["status"]
                )
        elif port["status"] == StatusEnum.ERROR:
            final = 1
            logging.error(
                "Not able to connect on port %s." "%s",
                port["port"],
                port["message"],
            )
    if final:
        raise RuntimeError("TCP payload test fail!")
    else:
        logging.info("Run TCP multi-connections test Passed!")


def server(start_port, end_port):
    """
    Start the server to listen on a range of ports.

    Args:
    - start_port (int): Starting port for the server.
    - end_port (int): Ending port for the server.
    """
    for port in range(start_port, end_port + 1):
        threading.Thread(target=handle_port, args=(port,)).start()


def handle_port(port):
    """
    Handle incoming connections on the specified port.

    Args:
    - port (int): Port to handle connections.
    """
    server = ("0.0.0.0", port)
    try:
        with socket.create_server(server) as server_socket:
            # Set send buffer size to 4096
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.listen()

            logging.info("Server listening on port %s", port)

            while True:
                try:
                    conn, addr = server_socket.accept()
                    with conn:
                        logging.info("Connected by %s.", addr)
                        while True:
                            data = conn.recv(4096)
                            if data:
                                conn.sendall(data)
                            else:
                                break
                except Exception as e:
                    logging.error("Error handling connection: %s", str(e))
    except Exception as e:
        logging.error(
            "%s: An unexpected error occurred for port %s", str(e), port
        )


def client(host, start_port, end_port, payload, start_time, results):
    """
    Start the client to connect to a range of server ports.

    Args:
    - host (str): Server host.
    - start_port (int): Starting port for the client.
    - end_port (int): Ending port for the client.
    - payload (int): Payload to send to the server.
    - done_event (threading.Event): Event to single when the client is done.
    - start_time (datetime): Time until which the client should run.
    """
    threads = []
    payload = generate_random_string(payload * 1024)
    for port in range(start_port, end_port + 1):
        thread = threading.Thread(
            target=send_payload,
            args=(host, port, payload, start_time, results),
        )
        threads.append(thread)
        thread.start()
    # Wait for all client threads to finish
    for thread in threads:
        thread.join()
    logging.info(
        "Running TCP multi-connections in %s", (datetime.now() - start_time)
    )
    check_result(results)


def send_payload(host, port, payload, start_time, results):
    """
    Send a payload to the specified port and handle the server response.

    Args:
    - host (str): Server host.
    - port (int): Port to connect to.
    - payload (int): Payload size in KB for the client.
    - start_time (datetime): Time until which the client should run.
    """
    # Retry connect to server port for 5 times.
    message = ""
    status_all = {}
    for _ in range(5):
        try:
            server_host = (host, port)
            with socket.create_connection(server_host) as client_socket:
                # Set send buffer size to 4096
                client_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_SNDBUF, 4096
                )
                logging.info("Connect to port %s", port)
                # Sleep until start time)
                start_time = start_time - datetime.now()
                time.sleep(start_time.total_seconds())
                logging.info("Sending payload to port %s.", port)
                # Sending payload for 10 times
                for x in range(10):
                    single_start = datetime.now()
                    client_socket.sendall(payload.encode())
                    received_data = ""
                    while len(received_data) < len(payload):
                        # set socket time out for 30 seconds,
                        # in case recv hang.
                        client_socket.settimeout(30)
                        try:
                            data = client_socket.recv(4096)
                            if not data:
                                break
                            received_data += data.decode()
                        except TimeoutError:
                            break
                    single_end = datetime.now() - single_start
                    if received_data != payload:
                        status_all[x] = {"time": single_end, "status": False}
                    else:
                        status_all[x] = {"time": single_end, "status": True}
                logging.info("Received payload from %s.", server_host)
                client_socket.close()
                break
        except socket.error as e:
            logging.error("%s on %s", e, port)
            message = str(e)
        except Exception as e:
            logging.error("%s on %s", e, port)
            message = str(e)
        time.sleep(3)
    results.append(format_output(port, message, status_all))
    return results


if __name__ == "__main__":
    """
    TCP Ping Test

    This script performs a TCP ping test between a server and multiple
    client ports.
    The server listens on a range of ports, and the clients connect to
    these ports to send a payload and receive a response from the server.

    Usage:
    - To run as a server: ./script.py server -p <star_port> -e <end_port>
    - To run as a client: ./script.py client -H <server_host> -p <start_port>
      -e <end_port> -P <payload_size>

    Arguments:
    - mode (str): Specify whether to run as a server or client.
    - host (str): Server host IP (client mode). This is mandatory arg.
    - port (int): Starting port for the server or server port for the client.
      Default is 1024.
    - payload (int): Payload size in KB for the client. Default is 64.
    - end_port (int): Ending port for the server. Default is 1223.

    Server Mode:
    - The server listens on a range of ports concurrently, handling
      incoming connections and send the received data back to client.

    Client Mode:
    - The client connects to a range of server ports,
      sending a payload and validating the received response.
      The script logs pass, fail, or error status for each port.
    """

    parser = argparse.ArgumentParser(
        description="Client-server with payload check on multiple ports"
    )

    subparsers = parser.add_subparsers(
        dest="mode", help="Run as server or client"
    )

    # Subparser for the server command
    server_parser = subparsers.add_parser("server", help="Run as server")
    server_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=1024,
        help="Starting port for the server",
    )
    server_parser.add_argument(
        "-e",
        "--end-port",
        type=int,
        default=1223,
        help="Ending port for the server",
    )

    # Subparser for the client command
    client_parser = subparsers.add_parser("client", help="Run as client")
    client_parser.add_argument(
        "-H", "--host", required=True, help="Server host (client mode)"
    )
    client_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=1024,
        help="Starting port for the client",
    )
    client_parser.add_argument(
        "-P",
        "--payload",
        type=int,
        default=64,
        help="Payload size in KB (client mode)",
    )
    client_parser.add_argument(
        "-e",
        "--end-port",
        type=int,
        default=1223,
        help="Ending port for the client",
    )
    args = parser.parse_args()

    results = []
    # Ramp up time to wait until all ports are connected before
    # starting to send the payload.
    start_time = datetime.now() + timedelta(seconds=20)

    if args.mode == "server":
        server(args.port, args.end_port)
    elif args.mode == "client":
        client(
            args.host,
            args.port,
            args.end_port,
            args.payload,
            start_time,
            results,
        )
