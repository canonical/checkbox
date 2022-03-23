# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
import json
import os
import shlex
import subprocess
import tempfile

from plainbox.impl.secure.config import PlainBoxConfigParser
from plainbox.impl.unit.unit import on_ubuntucore


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
        # Prefix the command with sh -c to comply with the Exec spec
        # See https://askubuntu.com/a/1242773/32239
        cmd = "sh -c " + cmd
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
        config.set(section, 'StandardOutput', 'tty')
        config.set(section, 'StandardError', 'tty')
        config.set(section, 'TTYPath', '/dev/console')
        if os.getenv('USER'):
            config.set(section, 'User', os.getenv('USER'))

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
        cmd = shlex.split(cmd)[0]
        snap_name = os.getenv('SNAP_NAME')
        base_dir = 'snap'
        if os.getenv("SNAP_APP_PATH"):
            base_dir = 'apps'
        # NOTE: This implies that any snap wishing to include a Checkbox
        # application to be autostarted creates snapcraft binary
        # called "checkbox-cli"
        binary_name = '/{}/bin/{}.checkbox-cli'.format(base_dir, snap_name)
        self.config.set('Service', 'ExecStart', '{} {}'.format(
                            binary_name, ' '.join(cmd.split()[1:])))
        filename = self.get_autostart_config_filename()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        stream = tempfile.NamedTemporaryFile('wt', delete=False)
        self.config.write(stream, space_around_delimiters=False)
        stream.close()
        subprocess.call(['sudo', 'cp', stream.name, filename])
        os.unlink(stream.name)
        subprocess.call(['sudo', 'systemctl', 'enable', self.service_name])

    def diffuse_application_restart(self, app_id: str) -> None:
        """
        This disables and removes the systemd unit that was created to resume
        the session after an OS reboot.
        """
        filename = self.get_autostart_config_filename()
        subprocess.call(['sudo', 'systemctl', 'disable', self.service_name])
        subprocess.call(['sudo', 'rm', filename])


class RemoteSnappyRestartStrategy(IRestartStrategy):

    """
    Remote Restart strategy for checkbox snaps.
    """

    def __init__(self, debug=False):
        self.debug = debug
        self.session_resume_filename = self.get_session_resume_filename()

    def get_session_resume_filename(self) -> str:
        if self.debug:
            return '/tmp/session_resume'
        snap_data = os.getenv('SNAP_DATA')
        return os.path.join(snap_data, 'session_resume')

    def prime_application_restart(self, app_id: str,
                                  session_id: str, cmd: str) -> None:
        with open(self.session_resume_filename, 'wt') as f:
            f.write(session_id)
            os.fsync(f.fileno())

    def diffuse_application_restart(self, app_id: str) -> None:
        try:
            os.remove(self.session_resume_filename)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                pass
            else:
                raise


class RemoteDebRestartStrategy(RemoteSnappyRestartStrategy):

    """
    Remote Restart strategy for checkbox installed from deb packages.
    """

    service_name = "checkbox-ng.service"

    def get_session_resume_filename(self) -> str:
        if self.debug:
            return '/tmp/session_resume'
        cache_dir = os.getenv('XDG_CACHE_HOME', '/var/cache')
        return os.path.join(cache_dir, 'session_resume')

    def prime_application_restart(self, app_id: str,
                                  session_id: str, cmd: str) -> None:
        with open(self.session_resume_filename, 'wt') as f:
            f.write(session_id)
            os.fsync(f.fileno())
        if cmd == self.service_name:
            subprocess.call(['systemctl', 'disable', self.service_name])


def detect_restart_strategy(session=None, session_type=None) -> IRestartStrategy:
    """
    Detect the restart strategy for the current environment.
    :param session:
        The current session object.
    :returns:
        A restart strategy object.
    :raises LookupError:
        When no such object can be found.
    """
    # debian and unconfined checkbox-ng.service
    # 'checkbox-slave' is deprecated, it's here so people can resume old
    # session, but the next line should become:
    #  session_type == 'remote':
    # with the next release or when we do inclusive naming refactor
    # or roughly after April of 2022
    if session_type in ('remote', 'checkbox-slave'):
        try:
            subprocess.run(
                ['systemctl', 'is-active', '--quiet', 'checkbox-ng.service'],
                check=True)
            return RemoteDebRestartStrategy()
        except subprocess.CalledProcessError:
                pass

    # XXX: RemoteSnappyRestartStrategy debug
    remote_restart_stragegy_debug = os.getenv('REMOTE_RESTART_DEBUG')
    if remote_restart_stragegy_debug:
        return RemoteSnappyRestartStrategy(debug=True)
    # If we are running as a confined Snappy app this variable will have been
    # set by the launcher script
    if on_ubuntucore():
        try:
            slave_status = subprocess.check_output(
                ['snapctl', 'get', 'slave'], universal_newlines=True).rstrip()
            if slave_status == 'disabled':
                return SnappyRestartStrategy()
            else:
                return RemoteSnappyRestartStrategy()
        except subprocess.CalledProcessError:
            return SnappyRestartStrategy()

    try:
        if session:
            app_blob = json.loads(
                session._context.state.metadata.app_blob.decode('UTF-8'))
            session_type = app_blob.get("type")
        else:
            session_type = None
    except AttributeError:
        session_type = None

    # Classic snaps
    snap_data = os.getenv('SNAP_DATA')
    if snap_data:
        # Classic snaps w/ remote service enabled and in use
        # 'checkbox-slave' is deprecated, it's here so people can resume old
        # session, but the next line should become:
        #  session_type == 'remote':
        # with the next release or when we do inclusive naming refactor
        # or roughly after April of 2022
        if session_type in ('remote', 'checkbox-slave'):
            try:
                slave_status = subprocess.check_output(
                    ['snapctl', 'get', 'slave'],
                    universal_newlines=True).rstrip()
                if slave_status == 'enabled':
                    return RemoteSnappyRestartStrategy()
            except subprocess.CalledProcessError:
                pass
        # Classic snaps w/o remote service
        else:
            return SnappyRestartStrategy()

    if os.path.isdir('/etc/xdg/autostart'):
        # NOTE: Assume this is a terminal application
        return XDGRestartStrategy(app_terminal=True)

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
