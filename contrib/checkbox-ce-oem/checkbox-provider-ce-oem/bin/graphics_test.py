#!/usr/bin/env python3

import os
import sys
import subprocess
import re
import time
import logging

logger = logging.getLogger(__name__)


def setup_logging(verbose=False):
    """Configure logging output.

    Args:
        verbose: If True, set logging level to DEBUG; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def is_ubuntu_frame_active():
    """Check if ubuntu-frame is active."""
    try:
        subprocess.check_output(["pgrep", "-if", "ubuntu-frame"])
        logger.info("The ubuntu-frame is active")
        return True
    except subprocess.CalledProcessError:
        logger.info("ubuntu-frame is not active")
        return False


def test_ubuntu_frame_launching():
    """Test ubuntu-frame launching."""
    if is_ubuntu_frame_active():
        logger.info("No need to bring it up again")
        logger.info("journal log of ubuntu frame:")
        subprocess.run(["journalctl", "-b", "0", "-g", "ubuntu-frame"])
    else:
        logger.info("Activating ubuntu-frame now...")
        try:
            subprocess.run(
                ["timeout", "20s", "ubuntu-frame"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            if e.returncode == 124:
                logger.info(
                    "\nPASS: Timeout reached without any failures detected."
                )
            else:
                return 1
    return 0


def test_glmark2_es2_wayland():
    """Test glmark2-es2-wayland."""
    cmd = [
        "env",
        "XDG_RUNTIME_DIR=/run/user/0",
        "graphics-test-tools.glmark2-es2-wayland",
    ]
    exit_code = 0

    frame_pid = None
    if not is_ubuntu_frame_active():
        logger.info("Activating ubuntu-frame now...")
        proc = subprocess.Popen(
            ["ubuntu-frame"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        frame_pid = proc.pid
        time.sleep(10)

    logger.info("Running glmark2-es2-wayland benchmark...")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    output = ""
    for line in process.stdout:
        logger.info(line.strip())
        output += line

    process.wait()

    if frame_pid:
        subprocess.run(["kill", str(frame_pid)])

    gl_vendor = os.environ.get("GL_VENDOR")
    gl_renderer = os.environ.get("GL_RENDERER")

    if not gl_vendor or not gl_renderer:
        logger.error(
            "FAIL: 'GL_VENDOR' or 'GL_RENDERER' is empty. "
            "Please set them in config file!"
        )
        return 1

    if not re.search(r"GL_VENDOR:\s+{}".format(gl_vendor), output):
        logger.error("FAIL: Wrong vendor!")
        logger.error(
            "The expected 'GL_VENDOR' should include '{}'!".format(gl_vendor)
        )
        exit_code = 1
    else:
        logger.info("PASS: GL_VENDOR is '{}'".format(gl_vendor))

    if not re.search(r"GL_RENDERER:\s+{}".format(gl_renderer), output):
        logger.error("FAIL: Wrong renderer!")
        logger.error(
            "The expected 'GL_RENDERER' should include '{}'".format(
                gl_renderer
            )
        )
        exit_code = 1
    else:
        logger.info("PASS: GL_RENDERER is '{}'".format(gl_renderer))

    return exit_code


def help_function():
    """Show help message."""
    logger.info("This script is used for graphics test cases")
    logger.info("Usage: graphics_test.py <test_case>")
    logger.info("Test cases currently implemented:")
    logger.info("\t<frame>: test_ubuntu_frame_launching")
    logger.info("\t<glmark2>: test_glmark2_es2_wayland")


def main():
    """Main function."""
    setup_logging()
    if len(sys.argv) != 2:
        help_function()
        sys.exit(1)

    test_case = sys.argv[1]
    if test_case == "frame":
        sys.exit(test_ubuntu_frame_launching())
    elif test_case == "glmark2":
        sys.exit(test_glmark2_es2_wayland())
    else:
        help_function()
        sys.exit(1)


if __name__ == "__main__":
    main()
