from contextlib import suppress
import enum
import unittest as ut
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
import checkbox_support.camera_pipelines as cam  # noqa: E402


class TestCapsResolver(ut.TestCase):
    def test_already_fixed(self):
        resolver = cam.CapsResolver()
        fixed_caps = MagicMock()
        fixed_caps.is_fixed.return_value = True

        r = resolver.get_all_fixated_caps(fixed_caps, "known_values")

        self.assertCountEqual(r, [fixed_caps])

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

    @patch("checkbox_support.camera_pipelines.GObject")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_resolvable_int_range(
        self, mock_Gst: MagicMock, mock_GObject: MagicMock
    ):
        # for simplicity we will only test up to the struct.set_list call
        resolver = cam.CapsResolver()
        caps = MagicMock()
        struct = MagicMock()
        struct.name = "test_struct"
        struct.has_field_typed.side_effect = (
            lambda p, t: p == "width" and t == mock_Gst.IntRange
        )

        mock_array = MagicMock()
        mock_GObject.ValueArray.return_value = mock_array
        mock_array.n_values = 2

        resolver.extract_int_range = MagicMock()
        resolver.extract_int_range.side_effect = ([640, 1280], [480, 720])

        # cap is video/x-raw, width=[ 600, 1300 ], height=[ 400, 800 ]
        caps.get_structure.return_value = struct
        caps.get_size.return_value = 1
        caps.is_fixed.return_value = False

        mock_Gst.Caps.from_string.is_fixed.return_value = True
        mock_Gst.Caps.from_string.is_empty.return_value = True

        resolver.get_all_fixated_caps(caps, "known_values")

        self.assertTrue(mock_GObject.ValueArray.called)
        self.assertEqual(mock_array.append.call_count, 2)

    @patch("checkbox_support.camera_pipelines.GObject")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_resolvable_fraction_range(
        self, mock_Gst: MagicMock, mock_GObject: MagicMock
    ):
        resolver = cam.CapsResolver()
        caps = MagicMock()
        struct = MagicMock()
        struct.name = "test_struct"
        struct.has_field_typed.side_effect = (
            lambda p, t: p == "framerate" and t == mock_Gst.FractionRange
        )

        mock_array = MagicMock()
        mock_GObject.ValueArray.return_value = mock_array
        mock_array.n_values = 2

        resolver.extract_fraction_range = MagicMock()
        resolver.extract_fraction_range.return_value = ((15, 1), (60, 1))

        # cap is video/x-raw, width=[ 600, 1300 ], height=[ 400, 800 ]
        caps.get_structure.return_value = struct
        caps.get_size.return_value = 1
        caps.is_fixed.return_value = False

        resolver.get_all_fixated_caps(caps, "known_values")

        mock_Gst.Structure.from_string.assert_called_with(
            "temp, framerate={15/1,30/1,60/1}"
        )

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

        self.assertRaises(ValueError, lambda: cam.run_pipeline(pipeline, 0))

        self.assertRaises(
            ValueError,
            lambda: cam.run_pipeline(
                pipeline,
                5,
                [(1, lambda: None), (0, lambda: None), (6, lambda: None)],
            ),
        )

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.GLib")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_run_pipeline_happy_path(
        self, mock_Gst: MagicMock, mock_GLib: MagicMock, mock_logger
    ):
        pipeline = MagicMock()

        mock_timeout_sources = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
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

        self.assertEqual(
            mock_GLib.timeout_add_seconds.call_count,
            # -1 because the last one is in the msg handler
            len(mock_timeout_sources) - 1,
        )

        # first call, first pair, 2nd element
        real_eos_handler = mock_GLib.timeout_add_seconds.call_args_list[0][0][
            1
        ]
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
            # check everything has been destroyed
            mock_timeout.destroy.assert_called_once_with()

        self.assertTrue(mock_main_loop.quit.called)

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_x_raw(
        self, mock_Gst: MagicMock, mock_run_pipeline, mock_logger
    ):
        mock_caps = MagicMock()
        mock_caps.to_string.return_value = "video/x-raw,width=1280,height=720"
        # video/x-raw doesn't need a decoder
        mock_caps.get_structure(0).get_name.return_value = "video/x-raw"
        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=mock_caps,
                file_path=Path("some/path"),
                delay_seconds=2,  # with delay, valve should be inserted
            )
        # -1 is taking the most recent call
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
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
        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=mock_caps,
                file_path=Path("some/path"),
                delay_seconds=0,  # no delay -> no valve
            )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
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

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_image_jpeg(
        self, mock_Gst: MagicMock, mock_run_pipeline, mock_logger
    ):
        mock_caps = MagicMock()
        # jpeg caps should be handled by jpegdec
        mock_caps.to_string.return_value = "image/jpeg,width=1280,height=720"
        mock_caps.get_structure(0).get_name.return_value = "image/jpeg"

        print(type(mock_Gst.parse_launch()))
        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=mock_caps,
                file_path=Path("some/path"),
                delay_seconds=0,  # no delay -> no valve
            )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
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
        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=mock_caps,
                file_path=Path("some/path"),
                delay_seconds=3,  # with delay
            )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
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

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_x_bayer(
        self, mock_Gst: MagicMock, mock_run_pipeline, mock_logger
    ):
        mock_caps = MagicMock()
        mock_caps.to_string.return_value = (
            "video/x-bayer,width=1280,height=720,format=rggb"
        )
        mock_caps.get_structure(0).get_name.return_value = "video/x-bayer"
        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=mock_caps,
                file_path=Path("some/path"),
                delay_seconds=3,  # with delay
            )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
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

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_no_caps(
        self, mock_Gst: MagicMock, mock_run_pipeline, mock_logger
    ):
        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=None,
                file_path=Path("some/path"),
                delay_seconds=3,  # with delay
            )

        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "videoconvert name=converter",
                    "valve name=photo-valve drop=True",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

        with suppress(TypeError):
            cam.take_photo(
                MagicMock(),
                caps=None,
                file_path=Path("some/path"),
                delay_seconds=0,
            )
        parse_launch_arg = mock_Gst.parse_launch.call_args_list[-1][0][0]
        self.assertEqual(
            parse_launch_arg,
            " ! ".join(
                [
                    "videoconvert name=converter",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_custom_quit_has_lowest_precedence(
        self, mock_Gst: MagicMock, mock_logger: MagicMock
    ):
        mock_message = MagicMock()
        mock_message.type = mock_Gst.MessageType.ERROR
        mock_loop = MagicMock()
        mock_quit_handler = (
            lambda *args: False
        )  # custom handler says it shouldn't quit, but got an error msg
        # so we should still quit
        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            mock_quit_handler,
            mock_loop,
            [],
        )
        self.assertTrue(mock_loop.quit.called)

        # warnings should be produced
        mock_loop.reset_mock()
        mock_message.type = mock_Gst.MessageType.WARNING
        mock_quit_handler = lambda *args: False
        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            mock_quit_handler,
            mock_loop,
            [],
        )
        self.assertTrue(mock_logger.warning.called)

        # Now suppose we have an element message
        mock_loop.reset_mock()
        mock_message.type = mock_Gst.MessageType.ELEMENT
        mock_quit_handler = lambda *args: True
        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            mock_quit_handler,
            mock_loop,
            [],
        )
        self.assertTrue(mock_loop.quit.called)


class UtilityFunctionTests(ut.TestCase):

    class MockElement:
        name = "someelement0"
        some_int_value = 1
        unreadable = "reading this will raise an exception"
        # above properties should be printed

        def list_properties(self):
            props = []
            for p in dir(self):
                if not p.startswith("__") and not callable(getattr(self, p)):
                    mock_prop = MagicMock()
                    mock_prop.name = p
                    props.append(mock_prop)
            return props

        def get_factory(self):
            mock = MagicMock()
            mock.get_name.return_value = "someelement"
            return mock

        def get_property(self, prop_name: str):
            if prop_name == "unreadable":
                raise Exception("unreadable prop")
            return getattr(self, prop_name)

    class E(enum.Enum):
        key = "value"

    def test_select_known_values_from_range_int(self):
        resolver = cam.CapsResolver()

        selected_values = resolver.select_known_values_from_range(
            "width", 80, 5376
        )  # real value from genio g350
        self.assertCountEqual(selected_values, [640, 1280, 1920, 2560, 3840])

        selected_values = resolver.select_known_values_from_range(
            "width", 1000, 2000
        )
        self.assertCountEqual(selected_values, [1280, 1920])

    def test_select_known_values_from_range_fraction(self):
        resolver = cam.CapsResolver()
        selected_values = resolver.select_known_values_from_range(
            "framerate", (0, 1), (1000, 1)
        )
        self.assertCountEqual(
            selected_values,
            [(15, 1), (30, 1), (60, 1), (120, 1)],
        )

    def test_select_known_values_mixed_types(self):
        resolver = cam.CapsResolver()
        self.assertRaises(
            TypeError,
            # static analyis should already complain about bad types here
            lambda: resolver.select_known_values_from_range(
                "width", 80, (30, 1)  # type: ignore
            ),
        )
        self.assertRaises(
            TypeError,
            lambda: resolver.select_known_values_from_range(
                "width", "blah", (30, 1)  # type: ignore
            ),
        )
        self.assertRaises(
            TypeError,
            lambda: resolver.select_known_values_from_range(
                "width", (25, 1), 1  # type: ignore
            ),
        )


if __name__ == "__main__":
    ut.main()
