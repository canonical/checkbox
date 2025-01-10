import io
import logging
import os
import rpyc
import sys

from contextlib import redirect_stdout, redirect_stderr
from importlib.machinery import SourceFileLoader
from rpyc.utils.server import ThreadedServer


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_std = logging.StreamHandler(sys.stdout)

CHECKBOX_PROVIDER_CEOEM_PATH = (
    "/snap/checkbox-ce-oem/current/providers/checkbox-provider-ce-oem/bin"
)
LIBS = {
    "enable_serial_server": {
        "source": os.path.join(CHECKBOX_PROVIDER_CEOEM_PATH, "serial_test.py"),
        "function": "server_mode",
    },
    "serial_check": {
        "source": os.path.join(
            CHECKBOX_PROVIDER_CEOEM_PATH, "rpyc_test_methods.py"
        ),
        "function": "serial_check",
    },
    "ethernet_check": {
        "source": os.path.join(
            CHECKBOX_PROVIDER_CEOEM_PATH, "rpyc_test_methods.py"
        ),
        "function": "ethernet_check",
    },
    "configure_local_network": {
        "source": os.path.join(
            CHECKBOX_PROVIDER_CEOEM_PATH, "rpyc_test_methods.py"
        ),
        "function": "configure_local_network",
    },
    "usb_storage_test": {
        "source": os.path.join(
            CHECKBOX_PROVIDER_CEOEM_PATH, "rpyc_test_methods.py"
        ),
        "function": "usb_storage_test",
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

        with redirect_stderr(sio_stderr) as stderr, redirect_stdout(
            sio_stdout
        ) as stdout:
            try:
                ret = func(*args, **kwargs)
            except SystemExit as exp:
                logging.error(exp.code)
                ret = None

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


def append_method_to_service(cls):
    for key, value in LIBS.items():
        func = _load_method_from_file(key, value["source"], value["function"])
        if func:
            setattr(cls, key, capture_io_logs(func))

    return cls


class RpycTestService(rpyc.Service):

    def __init__(self):
        super().__init__()
        self.logs = ""


def main():
    rpyc_service = append_method_to_service(RpycTestService)

    t = ThreadedServer(
        rpyc_service,
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
