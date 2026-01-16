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
from pathlib import Path
from checkbox_support.snap_utils.system import in_classic_snap

# Checkbox could run in a snap container, so we need to prepend this root path

CHECKBOX_RUNTIME = None
if "SNAP" in os.environ:
    # don't use $CHECKBOX_RUNTIME in Path() unless in classic
    if in_classic_snap():
        CHECKBOX_RUNTIME = Path(  # pyright: ignore[reportConstantRedefinition]
            os.environ["CHECKBOX_RUNTIME"]
        )
    else:
        CHECKBOX_RUNTIME = (  # pyright: ignore[reportConstantRedefinition]
            Path(os.environ["SNAP"]) / "checkbox-runtime"
        )

GLMARK2_DATA_PATH = Path("/usr/share/glmark2")


class GLSupportTester:

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

    def extract_gl_variable(
        self,
        glmark2_validate_output: str,
        gl_variable_name: "T.Literal['GL_VERSION', 'GL_RENDERER']",
    ) -> str:
        """Attempts to extract the specified gl variable from
        `glmark2 --validate`'s output

        :param glmark2_validate_output: stdout of `glmark2 --validate`
        :param gl_variable_name: the variable to get
        :raises SystemExit: when the value of this variable doesn't appear in
                            glmark2_validate_output
        :return: value of gl_variable_name, trimmed
        """
        gl_renderer_line = None  # type: str | None
        for line in glmark2_validate_output.splitlines():
            if gl_variable_name in line:
                gl_renderer_line = line.strip()
                break

        if gl_renderer_line is None:
            raise SystemExit(
                "{} was not in glmark2's output".format(gl_variable_name)
            )

        return gl_renderer_line.split(":")[-1].strip()

    def call_glmark2_validate(
        self, glmark2_executable_override: "str | None" = None
    ) -> str:
        """
        Calls 'glmark2 --validate --offscreen' with the symlink hack,
        but allow errors to be thrown unlike reboot_check_test.py

        :raises SystemExit: when XDG_SESSION_TYPE is not x11/wayland
        :return: stdout of `glmark2 --validate`
        """

        XDG_SESSION_TYPE = os.environ.get("XDG_SESSION_TYPE")
        if XDG_SESSION_TYPE not in ("x11", "wayland"):
            # usually it's tty if we get here,
            # happens when gnome failed to start or not using graphical session
            raise SystemExit(
                "Unsupported session type: '{}'. ".format(XDG_SESSION_TYPE)
                + "Expected either 'x11' or 'wayland'"
            )

        print("XDG_SESSION type used by the desktop is:", XDG_SESSION_TYPE)

        if glmark2_executable_override is not None:
            if shutil.which(glmark2_executable_override) is None:
                raise SystemExit(
                    "Override command '{}' doesn't exist".format(
                        glmark2_executable_override
                    )
                )
            glmark2_executable = glmark2_executable_override
        else:
            glmark2_executable = self.pick_glmark2_executable(
                XDG_SESSION_TYPE, platform.uname().machine
            )

        try:
            if CHECKBOX_RUNTIME and not os.path.exists(GLMARK2_DATA_PATH):
                # the official way to specify the location of the data files
                # is "--data-path path/to/data/files"
                # but 16, 18, 20 doesn't have this option
                # and the /usr/share/glmark2 path is hard-coded inside glmark2
                # by the GLMARK_DATA_PATH build macro

                # do not directly truediv against GLMARK2_DATA_PATH
                # absolute path on the right will overwrite the left hand side
                src = CHECKBOX_RUNTIME / "usr" / "share" / "glmark2"
                dst = GLMARK2_DATA_PATH
                print(
                    "[ DEBUG ] Symlinking glmark2 data dir ({} -> {})".format(
                        src, dst
                    )
                )
                os.symlink(src, dst, target_is_directory=True)

            glmark2_output = sp.check_output(
                # all glmark2 programs share the same args
                [glmark2_executable, "--off-screen", "--validate"],
                universal_newlines=True,
                # be more relaxed on this timeout in case
                # the device needs a lot of time to wake up the GPU
                timeout=120,
            )
            return glmark2_output
        finally:
            # immediately cleanup
            if CHECKBOX_RUNTIME and os.path.islink(GLMARK2_DATA_PATH):
                print("[ DEBUG ] Un-symlinking glmark2 data")
                os.unlink(GLMARK2_DATA_PATH)


def remove_prefix(s: str, prefix: str) -> str:
    """3.8 and older doesn't have <str>.removeprefix()"""
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


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


def main() -> None:
    args = parse_args()
    tester = GLSupportTester()
    glmark2_output = tester.call_glmark2_validate(args.glmark2_override)

    gl_version_str = (
        remove_prefix(
            tester.extract_gl_variable(
                glmark2_output, "GL_VERSION"
            ),  # 4.6 (Compatibility Profile) Mesa 25.0.7-0ubuntu0.25.04.1
            "OpenGL ES",  # OpenGL ES 3.0 Mesa 18.0.5
        )
        .strip()  # technically not needed but might as well be careful
        .split()[0]  # 4.6
        .strip()  # final cleanup
    )
    # Mesa Intel(R) Graphics (LNL)
    gl_renderer = tester.extract_gl_variable(glmark2_output, "GL_RENDERER")

    print("GL_VERSION:", gl_version_str)
    print("GL_RENDERER:", gl_renderer)

    # check if it's newer than 3.0
    # we don't have to check the minor version
    # since it would be just comparing a positive int to 0
    if int(gl_version_str.split(".")[0]) < 3:
        raise SystemExit(
            "The minimum required OpenGL version is 3.0, but got {}".format(
                gl_version_str
            )
        )

    if not tester.gl_renderer_str_is_hardware_renderer(gl_renderer):
        raise SystemExit(
            "This machine is not using a hardware renderer. "
            + "Got GL_RENDERER={}".format(gl_renderer)
        )

    print(
        "OK! This machine meets the minimum OpenGL version requirement",
        "({} >= 3.0)".format(gl_version_str),
        "and is using a hardware renderer for {} apps".format(
            os.environ["XDG_SESSION_TYPE"]
        ),  # wayland working doesn't necessarily imply Xwayland working
    )


if __name__ == "__main__":
    main()
