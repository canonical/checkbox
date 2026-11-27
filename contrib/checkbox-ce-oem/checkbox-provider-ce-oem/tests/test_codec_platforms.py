import argparse
import os
import unittest
from unittest import mock

import codec_cix_tool
import codec_dragonwing
import codec_genio
import codec_imx
import codec_rz
from codec_base import BaseCodecProject
from codec_platforms import (
    PLATFORM_FAMILIES,
    PlatformFamily,
    codec_factory,
    create_scenario_project,
)
from gst_utils import (
    GST_DISCOVERER,
    PipelineInterface,
    get_source_colorimetry,
)


class TestCodecFactory(unittest.TestCase):
    """codec_factory resolves each platform to its family module."""

    def test_factory_routes_families(self):
        self.assertIs(codec_factory("genio-1200"), codec_genio)
        self.assertIs(codec_factory("dragonwing"), codec_dragonwing)
        self.assertIs(codec_factory("imx-8mp"), codec_imx)
        self.assertIs(codec_factory("rzg2l"), codec_rz)
        self.assertIs(codec_factory("cix-tool-p1"), codec_cix_tool)

    def test_factory_returns_none_for_unknown_platform(self):
        self.assertIsNone(codec_factory("newplatform"))

    def test_factory_returns_none_for_family_without_module(self):
        PLATFORM_FAMILIES["fakefam"] = PlatformFamily(id_prefix="fakefam")
        try:
            self.assertIsNone(codec_factory("fakefam-1"))
        finally:
            del PLATFORM_FAMILIES["fakefam"]

    def test_factory_surfaces_broken_module_imports(self):
        # a bad import INSIDE codec_<family>.py must not be masked as
        # an unknown platform
        with mock.patch(
            "codec_platforms.importlib.import_module",
            side_effect=ImportError("boom", name="missing_dependency"),
        ):
            with self.assertRaises(ImportError):
                codec_factory("genio-1200")

    def test_module_scenario_apis(self):
        for module in (
            codec_genio,
            codec_dragonwing,
            codec_imx,
            codec_rz,
        ):
            self.assertTrue(hasattr(module, "create_encoder_psnr_project"))
        # only the platforms with their own decoder pipeline provide the
        # decoder-performance project; the others use the generic one
        self.assertTrue(
            hasattr(codec_imx, "create_decoder_performance_project")
        )
        self.assertTrue(
            hasattr(codec_rz, "create_decoder_performance_project")
        )
        self.assertFalse(
            hasattr(codec_genio, "create_decoder_performance_project")
        )
        self.assertFalse(
            hasattr(codec_dragonwing, "create_decoder_performance_project")
        )

    def test_cix_tool_module_scenario_apis(self):
        for hook in (
            "create_encoder_psnr_project",
            "create_transform_resize_project",
            "create_transform_rotate_and_flip_project",
            "create_decoder_performance_project",
        ):
            self.assertTrue(hasattr(codec_cix_tool, hook))

    def test_cix_tool_encoder_psnr_is_zero_copy(self):
        def pipeline(encoder, mux):
            args = argparse.Namespace(
                platform="cix-tool-p1",
                encoder_plugin=encoder,
                width=3840,
                height=2160,
                framerate=30,
                color_space="NV12",
                mux=mux,
            )
            return codec_cix_tool.create_encoder_psnr_project(
                args
            ).build_pipeline()

        self.assertIn(
            "3840x2160_30fps_h264.mp4 ! parsebin ! v4l2h264dec"
            " ! video/x-raw(memory:DMABuf),format=DMA_DRM,drm-format=NV12"
            " ! v4l2h264enc output-io-mode=dmabuf-import ! h264parse"
            " ! mp4mux ! filesink",
            pipeline("v4l2h264enc", "mp4mux"),
        )
        self.assertIn(
            "3840x2160_30fps_mjpeg.mov ! parsebin ! v4l2jpegdec",
            pipeline("v4l2jpegenc", "qtmux"),
        )

    def test_create_scenario_project_dispatch(self):
        class FakeDefault:
            def __init__(self, args):
                self.args = args

        # unknown platform -> the scenario's generic default
        project = create_scenario_project(
            "newplatform", "create_encoder_psnr_project", FakeDefault, None
        )
        self.assertIsInstance(project, FakeDefault)
        # module without the hook -> the generic default too
        project = create_scenario_project(
            "genio-1200",
            "create_decoder_performance_project",
            FakeDefault,
            None,
        )
        self.assertIsInstance(project, FakeDefault)
        # module with the hook -> the platform project
        args = mock.Mock(
            platform="genio-1200",
            encoder_plugin="v4l2h264enc",
            color_space="NV12",
            width=1920,
            height=1080,
            framerate=30,
            mux="mp4mux",
        )
        project = create_scenario_project(
            "genio-1200", "create_encoder_psnr_project", FakeDefault, args
        )
        self.assertIsInstance(project, codec_genio.GenioProject)


class TestBaseCodecProject(unittest.TestCase):
    """Every platform project inherits the basic class (which itself
    implements the PipelineInterface ABC) and overrides only what
    differs, like the camera platform classes."""

    def test_platform_projects_inherit_the_basic_class(self):
        for project_class in (
            codec_genio.GenioProject,
            codec_dragonwing.DragonwingProject,
            codec_imx.NxpIMX8mProject,
            codec_rz.RenesasProject,
        ):
            self.assertTrue(issubclass(project_class, BaseCodecProject))
            self.assertTrue(issubclass(project_class, PipelineInterface))

    @mock.patch("codec_genio.file_name_placeholder", return_value="sample.mp4")
    def test_genio_rgb_encoders_use_matching_rgb_samples(
        self, mock_placeholder
    ):
        for color_space, codec_short_name in (
            ("ARGB", "png_rgba"),
            ("RGB", "png_rgb24"),
        ):
            with self.subTest(color_space=color_space):
                project = codec_genio.GenioProject(
                    platform="genio-1200",
                    codec="v4l2h264enc",
                    color_space=color_space,
                    width=1920,
                    height=1080,
                    framerate=30,
                    mux="mp4mux",
                )

                self.assertEqual(
                    project.psnr_reference_file,
                    os.path.join(
                        codec_genio.VIDEO_CODEC_TESTING_DATA, "sample.mp4"
                    ),
                )
                mock_placeholder.assert_called_with(
                    width=1920,
                    height=1080,
                    framerate=30,
                    codec_short_name=codec_short_name,
                    ext="mp4",
                )

    def test_build_pipeline_rejects_unknown_encoder(self):
        project = BaseCodecProject(
            platform="any",
            codec="unknownenc",
            width=1920,
            height=1080,
            framerate=30,
        )
        with self.assertRaises(SystemExit):
            project.build_pipeline()

    def test_generic_defaults_inherit_the_basic_class(self):
        # every scenario script ships a generic default that platforms
        # can override through their codec_<family>.py module
        import gst_encoder_psnr
        import gst_transform_resize
        import gst_transform_rotate_and_flip
        import gst_v4l2_audio_video_synchronization as avsync_script
        import gst_video_decoder_md5_checksum_comparison as md5_script
        import gst_video_decoder_performance as perf_script

        for project_class in (
            gst_encoder_psnr.GenericEncoderProject,
            gst_transform_rotate_and_flip.GenericTransformRotateAndFlipProject,
            gst_transform_resize.GenericTransformResizeProject,
            avsync_script.GenericAudioVideoSyncProject,
            md5_script.GenericDecoderMd5ChecksumProject,
            perf_script.GenericDecoderPerformanceProject,
            codec_imx.ImxDecoderPerformanceProject,
            codec_rz.RenesasDecoderPerformanceProject,
            codec_cix_tool.CixTransformResizeProject,
            codec_cix_tool.CixTransformRotateAndFlipProject,
            codec_cix_tool.CixDecoderPerformanceProject,
        ):
            self.assertTrue(issubclass(project_class, BaseCodecProject))


class TestImxColorimetry(unittest.TestCase):
    def _project(self, height):
        project = codec_imx.NxpIMX8mProject(
            platform="imx-8mm",
            codec=codec_imx.GStreamerEncodePlugins.V4L2H264ENC.value,
            color_space="I420",
            width=1920,
            height=height,
            framerate=30,
        )
        project._golden_sample = "/tmp/source.mp4"
        return project

    @mock.patch("codec_imx.get_source_colorimetry", return_value="bt601")
    def test_prefers_source_colorimetry_over_height_default(self, get_color):
        project = self._project(height=720)

        self.assertEqual(project._colorimetry, "bt601")
        get_color.assert_called_once_with(project._golden_sample)

    @mock.patch("codec_imx.get_source_colorimetry", return_value=None)
    def test_uses_height_default_when_source_colorimetry_is_absent(
        self, get_color
    ):
        self.assertEqual(self._project(height=576)._colorimetry, "bt601")
        self.assertEqual(self._project(height=720)._colorimetry, "bt709")
        self.assertEqual(get_color.call_count, 2)

    @mock.patch(
        "codec_imx.get_source_colorimetry",
        side_effect=SystemExit("gst-discoverer failed"),
    )
    def test_discoverer_failure_is_not_treated_as_missing_metadata(
        self, get_color
    ):
        with self.assertRaisesRegex(SystemExit, "gst-discoverer failed"):
            self._project(height=720)._colorimetry


class TestGetSourceColorimetry(unittest.TestCase):
    @mock.patch("gst_utils.execute_command")
    def test_reads_colorimetry_from_verbose_caps(self, execute_command):
        execute_command.return_value = (
            "video/x-h264, colorimetry=(string)BT601, width=(int)1920"
        )

        self.assertEqual(get_source_colorimetry("/tmp/source.mp4"), "bt601")
        command = execute_command.call_args[1]
        self.assertIn("{} -v".format(GST_DISCOVERER), command["cmd"])
        self.assertEqual(command["timeout"], 30)

    @mock.patch("gst_utils.execute_command")
    def test_returns_none_for_absent_or_unknown_colorimetry(
        self, execute_command
    ):
        for metadata in (
            "video/x-h264, width=(int)1920",
            "video/x-h264, colorimetry=(string)unknown",
        ):
            execute_command.return_value = metadata
            with self.subTest(metadata=metadata):
                self.assertIsNone(get_source_colorimetry("/tmp/source.mp4"))


if __name__ == "__main__":
    unittest.main()
