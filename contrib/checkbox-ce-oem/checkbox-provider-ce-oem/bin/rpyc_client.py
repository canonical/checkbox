import time

from importlib import import_module


def rpyc_client(host, port):
    """
    Run command on RPYC.

    :param host: RPYC server IP address
    :param cmd: command to be executed
    :param args: command arguments
    :param kwargs: command keyword arguments
    :returns: whatever is returned by RPYC service
    :raises SystemExit: if the connection cannot be established
                        or the command is unknown
                        or a service error occurs
    """
    try:
        _rpyc = import_module("rpyc")
    except ImportError:
        try:
            _rpyc = import_module("plainbox.vendor.rpyc")
        except ImportError as exc:
            msg = "RPyC not found. Neither from sys nor from Checkbox"
            raise SystemExit(msg) from exc

    for _ in range(2):
        try:
            conn = _rpyc.connect(host, port, config={"allow_all_attrs": True})
            return conn
        except ConnectionRefusedError:
            time.sleep(1)
    else:
        raise SystemExit("Cannot connect to RPYC Host.")
