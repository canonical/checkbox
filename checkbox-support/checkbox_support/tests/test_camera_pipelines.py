from contextlib import suppress
import unittest as ut
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
import checkbox_support.camera_pipelines as cam  # noqa: E402


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

        mock_timeout_sources = (MagicMock(), MagicMock(), MagicMock())
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

    @patch("checkbox_support.camera_pipelines.type")
    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_image_jpeg(
        self,
        mock_Gst: MagicMock,
        mock_run_pipeline,
        mock_logger,
        mock_type: MagicMock,
    ):
        mock_caps = MagicMock()
        # jpeg caps should be handled by jpegdec
        mock_caps.to_string.return_value = "image/jpeg,width=1280,height=720"
        mock_caps.get_structure(0).get_name.return_value = "image/jpeg"

        mock_type.return_value = mock_Gst.Pipeline

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

    @patch("checkbox_support.camera_pipelines.type")
    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_x_bayer(
        self,
        mock_Gst: MagicMock,
        mock_run_pipeline,
        mock_logger,
        mock_type: MagicMock,
    ):
        mock_caps = MagicMock()
        mock_caps.to_string.return_value = (
            "video/x-bayer,width=1280,height=720,format=rggb"
        )
        mock_caps.get_structure(0).get_name.return_value = "video/x-bayer"
        mock_type.return_value = mock_Gst.Pipeline

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

    @patch("checkbox_support.camera_pipelines.type")
    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_no_caps(
        self,
        mock_Gst: MagicMock,
        mock_run_pipeline,
        mock_logger,
        mock_type: MagicMock,
    ):
        mock_type.return_value = mock_Gst.Pipeline
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

    @patch("checkbox_support.camera_pipelines.type")
    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_unknown_caps(
        self,
        mock_Gst: MagicMock,
        mock_run_pipeline,
        mock_logger,
        mock_type: MagicMock,
    ):
        mock_caps = MagicMock()
        mock_caps.to_string.return_value = (
            "video/x-theora,width=1280,height=720"
        )
        mock_caps.get_structure(0).get_name.return_value = "video/x-theora"
        mock_type.return_value = mock_Gst.Pipeline
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
                    'caps="video/x-theora,width=1280,height=720"',
                    "decodebin",
                    "videoconvert name=converter",
                    "valve name=photo-valve drop=True",
                    "jpegenc",
                    "multifilesink post-messages=True location=some/path",
                ]
            ),
        )

    @patch("checkbox_support.camera_pipelines.type")
    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.run_pipeline")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_pipeline_build_step_runtime_checks(
        self,
        mock_Gst: MagicMock,
        mock_run_pipeline,
        mock_logger,
        mock_type: MagicMock,
    ):
        mock_type.return_value = mock_Gst.Pipeline
        mock_pipeline = MagicMock()
        mock_Gst.parse_launch.return_value = mock_pipeline
        mock_pipeline.add.return_value = False

        with self.assertRaises(RuntimeError):
            cam.take_photo(
                MagicMock(),
                caps=None,
                file_path=Path("some/path"),
                delay_seconds=3,  # with delay
            )
        mock_pipeline.reset_mock()
        mock_pipeline.add.return_value = True
        mock_source = MagicMock()
        mock_source.link.return_value = False
        with self.assertRaises(RuntimeError):
            cam.take_photo(
                mock_source,
                caps=None,
                file_path=Path("some/path"),
                delay_seconds=3,  # with delay
            )

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_custom_quit_has_lowest_precedence(
        self, mock_Gst: MagicMock, mock_logger: MagicMock
    ):
        mock_message = MagicMock()
        mock_message.type = mock_Gst.MessageType.ERROR
        mock_loop = MagicMock()

        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            lambda *args: False,  # always quit when there's an error msg
            # even if the handler says no
            mock_loop,
            [],
        )
        self.assertTrue(mock_loop.quit.called)

        # warnings should be produced
        mock_loop.reset_mock()
        mock_message.type = mock_Gst.MessageType.WARNING
        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            cam.msg_is_multifilesink_save,  # no error/EOS
            mock_loop,
            [],
        )
        self.assertTrue(mock_logger.warning.called)

        # Now suppose we have a random element message
        mock_loop.reset_mock()
        mock_message.type = mock_Gst.MessageType.ELEMENT

        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            cam.msg_is_multifilesink_save,
            mock_loop,
            [],
        )
        self.assertFalse(mock_loop.quit.called)

        # finally the multifilesink save message

        mock_loop.reset_mock()
        mock_message.type = mock_Gst.MessageType.ELEMENT
        mock_struct = MagicMock()
        mock_message.get_structure.return_value = mock_struct
        mock_struct.get_name.return_value = "GstMultiFileSink"
        mock_struct.has_field.return_value = True
        cam.gst_msg_handler(
            MagicMock(),
            mock_message,
            MagicMock(),
            cam.msg_is_multifilesink_save,
            mock_loop,
            [],
        )
        self.assertTrue(mock_loop.quit.called)


class TestUtilFunctions(ut.TestCase):
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
                raise TypeError("unreadable prop")
            return getattr(self, prop_name)

    @patch("checkbox_support.camera_pipelines.Gst")
    def test_get_launch_line_null_and_exceptionchecks(
        self, mock_Gst: MagicMock
    ):
        device = MagicMock()
        device.create_element.return_value = None
        self.assertIsNone(cam.get_launch_line(device))

        mock_elem = MagicMock()
        device.create_element.return_value = mock_elem
        mock_elem.get_factory.return_value = None
        self.assertIsNone(cam.get_launch_line(device))

        mock_factory = MagicMock()
        mock_elem.get_factory.return_value = mock_factory
        mock_factory.get_name.return_value = None
        self.assertIsNone(cam.get_launch_line(device))

        mock_factory.get_name.return_value = "someelement"
        mock_Gst.ElementFactory.make.return_value = None
        self.assertIsNone(cam.get_launch_line(device))

        mock_factory = MagicMock()
        mock_elem.get_factory.return_value = mock_factory
        mock_factory.get_name.return_value = "someelement"
        mock_Gst.value_serialize.side_effect = ValueError
        # serialize() exceptions should be caught
        self.assertIsNone(cam.get_launch_line(device))

    @patch("checkbox_support.camera_pipelines.GObject")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_get_launch_line_happy_path(
        self, mock_Gst: MagicMock, mock_GObject: MagicMock
    ):
        device = MagicMock()
        mock_elem = MagicMock()
        mock_factory = MagicMock()
        mock_pure_elem = MagicMock()
        device.create_element.return_value = mock_elem
        mock_elem.get_factory.return_value = mock_factory
        mock_factory.get_name.return_value = "someelement"
        mock_Gst.ElementFactory.make.side_effect = (
            lambda name, _: name == "someelement" and mock_pure_elem
        )
        mock_GObject.PARAM_READWRITE = 1

        prop1 = MagicMock()
        prop1.name = "prop1"

        ignored_prop = MagicMock()
        ignored_prop.name = "parent"

        unreadable_prop = MagicMock()
        unreadable_prop.name = "unreadable"
        unreadable_prop.flags.__and__.return_value = (
            False  # can be anything != PARAM_READWRITE
        )

        unserializable_prop = MagicMock()
        unserializable_prop.name = "unserializable_prop"
        unserializable_value = "unserializable_value"
        mock_Gst.value_serialize.side_effect = lambda v: (
            None if v == unserializable_value else str(v)
        )
        unserializable_prop.flags.__and__.return_value = True

        mock_elem.list_properties.return_value = [
            prop1,
            ignored_prop,
            unreadable_prop,
            unserializable_prop,
        ]
        prop1.flags.__and__.return_value = mock_GObject.PARAM_READWRITE

        mock_pure_elem.get_property.return_value = 0
        mock_elem.get_property.side_effect = lambda prop_name: (
            unserializable_value
            if prop_name == unserializable_prop.name
            else 1
        )
        mock_Gst.value_compare.side_effect = lambda x, y: x == y
        mock_Gst.VALUE_EQUAL = True

        self.assertEqual(cam.get_launch_line(device), "someelement prop1=1")

    @patch("checkbox_support.camera_pipelines.logger")
    @patch("checkbox_support.camera_pipelines.Gst")
    def test_elem_to_str(
        self,
        mock_Gst: MagicMock,
        mock_logger: MagicMock,
    ):
        mock_Gst.value_serialize = lambda x: x
        elem = self.MockElement()  # type: cam.Gst.Element # type: ignore
        self.assertEqual(
            cam.elem_to_str(elem),
            "someelement name=someelement0 some_int_value=1",
        )

        elem2 = self.MockElement()  # type: cam.Gst.Element # type: ignore
        setattr(elem2, "parent", "someparentelem")
        self.assertEqual(  # parent should be omitted
            cam.elem_to_str(elem2),
            "someelement name=someelement0 some_int_value=1",
        )

        elem3 = self.MockElement()  # type: cam.Gst.Element # type: ignore
        setattr(elem3, "parent", "someparentelem")
        # unserializable value
        mock_Gst.value_serialize = lambda x: (
            x is None if x == elem3.some_int_value else x  # type: ignore
        )
        self.assertEqual(  # parent should be omitted
            cam.elem_to_str(elem3),
            "someelement name=someelement0",
        )


if __name__ == "__main__":
    ut.main()
