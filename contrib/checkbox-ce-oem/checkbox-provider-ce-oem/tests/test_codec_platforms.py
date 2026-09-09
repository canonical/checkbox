import unittest
from unittest import mock

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
from gst_utils import PipelineInterface


class TestCodecFactory(unittest.TestCase):
    """codec_factory resolves each platform to its family module."""

    def test_factory_routes_families(self):
        self.assertIs(codec_factory("genio-1200"), codec_genio)
        self.assertIs(codec_factory("dragonwing"), codec_dragonwing)
        self.assertIs(codec_factory("imx-8mp"), codec_imx)
        self.assertIs(codec_factory("rzg2l"), codec_rz)

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
        ):
            self.assertTrue(issubclass(project_class, BaseCodecProject))


if __name__ == "__main__":
    unittest.main()
