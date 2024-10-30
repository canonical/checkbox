import time

from importlib import import_module


def rpyc_client(host, cmd, *args, **kwargs):
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
            conn = _rpyc.connect(host, 60000, config={"allow_all_attrs": True})
            break
        except ConnectionRefusedError:
            time.sleep(1)
    else:
        raise SystemExit("Cannot connect to RPYC Host.")

    try:
        return getattr(conn.root, cmd)(*args, **kwargs)
    except AttributeError:
        raise SystemExit(
            "RPYC host does not provide a '{}' command.".format(cmd)
        )
    except _rpyc.core.vinegar.GenericException as exc:
        raise SystemExit(
            "Zapper host failed to process the requested command."
        ) from exc