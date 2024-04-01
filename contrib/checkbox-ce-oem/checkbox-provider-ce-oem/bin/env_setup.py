#!/usr/bin/env python3
import json
import logging
import argparse
import os
from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_gadget_snap

CONFIG_FILE = {
    "test-strict-confinement": {
        "channel": "edge",
        "plugs": {
            "shutdown": {
                "snapd": "shutdown",
            },
        },
    },
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


def get_snap_plugs(snapd, snap):
    """
    Get the list of plugs associated with a specific snap.

    Parameters:
        - snapd (Snapd): An instance of the Snapd class for interacting
                         with Snapd.
        - snap (str): The name of the snap for which plugs are to be retrieved.

    Returns:
        List[str]: A list of plugs associated with the specified snap.
    """
    snap_plugs = []
    for plug in snapd.interfaces()["plugs"]:
        if plug["snap"] == snap:
            snap_plugs.append(plug["plug"])
    return snap_plugs


def get_config(config_file, config_path):
    """
    Load and retrieve the configuration from a JSON file.
    Parameters:
        - config_path (str): The path to the JSON configuration file.
    Returns:
        dict: The loaded configuration dictionary. Returns DEFAULT_CONFIG_FILE
              if config_path is empty, not provided, or does not meet criteria.
    """
    if not config_path:
        logging.info("Config path not provided. Using default config.")
    # Check if the path exists and has a .json extension
    elif os.path.exists(config_path) and config_path.lower().endswith('.json'):
        try:
            with open(config_path) as file:
                return json.load(file)
        except FileNotFoundError:
            logging.warning("Config file %s not found. Using default config.",
                            config_path)
        except json.JSONDecodeError as e:
            logging.warning("Error decoding JSON in %s: %s. Using default "
                            "config.",
                            config_path, e)
    else:
        logging.warning("Invalid config path: %s. Using default config.",
                        config_path)

    return config_file


def connect_interfaces(snapd,
                       plug_snap,
                       expect_plugs,
                       snap_plugs):
    """
    Connect expected plugs to a specific snap.

    Parameters:
        - snapd (Snapd): An instance of the Snapd class for interacting
                         with Snapd.
        - plug_snap (str): The name of the snap to which plugs are to
                           be connected.
        - expect_plugs (dict): A dictionary specifying expected plugs
                               and their corresponding slots.
        - snap_plugs (list): A list of plugs associated with the
                             specified snap.

    Returns:
        bool: True if all plugs are successfully connected, False otherwise.
    """
    status = True
    for plug in expect_plugs.keys():
        if plug in snap_plugs:
            (slot_snap, slot_plug), = expect_plugs[plug].items()
            if slot_snap == 'gadget':
                slot_snap = get_gadget_snap()
            try:
                logging.info("Attempting to connect interface "
                             "\"%s:%s\" \"%s:%s\"",
                             plug_snap, plug, slot_snap, slot_plug
                             )
                snapd.connect(slot_snap,
                              slot_plug,
                              plug_snap,
                              plug)
            except Exception as err:
                status = False
                logging.error("Not able to connect plug \"%s:%s\" "
                              "to slot \"%s:%s\".",
                              plug_snap, plug, slot_snap, slot_plug
                              )
                logging.error(err)
        else:
            logging.error("Expect plug \"%s\" not in the snap \"%s\".",
                          plug, plug_snap
                          )
            status = False
    return status


def main():
    """
    This script facilitates the installation and connection of interfaces for
    a test snap.

    Usage:
        python script_name.py [--file CONFIG_FILE]

    Options:
        --file CONFIG_FILE  Path to the configuration file (JSON format)
                            specifying the target snap, its channel, and
                            the expected plugs to connect.

    Configuration File Format (JSON):
        The configuration file should follow the JSON format and contain
        a dictionary with snap names as keys and their respective
        configurations as values.

    Example Configuration:
        {
            "test-strict-confinement": {
                "channel": "edge",
                "plugs": {
                    "shutdown": {"snapd": "shutdown"},
                    ...
                }
            },
            ...
        }
    """
    parser = argparse.ArgumentParser(
        description="This is a script to install and connect expected plugs "
                    "for target snanp.")
    parser.add_argument('--file',
                        default=None,
                        help="The path with file name of the config file")
    args = parser.parse_args()
    status = True
    snapd = Snapd()
    config_file = get_config(CONFIG_FILE, args.file)
    for plug_snap in config_file.keys():
        logging.info("Attempting to install %s snap", plug_snap)
        if not snapd.list(plug_snap):
            try:
                snapd.install(plug_snap,
                              channel=config_file[plug_snap]['channel'])
            except Exception as err:
                logging.error(err)
                status = False
                continue
        else:
            logging.info("{} is already installed."
                         .format(plug_snap))
        snap_plugs = get_snap_plugs(snapd, plug_snap)
        expect_plugs = config_file[plug_snap]['plugs']
        status = connect_interfaces(snapd,
                                    plug_snap,
                                    expect_plugs,
                                    snap_plugs)
    if status:
        logging.info("Environment setup finished.")
    else:
        logging.error(
            "Environment setup finished with some error. "
            "Please check it and try it again."
        )
        raise SystemExit("Fail to setup environment!")


if __name__ == "__main__":
    main()
