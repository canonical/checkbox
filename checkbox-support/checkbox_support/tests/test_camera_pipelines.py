import typing as T
import unittest as ut
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
import camera_pipelines as cam


class TestCapsResolver(ut.TestCase):
    def test_discrete_caps(self):
        resolver = cam.CapsResolver()
        mixed = MagicMock()  # caps
        fixed1 = MagicMock()  # caps
        fixed2 = MagicMock()  # caps

        def make_caps(s: int):
            if s == id(mixed):
                return mixed
            if s == id(fixed1):
                return fixed1
            if s == id(fixed2):
                return fixed2

        cam.Gst.Caps.from_string.side_effect = make_caps  # type: ignore

        mixed.is_fixed.return_value = False
        fixed1.is_fixed.return_value = True
        fixed2.is_fixed.return_value = True

        mixed.fixate.return_value = fixed1
        mixed.subtract.return_value = fixed2

        for cap in mixed, fixed1, fixed2:
            cap.get_structure(0).has_field_typed.return_value = False
            cap.get_structure(0).to_string.return_value = id(cap)
            cap.is_empty.return_value = False
            cap.get_size.return_value = 1

        r = resolver.get_all_fixated_caps(mixed, "known_values")

        self.assertCountEqual(r, [fixed1, fixed2])

    @patch("camera_pipelines.GObject")
    def test_resolvable_int_range(self, mock_g_object: MagicMock):
        # test the get_all_fixated_caps function
        # using a mixed caps object that contain a int range
        resolver = cam.CapsResolver()
        mixed = MagicMock()
        struct = MagicMock()

        # cap is video/x-raw, width=[ 600, 1300 ], height=[ 400, 800 ]
        mixed.get_structure(0).return_value = struct

        fixed1 = MagicMock()  # caps
        fixed2 = MagicMock()  # caps
        fixed1.is_fixed.return_value = True
        fixed2.is_fixed.return_value = True

        mock_g_object.ValueArray = list  # has the same interface as list

        struct.copy.return_value = struct
        struct.fixate_field_nearest_int.side_effect = lambda prop, target: (
            self._mock_fixate_nearest(struct, prop, target, 600, 1300, False)
            if prop == "width"
            else self._mock_fixate_nearest(
                struct, prop, target, 400, 800, False
            )
        )
        struct.subtract.return_value = fixed2  # fixed 1 is extracted first

    def test_extract_int_range(self):
        # test just the extract function
        resolver = cam.CapsResolver()
        mock_struct = MagicMock()
        prop_name = "int_range_field"

        mock_struct.has_field_typed.return_value = True
        copy_1 = MagicMock()
        copy_2 = MagicMock()
        mock_struct.copy.side_effect = [copy_1, copy_2]

        copy_1.fixate_field_nearest_int.side_effect = (
            lambda prop, target: self._mock_fixate_nearest(
                copy_1, prop, target, 100, 200, False
            )
        )

        copy_2.fixate_field_nearest_int.side_effect = (
            lambda prop, target: self._mock_fixate_nearest(
                copy_2, prop, target, 100, 200, False
            )
        )

        self.assertEqual(
            resolver.extract_int_range(mock_struct, prop_name), (100, 200)
        )

    def test_extract_fraction_range(self):
        # test just the extract function
        resolver = cam.CapsResolver()
        mock_struct = MagicMock()
        prop_name = "frac_range_field"

        mock_struct.has_field_typed.return_value = True
        copy_1 = MagicMock()
        copy_2 = MagicMock()
        mock_struct.copy.side_effect = [copy_1, copy_2]

        # suppose the range is [15/1, 60,1]
        copy_1.fixate_field_nearest_fraction.side_effect = (
            lambda prop, target_num, target_denom: self._mock_fixate_nearest(
                copy_1, prop, target_num, (15, 1), (60, 1), False
            )
        )

        copy_2.fixate_field_nearest_fraction.side_effect = (
            lambda prop, target_num, target_denom: self._mock_fixate_nearest(
                copy_2, prop, target_num, (15, 1), (60, 1), False
            )
        )

        self.assertEqual(
            resolver.extract_fraction_range(mock_struct, prop_name),
            ((15, 1), (60, 1)),
        )

    def _mock_fixate_nearest(
        self,
        struct: MagicMock,
        prop: str,
        target_value: int,  # the actual param in fixate_field_nearest_int
        low: cam.CapsResolver.IntOrFractionTuple,
        high: cam.CapsResolver.IntOrFractionTuple,
        fixed_after_fixate: bool,
    ):
        if target_value <= 0:
            if type(low) is int:
                struct.get_int.return_value = (True, low)
            elif type(low) is tuple:
                struct.get_fraction.return_value = (True, *low)
            # mimic what fixate nearest does,
            # since the min width is 600, it's closet to 0
            # 400 is for height
        else:
            if type(high) is int:
                struct.get_int.return_value = (True, high)
            elif type(high) is tuple:
                struct.get_fraction.return_value = (True, *high)

        # gstreamer mutates the original field after calling fixate
        # it becomes fixed if the original field is a finite list,
        # if it was a continuous range then it stays not-fixed
        struct.has_field_typed.return_value = fixed_after_fixate


class TestPipelineLogic(ut.TestCase):
    def test_run_pipeline_assertions(self):
        pipeline = MagicMock()

        self.assertRaises(
            AssertionError, lambda: cam.run_pipeline(pipeline, 0)
        )

        self.assertRaises(
            AssertionError,
            lambda: cam.run_pipeline(
                pipeline,
                5,
                [(1, lambda: None), (0, lambda: None), (6, lambda: None)],
            ),
        )

    @patch("camera_pipelines.GLib")
    @patch("camera_pipelines.Gst")
    def test_run_pipeline_happy_path(
        self, mock_Gst: MagicMock, mock_GLib: MagicMock
    ):
        pipeline = MagicMock()

        mock_timeout_sources = (MagicMock(), MagicMock())
        mock_open_valve_fn = MagicMock(name="mock_open_valve")
        mock_eos_signal_obj = MagicMock()
        mock_eos_message = MagicMock(type=mock_Gst.MessageType.EOS)
        mock_main_loop = MagicMock()

        mock_GLib.timeout_add_seconds.side_effect = mock_timeout_sources
        pipeline.get_child_by_index(0).get_state.return_value = (
            mock_Gst.StateChangeReturn.SUCCESS,
        )
        mock_Gst.Event.new_eos.return_value = mock_eos_signal_obj

        cam.run_pipeline(
            pipeline,
            5,
            intermediate_calls=[(3, mock_open_valve_fn)],
        )

        self.assertEqual(mock_GLib.timeout_add_seconds.call_count, 2)

        real_eos_handler = mock_GLib.timeout_add_seconds.call_args_list[
            0
        ].args[1]
        real_eos_handler()
        pipeline.send_event.assert_called_with(mock_eos_signal_obj)

        # now pretend eos has been triggered

        cam.gst_msg_handler(
            MagicMock(),
            mock_eos_message,
            pipeline,
            None,  # no custom_quit handler
            mock_main_loop,
            mock_timeout_sources,  # type: ignore
        )
        pipeline.set_state.assert_called_with(mock_Gst.State.NULL)
        for mock_timeout in mock_timeout_sources:
            mock_timeout.destroy.assert_called_once()

        mock_main_loop.quit.assert_called()

    @patch("camera_pipelines.logger")
    @patch("camera_pipelines.run_pipeline")
    @patch("camera_pipelines.Gst")
    def test_take_photo_build_pipeline_step(
        self, mock_Gst: MagicMock, mock_run_pipeline, mock_logger
    ):
        mock_caps = MagicMock()
        mock_caps.to_string.return_value = "video/x-raw,width=1280,height=720"
        # video/x-raw doesn't need a decoder
        mock_caps.get_structure(0).get_name.return_value = "video/x-raw"
        cam.take_photo(
            MagicMock(),
            caps=mock_caps,
            file_path=Path("some/path"),
            delay_seconds=2,  # with delay, valve should be inserted
        )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[0][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "capsfilter name=source-caps "
                    'caps="video/x-raw,width=1280,height=720"',
                    "videoconvert name=converter",
                    "valve name=photo-valve drop=True",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

        mock_Gst.reset_mock()

        cam.take_photo(
            MagicMock(),
            caps=mock_caps,
            file_path=Path("some/path"),
            delay_seconds=0,  # no delay -> no valve
        )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[0][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "capsfilter name=source-caps "
                    'caps="video/x-raw,width=1280,height=720"',
                    "videoconvert name=converter",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

        mock_Gst.reset_mock()
        # jpeg caps should be handled by jpegdec
        mock_caps.to_string.return_value = "image/jpeg,width=1280,height=720"
        mock_caps.get_structure(0).get_name.return_value = "image/jpeg"
        cam.take_photo(
            MagicMock(),
            caps=mock_caps,
            file_path=Path("some/path"),
            delay_seconds=0,  # no delay -> no valve
        )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[0][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "capsfilter name=source-caps "
                    'caps="image/jpeg,width=1280,height=720"',
                    "jpegdec",
                    "videoconvert name=converter",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

        mock_Gst.reset_mock()
        mock_caps.to_string.return_value = "image/jpeg,width=1280,height=720"
        mock_caps.get_structure(0).get_name.return_value = "image/jpeg"
        cam.take_photo(
            MagicMock(),
            caps=mock_caps,
            file_path=Path("some/path"),
            delay_seconds=3,  # with delay
        )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[0][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "capsfilter name=source-caps "
                    'caps="image/jpeg,width=1280,height=720"',
                    "jpegdec",
                    "videoconvert name=converter",
                    "valve name=photo-valve drop=True",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

        mock_Gst.reset_mock()
        mock_caps.to_string.return_value = (
            "video/x-bayer,width=1280,height=720,format=rggb"
        )
        mock_caps.get_structure(0).get_name.return_value = "video/x-bayer"
        cam.take_photo(
            MagicMock(),
            caps=mock_caps,
            file_path=Path("some/path"),
            delay_seconds=3,  # with delay
        )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[0][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "capsfilter name=source-caps "
                    'caps="video/x-bayer,width=1280,height=720,format=rggb"',
                    "bayer2rgb",  # this element should be inserted for bayer
                    "videoconvert name=converter",
                    "valve name=photo-valve drop=True",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )


class TestElementToString(ut.TestCase):
    class MockElement:
        name = "someelement"
        some_int_value = 1

        def to_string(self):
            return "someelement prop1=value1 name={}".format(self.name)

        def list_properties(self):
            return [
                p
                for p in dir(self)
                if not p.startswith("__") and not callable(getattr(self, p))
            ]


if __name__ == "__main__":
    ut.main()
