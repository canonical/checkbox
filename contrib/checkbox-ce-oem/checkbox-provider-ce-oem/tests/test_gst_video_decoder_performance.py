import unittest

from gst_video_decoder_performance import build_jetson_gst_command


class TestBuildJetsonGstCommand(unittest.TestCase):
    """The Jetson decoder pipeline: parsebin + nvv4l2decoder + nvvidconv."""

    def test_command_shape(self):
        cmd = build_jetson_gst_command(
            gst_bin="gst-launch-1.0",
            golden_sample_path="/data/1080p_30fps_h264.mp4",
            decoder="nvv4l2decoder",
            sink="fakesink",
            fpsdisplaysink_sync="false",
        )
        self.assertIn(
            "filesrc location=/data/1080p_30fps_h264.mp4 ! parsebin", cmd
        )
        self.assertIn("nvv4l2decoder ! queue ! nvvidconv", cmd)
        self.assertIn("video/x-raw,format=NV12", cmd)
        self.assertIn('fpsdisplaysink video-sink="fakesink"', cmd)
        self.assertIn("sync=false", cmd)


if __name__ == "__main__":
    unittest.main()
