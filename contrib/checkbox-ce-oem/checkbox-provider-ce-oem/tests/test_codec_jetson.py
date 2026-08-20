import argparse
import unittest

import codec_jetson
from codec_platforms import codec_factory
from gst_resources_generator import (
    compose_encoder_psnr_name,
    compose_decoder_performance_name,
)


class TestJetsonFactoryAndNames(unittest.TestCase):
    def test_factory_routes_jetson_platforms(self):
        for platform in (
            "jetson-orin-agx",
            "jetson-orin-nx",
            "jetson-orin-nano",
            "jetson-thor",
        ):
            self.assertIs(codec_factory(platform), codec_jetson)

    def test_encoder_name_shape(self):
        config = {
            "scenario": "gst_encoder_psnr",
            "encoder_plugin": "nvv4l2av1enc",
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "color_space": "",
            "mux": "",
        }
        self.assertEqual(
            compose_encoder_psnr_name("jetson-orin-agx", config),
            "jetson-gst_encoder_psnr-nvv4l2av1enc-1920x1080@30fps",
        )

    def test_perf_name_includes_sample(self):
        self.assertEqual(
            compose_decoder_performance_name(
                "jetson-orin-nano",
                "nvv4l2decoder",
                "1080p_30fps_av1",
                "gst_video_decoder_performance_fakesink",
            ),
            "jetson-gst_video_decoder_performance_fakesink-nvv4l2decoder"
            "-1080p_30fps_av1",
        )


class TestJetsonProject(unittest.TestCase):
    def _project(self, codec):
        return codec_jetson.JetsonProject(
            platform="jetson-orin-agx",
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

    def test_h265_pipeline_uses_h265_input(self):
        pipeline = self._project("nvv4l2h265enc").build_pipeline()
        self.assertIn("1080p_60fps_h265.mp4", pipeline)
        self.assertIn("qtdemux ! queue ! h265parse ! nvv4l2decoder", pipeline)
        self.assertIn("nvv4l2h265enc bitrate=8000000", pipeline)

    def test_av1_pipeline_uses_matroska(self):
        p = self._project("nvv4l2av1enc")
        pipeline = p.build_pipeline()
        self.assertIn("nvv4l2av1enc ! av1parse ! matroskamux", pipeline)
        self.assertTrue(p.artifact_file.endswith(".mkv"))

    def test_unknown_codec_exits(self):
        with self.assertRaises(SystemExit):
            self._project("nvv4l2vp9enc").build_pipeline()

    def test_create_encoder_psnr_project(self):
        args = argparse.Namespace(
            platform="jetson-thor",
            encoder_plugin="nvv4l2h264enc",
            color_space="",
            width=1920,
            height=1080,
            framerate=60,
            mux="",
        )
        self.assertIsInstance(
            codec_jetson.create_encoder_psnr_project(args),
            codec_jetson.JetsonProject,
        )


class TestJetsonDecoderPerformanceCommand(unittest.TestCase):
    def test_command_shape(self):
        args = argparse.Namespace(
            platform="jetson-orin-nx",
            decoder_plugin="nvv4l2decoder",
            golden_sample_path="/data/1080p_30fps_h264.mp4",
            sink="fakesink",
            fpsdisplaysink_sync="false",
        )
        cmd = codec_jetson.create_decoder_performance_project(
            args
        ).build_pipeline()
        self.assertIn(
            "filesrc location=/data/1080p_30fps_h264.mp4 ! parsebin", cmd
        )
        self.assertIn("nvv4l2decoder ! queue ! nvvidconv", cmd)
        self.assertIn("video/x-raw,format=NV12", cmd)
        self.assertIn('fpsdisplaysink video-sink="fakesink"', cmd)
        self.assertIn("sync=false", cmd)


if __name__ == "__main__":
    unittest.main()
