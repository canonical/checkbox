import unittest
from unittest.mock import MagicMock, patch

from checkbox_support.scripts.nvlink_status import (
    NVML_ERROR_NOT_SUPPORTED,
    NVML_SUCCESS,
    check_nv_link_status,
    main,
)


def _make_nvml_mock(
    device_count=1, link_states=None, init_ret=NVML_SUCCESS, count_ret=None
):
    """
    Build a MagicMock standing in for the ctypes.CDLL("libnvidia-ml.so.1")
    object, wiring up nvmlInit_v2/nvmlDeviceGetCount_v2/
    nvmlDeviceGetHandleByIndex_v2/nvmlDeviceGetNvLinkState/nvmlShutdown.

    :param device_count: number of devices nvmlDeviceGetCount_v2 reports

    :param link_states: iterable of NVLink link states (0/1) returned in
                         order for nvmlDeviceGetNvLinkState calls, or
                         empty/None for "not supported"/no active links

    :param init_ret: return code of nvmlInit_v2

    :param count_ret: return code of nvmlDeviceGetCount_v2, defaults to
                       NVML_SUCCESS
    """
    if count_ret is None:
        count_ret = NVML_SUCCESS
    link_states = list(link_states or [])

    nvml = MagicMock()
    nvml.nvmlInit_v2.return_value = init_ret

    def fake_get_count(count_ptr):
        count_ptr._obj.value = device_count
        return count_ret

    nvml.nvmlDeviceGetCount_v2.side_effect = fake_get_count

    def fake_get_handle(index, handle_ptr):
        handle_ptr._obj.value = 1
        return NVML_SUCCESS

    nvml.nvmlDeviceGetHandleByIndex_v2.side_effect = fake_get_handle

    call_counter = {"n": 0}

    def fake_get_nvlink_state(handle, link, state_ptr):
        idx = call_counter["n"]
        call_counter["n"] += 1
        if idx >= len(link_states):
            return NVML_ERROR_NOT_SUPPORTED
        state_ptr._obj.value = link_states[idx]
        return NVML_SUCCESS

    nvml.nvmlDeviceGetNvLinkState.side_effect = fake_get_nvlink_state

    return nvml


class CheckNvLinkStatusTests(unittest.TestCase):
    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_nvlink_detected(self, mock_cdll):
        mock_cdll.return_value = _make_nvml_mock(link_states=[0, 1])
        self.assertTrue(check_nv_link_status())

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_nvlink_not_detected(self, mock_cdll):
        mock_cdll.return_value = _make_nvml_mock(link_states=[0, 0])
        self.assertFalse(check_nv_link_status())

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_nvlink_not_supported(self, mock_cdll):
        mock_cdll.return_value = _make_nvml_mock(link_states=[])
        self.assertFalse(check_nv_link_status())

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_nvml_init_failed(self, mock_cdll):
        mock_cdll.return_value = _make_nvml_mock(init_ret=1)
        self.assertFalse(check_nv_link_status())

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_device_count_failed(self, mock_cdll):
        mock_cdll.return_value = _make_nvml_mock(count_ret=1)
        self.assertFalse(check_nv_link_status())

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_missing_lib_default_result(self, mock_cdll):
        mock_cdll.side_effect = OSError("library not found")
        self.assertFalse(check_nv_link_status())

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_missing_lib_custom_result(self, mock_cdll):
        mock_cdll.side_effect = OSError("library not found")
        self.assertTrue(check_nv_link_status(missing_lib_result=True))

    @patch("checkbox_support.scripts.nvlink_status.ctypes.CDLL")
    def test_shutdown_called(self, mock_cdll):
        nvml_mock = _make_nvml_mock(link_states=[1])
        mock_cdll.return_value = nvml_mock
        check_nv_link_status()
        nvml_mock.nvmlShutdown.assert_called_once()


class MainTests(unittest.TestCase):
    @patch("checkbox_support.scripts.nvlink_status.check_nv_link_status")
    def test_exit_code_0_when_detected(self, mock_check):
        mock_check.return_value = True
        self.assertEqual(main([]), 0)

    @patch("checkbox_support.scripts.nvlink_status.check_nv_link_status")
    def test_exit_code_1_when_not_detected(self, mock_check):
        mock_check.return_value = False
        self.assertEqual(main([]), 1)

    @patch("checkbox_support.scripts.nvlink_status.check_nv_link_status")
    def test_missing_lib_exit_code_default(self, mock_check):
        # default --missing-lib-exit-code is 1, so check_nv_link_status
        # should be called with missing_lib_result=False
        mock_check.return_value = False
        main([])
        mock_check.assert_called_once_with(False)

    @patch("checkbox_support.scripts.nvlink_status.check_nv_link_status")
    def test_missing_lib_exit_code_override(self, mock_check):
        mock_check.return_value = True
        result = main(["--missing-lib-exit-code", "0"])
        mock_check.assert_called_once_with(True)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
