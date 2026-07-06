#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import re
import time
import logging

logger = logging.getLogger(__name__)


def debug_logging(verbose=False):
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
        proc = launch_ubuntu_frame()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait()
            logger.info("PASS: Timeout reached without any failures detected.")
        else:
            if proc.returncode != 0:
                logger.error(
                    "FAIL: ubuntu-frame exited earlier with code %s",
                    proc.returncode,
                )
                return 1
    return 0


def launch_ubuntu_frame():
    logger.info("Activating ubuntu-frame now...")
    proc = subprocess.Popen(
        ["ubuntu-frame"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def test_glmark2_es2_wayland():
    """Test glmark2-es2-wayland."""
    cmd = [
        "env",
        "XDG_RUNTIME_DIR=/run/user/0",
        "graphics-test-tools.glmark2-es2-wayland",
    ]
    exit_code = 0
    proc = None

    gl_vendor = os.environ.get("GL_VENDOR")
    gl_renderer = os.environ.get("GL_RENDERER")

    if not gl_vendor or not gl_renderer:
        logger.error(
            "FAIL: 'GL_VENDOR' or 'GL_RENDERER' is empty."
            "Please set them in config file!"
        )
        return 1

    if not is_ubuntu_frame_active():
        proc = launch_ubuntu_frame()
        time.sleep(10)

    logger.info("Running glmark2-es2-wayland benchmark...")
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True
        )
    except subprocess.CalledProcessError as e:
        output = e.output
    logger.info(output)

    if proc and proc.pid:
        proc.terminate()

    vendor_match = re.search(r"GL_VENDOR:\s+(.*)", output)
    renderer_match = re.search(r"GL_RENDERER:\s+(.*)", output)

    if not vendor_match or not renderer_match:
        logger.error(
            "FAIL: Could not find GL_VENDOR or GL_RENDERER in the output."
        )
        return 1

    if gl_vendor not in vendor_match.group(1):
        logger.error("FAIL: Wrong vendor!")
        logger.error(
            "The expected 'GL_VENDOR' should include '%s'!", gl_vendor
        )
        exit_code = 1
    else:
        logger.info("PASS: GL_VENDOR is '%s'" % vendor_match.group(1))

    if gl_renderer not in renderer_match.group(1):
        logger.error("FAIL: Wrong renderer!")
        logger.error(
            "The expected 'GL_RENDERER' should include '%s'", gl_renderer
        )
        exit_code = 1
    else:
        logger.info("PASS: GL_RENDERER is '%s'" % renderer_match.group(1))

    return exit_code


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="This script is used for graphics test cases"
    )
    parser.add_argument(
        "test_case",
        choices=["frame", "glmark2"],
        help="Test case to run",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )
    args = parser.parse_args()
    debug_logging(args.debug)

    if args.test_case == "frame":
        sys.exit(test_ubuntu_frame_launching())
    elif args.test_case == "glmark2":
        sys.exit(test_glmark2_es2_wayland())


if __name__ == "__main__":
    main()
