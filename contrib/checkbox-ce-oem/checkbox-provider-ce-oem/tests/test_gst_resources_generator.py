import io
import unittest
from unittest.mock import patch, mock_open, MagicMock, call
from gst_resources_generator import load_json_config, GstResources


class TestLoadJsonConfig(unittest.TestCase):
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open", new_callable=mock_open)
    @patch("json.load")
    def test_load_json_config(
        self, mock_json_load, mock_open, mock_path_exists
    ):
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"key": "value"}
        json_path = "/fake.json"
        data = load_json_config(json_path)
        mock_path_exists.assert_called_once_with()
        mock_open.assert_called_once_with("r")
        mock_json_load.assert_called_once_with(
            mock_open.return_value.__enter__.return_value
        )
        self.assertEqual(data, {"key": "value"})

    @patch("pathlib.Path.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_load_json_config_file_not_found(self, mock_exists, mock_open):
        mock_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            load_json_config("/fake.json")
        mock_open.assert_not_called()


class TestGstResources(unittest.TestCase):
    def test_gst_v4l2_video_decoder_md5_checksum_comparison_helper(self):
        args = MagicMock()
        args.gst_testing_data_path = "/fake-path"
        args.gst_conf_name = "platform_conf"

        ins = GstResources(args, {})
        ins._current_scenario_name = "scenario1"

        expected_result = {
            "scenario": "scenario1",
            "decoder_plugin": "plugin1",
            "width": 1920,
            "height": 1080,
            "color_space": "rgb",
            "golden_sample_file": (
                "/fake-path/video_golden_samples" "/1920x1080-plugin1-rgb.mp4"
            ),
            "golden_md5_checkum_file": (
                "/fake-path/scenario1/"
                "golden_md5_checksum/platform_conf/1920x1080-plugin1-rgb.md5"
            ),
        }

        result = ins._gst_v4l2_video_decoder_md5_checksum_comparison_helper(
            decoder_plugin="plugin1",
            width=1920,
            height=1080,
            color_space="rgb",
            source_format="mp4",
        )

        self.assertEqual(result, expected_result)

    @patch.object(
        GstResources, "_gst_v4l2_video_decoder_md5_checksum_comparison_helper"
    )
    def test_gst_v4l2_video_decoder_md5_checksum_comparison_multi_color_space(
        self, mock_helper
    ):
        args = MagicMock()
        ins = GstResources(args, {})

        scenario_data = [
            {
                "decoder_plugin": "plugin1",
                "resolutions": [{"width": 1920, "height": 1080}],
                "color_spaces": ["rgb", "yuv"],
                "source_format": "mp4",
            }
        ]

        ins.gst_v4l2_video_decoder_md5_checksum_comparison(scenario_data)

        mock_helper.assert_has_calls(
            [
                call(
                    decoder_plugin="plugin1",
                    width=1920,
                    height=1080,
                    color_space="rgb",
                    source_format="mp4",
                ),
                call(
                    decoder_plugin="plugin1",
                    width=1920,
                    height=1080,
                    color_space="yuv",
                    source_format="mp4",
                ),
            ]
        )

    @patch.object(
        GstResources, "_gst_v4l2_video_decoder_md5_checksum_comparison_helper"
    )
    def test_gst_v4l2_video_decoder_md5_checksum_comparison_multi_resolutions(
        self, mock_helper
    ):
        args = MagicMock()
        ins = GstResources(args, {})

        scenario_data = [
            {
                "decoder_plugin": "plugin1",
                "resolutions": [
                    {"width": 320, "height": 320},
                    {"width": 1920, "height": 1080},
                ],
                "color_spaces": ["NV12"],
                "source_format": "mp4",
            }
        ]

        ins.gst_v4l2_video_decoder_md5_checksum_comparison(scenario_data)

        mock_helper.assert_has_calls(
            [
                call(
                    decoder_plugin="plugin1",
                    width=320,
                    height=320,
                    color_space="NV12",
                    source_format="mp4",
                ),
                call(
                    decoder_plugin="plugin1",
                    width=1920,
                    height=1080,
                    color_space="NV12",
                    source_format="mp4",
                ),
            ]
        )

    @patch.object(
        GstResources, "_gst_v4l2_video_decoder_md5_checksum_comparison_helper"
    )
    def test_gst_v4l2_video_decoder_md5_checksum_comparison_multi_decoders(
        self, mock_helper
    ):
        args = MagicMock()
        ins = GstResources(args, {})

        scenario_data = [
            {
                "decoder_plugin": "plugin1",
                "resolutions": [
                    {"width": 320, "height": 320},
                ],
                "color_spaces": ["NV12"],
                "source_format": "mp4",
            },
            {
                "decoder_plugin": "plugin2",
                "resolutions": [
                    {"width": 3840, "height": 2160},
                ],
                "color_spaces": ["ABC"],
                "source_format": "webm",
            },
        ]

        ins.gst_v4l2_video_decoder_md5_checksum_comparison(scenario_data)

        mock_helper.assert_has_calls(
            [
                call(
                    decoder_plugin="plugin1",
                    width=320,
                    height=320,
                    color_space="NV12",
                    source_format="mp4",
                ),
                call(
                    decoder_plugin="plugin2",
                    width=3840,
                    height=2160,
                    color_space="ABC",
                    source_format="webm",
                ),
            ]
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_dump_resources(self, mock_stdout):
        args = MagicMock()
        ins = GstResources(args, {})
        ins._resource_items = [
            {"key1": "value1", "foo1": "bar1"},
            {
                "key2": "value2",
                "foo2": "bar2",
                "good2": "bad2",
            },
        ]

        ins._dump_resources()

        expected_output = (
            "key1: value1\nfoo1: bar1\n\n"
            "key2: value2\nfoo2: bar2\ngood2: bad2\n\n\n"
        )

        self.assertEqual(mock_stdout.getvalue(), expected_output)
        self.assertEqual(ins._resource_items, [])


if __name__ == "__main__":
    unittest.main()
