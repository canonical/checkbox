#!/usr/bin/env python3

import logging
import os
import re
import subprocess
import sys


VENDOR_MAP = {
    "0x8086": "Intel",
    "0x10de": "NVIDIA",
    "0x1002": "AMD",
    # Add other vendor IDs as needed
}


def get_graphics_info():
    """
    Scans /sys/class/drm to find graphics cards and their properties.
    """
    graphics_info = []
    drm_path = "/sys/class/drm/"
    if not os.path.isdir(drm_path):
        logging.error("Error: DRM directory not found at '%s'", drm_path)
        return

    # Find all card directories (e.g., card0, card1)
    card_dirs = sorted(
        [d for d in os.listdir(drm_path) if re.search(r"card[0-9]*$", d)]
    )

    if not card_dirs:
        logging.error("No graphics cards found in /sys/class/drm.")
        return

    logging.info("--- Graphics Card Information ---")

    for card_dir in card_dirs:
        full_card_path = os.path.join(drm_path, card_dir)
        device_path = os.path.join(full_card_path, "device")

        connectors = []
        for item in os.listdir(full_card_path):
            # Connectors are subdirectories like cardX-DP-1
            pattern = "{}-".format(card_dir)
            if item.startswith(pattern):
                # Extract just the connector name (e.g., DP-1)
                connector_name = item.replace(pattern, "")
                connectors.append(connector_name)

        driver = "N/A"
        uevent_path = os.path.join(device_path, "uevent")
        if os.path.exists(uevent_path):
            try:
                with open(uevent_path, "r") as f:
                    for line in f:
                        if line.startswith("DRIVER="):
                            driver = line.strip().split("=")[1]
                            break
            except IOError as e:
                driver = "Error reading uevent: {}".format(e)

        vendor_name = "Unknown"
        vendor_path = os.path.join(device_path, "vendor")
        if os.path.exists(vendor_path):
            try:
                with open(vendor_path, "r") as f:
                    vendor_id = f.read().strip()
                    vendor_name = VENDOR_MAP.get(
                        vendor_id, "Unknown ID: {}".format(vendor_id)
                    )
            except IOError:
                vendor_name = "Could not read vendor file"

        card_name = "N/A"
        if os.path.islink(device_path):
            try:
                pci_path = os.path.realpath(device_path)
                pci_address = os.path.basename(pci_path)
                if pci_address.split(":")[0].isnumeric():
                    logging.info(
                        "Check card name with PCI bus: %s", pci_address
                    )
                    lspci_output = subprocess.check_output(
                        ["lspci", "-s", pci_address], text=True
                    ).strip()
                    card_name = " ".join(lspci_output.split(" ")[1:])
                else:
                    card_name = "Unknown"
            except (subprocess.CalledProcessError, FileNotFoundError):
                card_name = "Unknown"

        card_info = {
            "Index": card_dir,
            "Vendor": vendor_name,
            "Name": card_name,
            "Driver": driver,
            "Connectors": connectors,
        }
        graphics_info.append(card_info)

    return graphics_info


def verify_nvidia_modeset_enable():
    enable = None
    nvidia_modeset_path = "/sys/module/nvidia_drm/parameters/modeset"
    if os.path.exists(nvidia_modeset_path):
        try:
            with open(nvidia_modeset_path, "r") as f:
                modeset = f.read().strip()
        except IOError as e:
            modeset = "Error reading modeset: {}".format(e)

    if modeset.lower() == "y":
        enable = True
    else:
        enable = False

    return enable


def main():
    root_logger = logging.getLogger()
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stdout_handler)

    result = True
    graphic_info = get_graphics_info()
    logging.info("graphic card information: %s", graphic_info)

    nvidia_cards = [gc for gc in graphic_info if gc["Vendor"] == "NVIDIA"]
    if nvidia_cards:
        for info in graphic_info:
            if info["Driver"] != "nvidia":
                logging.error(
                    "Error: %s is not running with nvidia propietary driver",
                    info["Name"],
                )
                result = False
        if result:
            logging.info(
                "All Nvidia graphic cards running with propietary driver"
            )
    else:
        result = False
        logging.error("Error: no Nvidia graphic card been detected")

    # verify nvidia running with propietary driver
    if not verify_nvidia_modeset_enable():
        result = False
        logging.error("Error: nvidia-drm.modeset is not enabled")

    if result:
        logging.info(
            (
                "Passed: Nvidia cards running with propieratry driver "
                "and nvidia-drm.modeset been enabled"
            )
        )
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
