#!/usr/bin/env python3
"""
Reboot networking, wait for a while and check if it's possible to send
some pings
"""
import sys
import os
import time
import threading
import logging
import logging.handlers

from subprocess import check_output, check_call, CalledProcessError, STDOUT
from argparse import ArgumentParser

try:
    import gi

    gi.require_version("GLib", "2.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GObject, GLib

    GLib.threads_init()
    GObject.threads_init()
    gtk_found = True
except (ImportError, RuntimeError):
    gtk_found = False


class PingError(Exception):
    def __init__(self, address, reason):
        self.address = address
        self.reason = reason


def main():
    args = parse_args()

    # Verify that script is run as root
    if os.getuid():
        sys.stderr.write(
            "This script needs superuser permissions to run correctly\n"
        )
        return 1

    configure_logging(args.log_level, args.output)

    # Select interface based on graphich capabilities available
    if "DISPLAY" in os.environ and gtk_found:
        factory = GtkApplication
    else:
        factory = CliApplication

    app = factory(args.address, args.times)
    return app.run()


class Application:
    """
    Network restart application
    """

    def __init__(self, address, times):
        self.address = address
        self.times = times
        self.return_code = 0

    def run(self):
        """
        Restart networking as many times as requested
        and use ping to verify
        """
        networking = Networking(self.address)
        logging.info("Initial connectivity check")
        success = ping(self.address)
        if not success:
            raise PingError(self.address, "Some interface is down")

        for i in range(self.times):
            if self.return_code:
                break
            if self.progress_cb:
                fraction = float(i) / self.times
                self.progress_cb(fraction)
            logging.info("Iteration {0}/{1}...".format(i + 1, self.times))
            networking.restart()
        else:
            if self.progress_cb:
                self.progress_cb(1.0)
            logging.info("Test successful")

        return self.return_code


class CliApplication(Application):
    progress_cb = None


class GtkApplication(Application):
    def __init__(self, address, times):
        Application.__init__(self, address, times)

        dialog = Gtk.Dialog(
            title="Network restart",
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL),
        )
        dialog.set_default_size(300, 100)

        alignment = Gtk.Alignment()
        alignment.set(0.5, 0.5, 1.0, 0.1)
        alignment.set_padding(10, 10, 10, 10)
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_show_text(True)
        alignment.add(progress_bar)

        content_area = dialog.get_content_area()
        content_area.pack_start(alignment, expand=True, fill=True, padding=0)

        dialog.connect("response", self.response_cb)
        dialog.show_all()

        # Add new logger handler to write info logs to progress bar
        logger = logging.getLogger()
        stream = ProgressBarWriter(progress_bar)
        formatter = logging.Formatter("%(message)s")
        log_handler = logging.StreamHandler(stream)
        log_handler.setLevel(logging.INFO)
        log_handler.setFormatter(formatter)
        logger.addHandler(log_handler)

        self.return_code = 0
        self.dialog = dialog
        self.progress_bar = progress_bar
        self.progress_log_handler = log_handler

    def response_cb(self, dialog, response_id):
        """
        Cancel test case execution
        when cancel or close button are closed
        """
        self.return_code = response_id
        logging.info("Test cancelled")
        Gtk.main_quit()

    def progress_cb(self, fraction):
        """
        Update progress bar
        """
        GLib.idle_add(self.progress_bar.set_fraction, fraction)

    def thread_target(self):
        """
        Run test case in a separate thread
        """
        try:
            Application.run(self)
        except PingError as exception:
            logging.error(
                "Failed to ping {0!r}\n{1}".format(
                    exception.address, exception.reason
                )
            )
            self.return_code = -1
        except CalledProcessError:
            self.return_code = -1
        finally:
            Gtk.main_quit()

    def run(self):
        """
        Launch test case and gtk mainloop
        """
        thread = threading.Thread(target=self.thread_target)
        thread.daemon = True
        thread.start()
        Gtk.main()
        return self.return_code


class ProgressBarWriter:
    """
    Write logs to a progress bar
    """

    def __init__(self, progressbar):
        self.progressbar = progressbar

    def write(self, message):
        if message == "\n":
            return
        GLib.idle_add(self.progressbar.set_text, message)


def ping(address):
    """
    Send ping to a given address
    """
    logging.info("Pinging {0!r}...".format(address))
    try:
        check_call(
            "ping -c 1 -w 5 {0}".format(address),
            stdout=open(os.devnull, "w"),
            stderr=STDOUT,
            shell=True,
        )
    except CalledProcessError:
        return False

    return True


class Networking:
    """
    Networking abstraction to start/stop all interfaces
    """

    def __init__(self, address):
        self.address = address
        self.interfaces = self._get_interfaces()

    def _get_interfaces(self):
        """
        Get all network interfaces
        """
        output = check_output(["/sbin/ifconfig", "-s", "-a"])
        lines = output.splitlines()[1:]
        interfaces = [
            interface
            for interface in [line.split()[0] for line in lines]
            if interface != "lo"
        ]
        return interfaces

    def restart(self):
        """
        Restart networking
        """
        self._stop()
        self._start()

    def _start(self):
        """
        Start networking
        """
        logging.info("Bringing all interfaces up...")
        for interface in self.interfaces:
            try:
                check_output(["/sbin/ifconfig", interface, "up"])
            except CalledProcessError:
                logging.error(
                    "Unable to bring up interface {0!r}".format(interface)
                )
                raise

        logging.info("Starting network manager...")
        try:
            check_output(["/sbin/start", "network-manager"])
        except CalledProcessError:
            logging.error("Unable to start network manager")
            raise

        # Verify that network interface is up
        for timeout in [2, 4, 8, 16, 32, 64]:
            logging.debug("Waiting ({0} seconds)...".format(timeout))
            time.sleep(timeout)
            success = ping(self.address)
            if success:
                break
        else:
            raise PingError(self.address, "Some interface is still down")

    def _stop(self):
        """
        Stop network manager
        """
        logging.info("Stopping network manager...")
        try:
            check_output(["/sbin/stop", "network-manager"])
        except CalledProcessError:
            logging.error("Unable to stop network manager")
            raise

        logging.info("Bringing all interfaces down...")
        for interface in self.interfaces:
            try:
                check_output(["/sbin/ifconfig", interface, "down"])
            except CalledProcessError:
                logging.error(
                    "Unable to bring down interface {0!r}".format(interface)
                )
                raise

        # Verify that network interface is down
        for timeout in [2, 4, 8]:
            logging.debug("Waiting ({0} seconds)...".format(timeout))
            time.sleep(timeout)
            success = ping(self.address)
            if not success:
                break
        else:
            raise PingError(self.address, "Some interface is still up")


def parse_args():
    """
    Parse command line options
    """
    parser = ArgumentParser(
        "Reboot networking interface and verify that is up again afterwards"
    )
    parser.add_argument(
        "-a",
        "--address",
        default="ubuntu.com",
        help=(
            "Address to ping to verify that network connection is up "
            "('%(default)s' by default)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default="/var/log",
        help="The path to the log directory. \
                              Default is /var/log",
    )
    parser.add_argument(
        "-t",
        "--times",
        type=int,
        default=1,
        help=(
            "Number of times that the network interface has to be restarted "
            "(%(default)s by default)"
        ),
    )
    log_levels = ["notset", "debug", "info", "warning", "error", "critical"]
    parser.add_argument(
        "--log-level",
        dest="log_level_str",
        default="notset",
        choices=log_levels,
        help=(
            "Log level. "
            "One of {0} or {1} (%(default)s by default)".format(
                ", ".join(log_levels[:-1]), log_levels[-1]
            )
        ),
    )
    args = parser.parse_args()
    args.log_level = getattr(logging, args.log_level_str.upper())
    return args


def configure_logging(log_level, output):
    """
    Configure logging
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Log to sys.stderr using log level passed through command line
    if log_level != logging.NOTSET:
        log_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)-8s %(message)s")
        log_handler.setFormatter(formatter)
        log_handler.setLevel(log_level)
        logger.addHandler(log_handler)

    # Log to rotating file using DEBUG log level
    log_filename = os.path.join(
        output,
        "{0}.log".format(os.path.splitext(os.path.basename(__file__))[0]),
    )
    rollover = os.path.exists(log_filename)
    log_handler = logging.handlers.RotatingFileHandler(
        log_filename, mode="a+", backupCount=3
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    log_handler.setFormatter(formatter)
    log_handler.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)
    if rollover:
        log_handler.doRollover()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PingError as exception:
        logging.error(
            "Failed to ping {0!r}\n{1}".format(
                exception.address, exception.reason
            )
        )
        sys.exit(1)
