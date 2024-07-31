# Copyright 2022 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Paolo Gentili <paolo.gentili@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""
This program acts as a proxy to Zapper Hardware.

It uses internal Zapper Control RPyC API.
"""
import argparse
import os
import time

from importlib import import_module


def zapper_run(host, cmd, *args, **kwargs):
    """
    Run command on Zapper.

    :param host: Zapper IP address
    :param cmd: command to be executed
    :param args: command arguments
    :param kwargs: command keyword arguments
    :returns: whatever is returned by Zapper service
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
        raise SystemExit("Cannot connect to Zapper Host.")

    try:
        return getattr(conn.root, cmd)(*args, **kwargs)
    except AttributeError:
        raise SystemExit(
            "Zapper host does not provide a '{}' command.".format(cmd)
        )
    except _rpyc.core.vinegar.GenericException as exc:
        raise SystemExit(
            "Zapper host failed to process the requested command."
        ) from exc


def get_capabilities(host):
    """Get Zapper capabilities."""
    try:
        capabilities = zapper_run(host, "get_capabilities")
        capabilities.append({"available": True})
    except SystemExit:
        capabilities = [{"available": False}]

    def stringify_cap(cap):
        return "\n".join(
            "{}: {}".format(key, val) for key, val in sorted(cap.items())
        )

    print("\n\n".join(stringify_cap(cap) for cap in capabilities))


def main(arguments=None):
    """Entry point."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default=os.environ.get("ZAPPER_HOST"),
        help=(
            "Address of Zapper to connect to. If not supplied, "
            "ZAPPER_HOST environment variable will be used."
        ),
    )
    parser.add_argument("cmd")
    parser.add_argument("args", nargs="*")
    args = parser.parse_args(arguments)

    if args.cmd == "get_capabilities":
        get_capabilities(args.host)
    else:
        result = zapper_run(args.host, args.cmd, *args.args)
        print(result)


if __name__ == "__main__":
    main()
