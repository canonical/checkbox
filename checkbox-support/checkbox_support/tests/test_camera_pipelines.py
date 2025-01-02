import itertools
from unittest.mock import MagicMock, patch

import unittest as ut
import sys
import gi
from checkbox_support.camera_pipelines import CapsResolver

gi.require_version("Gst", "1.0")
from gi.repository import Gst


class CapsResolverTests(ut.TestCase):

    resolver = None

    @classmethod
    def setUpClass(cls):
        Gst.init([])
        cls.resolver = CapsResolver()

    def test_fraction_list(self):
        out = self.resolver.get_all_fixated_caps(
            Gst.Caps.from_string(
                "image/jpeg, width=1280, height=720, framerate={ (fraction)30/1, (fraction)15/1 }"
            ),
            "remap",
        )

        self.assertEqual(
            [c.to_string() for c in out],
            [
                "image/jpeg, width=(int)1280, height=(int)720, framerate=(fraction)30/1",
                "image/jpeg, width=(int)1280, height=(int)720, framerate=(fraction)15/1",
            ],
        )

    def test_fraction_range(self):
        out = self.resolver.get_all_fixated_caps(
            Gst.Caps.from_string(
                "image/jpeg, width=1280, height=720, framerate=[ (fraction)1/1, (fraction)100/1 ]"
            ),
            "remap",
        )

        self.assertCountEqual(  # quality without order
            [cap.to_string() for cap in out],
            [
                "image/jpeg, width=(int)1280, height=(int)720, framerate=(fraction)15/1",
                "image/jpeg, width=(int)1280, height=(int)720, framerate=(fraction)30/1",
                "image/jpeg, width=(int)1280, height=(int)720, framerate=(fraction)60/1",
            ],
        )

    def test_int_range(self):
        out = self.resolver.get_all_fixated_caps(
            Gst.Caps.from_string(
                "image/jpeg, width=[1, 1280], height=[1, 720], framerate=[ (fraction)1/1, (fraction)100/1 ]"
            ),
            "remap",
        )
        answer = [
            "image/jpeg, width=(int){}, height=(int){}, framerate=(fraction){}".format(
                width, height, framerate
            )
            for width, height, framerate in itertools.product(
                (640, 1280), (480, 720), ("15/1", "30/1", "60/1")
            )
        ]
        self.assertCountEqual(  # quality without order
            [cap.to_string() for cap in out],
            answer,
        )

    def test_all_lists(self):
        widths = ["20", "30", "40"]
        heights = ["10", "720"]
        framerates = ["15/1", "30/1", "60/1"]
        answer = [
            "image/jpeg, width=(int){}, height=(int){}, framerate=(fraction){}".format(
                width, height, framerate
            )
            for width, height, framerate in itertools.product(
                widths, heights, framerates
            )
        ]
        out = self.resolver.get_all_fixated_caps(
            Gst.Caps.from_string(
                "image/jpeg, width={{{}}}, height={{{}}}, framerate={{{}}}".format(
                    ", ".join(widths),
                    ", ".join(heights),
                    ", ".join(framerates),
                )
            ),
            "remap",
        )
        self.assertCountEqual([cap.to_string() for cap in out], answer)


if __name__ == "__main__":
    ut.main()
