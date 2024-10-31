#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import time
import shlex
import uuid

from rpyc_client import rpyc_client

MEDIA_SERVER_IP = os.getenv("MEDIA_SERVER_IP", "10.102.182.83")
PLAINBOX_SESSION_SHARE = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")


def resource_generator():
    pass


class MediaServerAdapter:
    """
    MediaServerAdapter class handles anything on Media Server side. A Media
    Server can be a laptop with Ubuntu Desktop environment 24.04 or later.

    (Whatever?) No matter what type of Media Server is, the golden sample
    (big_buck_bunny) must be placed on it properly.
    """

    MEDIA_SERVER_IP = "HDMI_INPUT_MEDIA_SERVER_IP"

    def __init__(self) -> None:
        self._media_server_ip = os.getenv(self.MEDIA_SERVER_IP)
        self._golden_sample = os.path.join(
            "$HOME",
            "media_server",
            "sample_2_big_bug_bunny",
            "big_bug_bunny_1920x1080_60fps_h264.mp4",
        )


def play_video(file_path) -> None:
    """
    Trigger the Media Server plays a video through RPyC.
    """
    # FIXME: leverage the generic rpyc_client function in the future
    rpyc_conn = rpyc_client(host=MEDIA_SERVER_IP, port=18819)
    rpyc_conn.root.play_video(file_path)


class RecorderCtx:
    def __init__(self, record_command: str, timeout: int = 600) -> None:
        self._record_command = record_command
        self._timeout = timeout
        self._process = None

    def __enter__(self):
        # Start the GStreamer process
        self._process = subprocess.Popen(shlex.split(self._record_command))
        time.sleep(2)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            # Wait for the process to complete, with a timeout
            self._process.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            print("Process did not complete within the timeout, killing it...")
            self._process.kill()
            self._process.wait()  # Ensure it fully terminates


def generate_artifact_name(extension: str = "mp4") -> str:
    n = "{}.{}".format(str(uuid.uuid4()).replace("-", "")[:6], extension)
    return os.path.join(PLAINBOX_SESSION_SHARE, n)


def video_record() -> str:
    """
    Record the video
    """
    af = generate_artifact_name()
    # 1. Use gstreamer to record video of HDMI Input for 20 secs in background
    # 2. Play a video (golden sample) through RPyC API
    # 3. Validation
    command = (
        "gst-launch-1.0 -q v4l2src device=/dev/video5 num-buffers=1200 !"
        " video/x-raw,width=1920,height=1080,format=NV21 ! queue ! "
        "v4l2h264enc output-io-mode=dmabuf-import capture-io-mode=mmap ! "
        "queue ! h264parse ! qtmux ! filesink location={}"
    ).format(af)
    golden_path = "/home/ubuntu/sample/video1.mp4"
    with RecorderCtx(record_command=command):
        print("Recording...")
        play_video(file_path=golden_path)
        print("Done...")

    return af


def main() -> None:
    af = video_record()
    # TODO: validation
    print(af)


if __name__ == "__main__":
    main()
