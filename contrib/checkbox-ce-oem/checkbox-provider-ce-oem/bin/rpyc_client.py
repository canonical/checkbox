import time
import rpyc


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
    for _ in range(2):
        try:
            conn = rpyc.connect(
                host,
                60000,
                config={"allow_all_attrs": True, "allow_exposed_attrs": False},
            )
            break
        except ConnectionRefusedError:
            time.sleep(1)
    else:
        raise SystemExit("Cannot connect to RPYC Host.")

    try:
        func = getattr(conn.root, cmd)
        wrap = rpyc.async_(func)
        res = wrap(*args, **kwargs)
        while res.ready:
            print("Waiting for RPYC server complete {}".format(func))
            time.sleep(1)
            break
        if getattr(res._conn.root, "logs"):
            print(res._conn.root.logs)
        return res.value
        # return getattr(conn.root, cmd)(*args, **kwargs)
    except AttributeError:
        raise SystemExit("RPYC host does not provide a '{}' command.".format(cmd))
    except rpyc.core.vinegar.GenericException as exc:
        raise SystemExit(
            "Zapper host failed to process the requested command."
        ) from exc
