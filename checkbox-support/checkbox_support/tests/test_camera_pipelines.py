import unittest as ut
from unittest.mock import MagicMock, patch
import sys

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
        resolver = cam.CapsResolver()
        cap = MagicMock()
        struct = MagicMock()

        # cap is video/x-raw, width=[ 600, 1300 ], height=[ 400, 800 ]
        cap.get_structure(0).return_value = struct

        mock_g_object.ValueArray = list

        def mock_fixate_nearest_int(prop: str, target_int: int):
            if target_int < 0:
                struct.get_int.return_value = (
                    True,
                    600 if prop == "width" else 400,
                )
            else:
                struct.get_int.return_value = (
                    True,
                    1300 if prop == "width" else 800,
                )

            struct.has_field_typed(prop, cam.Gst.IntRange).return_value = False

        struct.copy.return_value = struct

        struct.fixate_field_nearest_int.side_effect = mock_fixate_nearest_int


if __name__ == "__main__":
    ut.main()
