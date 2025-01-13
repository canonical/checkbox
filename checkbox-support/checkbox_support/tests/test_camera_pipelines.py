import typing as T
import unittest as ut
from unittest.mock import MagicMock, patch
import sys

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
from build.lib.build.lib.build.lib.build.lib.build.lib.build.lib.build.lib.checkbox_support.camera_pipelines import (
    CapsResolver,
)
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
        resolver = CapsResolver()
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
        resolver = CapsResolver()
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
            ((15, 1), (60,1)),
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


if __name__ == "__main__":
    ut.main()
