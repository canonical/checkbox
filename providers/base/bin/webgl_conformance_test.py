#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#     Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

from checkbox_support.helpers.file_watcher import FileWatcher
from pathlib import Path
import subprocess
import argparse
import requests
import logging
import time
import json
import sys
import os


def watch_test_result(directory: str, filename: str) -> bool:
    """
    Monitors a directory for the creation of a specific file.

    :param directory: The directory being monitored.
    :param filename: The filename being monitored.
    :returns: True when the file is created, False otherwise.
    :raises SystemExit: If the directory does not exist or the
                            inotify watch fails.
    """
    if not os.path.isdir(directory):
        raise SystemExit("Directory [{}] does not exist".format(directory))

    fw = FileWatcher()
    watch_fd = fw.watch_directory(directory, "c")
    if watch_fd < 0:
        raise SystemExit("Failed to add inotify watch")

    try:
        while True:
            events = fw.read_events(1024)
            for event in events:
                if event.event_type == "create" and event.name == filename:
                    logging.info("event detected: {}".format(event))
                    return True
    except Exception as e:
        logging.error("An error occurred during file watching: {}".format(e))
        return False
    finally:
        fw.stop_watch(watch_fd)


def is_webgl_conformance_url_reachable(url: str) -> bool:
    """
    Ensures that the WebGL conformance website is reachable.

    :param url: The WebGL conformance test website URL.
    :returns: True when reachable, False otherwise.
    """
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def remove_duplicate_file(file_path: str):
    """
    Removes a file if it exists.

    :param file_path: The full path to the file to be removed.
    """
    if os.path.exists(file_path):
        os.remove(file_path)
        logging.info("File removed: {}".format(file_path))


def validate_result(file_path: str):
    """
    Validates the WebGL conformance test result.

    :param file_path: The full path to the test result file.
    :raises SystemExit: If the test results are invalid or indicate
                            failures or software rendering.
    """
    failures = 0
    timeouts = 0
    is_software_renderer = False

    if not os.path.getsize(file_path) > 0:
        raise SystemExit("WebGL conformance tests result is empty")

    with open(file_path, "r") as f:
        try:
            result = json.load(f)
            pretty_result = json.dumps(result, indent=2)
            logging.info(pretty_result)
            failures = len(result.get("failures", []))
            timeouts = len(result.get("timeouts", []))
            # firefox will show llvm in the WebGL RENDERER field
            # chromium and chrome will show swiftShader in
            # the Unmasked RENDERER field
            webgl_renderer = result.get("testinfo", {}).get(
                "WebGL RENDERER", ""
            )
            unmasked_renderer = result.get("testinfo", {}).get(
                "Unmasked RENDERER", ""
            )

            is_software_renderer = (
                "llvm" in webgl_renderer or "SwiftShader" in unmasked_renderer
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise SystemExit("Failed to parse test result file: {}".format(e))

    # remove the file to avoid conflicts with the next test run
    os.remove(file_path)

    if is_software_renderer:
        raise SystemExit("Test is not running on hardware renderer")
    if failures > 0 or timeouts > 0:
        raise SystemExit("Not all WebGL conformance tests are passed")


def execute_webgl_test(browser: str, skip: str, filename: str, native: bool):
    """
    Starts the WebGL conformance test.

    :param browser: The target browser.
    :param skip: A string of tests to be skipped.
    :param filename: The filename for the test result.
    :param native: Use native OpenGL backend for Chromium/Chrome.
    """
    test_url = os.getenv(
        "WEBGL_CONFORMANCE_TEST_URL",
        default="http://localhost:8000/local-tests.html",
    )
    if not is_webgl_conformance_url_reachable(test_url):
        raise SystemExit("Test URL is not reachable: {}".format(test_url))

    # browser default download directory
    download = os.path.join(str(Path.home()), "Downloads")
    download_file_path = os.path.join(download, filename)

    remove_duplicate_file(download_file_path)

    cmd = [browser]
    if "firefox" == browser:
        # Don't keep old tab (--private-window)
        cmd.extend(["--new-instance", "--private-window"])
    elif browser in ["chromium", "google-chrome"]:
        cmd.append("--new-window")
        if native:
            # using native OpenGL backend
            cmd.append("--use-gl=desktop")
        if browser == "google-chrome":
            # Don't pop up welcome and register windows
            cmd.extend(["--no-first-run", "--disable-fre"])
            # Don't pop up keyring authentication
            cmd.append("--password-store=basic")
    if skip != "":
        cmd.append("{}?run=1&skip={}".format(test_url, skip))
    else:
        cmd.append("{}?run=1".format(test_url))

    logging.info("Executing command: {}".format(" ".join(cmd)))
    process = subprocess.Popen(cmd)

    watch_test_result(download, filename)

    # Firefox needs more time to save the file.
    time.sleep(5)

    process.terminate()
    process.wait()

    validate_result(download_file_path)


def parse_args(args=sys.argv[1:]):
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        prog="WebGL conformance test",
        description="Start the WebGL conformance test",
    )
    parser.add_argument(
        "browser",
        choices=["firefox", "chromium", "google-chrome"],
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Tests to be skipped (default: %(default)s).",
    )
    # filename defined in self host server
    parser.add_argument(
        "--filename",
        default="webgl-test-results.json",
        help="The filename of the test results (default: %(default)s).",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="Use native OpenGL backend for chromium/chrome.",
    )
    return parser.parse_args(args)


def main():
    args = parse_args()
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    execute_webgl_test(args.browser, args.skip, args.filename, args.native)


if __name__ == "__main__":
    main()
