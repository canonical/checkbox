#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

import shutil
import subprocess as sp
import typing as T
import os
import platform
import argparse

# Checkbox could run in a snap container, so we need to prepend this root path
RUNTIME_ROOT = os.getenv("CHECKBOX_RUNTIME", default="").rstrip("/")
# Snap mount point, see
# https://snapcraft.io/docs/environment-variables#heading--snap
SNAP = os.getenv("SNAP", default="").rstrip("/")
# global const for subprocess calls that should timeout
COMMAND_TIMEOUT_SECONDS = 30


class GLSupportTester:

    def get_desktop_environment_variables(
        self,
    ) -> "dict[str, str]":
        """Gets all the environment variables used by the desktop process

        :return: dict[str, str] similar to os.environ
            None if the desktop process is not found
        """
        # "-s" guarantees at most 1 result
        # do not use check_output here,
        # pidof will return 1 when process is not found
        gnome_pid = sp.run(
            ["pidof", "-s", "gnome-shell"],
            stdout=sp.PIPE,
            universal_newlines=True,
        )
        # TODO: remove unity related checks after 16.04 reaches EOL
        compiz_pid = sp.run(  # 16.04 only
            ["pidof", "-s", "compiz"], stdout=sp.PIPE, universal_newlines=True
        )

        desktop_pid = None  # type: int | None
        if gnome_pid.returncode == 0:
            desktop_pid = int(gnome_pid.stdout)
        elif compiz_pid.returncode == 0:
            desktop_pid = int(compiz_pid.stdout)

        if desktop_pid is None:
            # this means the desktop failed to load
            # or we are not in a graphical session
            raise RuntimeError(
                "Unable to get the environment variables "
                + "used by either gnome or unity. "
                + "Is the desktop process running?",
            )

        # /proc/pid/environ is a null-char separated string
        proc_env_strings = sp.check_output(
            ["cat", "/proc/{}/environ".format(desktop_pid)],
            universal_newlines=True,
        ).split("\0")

        # ideally we don't manually parse this and just use the env file
        # but py3.5 only takes a mapping for the env param
        desktop_env_vars = {}  # type: dict[str, str]
        for env_str in proc_env_strings:
            kv = env_str.split("=", maxsplit=1)  # DISPLAY=:0
            if len(kv) == 2:
                key, value = kv
                desktop_env_vars[key] = value

        return desktop_env_vars

    def pick_glmark2_executable(
        self, xdg_session_type: str, cpu_arch: str
    ) -> str:
        """
        Pure function that picks a glmark2 executable based on xdg_session_type
        and cpu arch

        :param xdg_session_type: the $XDG_SESSION_TYPE variable
        :param cpu_arch: the `uname -m` value like x86_64
        :return: glmark2 command to use. Caller is responsible for checking if
                 the command exists
        """
        if cpu_arch in ("x86_64", "amd64"):
            # x86 DUTs should run the version that uses the full opengl api
            glmark2_executable = "glmark2"
        else:
            # default to es2 as the common denominator
            # TODO: explicitly check for aarch64?
            glmark2_executable = "glmark2-es2"

        if xdg_session_type == "wayland":
            glmark2_executable += "-wayland"
        # if x11, don't add anything
        return glmark2_executable

    def gl_renderer_str_is_hardware_renderer(self, gl_renderer: str) -> bool:
        """Checks if gl_renderer is produced by a hardware renderer.

        This uses the same logic as unity_support_test. Details:
        https://github.com/canonical/checkbox/issues/1630#issuecomment-2540843110

        :param gl_renderer: the GL_RENDERER string.
        https://registry.khronos.org/OpenGL-Refpages/gl4/html/glGetString.xhtml
        :return: whether GL_RENDERER is produced by a hardware renderer
        """
        # These 2 values are carried over from unity_support_test
        # never seen this before on devices after ubuntu 16
        if gl_renderer in ("Software Rasterizer", "Mesa X11"):
            return False
        # https://docs.mesa3d.org/envvars.html#envvar-GALLIUM_DRIVER
        # it's almost always the 'llvmpipe' case if we find software rendering
        if "llvmpipe" in gl_renderer or "softpipe" in gl_renderer:
            return False

        return True

    def extract_gl_renderer_str(
        self,
        glmark2_validate_output: str,
        gl_variable_name: "T.Literal['GL_VERSION', 'GL_RENDERER']",
    ) -> str:
        """Attempts to extract the specified gl variable from
        `glmark2 --validate`'s output

        :param glmark2_validate_output: stdout of `glmark2 --validate`
        :param gl_variable_name: the variable to get
        :raises ValueError: when the value of this variable doesn't appear in
                            glmark2_validate_output
        :return: value of gl_variable_name, trimmed
        """
        gl_renderer_line = None  # type: str | None
        for line in glmark2_validate_output.splitlines():
            if gl_variable_name in line:
                gl_renderer_line = line
                break

        if gl_renderer_line is None:
            raise ValueError(
                "{} was not in glmark2's output".format(gl_variable_name)
            )

        return gl_renderer_line.split(":")[-1].strip()

    def call_glmark2_validate(
        self, glmark2_executable_override: "str|None" = None
    ) -> str:
        """
        Calls 'glmark2 --validate' with the symlink hack,
        but allow error to be thrown unlike reboot_check_test.py

        :raises ValueError: when XDG_SESSION_TYPE is not x11/wayland
        :return: stdout of `glmark2 --validate`
        """
        desktop_env_vars = self.get_desktop_environment_variables()

        XDG_SESSION_TYPE = desktop_env_vars.get("XDG_SESSION_TYPE")
        if XDG_SESSION_TYPE not in ("x11", "wayland"):
            # usually it's tty if we get here,
            # happens when gnome failed to start or not using graphical session
            raise ValueError(
                "Unsupported session type: '{}'. ".format(XDG_SESSION_TYPE)
                + "Expected either 'x11' or 'wayland'"
            )

        print("XDG_SESSION type used by the desktop is:", XDG_SESSION_TYPE)

        if glmark2_executable_override is not None:
            if shutil.which(glmark2_executable_override) is None:
                raise FileNotFoundError(
                    "Override '{}' doesn't exist".format(
                        glmark2_executable_override
                    )
                )
            glmark2_executable = glmark2_executable_override
        else:
            glmark2_executable = self.pick_glmark2_executable(
                XDG_SESSION_TYPE, platform.uname().machine
            )
        glmark2_data_path = "/usr/share/glmark2"

        try:
            if RUNTIME_ROOT and not os.path.exists(glmark2_data_path):
                # the official way to specify the location of the data files
                # is "--data-path path/to/data/files"
                # but 16, 18, 20 doesn't have this option
                # and the /usr/share/glmark2 path is hard-coded inside glmark2
                # by the GLMARK_DATA_PATH build macro
                src = "{}/usr/share/glmark2".format(RUNTIME_ROOT)
                dst = glmark2_data_path
                print(
                    "[ DEBUG ] Symlinking glmark2 data dir ({} -> {})".format(
                        src, dst
                    )
                )
                os.symlink(src, dst, target_is_directory=True)
            # override is needed for snaps on classic ubuntu
            # to allow the glmark2 command itself to be discovered
            # in debian version of checkbox this line does nothing
            desktop_env_vars["PATH"] = os.environ["PATH"]
            glmark2_output = sp.check_output(
                # all glmark2 programs share the same args
                [glmark2_executable, "--off-screen", "--validate"],
                universal_newlines=True,
                # be more relaxed on this timeout in case
                # the device needs a lot of time to wake up the GPU
                timeout=120,
                # literally dump all envs from gnome/unity to glmark2
                env=desktop_env_vars,
            )
            return glmark2_output
        finally:
            # immediately cleanup
            if RUNTIME_ROOT and os.path.islink(glmark2_data_path):
                print("[ DEBUG ] Un-symlinking glmark2 data")
                os.unlink(glmark2_data_path)


def remove_prefix(s: str, prefix: str):
    """3.5 doesn't have <str>.removeprefix()"""
    if not s.startswith(prefix):
        return s
    return s[len(prefix) :]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--glmark2-override",
        help=(
            "Override the glmark2 executable to use, "
            "even if it might be unsupported on this platform"
        ),
        choices=(
            "glmark2",
            "glmark2-wayland",
            "glmark2-es2",
            "glmark2-es2-wayland",
        ),
        required=False,
    )
    return parser.parse_args()


def main():
    args = parse_args()
    tester = GLSupportTester()
    glmark2_output = tester.call_glmark2_validate(args.glmark2_override)

    gl_version_number = (
        remove_prefix(
            tester.extract_gl_renderer_str(
                glmark2_output, "GL_VERSION"
            ),  # 4.6 (Compatibility Profile) Mesa 25.0.7-0ubuntu0.25.04.1
            "OpenGL ES",
        )
        .split()[0]  # 4.6
        .strip()
    )
    # Mesa Intel(R) Graphics (LNL)
    gl_renderer = tester.extract_gl_renderer_str(glmark2_output, "GL_RENDERER")

    print("GL_VERSION:", gl_version_number)
    print("GL_RENDERER:", gl_renderer)

    # check if it's newer than 3.0
    # we don't have to check the minor version
    # since it would be just comparing to 0
    if int(gl_version_number.split(".")[0]) < 3:
        raise ValueError(
            "The minimum required OpenGL version is 3.0, but got {}".format(
                gl_version_number
            )
        )

    if not tester.gl_renderer_str_is_hardware_renderer(gl_renderer):
        raise ValueError(
            "This machine is not using a hardware renderer. "
            + "Got GL_RENDERER={}".format(gl_renderer)
        )

    print(
        "OK! This machine meets the minimum OpenGL version requirement",
        "({} >= 3.0)".format(gl_version_number),
        "and is using a hardware renderer",
    )


if __name__ == "__main__":
    main()
