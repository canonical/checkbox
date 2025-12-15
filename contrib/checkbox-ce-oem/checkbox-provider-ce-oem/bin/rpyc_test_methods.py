import logging
import subprocess
import time

from importlib import reload
from pathlib import Path
from checkbox_support.scripts import (
    run_watcher,
    usb_read_write,
)


# Method for testing
def _get_ethernet_ifaces():
    return set([i.name for i in Path("/sys/class/net").iterdir()])


def _get_serial_ifaces():
    return set([i.name for i in Path("/dev/serial/by-id").iterdir()])


def _device_node_detect(func, device_type=""):
    starting_ifaces = func()

    attempts = 20
    while attempts > 0:
        now_ifaces = func()
        # check if something disappeared
        if not starting_ifaces == now_ifaces & starting_ifaces:
            raise SystemExit(
                "Interface(s) disappeared: {}".format(
                    ", ".join(list(starting_ifaces - now_ifaces))
                )
            )
        new_ifaces = now_ifaces - starting_ifaces
        if new_ifaces:
            print()
            print("New interface(s) detected: {}".format(", ".join(list(new_ifaces))))
            return new_ifaces
        time.sleep(1)
        print(".", end="", flush=True)
        attempts -= 1
    print()
    raise SystemExit("Failed to detect new {} interface".format(device_type))


def configure_local_network(interface, net_info):
    logging.info("Turn down the link of %s interface", interface)
    subprocess.check_output(
        "ip link set dev {} down".format(interface),
        shell=True,
        text=True,
    )
    logging.info("Turn down the link of %s interface", interface)
    subprocess.check_output(
        "ip addr add {} dev {}".format(net_info, interface),
        shell=True,
        text=True,
    )
    logging.info("Turn up the link of %s interface", interface)
    subprocess.check_output(
        "ip link set dev {} up".format(interface),
        shell=True,
        text=True,
    )


def serial_check():
    return _device_node_detect(_get_serial_ifaces, "serial")


def ethernet_check():
    return _device_node_detect(_get_ethernet_ifaces, "ethernet")


def usb_storage_test(usb_type):
    logging.info("%s drive read/write testing on RPYC", usb_type)
    usb_read_write.REPETITION_NUM = 2
    watcher = run_watcher.USBStorage(usb_type)
    mounted_partition = watcher.run_insertion()
    logging.info("%s drive been mounted to %s on RPYC", usb_type, mounted_partition)
    watcher.run_storage(mounted_partition)
    # usb_read_write been imported in run_watcher
    # the temporary mount point been created while import it
    #   and the directory been removed in gen_random_file function
    # thus, we need to reload it to create temporary mount point
    #   in every testing cycle
    reload(usb_read_write)
