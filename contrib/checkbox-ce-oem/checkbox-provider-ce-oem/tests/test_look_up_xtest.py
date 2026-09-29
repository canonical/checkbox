import unittest
from unittest.mock import patch

import look_up_xtest


class TestListApps(unittest.TestCase):

    @patch.object(look_up_xtest.ExtendSanpd, "_get")
    def test_builds_names_query_when_snap_given(self, mock_get):
        look_up_xtest.ExtendSanpd().list_apps("hon-x-test")
        mock_get.assert_called_once_with("/v2/apps", params="names=hon-x-test")

    @patch.object(look_up_xtest.ExtendSanpd, "_get")
    def test_no_params_when_snap_omitted(self, mock_get):
        look_up_xtest.ExtendSanpd().list_apps()
        mock_get.assert_called_once_with("/v2/apps", params=None)


class TestLookUpApp(unittest.TestCase):

    @patch.object(look_up_xtest.ExtendSanpd, "list_apps")
    def test_scopes_lookup_to_requested_snap(self, mock_list_apps):
        # Regression test: list_apps() must actually be called with
        # the snap name so snapd only returns that snap's apps —
        # otherwise an "xtest" app belonging to an unrelated snap
        # (e.g. a board's gadget snap) could be matched instead.
        mock_list_apps.return_value = {
            "result": [{"snap": "hon-x-test", "name": "xtest"}]
        }
        result = look_up_xtest.look_up_app("xtest", "hon-x-test")
        mock_list_apps.assert_called_once_with("hon-x-test")
        self.assertEqual(result, "hon-x-test.xtest")


if __name__ == "__main__":
    unittest.main()
