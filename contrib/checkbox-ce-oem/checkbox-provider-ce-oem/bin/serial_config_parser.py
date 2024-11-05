#!/usr/bin/env python3
import argparse


def print_ports_config(string: str, rs485_conf: str = None):
    ports_config_list = string.split()
    rs485_conf_lists = {}
    """
    Parse RS485 config,
    e.g.
    Input:
    RS485_CONFIG = "/dev/ttySC0:True:False:0.0:0.0
    /dev/ttySC2:True:False:0.0:0.0"

    Output:
    rs485_conf_lists = {
        "/dev/ttySC0": {
            "rts_level_for_tx": True,
            "rts_level_for_rx": False,
            "delay_before_tx: 0.0,
            "delay_before_rx: 0.0,
        }
        "/dev/ttySC2": {
            "rts_level_for_tx": True,
            "rts_level_for_rx": False,
            "delay_before_tx: 0.0,
            "delay_before_rx: 0.0,
        }
    }
    """
    if rs485_conf:
        for rs485_conf_list in rs485_conf.split():
            node, rts_tx, rts_rx, delay_tx, delay_rx = rs485_conf_list.split(
                ":"
            )
            rs485_conf_lists[node] = {
                "rts_level_for_tx": rts_tx,
                "rts_level_for_rx": rts_rx,
                "delay_before_tx": delay_tx,
                "delay_before_rx": delay_rx,
            }
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

        # Init a config dict if type is RS485
        if port_type == "RS485":
            serial["rs485_conf"] = {
                "rts_level_for_tx": True,
                "rts_level_for_rx": False,
                "delay_before_tx": 0.0,
                "delay_before_rx": 0.0,
            }
        serial["node"] = port_node
        serial["baudrate"] = baud_rate

        # Mapping rs485 configs with rs485 node name and update the config
        if port_node in rs485_conf_lists.keys():
            serial["rs485_conf"] = rs485_conf_lists[port_node]
        serials.append(serial)
        if port_type == "RS485":
            rs485_nodes.append(port_node)
        if port_type == "RS422":
            rs422_nodes.append(port_node)

    for serial in serials:
        print("type: {}".format(serial["type"]))
        print("node: {}".format(serial["node"]))
        if serial["type"] == "RS485":
            for key, value in serial["rs485_conf"].items():
                print("{}: {}".format(key, value))
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
    parser.add_argument(
        "--rs485-conf",
        type=str,
        help="RS485 sepcific configurations.",
        default=None,
        required=False,
    )
    args = parser.parse_args()
    print_ports_config(args.string, args.rs485_conf)


if __name__ == "__main__":
    main()
