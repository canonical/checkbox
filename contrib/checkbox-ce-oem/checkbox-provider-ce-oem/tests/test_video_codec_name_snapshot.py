"""
Freeze the job names the video-codec resource emits for every shipped
conf file.

The unified templates render `id: ce-oem-video-codec/{{ name }}`, so
these names ARE the job ids - any accidental edit to the composition
logic or PLATFORM_FAMILIES silently renames historical jobs. This test
is the guard: it fails on any change to the emitted names.

After an agreed, deliberate id change, regenerate the snapshot with:
    python3 tests/test_video_codec_name_snapshot.py --regen
"""

import argparse
import glob
import os
import sys
import unittest
from unittest import mock

from gst_resources_generator import GstResources

PROVIDER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF_DIR = os.path.join(PROVIDER_ROOT, "data", "video-codec-test-confs")
SNAPSHOT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "video_codec_job_names.txt"
)


def emitted_names():
    """Return '<conf> <name>' lines for every conf, deterministically."""
    lines = []
    for conf_path in sorted(glob.glob(os.path.join(CONF_DIR, "*.json"))):
        conf_name = os.path.basename(conf_path)[: -len(".json")]
        args = argparse.Namespace(
            video_codec_conf_file=conf_path,
            video_codec_testing_data_path="/tmp/video-codec-snapshot",
        )
        # Pin the environment probes so the avsync video_sink (part of
        # its name) does not depend on the machine running the tests.
        with mock.patch(
            "gst_resources_generator.has_desktop_environment",
            return_value=False,
        ), mock.patch(
            "gst_resources_generator.on_ubuntucore", return_value=False
        ):
            resources = GstResources(args)
            for scenario in resources._scenarios:
                resources._current_scenario_name = scenario
                getattr(resources, scenario)(resources._scenarios[scenario])
                lines.extend(
                    "{} {}".format(conf_name, item["name"])
                    for item in resources._resource_items
                )
                resources._resource_items = []
    return lines


class TestJobNameSnapshot(unittest.TestCase):
    def test_names_match_snapshot(self):
        with open(SNAPSHOT_FILE) as snapshot:
            expected = snapshot.read().splitlines()
        self.assertEqual(
            emitted_names(),
            expected,
            "\nEmitted job names differ from tests/video_codec_job_names"
            ".txt.\nJob ids are the names - only regenerate the snapshot"
            " (--regen) for an\nagreed, deliberate id change.",
        )


if __name__ == "__main__":
    if "--regen" in sys.argv:
        with open(SNAPSHOT_FILE, "w") as snapshot:
            snapshot.write("\n".join(emitted_names()) + "\n")
        print("wrote {}".format(SNAPSHOT_FILE))
    else:
        unittest.main()
