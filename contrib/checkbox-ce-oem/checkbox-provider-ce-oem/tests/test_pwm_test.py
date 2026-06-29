import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pwm_test import CheckCommand
from pwm_test import DebugfsPwmParser
from pwm_test import PwmController
from pwm_test import PwmOutput


class FakePwmSysfs:
    def __init__(self, controllers):
        self.controllers = controllers
        self.pwmchips = {
            "platform/1100e000.disp-pwm0": Path("/sys/class/pwm/pwmchip0"),
            "platform/11008000.pwm": Path("/sys/class/pwm/pwmchip2"),
        }

    def read_controllers(self):
        return self.controllers

    def resolve_pwmchip_path_by_name(self, chip_name):
        return self.pwmchips[chip_name]


class TestDebugfsPwmParser(unittest.TestCase):
    def test_parse_controllers_preserves_controller_device_counts(self):
        parser = DebugfsPwmParser()

        controllers = parser.parse_controllers(
            "\n".join(
                [
                    "0: platform/1100e000.disp-pwm0, 1 PWM device",
                    " pwm-0   (backlight-lcd0      ): "
                    "requested enabled period: 500000 ns duty: 153470 ns "
                    "polarity: normal",
                    "",
                    "1: platform/11008000.pwm, 3 PWM devices",
                    " pwm-0   ((null)              ): "
                    "period: 0 ns duty: 0 ns polarity: normal",
                    " pwm-1   ((null)              ): "
                    "period: 0 ns duty: 0 ns polarity: normal",
                    " pwm-2   ((null)              ): "
                    "period: 0 ns duty: 0 ns polarity: normal",
                ]
            )
        )

        self.assertEqual(len(controllers), 2)
        self.assertEqual(
            controllers[0].chip_name, "platform/1100e000.disp-pwm0"
        )
        self.assertEqual(controllers[0].device_count, 1)
        self.assertEqual(len(controllers[1].outputs), 3)


class TestCheckCommand(unittest.TestCase):
    def setUp(self):
        self.controllers = [
            PwmController(
                chip_name="platform/1100e000.disp-pwm0",
                device_count=1,
                outputs=(
                    PwmOutput(
                        chip_name="platform/1100e000.disp-pwm0",
                        pwm_name="pwm-0",
                        consumer="backlight-lcd0",
                        requested=True,
                        enabled=True,
                        period=500000,
                        duty=153470,
                        polarity="normal",
                    ),
                ),
            ),
            PwmController(
                chip_name="platform/11008000.pwm",
                device_count=2,
                outputs=(
                    PwmOutput(
                        chip_name="platform/11008000.pwm",
                        pwm_name="pwm-0",
                        consumer=None,
                        requested=False,
                        enabled=False,
                        period=0,
                        duty=0,
                        polarity="normal",
                    ),
                    PwmOutput(
                        chip_name="platform/11008000.pwm",
                        pwm_name="pwm-1",
                        consumer=None,
                        requested=False,
                        enabled=False,
                        period=0,
                        duty=0,
                        polarity="normal",
                    ),
                ),
            ),
        ]

    def test_check_lists_mapping_without_expected_count(self):
        output = io.StringIO()

        with redirect_stdout(output):
            result = CheckCommand(FakePwmSysfs(self.controllers)).run(None)

        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("PWM_CHIP: pwmchip0", text)
        self.assertIn("Consumer: backlight-lcd0", text)
        self.assertIn("Consumer: NotDefined", text)
        self.assertIn("TOTAL_PWM_CHIP_NUM: 2", text)
        self.assertIn("TOTAL_PWM_DEV_NUM: 3", text)
        self.assertIn("RESULT: PASS", text)

    def test_check_validates_expected_count_mismatch(self):
        output = io.StringIO()

        with redirect_stdout(output):
            result = CheckCommand(FakePwmSysfs(self.controllers)).run(4)

        self.assertEqual(result, 1)
        text = output.getvalue()
        self.assertIn("EXPECTED_PWM_DEV_TOTAL_NUM: 4", text)
        self.assertIn("RESULT: FAIL", text)
        self.assertIn("ERROR: discovered 3 PWM devices, expected 4", text)


if __name__ == "__main__":
    unittest.main()
