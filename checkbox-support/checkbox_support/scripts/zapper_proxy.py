# Copyright 2022 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

It uses internal Zapper Control RPyC API. Should this API change, additional
ZapperControl classes should be added here.
"""
import os

from abc import abstractmethod
from importlib import import_module

from checkbox_support.vendor.auto_argparse import AutoArgParser


# Zapper Control is expected to change its RPC API.  Following adapter classes
# serve the purpose of maintaining funcionality throughout the RPC API version
# changes.

class IZapperControl:
    """Interface to the Zapper Control."""
    @abstractmethod
    def usb_get_state(self, address):
        """
        Get state of USBMUX addon.
        Note that the address string is used as-is without any checks done on
        this side. Any validation and use of that param will be done on the
        remote end.

        :param str address: address of USBMUX to get state from.
        :return str: state of the USBMUX addon.
        """

    @abstractmethod
    def usb_set_state(self, address, state):
        """
        Set state of USBMUX addon.
        Note that both arguments are used as-is without any checks done on
        this side. Any validation and use of those params will be done on the
        remote end.

        :param str address: address of USBMUX the state should be set on.
        :param str state: state to set on the USBMUX addon
        """

    @abstractmethod
    def get_capabilities(self):
        """Get Zapper's setup capabilities in checkbox resource form."""


class ZapperControlV1(IZapperControl):
    """
    Control Zapper via RPyC using v1 of the API.

    :return str: list of capabilities in Checkbox resource form.
    """
    def __init__(self, connection):
        self._conn = connection

    def usb_get_state(self, address):
        ret = []
        success = self._conn.root.zombiemux_get_state(address, ret)
        if not success:
            raise SystemExit(
                "Failed to get state for address {}.".format(address))
        print("State for address {} is {}".format(address, ret[0]))

    def usb_set_state(self, address, state):
        success = self._conn.root.zombiemux_set_state(address, state)
        if not success:
            raise SystemExit(
                "Failed to set '{}' state for address {}.".format(
                    state, address))
        print("State '{}' set for the address {}.".format(state, address))

    def get_capabilities(self):
        capabilities = self._conn.root.get_capabilities()

        def stringify_cap(cap):
            return '\n'.join(
                '{}: {}'.format(key, val) for key, val in sorted(cap.items()))
        print('\n\n'.join(stringify_cap(cap) for cap in capabilities))


class ControlVersionDecider:
    """
    This class helps establish which API version of Zapper Control to use.

    Normally it would be just in the main function, but some of the clients of
    this functionality may be internal code from checkbox-support, this class
    makes it possible to use the code without spawning new python process
    (processing args etc.)

    It is a class and not a function, because we should inform the user about
    missing RPyC module as soon as possible, in this case in the __init__.  The
    RPyC is kept in the instance state, so later on it may be used to run the
    actual functionality.
    """
    def __init__(self):
        # to not make checkbox-support dependant on RPyC let's use one
        # available in the system, and if it's not available let's try loading
        # one provided by Checkbox. Real world usecase would be to run this
        # program from within Checkbox, so chances for not finding it are
        # pretty slim.
        try:
            self._rpyc = import_module('rpyc')
        except ImportError:
            try:
                self._rpyc = import_module('plainbox.vendor.rpyc')
            except ImportError as exc:
                msg = "RPyC not found. Neither from sys nor from Checkbox"
                raise SystemExit(msg) from exc

    def decide(self, host):
        """
        Determine which version of Zapper Control API to use.

        :param str host: Address of the Zapper host to connect to.
        :returns IZapperControl: An appropriate ZapperControl instance.
        """
        conn = self._rpyc.connect(
            host, 60000, config={"allow_all_attrs": True})
        try:
            version = conn.root.get_api_version()
        except AttributeError:
            # there was no "get_api_version" method on Zapper
            # so this means the oldest version possible - 1
            version = 1
        # the following mapping could be replaced by something that generates
        # a class name and tries looking it up in this module, but using dict
        # feels simpler due to explicitness and can include classes defined in
        # some other modules
        control_cls = {
            1: ZapperControlV1,
        }.get(version, None)
        if control_cls is None:
            raise SystemExit((
                "Zapper host returned unknown Zapper Control Version: {ver}\n"
                "Implement ZapperControlV{ver} in checkbox_support!"
            ).format(ver=version))
        return control_cls(conn)


def main():
    """Entry point."""
    decider = ControlVersionDecider()

    # generate argparse from the interface of Zapper Control
    parser = AutoArgParser(cls=IZapperControl)
    parser.add_argument(
        '--host', default=os.environ.get('ZAPPER_ADDRESS'),
        help=("Address of Zapper to connect to. If not supplied, "
              "ZAPPER_ADDRESS environment variable will be used.")
    )
    # turn Namespace into a normal dict
    args = parser.parse_args()
    # popping elements from the dict, so at the end the end the right method
    # is called with only the item that are expected
    host = args.host
    if host is None:
        raise SystemExit(
            "You have to provide Zapper host, either via '--host' or via "
            "ZAPPER_ADDRESS environment variable")
    zapper_control = decider.decide(host)
    parser.run(zapper_control)


if __name__ == '__main__':
    main()
