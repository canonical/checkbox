import unittest
from unittest import mock

import codec_dragonwing
import codec_genio
import codec_imx
import codec_rz
from codec_base import BaseCodecProject
from codec_platforms import PLATFORM_FAMILIES, PlatformFamily, codec_factory
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
        # decoder-performance builder; the others use the generic one
        self.assertTrue(
            hasattr(codec_imx, "build_decoder_performance_command")
        )
        self.assertTrue(hasattr(codec_rz, "build_decoder_performance_command"))
        self.assertFalse(
            hasattr(codec_genio, "build_decoder_performance_command")
        )
        self.assertFalse(
            hasattr(codec_dragonwing, "build_decoder_performance_command")
        )
        # the transform scenarios resolve through the factory too; only
        # genio implements them today
        self.assertTrue(
            hasattr(codec_genio, "create_transform_rotate_and_flip_project")
        )
        self.assertTrue(
            hasattr(codec_genio, "create_transform_resize_project")
        )


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


if __name__ == "__main__":
    unittest.main()
