import unittest

import codec_carmel
import codec_genio
import codec_imx
import codec_renesas
from codec_platforms import codec_factory


class TestCodecFactory(unittest.TestCase):
    """codec_factory resolves each platform to its family module."""

    def test_factory_routes_families(self):
        self.assertIs(codec_factory("genio-1200"), codec_genio)
        self.assertIs(codec_factory("carmel"), codec_carmel)
        self.assertIs(codec_factory("nxp-imx8mp"), codec_imx)
        self.assertIs(codec_factory("rzg2l"), codec_renesas)

    def test_factory_returns_none_for_unknown_platform(self):
        self.assertIsNone(codec_factory("newplatform"))

    def test_module_scenario_apis(self):
        for module in (
            codec_genio,
            codec_carmel,
            codec_imx,
            codec_renesas,
        ):
            self.assertTrue(hasattr(module, "create_encoder_psnr_project"))
        # only the platforms with their own decoder pipeline provide the
        # decoder-performance builder; the others use the generic one
        self.assertTrue(
            hasattr(codec_imx, "build_decoder_performance_command")
        )
        self.assertTrue(
            hasattr(codec_renesas, "build_decoder_performance_command")
        )
        self.assertFalse(
            hasattr(codec_genio, "build_decoder_performance_command")
        )
        self.assertFalse(
            hasattr(codec_carmel, "build_decoder_performance_command")
        )


if __name__ == "__main__":
    unittest.main()
