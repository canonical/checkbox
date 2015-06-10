# This file is part of Checkbox.
#
# Copyright 2013-2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`checkbox_ng.commands.service` -- service sub-command
==========================================================

"""

from gettext import gettext as _
import logging
import os

from dbus import StarterBus, SessionBus
from dbus.mainloop.glib import DBusGMainLoop, threads_init
from dbus.service import BusName
from gi.repository import GObject
from plainbox.impl.highlevel import Service

from checkbox_ng.commands import CheckboxCommand
from checkbox_ng.service import ServiceWrapper


logger = logging.getLogger("checkbox.ng.commands.service")


def connect_to_session_bus():
    """
    Connect to the session bus properly.

    Returns a tuple (session_bus, loop) where loop is a GObject.MainLoop
    instance. The loop is there so that you can listen to signals.
    """
    # We'll need an event loop to observe signals. We will need the instance
    # later below so let's keep it. Note that we're not passing it directly
    # below as DBus needs specific API. The DBusGMainLoop class that we
    # instantiate and pass is going to work with this instance transparently.
    #
    # NOTE: DBus tutorial suggests that we should create the loop _before_
    # connecting to the bus.
    logger.debug("Setting up glib-based event loop")
    # Make sure gobject threads don't crash
    GObject.threads_init()
    threads_init()
    loop = GObject.MainLoop()
    # Let's get the system bus object.
    logger.debug("Connecting to DBus session bus")
    if os.getenv("DBUS_STARTER_ADDRESS"):
        session_bus = StarterBus(mainloop=DBusGMainLoop())
    else:
        session_bus = SessionBus(mainloop=DBusGMainLoop())
    return session_bus, loop


class ServiceInvocation:

    def __init__(self, provider_loader, config_loader, ns):
        self.provider_loader = provider_loader
        self.config_loader = config_loader
        self.ns = ns

    def run(self):
        bus, loop = connect_to_session_bus()
        logger.info(_("Setting up DBus objects..."))
        session_list = []  # TODO: load sessions
        logger.debug(_("Constructing Service object"))
        service_obj = Service(
            self.provider_loader(), session_list, self.config_loader())
        logger.debug(_("Constructing ServiceWrapper"))
        service_wrp = ServiceWrapper(service_obj, on_exit=lambda: loop.quit())
        logger.info(_("Publishing all objects on DBus"))
        service_wrp.publish_related_objects(bus)
        logger.info(
            _("Publishing all managed objects (events should fire there)"))
        service_wrp.publish_managed_objects()
        logger.debug(_("Attempting to claim bus name: %s"), self.ns.bus_name)
        bus_name = BusName(self.ns.bus_name, bus)
        logger.info(
            _("PlainBox DBus service ready, claimed name: %s"),
            bus_name.get_name())
        try:
            loop.run()
        except KeyboardInterrupt:
            logger.warning(_(
                "Main loop interrupted!"
                " It is recommended to call the Exit() method on the"
                " exported service object instead"))
        finally:
            logger.debug(_("Releasing %s"), bus_name)
            # XXX: ugly but that's how one can reliably release a bus name
            del bus_name
            # Remove objects from the bus
            service_wrp.remove_from_connection()
            logger.debug(_("Closing %s"), bus)
            bus.close()
            logger.debug(_("Main loop terminated, exiting..."))


class ServiceCommand(CheckboxCommand):
    """
    DBus service for PlainBox
    """

    def invoked(self, ns):
        return ServiceInvocation(
            self.provider_loader, self.config_loader, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser("service", help=_("spawn dbus service"))
        self.register_arguments(parser)

    def register_arguments(self, parser):
        parser.add_argument(
            '--bus-name', action="store",
            default="com.canonical.certification.PlainBox1",
            help=_("use the specified DBus bus name"))
        parser.set_defaults(command=self)
