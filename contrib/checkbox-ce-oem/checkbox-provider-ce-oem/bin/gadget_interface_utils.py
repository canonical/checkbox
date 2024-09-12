#!/usr/bin/env python3
import os
import sys
import json
import logging
import argparse
from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_gadget_snap


DEFAULT_SCHEMA = os.path.join(
    os.environ.get("PLAINBOX_PROVIDER_DATA", ""),
    "gadget_interface_schema.json",
)


def register_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "This is a script has following method"
            " 1. generate a gadget interface JSON file"
            " 2. generate checkbox resource from gadget interface file"
        )
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="The path with file name of the config file",
    )
    parser.add_argument("--action", type=str, choices=["generate", "dump"])
    return parser.parse_args()


def schema_validation(content: dict, schema_file: str = DEFAULT_SCHEMA):
    import jsonschema

    with open(schema_file, "r") as fp:
        schema_content = json.load(fp)

    jsonschema.validate(content, schema_content)


def _generate_plug_data(interface: dict):
    if interface.get("interface"):
        return {
            "name": interface["plug"],
            "interface": interface["interface"],
        }
    else:
        logging.error("Incorrect plug interface data: %s", interface)


def _generate_slot_data(interface: dict):
    if interface.get("interface"):
        return {
            "name": interface["slot"],
            "interface": interface["interface"],
            "attrs": interface["attrs"],
        }
    else:
        logging.error("Incorrect slot interface data: %s", interface)


def gadget_interface_generator(
    file: str, by_gadget: bool = True, validate_by_schema: bool = False
):
    func_mapping = {"plugs": _generate_plug_data, "slots": _generate_slot_data}
    snap_interfaces = {"plugs": [], "slots": []}

    if by_gadget:
        gadget_snap = get_gadget_snap()
        system_snap_interfaces = Snapd().interfaces()
        for key, func in func_mapping.items():
            for interface in system_snap_interfaces[key]:
                if interface["snap"] != gadget_snap:
                    continue
                snap_interfaces[key].append(func(interface))
    else:
        pass

    if validate_by_schema:
        schema_validation(snap_interfaces)

    with open(file, "w") as fp:
        json.dump(snap_interfaces, fp, indent=4)

    logging.info("Generate gadget slot and plug interface to %s", file)


def _print_formatted_slot_data(interface):
    required_keys = ["name", "interface", "attrs"]
    for key in required_keys:
        print("{}: {}".format(key, interface[key]))
    print("type: slot")
    print()


def _print_formatted_plug_data(interface):
    required_keys = ["name", "interface"]
    for key in required_keys:
        print("{}: {}".format(key, interface[key]))
    print("type: plug")
    print()


def gadget_interface_parser(file: str, validate_by_schema: bool = False):
    func_mapping = {
        "plugs": _print_formatted_plug_data,
        "slots": _print_formatted_slot_data,
    }
    if not os.path.exists(file):
        print("file: gadget file not found")
        exit()

    with open(file, "r") as fp:
        snap_interfaces = json.load(fp)

    if validate_by_schema:
        schema_validation(snap_interfaces)

    for key, func in func_mapping.items():
        for interface in snap_interfaces[key]:
            func(interface)


def main():
    args = register_arguments()
    if args.action == "generate":
        gadget_interface_generator(args.file)
    elif args.action == "dump":
        gadget_interface_parser(args.file)
    else:
        raise ValueError("Unsupported action")


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.basicConfig(
        level=logging.ERROR,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
        ],
    )
    main()
