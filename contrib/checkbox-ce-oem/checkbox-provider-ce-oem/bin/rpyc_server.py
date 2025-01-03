import io
import logging
import rpyc
import subprocess
import sys
import time

from contextlib import redirect_stdout, redirect_stderr
from importlib import reload
from importlib.machinery import SourceFileLoader
from pathlib import Path
from rpyc.utils.server import ThreadedServer

from checkbox_support.scripts import (
    run_watcher,
    usb_read_write,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_std = logging.StreamHandler(sys.stdout)


LIBS = {
    "enable_serial_server": {
        "source": (
            "/snap/checkbox-ce-oem/current/providers/"
            "checkbox-provider-ce-oem/bin/serial_test.py"
        ),
        "function": "server_mode",
    },
    "network_ping": {
        "source": (
            "/snap/checkbox22/current/providers/"
            "checkbox-provider-base/bin/gateway_ping_test.py"
        ),
        "function": "perform_ping_test",
    },
}
dynamic_integrate_funcs = [LIBS[k]["function"] for k in LIBS.keys()]


def capture_io_logs(func):
    def wrap(*args, **kwargs):
        sio_stdout = io.StringIO()
        sio_stderr = io.StringIO()
        cls = args[0]
        if func.__name__ in dynamic_integrate_funcs:
            args = args[1:]

        with redirect_stderr(sio_stderr) as stderr, redirect_stdout(sio_stdout) as stdout:
            try:
                ret = func(*args, **kwargs)
            except SystemExit as exp:
                ret = exp.code

        cls.logs = "stdout logs: {}".format(stdout.getvalue())
        cls.logs += "\nstderr logs: {}".format(stderr.getvalue())
        return ret
    return wrap


def _load_method_from_file(name, file, func):
    try:
        _module = SourceFileLoader(name, file).load_module()
        return getattr(_module, func)
    except FileNotFoundError as e:
        logger.error("Failed to import module from %s file", file)
        logger.debug(e)
    except AttributeError as e:
        logger.error("Failed to get %s function from %s file", func, file)
        logger.debug(e)


class RpycTestService(rpyc.Service):

    def __init__(self):
        super().__init__()
        self.logs = ""
        for key, value in LIBS.items():
            func = _load_method_from_file(
                key, value["source"], value["function"]
            )
            if func:
                setattr(RpycTestService, key, capture_io_logs(func))

    def on_connect(self, conn):
        # code that runs when a connection is created
        # (to init the service, if needed)
        pass

    def on_disconnect(self, conn):
        # code that runs after the connection has already closed
        # (to finalize the service, if needed)
        pass

    def _get_ethernet_ifaces(self):
        return set([i.name for i in Path("/sys/class/net").iterdir()])

    def _get_serial_ifaces(self):
        return set([i.name for i in Path("/dev/serial/by-id").iterdir()])

    def _device_node_detect(self, func, device_type=""):
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
                print(
                    "New interface(s) detected: {}".format(
                        ", ".join(list(new_ifaces))
                    )
                )
                return new_ifaces
            time.sleep(1)
            print(".", end="", flush=True)
            attempts -= 1
        print()
        raise SystemExit(
            "Failed to detect new {} interface".format(device_type)
        )

    @capture_io_logs
    def serial_check(self):
        return self._device_node_detect(self._get_serial_ifaces, "serial")

    @capture_io_logs
    def ethernet_check(self):
        return self._device_node_detect(self._get_ethernet_ifaces, "ethernet")

    @capture_io_logs
    def configure_local_network(self, interface, net_info):
        logger.info("set %s to %s interface on RPYC", net_info, interface)
        subprocess.check_output(
            "ip addr add {} dev {}".format(net_info, interface),
            shell=True,
            text=True,
        )

    @capture_io_logs
    def usb_storage_test(self, usb_type):
        logger.info("%s drive read/write testing on RPYC", usb_type)
        usb_read_write.REPETITION_NUM = 2
        watcher = run_watcher.USBStorage(usb_type)
        mounted_partition = watcher.run_insertion()
        logger.info(
            "%s drive been mounted to %s on RPYC", usb_type, mounted_partition
        )
        watcher.run_storage(mounted_partition)
        # usb_read_write been imported in run_watcher
        # the temporary mount point been created while import it and been removed in gen_random_file function
        # thus, we need to reload it to create temporary mount point in every testing cycle
        reload(usb_read_write)


def main():
    t = ThreadedServer(
        RpycTestService,
        port=60000,
        logger=logger,
        protocol_config={
            "allow_all_attrs": True,
            "allow_exposed_attrs": False,
        },
    )
    t.start()


if __name__ == "__main__":
    main()
