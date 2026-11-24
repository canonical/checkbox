import unittest
from pathlib import Path

from plainbox.impl.resource import (
    ExpressionFailedError,
    Resource,
    ResourceProgram,
)
from plainbox.impl.secure.rfc822 import load_rfc822_records


class TestDiskTestExclusions(unittest.TestCase):
    def test_os_disk_cannot_satisfy_excluded_disk_requirement(self):
        units = Path(__file__).resolve().parents[1] / "units"
        resources = {
            "device": [
                Resource({"name": "sda", "ignore_test": "False"}),
                Resource({"name": "sdg", "ignore_test": "True"}),
            ],
        }
        for path in (
            "disk/jobs.pxu",
            "benchmarks/jobs.pxu",
        ):
            with (units / path).open() as stream:
                records = list(load_rfc822_records(stream))
            for record in records:
                source = record.data.get("template-resource")
                if source not in resources:
                    continue
                # Inventory and non-storage templates need no exclusion.
                if source == "device" and (
                    record.data.get("template-filter")
                    not in (
                        "device.category == 'DISK'",
                        "device.category == 'DISK' and device.name != ''",
                    )
                ):
                    continue
                with self.subTest(job=record.data["id"]):
                    requirements = record.data.get("requires", "")
                    guard = next(
                        (
                            line
                            for line in requirements.splitlines()
                            if f"{source}.ignore_test" in line
                        ),
                        "",
                    )
                    self.assertTrue(guard, "Missing disk exclusion guard")
                    allowed = ResourceProgram(guard.format(name="sda"))
                    self.assertTrue(allowed.evaluate_or_raise(resources))
                    self.assertTrue(
                        allowed.evaluate_or_raise(
                            {"device": [Resource({"name": "sda"})]}
                        )
                    )
                    excluded = ResourceProgram(guard.format(name="sdg"))
                    with self.assertRaises(ExpressionFailedError):
                        excluded.evaluate_or_raise(resources)


if __name__ == "__main__":
    unittest.main()
