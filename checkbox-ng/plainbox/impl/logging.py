# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.impl.logging` -- configuration for logging
=========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

__all__ = ['setup_logging', 'adjust_logging']

import logging
import logging.config
import os
import sys

from plainbox.impl.color import ansi_on, ansi_off


logger = logging.getLogger("plainbox.logging")

# XXX: enable ansi escape sequences if sys.std{out,err} are both TTYs
#
# This is a bad place to take this decision (ideally we'd do that per log
# handler) but it's rather hard to do correctly (handlers know where stuff
# goes, formatters decide how stuff looks like) so this half solution is
# better than nothing.
if sys.stdout.isatty() and sys.stderr.isatty():
    ansi = ansi_on
else:
    ansi = ansi_off


class ANSIFormatter(logging.Formatter):
    """
    Formatter that allows to expand '{ansi}' (using new-style
    python formatting syntax) inside format descriptions.
    """

    def __init__(self, fmt=None, datefmt=None, style='%'):
        if fmt is not None:
            fmt = fmt.format(ansi=ansi)
        super(ANSIFormatter, self).__init__(fmt, datefmt, style)


class LevelFilter:
    """
    Log filter that accepts records in a certain level range
    """

    def __init__(self, min_level="NOTSET", max_level="CRITICAL"):
        self.min_level = logging._checkLevel(min_level)
        self.max_level = logging._checkLevel(max_level)

    def filter(self, record):
        if self.min_level <= record.levelno <= self.max_level:
            return 1
        else:
            return 0


class LoggingHelper:
    """
    Helper class that manages logging subsystem
    """

    def setup_logging(self):
        # Ensure that the logging directory exists. This is important
        # because we're about to open some files there.
        if not os.path.exists(self.log_dir):
            # It seems that exists_ok is flaky
            os.makedirs(self.log_dir, exist_ok=True)
        # Apply the default configuration. This overrides anything currently
        # defined for all of the logging subsystem in this python runtime
        logging.config.dictConfig(self.DEFAULT_CONFIG)

    def adjust_logging(self, level=None, trace_list=None, debug_console=False):
        # Bump logging on the root logger if requested
        if level is not None:
            logging.getLogger(None).setLevel(level)
            logger.debug("Enabled %r on root logger", level)
            logging.getLogger("plainbox").setLevel(level)
        # Enable tracing on specified loggers
        if trace_list is not None:
            for name in trace_list:
                logging.getLogger(name).setLevel(logging.DEBUG)
                logger.debug("Enabled debugging on logger %r", name)
        if debug_console and (level == 'DEBUG' or trace_list):
            # Enable DEBUG logging to console if explicitly requested
            logging.config.dictConfig(self.DEBUG_CONSOLE_CONFIG)

    @property
    def log_dir(self):
        """
        directory with all of the log files
        """
        xdg_cache_home = os.environ.get('XDG_CACHE_HOME') or \
            os.path.join(os.path.expanduser('~'), '.cache')
        return os.path.join(xdg_cache_home, 'plainbox', 'logs')

    @property
    def DEFAULT_CONFIG(self):
        return {
            "version": 1,
            "formatters": {
                "console_debug": {
                    "()": "plainbox.impl.logging.ANSIFormatter",
                    "format": (
                        "{ansi.f.BLACK}{ansi.s.BRIGHT}"
                        "%(levelname)s"
                        "{ansi.s.NORMAL}{ansi.f.RESET}"
                        " "
                        "{ansi.f.CYAN}{ansi.s.DIM}"
                        "%(name)s"
                        "{ansi.f.RESET}{ansi.s.NORMAL}"
                        ": "
                        "{ansi.s.DIM}"
                        "%(message)s"
                        "{ansi.s.NORMAL}"
                    ),
                },
                "console_info": {
                    "()": "plainbox.impl.logging.ANSIFormatter",
                    "format": (
                        "{ansi.f.WHITE}{ansi.s.BRIGHT}"
                        "%(levelname)s"
                        "{ansi.s.NORMAL}{ansi.f.RESET}"
                        " "
                        "{ansi.f.CYAN}%(name)s{ansi.f.RESET}"
                        ": "
                        "%(message)s"
                    ),
                },
                "console_warning": {
                    "()": "plainbox.impl.logging.ANSIFormatter",
                    "format": (
                        "{ansi.f.YELLOW}{ansi.s.BRIGHT}"
                        "%(levelname)s"
                        "{ansi.f.RESET}{ansi.s.NORMAL}"
                        " "
                        "{ansi.f.CYAN}%(name)s{ansi.f.RESET}"
                        ": "
                        "{ansi.f.WHITE}%(message)s{ansi.f.RESET}"
                    ),
                },
                "console_error": {
                    "()": "plainbox.impl.logging.ANSIFormatter",
                    "format": (
                        "{ansi.f.RED}{ansi.s.BRIGHT}"
                        "%(levelname)s"
                        "{ansi.f.RESET}{ansi.s.NORMAL}"
                        " "
                        "{ansi.f.CYAN}%(name)s{ansi.f.RESET}"
                        ": "
                        "{ansi.f.WHITE}%(message)s{ansi.f.RESET}"
                    ),
                },
                "log_precise": {
                    "format": (
                        "%(asctime)s "
                        "[pid:%(process)s, thread:%(threadName)s, "
                        "reltime:%(relativeCreated)dms] "
                        "%(levelname)s %(name)s: %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "filters": {
                "only_debug": {
                    "()": "plainbox.impl.logging.LevelFilter",
                    "max_level": "DEBUG",
                },
                "only_info": {
                    "()": "plainbox.impl.logging.LevelFilter",
                    "min_level": "INFO",
                    "max_level": "INFO",
                },
                "only_warnings": {
                    "()": "plainbox.impl.logging.LevelFilter",
                    "min_level": "WARNING",
                    "max_level": "WARNING",
                },
            },
            "handlers": {
                "console_debug": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "console_debug",
                    "filters": ["only_debug"],
                    "level": 150,
                },
                "console_info": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "console_info",
                    "filters": ["only_info"],
                },
                "console_warning": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "console_warning",
                    "filters": ["only_warnings"],
                },
                "console_error": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "console_error",
                    "level": "ERROR",
                },
                "logfile_debug": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": os.path.join(self.log_dir, "debug.log"),
                    "maxBytes": 32 << 20,
                    "backupCount": 3,
                    "mode": "a",
                    "formatter": "log_precise",
                    "delay": True,
                    "filters": ["only_debug"],
                },
                "logfile_error": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": os.path.join(self.log_dir, "error.log"),
                    "backupCount": 3,
                    "level": "ERROR",
                    "mode": "a",
                    "formatter": "log_precise",
                    "delay": True,
                },
                "logfile_crash": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": os.path.join(self.log_dir, "crash.log"),
                    "backupCount": 3,
                    "level": "ERROR",
                    "mode": "a",
                    "formatter": "log_precise",
                    "delay": True,
                },
            },
            "loggers": {
                "plainbox": {
                    "level": "WARNING",
                    "handlers": [
                        "console_debug",
                        "console_info",
                        "console_warning",
                        "console_error",
                        "logfile_error",
                        "logfile_debug"
                    ],
                },
                "plainbox.crashes": {
                    "level": "ERROR",
                    "handlers": ["logfile_crash"],
                },
            },
            "root": {
                "level": "WARNING",
            },
            "incremental": False,
            "disable_existing_loggers": True,
        }

    @property
    def DEBUG_CONSOLE_CONFIG(self):
        return {
            "version": 1,
            "handlers": {
                "console_debug": {
                    "level": "DEBUG",
                },
            },
            "incremental": True,
        }


# Instantiate the helper
_LoggingHelper = LoggingHelper()

# And expose two methods from it
setup_logging = _LoggingHelper.setup_logging
adjust_logging = _LoggingHelper.adjust_logging
