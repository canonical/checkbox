# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hector Cao <hector.cao@canonical.com>
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

class ContainerBaseMachine:
    """Base implementation of Machine using LXD container as the backend."""

    CHECKBOX = 'checkbox-cli '  # mind the trailing space !

    def __init__(self, config, container):
        self.config = config
        self._container = container
        self._checkbox_wrapper = self.CHECKBOX

    def execute(self, cmd, env={}, verbose=False, timeout=0):
        return run_or_raise(
            self._container, self._checkbox_wrapper + cmd, env, verbose,
            timeout)

    def interactive_execute(self, cmd, env={}, verbose=False, timeout=0):
        return interactive_execute(
            self._container, self._checkbox_wrapper + cmd, env, verbose,
            timeout)

    def rollback_to(self, savepoint):
        if self._container.status != 'Stopped':
            self._container.stop(wait=True)
        self._container.restore_snapshot(savepoint, wait=True)
        self._container.start(wait=True)
        logger.opt(colors=True).debug(
            "[<y>restored</y>    ] {}", self._container.name)
        if self.config.role == 'service':
            attempts_left = 60
            out = ''
            while attempts_left and out.rstrip() not in (
                'starting', 'running', 'degraded'
            ):
                time.sleep(1)
                (ret, out, err) = self._container.execute(
                    ['systemctl', 'is-system-running'])
                attempts_left -= 1
            if not attempts_left:
                raise SystemExit("Rollback failed (systemd not ready)")

    def put(self, filepath, data, mode=None, uid=1000, gid=1000):
        try:
            self._container.files.put(filepath, data, mode, uid, gid)
        except pylxd.exceptions.NotFound:
            dirname = os.path.dirname(filepath)
            logger.debug(("Cannot put {} on container. Trying to create"
                          " directory {} and put the file again..."), filepath,
                         dirname)
            self._container.files.mk_dir(dirname, mode, uid, gid)
            self._container.files.put(filepath, data, mode, uid, gid)

    def get_connecting_cmd(self):
        return "lxc exec {} -- sudo --user ubuntu --login".format(
            self._container.name)

    @property
    def address(self):
        addresses = self._container.state().network['eth0']['addresses']
        return addresses[0]['address']

    def get_early_dir_transfer(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def get_file_transfer(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def get_early_setup(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def get_late_setup(self):
        """
        .. note:: You should override this method in your subclass.
        """
        return []

    def start_remote(self, host, launcher, interactive=False, timeout=0):
        assert (self.config.role == 'remote')

        if interactive:
            # Return a PTS object to interact with
            return self.interactive_execute(
                'remote {} {}'.format(host, launcher), verbose=True,
                timeout=timeout)
        else:
            # Return an ExecuteResult named tuple
            return self.execute(
                'remote {} {}'.format(host, launcher), verbose=True,
                timeout=timeout)

    def start(self, cmd=None, env={}, interactive=False, timeout=0):
        assert (self.config.role == 'local')
        if interactive:
            # Return a PTS object to interact with
            return self.interactive_execute(
                cmd, env=env, verbose=True, timeout=timeout)
        else:
            # Return an ExecuteResult named tuple
            return self.execute(
                cmd, env=env, verbose=True, timeout=timeout)

    def run_cmd(self, cmd, env={}, interactive=False, timeout=0):
        verbose = True
        if interactive:
            # Return a PTS object to interact with
            return interactive_execute(
                self._container, cmd, env, verbose, timeout)
        else:
            # Return an ExecuteResult named tuple
            return run_or_raise(
                self._container, cmd, env, verbose, timeout)

    def start_service(self, force=False):
        """
        .. note:: You should override this method in your subclass.
        """
        pass

    def stop_service(self):
        """
        .. note:: You should override this method in your subclass.
        """
        pass

    def reboot(self, timeout=0):
        verbose = True
        return run_or_raise(
            self._container, "sudo reboot", verbose, timeout)

    def is_service_active(self):
        """
        .. note:: You should override this method in your subclass.
        """
        pass

    def start_user_session(self):
        assert (self.config.role in ('service', 'local'))
        # Start a set of ubuntu-user-owned processes to fake an active GDM user
        # session (A virtual framebuffer and a pulseaudio server with a dummy
        # output)
        interactive_execute(
            self._container,
            "DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority "
            "XDG_SESSION_TYPE=x11 /usr/bin/Xvfb -screen 0 1280x1024x24")
        # Note: running the following commands as part of standard setup does
        # not make them persistent as after restoring snapshots user/1000
        # is gone from /run
        pulseaudio_setup_cmds = [
            'sudo mkdir -v -p /run/user/1000/pulse',
            'sudo chown -R ubuntu:ubuntu /run/user/1000/',
            "pulseaudio --start --exit-idle-time=-1 --disallow-module-loading",
        ]
        env = {'XDG_RUNTIME_DIR': '/run/user/1000'}
        for cmd in pulseaudio_setup_cmds:
            run_or_raise(self._container, cmd, env)

    def switch_off_networking(self):
        return run_or_raise(self._container, "sudo ip link set eth0 down")

    def switch_on_networking(self):
        return run_or_raise(self._container, "sudo ip link set eth0 up")
