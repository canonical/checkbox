import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import pci_driver_conflict

WIFI = "0001:01:00.0"
# RTL8822CE on a Jetson Orin: rtw88_8822ce (in-kernel) and rtl8822ce (NVIDIA)
# both match it
MODALIAS = "pci:v000010ECd0000C822sv00001A3Bsd00003751bc02sc80i00"
ALIASES = (
    "alias pci:v000010ECd0000C822sv*sd*bc*sc*i* rtw88_8822ce\n"
    "alias pci:v000010ECd0000C822sv*sd*bc*sc*i* rtl8822ce\n"
    "alias pci:v000010ECd00008168sv*sd*bc*sc*i* r8168\n"
)


class FakeSystem:
    def __init__(self, root):
        self.root = Path(root)
        self.sys = self.root / "sys"

    def driver(self, name, module, devices=()):
        """Add a PCI driver of a module, with the devices bound to it."""
        path = self.sys / "bus" / "pci" / "drivers" / name
        path.mkdir(parents=True)
        (path / "bind").touch()
        for device in devices:
            (path / device).mkdir()
        mod_drivers = self.sys / "module" / module / "drivers"
        mod_drivers.mkdir(parents=True, exist_ok=True)
        os.symlink(path, mod_drivers / ("pci:" + name))
        os.symlink(self.sys / "module" / module, path / "module")
        return path

    def device(self, name, driver_path, modalias=MODALIAS):
        path = self.sys / "bus" / "pci" / "devices" / name
        path.mkdir(parents=True)
        (path / "modalias").write_text(modalias + "\n")
        (path / "vendor").write_text("0x10ec\n")
        (path / "device").write_text("0xc822\n")
        os.symlink(driver_path, path / "driver")

    def run(self, loaded, ignore="", extra_aliases=""):
        (self.root / "modules.alias").write_text(ALIASES + extra_aliases)
        (self.root / "modules").write_text(
            "".join("{} 1 0 - Live 0x0\n".format(m) for m in loaded)
        )
        out = io.StringIO()
        with redirect_stdout(out):
            ret = pci_driver_conflict.main(
                [
                    "--ignore",
                    ignore,
                    "--sys-root",
                    str(self.sys),
                    "--modules-alias",
                    str(self.root / "modules.alias"),
                    "--proc-modules",
                    str(self.root / "modules"),
                ]
            )
        return ret, out.getvalue()


class TestPciDriverConflict(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.system = FakeSystem(tmp.name)
        nvidia = self.system.driver("rtl88x2ce", "rtl8822ce", [WIFI])
        self.system.device(WIFI, nvidia)

    def test_loaded_module_with_no_device_fails(self):
        self.system.driver("rtw_8822ce", "rtw88_8822ce")
        ret, out = self.system.run(["rtl8822ce", "rtw88_8822ce"])
        self.assertEqual(ret, 1)
        self.assertIn(
            "FAIL: 0001:01:00.0 [10ec:c822] is bound to module rtl8822ce, "
            "but module rtw88_8822ce also matches it",
            out,
        )

    def test_blocked_module_is_not_loaded(self):
        ret, out = self.system.run(["rtl8822ce"])
        self.assertEqual(ret, 0)
        self.assertIn("PASS", out)

    def test_module_that_drives_another_device_passes(self):
        self.system.driver("rtw_8822ce", "rtw88_8822ce", ["0002:01:00.0"])
        ret, _ = self.system.run(["rtl8822ce", "rtw88_8822ce"])
        self.assertEqual(ret, 0)

    def test_module_in_the_bound_driver_stack_passes(self):
        # like nvidia_drm -> nvidia_modeset -> nvidia on Jetson AGX Thor
        modules = self.system.sys / "module"
        (modules / "rtl8822ce" / "holders" / "rtl_helper").mkdir(parents=True)
        (modules / "rtl_helper" / "holders" / "rtw88_8822ce").mkdir(
            parents=True
        )
        self.system.driver("rtw_8822ce", "rtw88_8822ce")
        ret, _ = self.system.run(["rtl8822ce", "rtl_helper", "rtw88_8822ce"])
        self.assertEqual(ret, 0)

    def test_modules_of_one_driver_selector_pass(self):
        # like snd_hda_intel and snd_sof_pci_intel_* with snd_intel_dspcfg
        holders = self.system.sys / "module" / "snd_intel_dspcfg" / "holders"
        (holders / "rtl8822ce").mkdir(parents=True)
        (holders / "rtw88_8822ce").mkdir()
        self.system.driver("rtw_8822ce", "rtw88_8822ce")
        ret, _ = self.system.run(["rtl8822ce", "rtw88_8822ce"])
        self.assertEqual(ret, 0)

    def test_driver_family_passes(self):
        # i915 drives the GPU, xe is loaded and declines it (force_probe)
        gpu = "pci:v00008086d00009A49sv00001028sd00000A38bc03sc00i00"
        i915 = self.system.driver("i915", "i915", ["0000:00:02.0"])
        self.system.device("0000:00:02.0", i915, modalias=gpu)
        self.system.driver("xe", "xe")
        aliases = "alias pci:v00008086d00009A49sv*sd*bc03sc*i* {}\n"
        ret, out = self.system.run(
            ["rtl8822ce", "i915", "xe"],
            extra_aliases=aliases.format("i915") + aliases.format("xe"),
        )
        self.assertEqual(ret, 0)
        self.assertIn("Checked 2 PCI devices", out)

    def test_selector_of_the_other_module_only_fails(self):
        holders = self.system.sys / "module" / "snd_intel_dspcfg" / "holders"
        (holders / "rtw88_8822ce").mkdir(parents=True)
        self.system.driver("rtw_8822ce", "rtw88_8822ce")
        ret, _ = self.system.run(["rtl8822ce", "rtw88_8822ce"])
        self.assertEqual(ret, 1)

    def test_ignored_module_passes(self):
        self.system.driver("rtw_8822ce", "rtw88_8822ce")
        ret, out = self.system.run(
            ["rtl8822ce", "rtw88_8822ce"], ignore="rtw88-8822ce"
        )
        self.assertEqual(ret, 0)
        self.assertIn("Ignored modules: rtw88_8822ce", out)

    def test_device_without_driver_is_skipped(self):
        r8168 = "pci:v000010ECd00008168sv00001A3Bsd00003751bc02sc00i00"
        path = self.system.sys / "bus" / "pci" / "devices" / "0008:01:00.0"
        path.mkdir(parents=True)
        (path / "modalias").write_text(r8168)
        ret, out = self.system.run(["rtl8822ce", "r8168"])
        self.assertEqual(ret, 0)
        self.assertIn("Checked 1 PCI devices", out)

    def test_no_pci_bus_passes(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ret, out = FakeSystem(tmp.name).run([])
        self.assertEqual(ret, 0)
        self.assertIn("Checked 0 PCI devices", out)


if __name__ == "__main__":
    unittest.main()
