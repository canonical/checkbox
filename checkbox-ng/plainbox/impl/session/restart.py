# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>
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

"""Interfaces and implementation of application restart strategies."""

import abc
import errno
import os
import subprocess

from plainbox.impl.secure.config import PlainBoxConfigParser


class IRestartStrategy(metaclass=abc.ABCMeta):

    """Interface for managing application restarts."""

    @abc.abstractmethod
    def prime_application_restart(self, app_id: str,
                                  session_id: str, cmd: str,) -> None:
        """
        Configure the system to restart the testing application.

        :param app_id:
            Identifier of the testing application.
        :param session_id:
            Identifier of the session to resume.
        :param cmd:
            The command to execute to resume the session.
        """

    @abc.abstractmethod
    def diffuse_application_restart(self, app_id: str) -> None:
        """
        Configure the system not to restart the testing application.

        :param app_id:
            Identifier of the testing application.
        """


class XDGRestartStrategy(IRestartStrategy):

    """
    Restart strategy implemented with the XDG auto-start mechanism.

    See: https://developer.gnome.org/autostart-spec/
    """

    def __init__(
        self, *,
        app_name: str=None,
        app_generic_name: str=None,
        app_comment: str=None,
        app_icon: str=None,
        app_terminal: bool=False,
        app_categories: str=None,
        app_startup_notify: bool=False
    ):
        """
        Initialize the XDG resume strategy.

        :param cmd_callback:
            The command callback
        """
        self.config = config = PlainBoxConfigParser()
        self.app_terminal = app_terminal
        section = 'Desktop Entry'
        config.add_section(section)
        config.set(section, 'Type', 'Application')
        config.set(section, 'Version', '1.0')
        config.set(section, 'Name',
                   app_name or 'Resume Testing Session')
        config.set(section, 'GenericName',
                   app_generic_name or 'Resume Testing Session')
        config.set(section, 'Comment',
                   app_comment or 'Automatically resume the testing session')
        config.set(section, 'Terminal', 'true' if app_terminal else 'false')
        if app_icon:
            config.set(section, 'Icon', app_icon)
        config.set(section, 'Categories', app_categories or 'System')
        config.set(section, 'StartupNotify',
                   'true' if app_startup_notify else 'false')

    def get_desktop_filename(self, app_id: str) -> str:
        # TODO: use correct xdg lookup mechanism
        return os.path.expandvars(
            "$HOME/.config/autostart/{}.desktop".format(app_id))

    def prime_application_restart(self, app_id: str,
                                  session_id: str, cmd: str) -> None:
        filename = self.get_desktop_filename(app_id)
        if self.app_terminal:
            cmd += ';$SHELL'
        self.config.set('Desktop Entry', 'Exec', cmd)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'wt') as stream:
            self.config.write(stream, space_around_delimiters=False)

    def diffuse_application_restart(self, app_id: str) -> None:
        filename = self.get_desktop_filename(app_id)
        try:
            os.remove(filename)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                pass
            else:
                raise


class SnappyRestartStrategy(IRestartStrategy):

    """
    Restart strategy based on systemd calling snappy wrappers.
    """

    service_name = "plainbox-autostart.service"

    def __init__(self):
        self.config = config = PlainBoxConfigParser()

        section = 'Unit'
        config.add_section(section)
        config.set(section, 'Description', 'Plainbox Resume Wrapper')
        config.set(section, 'After', 'ubuntu-snappy.frameworks.target')
        config.set(section, 'Requires', 'ubuntu-snappy.frameworks.target')
        config.set(section, 'X-Snappy', 'yes')

        section = 'Service'
        config.add_section(section)
        config.set(section, 'Type', 'oneshot')

        section = 'Install'
        config.add_section(section)
        config.set(section, 'WantedBy', 'multi-user.target')

    def get_autostart_config_filename(self) -> str:
        return os.path.abspath(
            os.path.join(os.sep, "etc", "systemd", "system",
                         self.service_name))

    def prime_application_restart(self, app_id: str, session_id: str,
                                  cmd: str,) -> None:
        """
        In this stategy plainbox will create and enable a systemd unit that
        will be run when the OS resumes.
        """
        snap_name = os.getenv('SNAP_NAME')
        # NOTE: This implies that any snap wishing to include a Checkbox
        # application to be autostarted creates snapcraft binary
        # called "checkbox-autostart"
        self.config.set('Service', 'ExecStart',
                        '/apps/bin/{}.checkbox-autostart --resume {}'.format(
                            snap_name, session_id))
        filename = self.get_autostart_config_filename()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'wt') as stream:
            self.config.write(stream, space_around_delimiters=False)
        subprocess.call(['systemctl', 'enable', self.service_name])

    def diffuse_application_restart(self, app_id: str) -> None:
        """
        This disables and removes the systemd unit that was created to resume
        the session after an OS reboot.
        """
        filename = self.get_autostart_config_filename()
        subprocess.call(['systemctl', 'disable', self.service_name])
        try:
            os.remove(filename)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                pass
            else:
                raise


def detect_restart_strategy() -> IRestartStrategy:
    """
    Detect the restart strategy for the current environment.

    :returns:
        A restart strategy object.
    :raises LookupError:
        When no such object can be found.
    """
    if os.path.isdir('/etc/xdg/autostart'):
        # NOTE: Assume this is a terminal application
        return XDGRestartStrategy(app_terminal=True)

    # If we are running as a confined Snappy app this variable will have been
    # set by the launcher script
    if(os.getenv("SNAP") or os.getenv("SNAP_APP_PATH")):
        return SnappyRestartStrategy()

    raise LookupError("Unable to find appropriate strategy.""")

def get_strategy_by_name(name: str) -> type:
    """
    Get restart strategy class identified by a string.

    :param name:
        Name of the strategy.
    :returns:
        Class conforming to IRestartStrategy.
    :raises KeyError:
        When there's no strategy associated with that name.
    """
    return {
        'XDG': XDGRestartStrategy,
        'Snappy': SnappyRestartStrategy,
    }[name]
