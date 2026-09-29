import unittest

from codec_platforms import (
    PLATFORM_FAMILIES,
    PlatformFamily,
    get_platform_family,
)
from gst_resources_generator import (
    GstResources,
    compose_encoder_psnr_name,
    compose_decoder_performance_name,
)


class TestPlatformFamily(unittest.TestCase):
    def test_families(self):
        self.assertEqual(get_platform_family("genio-1200"), "genio")
        self.assertEqual(get_platform_family("dragonwing"), "dragonwing")
        self.assertEqual(get_platform_family("imx-8mp"), "imx")
        self.assertEqual(get_platform_family("rzg2l"), "rz")
        self.assertEqual(get_platform_family("newplatform"), "")

    def test_entries_are_platform_family_dataclasses(self):
        for spec in PLATFORM_FAMILIES.values():
            self.assertIsInstance(spec, PlatformFamily)


class TestComposeEncoderPsnrName(unittest.TestCase):
    """Names must follow each platform family's declared id shape."""

    def _config(self, **overrides):
        config = {
            "scenario": "gst_encoder_psnr",
            "encoder_plugin": "v4l2h264enc",
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "color_space": "NV12",
            "mux": "mp4mux",
        }
        config.update(overrides)
        return config

    def test_genio_shape(self):
        self.assertEqual(
            compose_encoder_psnr_name("genio-1200", self._config()),
            "genio-gst_encoder_psnr-v4l2h264enc-1920x1080@30fps-NV12-mp4mux",
        )

    def test_dragonwing_shape(self):
        self.assertEqual(
            compose_encoder_psnr_name(
                "dragonwing", self._config(color_space="", mux="")
            ),
            "dragonwing-gst_encoder_psnr-v4l2h264enc-1920x1080@30fps",
        )

    def test_imx8_shape(self):
        self.assertEqual(
            compose_encoder_psnr_name("imx-8mp", self._config(mux="")),
            "imx8-gst_encoder_psnr-v4l2h264enc-1920x1080@30fps-NV12",
        )

    def test_rz_shape(self):
        self.assertEqual(
            compose_encoder_psnr_name(
                "rzg2l", self._config(encoder_plugin="omxh264enc", mux="")
            ),
            "renesas-gst_encoder_psnr-omxh264enc-1920x1080@30fps-NV12",
        )

    def test_unknown_platform_appends_only_set_fields(self):
        self.assertEqual(
            compose_encoder_psnr_name("newplatform", self._config(mux="")),
            "gst_encoder_psnr-v4l2h264enc-1920x1080@30fps-NV12",
        )


class TestScenarioDispatch(unittest.TestCase):
    def test_unknown_scenario_exits_with_conf_context(self):
        resources = GstResources.__new__(GstResources)
        resources._scenarios = {"not_a_scenario": []}
        resources._conf_name = "some-conf"
        with self.assertRaises(SystemExit) as ctx:
            resources.main()
        self.assertIn("not_a_scenario", str(ctx.exception))
        self.assertIn("some-conf", str(ctx.exception))


class TestComposeDecoderPerformanceName(unittest.TestCase):
    def test_default_shape(self):
        self.assertEqual(
            compose_decoder_performance_name(
                "rzg2l",
                "omxh264dec",
                "1080p_30fps_h264",
                "gst_video_decoder_performance_fakesink",
            ),
            "gst_video_decoder_performance_fakesink-omxh264dec",
        )

    def test_sample_name_included_when_family_requires_it(self):
        PLATFORM_FAMILIES["fakefam"] = PlatformFamily(
            id_prefix="fakefam",
            perf_id_includes_sample=True,
        )
        try:
            self.assertEqual(
                compose_decoder_performance_name(
                    "fakefam-1",
                    "onedecoder",
                    "1080p_30fps_av1",
                    "gst_video_decoder_performance_fakesink",
                ),
                "fakefam-gst_video_decoder_performance_fakesink-onedecoder"
                "-1080p_30fps_av1",
            )
        finally:
            del PLATFORM_FAMILIES["fakefam"]


if __name__ == "__main__":
    unittest.main()
