#!/usr/bin/env python3
import argparse


def print_ports_config(string: str):
    ports_config_list = string.split()
    serials = []
    rs485_nodes = []
    rs422_nodes = []
    for port_config in ports_config_list:
        config_parts = port_config.split(":")
        if len(config_parts) != 3:
            print(
                "Error: Invalid format for serial port configuration:",
                port_config,
            )
            print("Should be 'TYPE:NODE:BAUDRATE'")
            raise SystemExit(1)
        serial = {}
        port_type, port_node, baud_rate = config_parts
        serial["type"] = port_type
        serial["node"] = port_node
        serial["baudrate"] = baud_rate
        serials.append(serial)
        if port_type == "RS485":
            rs485_nodes.append(port_node)
        if port_type == "RS422":
            rs422_nodes.append(port_node)

    for serial in serials:
        print("type: {}".format(serial["type"]))
        print("node: {}".format(serial["node"]))
        print("baudrate: {}".format(serial["baudrate"]))
        print("group: ", end="")
        if serial["type"] == "RS485":
            for rs485_node in rs485_nodes:
                if rs485_node != serial["node"]:
                    print("{} ".format(rs485_node), end="")
        if serial["type"] == "RS422":
            for rs422_node in rs422_nodes:
                if rs422_node != serial["node"]:
                    print("{} ".format(rs422_node), end="")
        print("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "string",
        type=str,
        help="The string needed to be parsed",
    )
    args = parser.parse_args()
    print_ports_config(args.string)


if __name__ == "__main__":
    main()
