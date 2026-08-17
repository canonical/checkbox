import argparse
import unittest

from gst_encoder_psnr import JetsonProject, project_factory


class TestJetsonProject(unittest.TestCase):
    """Pipelines and factory routing for the Jetson platforms."""

    def _project(self, codec, platform="orin-agx"):
        return JetsonProject(
            platform=platform,
            codec=codec,
            width=1920,
            height=1080,
            framerate=60,
        )

    def test_h264_pipeline(self):
        p = self._project("nvv4l2h264enc")
        pipeline = p.build_pipeline()
        self.assertIn("qtdemux ! queue ! h264parse ! nvv4l2decoder", pipeline)
        self.assertIn("nvv4l2h264enc bitrate=20000000", pipeline)
        self.assertIn("h264parse ! mp4mux", pipeline)
        self.assertIn("1080p_60fps_h264.mp4", pipeline)
        self.assertTrue(p.artifact_file.endswith(".mp4"))

    def test_h265_pipeline(self):
        pipeline = self._project("nvv4l2h265enc").build_pipeline()
        self.assertIn("nvv4l2h265enc bitrate=8000000", pipeline)
        self.assertIn("h265parse ! mp4mux", pipeline)

    def test_av1_pipeline_uses_matroska(self):
        p = self._project("nvv4l2av1enc")
        pipeline = p.build_pipeline()
        self.assertIn("nvv4l2av1enc ! av1parse ! matroskamux", pipeline)
        self.assertTrue(p.artifact_file.endswith(".mkv"))

    def test_unknown_codec_exits(self):
        with self.assertRaises(SystemExit):
            self._project("nvv4l2vp9enc").build_pipeline()

    def test_factory_routes_jetson_platforms(self):
        for platform in ("orin-agx", "orin-nx", "thor"):
            args = argparse.Namespace(
                platform=platform,
                encoder_plugin="nvv4l2h264enc",
                color_space="",
                width=1920,
                height=1080,
                framerate=60,
                mux="",
            )
            self.assertIsInstance(project_factory(args), JetsonProject)


if __name__ == "__main__":
    unittest.main()
