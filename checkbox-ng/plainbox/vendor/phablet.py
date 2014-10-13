#!/usr/bin/env python3
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the the GNU General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the applicable version of the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
:mod:`phablet` -- Ubuntu Phablet API
====================================

This module provides a very simple synchronous command execution interface for
the Ubuntu Phablet (phone and tablet)

Example:

    phablet = Phablet()
    retval = phablet.run('false')

You can also use phablet as an executable:

    python3 -m phablet --help
"""

from gettext import gettext as _
import argparse
import logging
import os
import subprocess

__version__ = "0.1"

_logger = logging.getLogger("phablet")


class PhabletError(Exception):
    """
    Base class for all phablet exceptions
    """


class UnableToStartSSH(PhabletError):
    """
    Exception raised when ssh cannot be started on the phablet device
    """

    def __str__(self):
        return _("Unable to start SSH on the phablet device")


class PortForwardingError(PhabletError):
    """
    Exception raised TCP port forwarding between the tablet and the local
    machine cannot be established
    """

    def __str__(self):
        return _("Unable to setup port forwarding to the phablet device")


class DeviceNotDetected(PhabletError):
    """
    Exception raised when the phablet device is not connected or not turned on
    """

    def __str__(self):
        return _("No phablet devices detected")


class MultipleDevicesDetected(PhabletError):
    """
    Exception raised when multiple devices are connected and :class:`Phablet`
    is constructed without passing a specific device serial number.
    """

    def __str__(self):
        return _("Multiple phablet devices detected")


class UnableToPurgeKnownSSHHost(PhabletError):
    """
    Exception raised when ~/.ssh/known_hosts entry for the phablet cannot
    be purged.
    """

    def __str__(self):
        return _(
            "Unable to purge phablet device entry from ~/.ssh/known_hosts")


class UnableToCopySSHKey(PhabletError):
    """
    Exception raised when local public ssh key cannot be copied over as a know
    authorized key onto the phablet device
    """

    def __str__(self):
        return _("Unable to copy public ssh key over to the phablet device")


class NoPublicKeysFound(PhabletError):
    """
    Exception raised when there are no public keys that can be used to
    authorize the connection to a phablet device
    """

    def __str__(self):
        return _("No public ssh keys found on the local account")


class ProgrammingError(PhabletError):
    """
    Exception raised if the API is used incorrectly.
    """

    def __str__(self):
        return _("Programming error: {0}").format(self.args)


class Phablet:
    """
    Pythonic interface to the Ubuntu Phablet
    """

    def __init__(self, serial=None):
        """
        Initialize a new Phablet device.

        :param serial:
            serial number of the phablet device to talk to

        Note that if you don't specify the serial number and the user happens
        to have more than one device connected then :meth:`run()` will raise
        :class:`MultipleDevicesDetected`.
        """
        self._serial = serial
        self._port = None

    @property
    def serial(self):
        """
        serial number of the device (or None)
        """
        return self._serial

    @property
    def port(self):
        """
        local tcp port where phablet ssh is exposed

        This is None if ssh port forwarding was not established yet
        """
        return self._port

    def run(self, cmd, timeout=None, key=None):
        """
        Run a command on the phablet device using ssh

        :param cmd:
            a list of strings to execute as a command
        :param timeout:
            a timeout (in seconds) for device discovery
        :param key:
            a path to a public ssh key to use for connection
        :returns:
            the exit code of the command

        This method will not allow you to capture stdout/stderr from the target
        process. If you wish to do that please consider switching to one of
        subprocess functions along with. :meth:`cmdline()`.
        """
        if not isinstance(cmd, list):
            raise TypeError("cmd needs to be a list")
        if not all(isinstance(item, str) for item in cmd):
            raise TypeError("cmd needs to be a list of strings")
        self.connect(timeout, key)
        return self._run_ssh(cmd)

    def connect(self, timeout=None, key=None):
        """
        Perform one-time setup procedure.

        :param timeout:
            a timeout (in seconds) for device discovery
        :param key:
            a path to a public ssh key to use for connection

        This method will allow you to execute :meth:`cmdline()`
        repeatedly without incurring the extra overhead of the setup procedure.

        Note that this procedure needs to be repeated whenever:
        - the target device reboots
        - the local adb server is restarted
        - your ssh keys change

        .. versionadded:: 0.2
        """
        if self.port is not None:
            return
        self._wait_for_device(timeout)
        self._setup_port_forwarding()
        self._purge_known_hosts_entry()
        self._copy_ssh_key(key)

    def ssh_cmdline(self, cmd):
        """
        Get argument list for meth:`subprocess.Popen()` to run ssh.

        :param cmd:
            a list of arguments to pass to ssh
        :returns:
            argument list to pass as the first argument to subprocess.Popen()

        .. note::
            you must call :meth:`connect()` at least once
            before calling this method.

        This method returns the ``args`` argument (first argument) to
        subprocess.Popen() required to execute the specified command on the
        phablet device. You can use it to construct your own connections, to
        intercept command output or to setup any additional things that you may
        require.

        .. versionadded:: 0.2
        """
        if not isinstance(cmd, list):
            raise TypeError("cmd needs to be a list")
        if not all(isinstance(item, str) for item in cmd):
            raise TypeError("cmd needs to be a list of strings")
        if self._port is None:
            raise ProgrammingError("run connect() first")
        ssh_cmd = ['ssh']
        for opt in self._get_ssh_options():
            ssh_cmd.append('-o')
            ssh_cmd.append(opt)
        ssh_cmd.extend(['phablet@localhost', '--'])
        ssh_cmd.extend(cmd)
        _logger.debug("ssh_cmdline %r => %r", cmd, ssh_cmd)
        return ssh_cmd

    cmdline = ssh_cmdline

    def rsync_cmdline(self, src, dest, *rsync_options):
        """
        Get argument list for meth:`subprocess.Popen()` to run rsync.

        :param src:
            source file or directory
        :param dest:
            destination file or directory
        :param rsync_options:
            any additional arguments to pass to rsync, useful if you
            want to pass '-a'
        :returns:
            argument list to pass as the first argument to subprocess.Popen()

        .. note::
            you must call :meth:`connect()` at least once
            before calling this method.

        This method returns the ``args`` argument (first argument) to
        subprocess.Popen() required to rsync something over to the phablet
        device. You can use it to construct your own connections, to intercept
        command output or to setup any additional things that you may require.

        .. versionadded:: 0.2
        """
        if not all(isinstance(item, str) for item in rsync_options):
            raise TypeError("cmd needs to be a list of strings")
        if self._port is None:
            raise ProgrammingError("run connect() first")
        ssh_cmd = ['ssh']
        for opt in self._get_ssh_options():
            ssh_cmd.append('-o')
            ssh_cmd.append(opt)
        rsync_cmd = ['rsync', '-e', ' '.join(ssh_cmd),
                     str(src), 'phablet@localhost:{}'.format(dest)]
        rsync_cmd.extend(rsync_options)
        _logger.debug("rsync_cmdline %r-> %r (with %s) => %r",
                      src, dest, ' '.join(rsync_options), rsync_cmd)
        return rsync_cmd

    def push(self, src, dest, timeout=None, key=None):
        """
        Push (synchronize) some data onto the phablet device

        :param src:
            source file or directory
        :param dest:
            destination file or directory
        :param timeout:
            a timeout (in seconds) for device discovery
        :param key:
            a path to a public ssh key to use for connection
        :returns:
            the exit code of the command
        """
        self.connect(timeout, key)
        _logger.info("Pushing %r to %r", src, dest)
        return self._check_call(
            self.rsync_cmdline(src, dest, '-a'))

    def _check_call(self, *args, **kwargs):
        kwargs_display = dict(kwargs)
        if 'env' in kwargs_display:
            del kwargs_display['env']
        _logger.debug("check_call: %r %r", args, kwargs_display)
        return subprocess.check_call(*args, **kwargs)

    def _check_output(self, *args, **kwargs):
        kwargs_display = dict(kwargs)
        if 'env' in kwargs:
            del kwargs_display['env']
        _logger.debug("check_output: %r %r", args, kwargs_display)
        return subprocess.check_output(*args, **kwargs)

    def _call(self, *args, **kwargs):
        kwargs_display = dict(kwargs)
        if 'env' in kwargs_display:
            del kwargs_display['env']
        _logger.debug("call: %r %r", args, kwargs_display)
        return subprocess.call(*args, **kwargs)

    def _invoke_adb(self, cmd, *args, **kwargs):
        env = os.environ
        if self._serial is not None:
            env['ANDROID_SERIAL'] = self._serial
        return self._check_call(
            cmd, *args, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, **kwargs)

    def _wait_for_device(self, timeout):
        _logger.info("Waiting for device")
        if hasattr(subprocess, "TimeoutExpired"):
            try:
                self._invoke_adb(['adb', 'wait-for-device'], timeout=timeout)
            except subprocess.TimeoutExpired:
                raise DeviceNotDetected
            except subprocess.CalledProcessError:
                if self._serial is None:
                    raise MultipleDevicesDetected
                else:
                    raise DeviceNotDetected
        else:
            if timeout is not None:
                raise ValueError("timeout is not supported on python2.x")
            try:
                self._invoke_adb(['adb', 'wait-for-device'])
            except subprocess.CalledProcessError:
                if self._serial is None:
                    raise MultipleDevicesDetected
                else:
                    raise DeviceNotDetected

    def _setup_port_forwarding(self):
        if self._port is not None:
            return
        _logger.info("Starting ssh on the device")
        try:
            self._invoke_adb(['adb', 'shell', (
                'gdbus call -y -d com.canonical.PropertyService'
                ' -o /com/canonical/PropertyService'
                ' -m com.canonical.PropertyService.SetProperty ssh true')])
        except subprocess.CalledProcessError:
            raise UnableToStartSSH
        _logger.info("Setting up port forwarding")
        for port in range(2222, 2299):
            try:
                self._check_call([
                    'adb', 'forward', 'tcp:{0}'.format(port), 'tcp:22'])
            except subprocess.CalledProcessError:
                continue
            else:
                self._port = port
                break
        else:
            raise PortForwardingError

    def _purge_known_hosts_entry(self):
        assert self._port is not None
        _logger.info("Purging ~/.ssh/known_hosts entry")
        try:
            _logger.debug
            self._check_call([
                'ssh-keygen', '-f', os.path.expanduser('~/.ssh/known_hosts'),
                '-R', '[localhost]:{0}'.format(self._port)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            raise UnableToPurgeKnownSSHHost

    def _find_public_key(self):
        _logger.info("Looking for a public ssh key")
        candidates = []
        ssh_dir = os.path.expanduser('~/.ssh/')
        for filename in os.listdir(ssh_dir):
            ssh_key = os.path.join(ssh_dir, filename)
            if os.path.isfile(ssh_key) and filename.endswith('.pub'):
                candidates.append(ssh_key)
        # Sort the keys by modification time, pick the most recent key
        candidates.sort(key=lambda f: os.stat(f).st_mtime, reverse=True)
        _logger.debug("Available ssh public keys: %r", candidates)
        if candidates:
            return candidates[0]

    def _copy_ssh_key(self, key):
        if key is None:
            key = self._find_public_key()
        if key is None:
            raise NoPublicKeysFound
        _logger.info("Setting up SSH connection using key: %s", key)
        try:
            self._invoke_adb([
                'adb', 'push', key, '/home/phablet/.ssh/authorized_keys'])
            self._invoke_adb([
                'adb', 'shell', 'chown', 'phablet:phablet', '-R',
                '/home/phablet/.ssh/'])
            self._invoke_adb([
                'adb', 'shell', 'chmod', '700', '/home/phablet/.ssh'])
            self._invoke_adb([
                'adb', 'shell', 'chmod', '600',
                '/home/phablet/.ssh/authorized_keys'])
        except subprocess.CalledProcessError:
            raise UnableToCopySSHKey

    def _run_ssh(self, cmd):
        return self._call(self.cmdline(cmd))

    def _get_ssh_options(self):
        return [
            'CheckHostIP=no',
            'StrictHostKeyChecking=no',
            'UserKnownHostsFile=/dev/null',
            'LogLevel=quiet',
            'KbdInteractiveAuthentication=no',
            'PasswordAuthentication=no',
            'Port={0}'.format(self._port),
        ]


class RemoteTemporaryDirectory:
    """
    A context manager for creating a temporary directory on a phablet device.

    Example copying a script to a temporary directory on the phablet::

        with RemoteTemporaryDirectory(phablet) as dirname:
            phablet.sync('script',  dirname)
            phablet.run(os.path.join(dirname, 'script'))

    .. versionadded:: 0.2
    """

    def __init__(self, phablet):
        """
        Initialize the remote temporary directory

        :param phablet:
            a Phablet instance. May be disconnected, it will be connected to if
            necessary. If you want to handle custom connection timeout or key
            settings please call phablet.connect() earlier.

        .. note::
            The directory is only created when this object is used as a context
            manager.
        """
        if not isinstance(phablet, Phablet):
            raise TypeError("phablet")
        self.dirname = None
        self.phablet = phablet

    def __enter__(self):
        if self.phablet.port is None:
            self.phablet.connect()
        self.dirname = self.phablet._check_output(
            self.phablet.ssh_cmdline(['mktemp', '-d', '--quiet']),
            universal_newlines=True
        ).splitlines()[0]
        return self.dirname

    def __exit__(self, *args):
        self.phablet._check_call(
            self.phablet.ssh_cmdline(['rm', '-rf', self.dirname]))


class SynchronizedDirectory:
    """
    A context manager for creating a temporary copy of a local directory
    remotely

    Example synchronizing data to a (random, temporary) directory:

        with SynchronizedDirectory('/usr/bin', phablet) as dirname:
            phablet.run(os.path.join(dirname, 'false'))

    .. versionadded:: 0.2
    """

    def __init__(self, dirname, phablet):
        if not isinstance(phablet, Phablet):
            raise TypeError("phablet")
        self.phablet = phablet
        self.dirname = dirname
        self.remote_tmpdir = RemoteTemporaryDirectory(phablet)

    def __enter__(self):
        remote_dirname = self.remote_tmpdir.__enter__()
        self.phablet.push(self.dirname, remote_dirname)
        return remote_dirname

    def __exit__(self, *args):
        self.remote_tmpdir.__exit__()


def main(args=None):
    """
    Phablet command line user interface

    This function implements the phablet command line tool
    """
    parser = argparse.ArgumentParser(
        description=_("Run a command on Ubuntu Phablet"),
        epilog="""
        This tool will start ssh on your connected Ubuntu Touch device, forward
        a local port to the device, copy your ssh id down to the device (so you
        can log in without a password), and then ssh into the device through
        the locally forwarded port.

        This results in a very nice shell, which for example can display the
        output of 'top' at the correct terminal size, rather than being stuck
        at 80x25 like 'adb shell'

        Like ssh-copy-id, this script will push down the newest ssh key it can
        find in ~/.ssh/*.pub, so if you find the wrong key being pushed down,
        simply use 'touch' to make your desired key the newest one, and then
        this script will find it.
        """)
    dev_group = parser.add_argument_group(_("device connection options"))
    dev_group.add_argument(
        '-s', '--serial', action='store',
        help=_('connect to the device with the specified serial number'),
        default=None)
    if hasattr(subprocess, 'TimeoutExpired'):
        dev_group.add_argument(
            '-t', '--timeout', type=float, default=30.0,
            help=_('timeout for device discovery'))
    else:
        dev_group.add_argument(
            '-t', '--timeout', type=float, default=None,
            help=argparse.SUPPRESS)
    dev_group.add_argument(
        '-k', '--public-key', action='store', default=None,
        help=_('use the specified public key'))
    log_group = parser.add_argument_group(_("logging options"))
    log_group.add_argument(
        '--verbose', action='store_const', dest='log_level',
        const='INFO', help=_('be more verbose during connection set-up'))
    log_group.add_argument(
        '--log-level', action='store',
        help=_('set log level (for debugging)'),
        choices=[
            logging.getLevelName(level)
            for level in [
                logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR,
                logging.CRITICAL]])
    parser.add_argument(
        'cmd', nargs='...',
        help=_('command to run on the phablet, '
               ' if left out an interactive shell is started'))
    parser.add_argument('--version', action='version', version=__version__)
    parser.set_defaults(log_level='WARNING')
    ns = parser.parse_args(args)
    try:
        # Py3k
        level = logging._nameToLevel[ns.log_level]
    except AttributeError:
        # Py27
        level = logging._levelNames[ns.log_level]
    logging.basicConfig(
        level=level, style='{', format="[{levelname:10}] {message}")
    try:
        phablet = Phablet(ns.serial)
        return phablet.run(ns.cmd, timeout=ns.timeout, key=ns.public_key)
    except PhabletError as exc:
        _logger.critical("%s", exc)
        return 255


if __name__ == "__main__":
    raise SystemExit(main())
