#!/usr/bin/env python3
import os
import subprocess
from pathlib import (
    Path,
)


def print_as_resource(
    d: dict,
) -> None:
    for (
        k,
        v,
    ) in d.items():
        print("{}: {}".format(k, v))

    print("")


def get_extra_flags(
    category,
) -> list[str]:
    extra_flags = []
    if category.startswith("ZeInit"):
        extra_flags.append("--ze-init-tests")
    return extra_flags


def get_metric_streamer_allowed_states(
    category: str,
) -> list[str]:
    if category.startswith("Metric"):
        return ["supported"]
    else:
        return [
            "supported",
            "unsupported",
        ]


def get_ivpu_bo_create_allowed_states(
    category: str,
    test_name: str,
) -> list[str]:
    if category in [
        "CompilerInDriverWithProfiling",
        "CommandMemoryFill",
    ] or (
        category == "ImmediateCmdList" and test_name == "FillCopyUsingBarriers"
    ):
        return ["supported"]
    else:
        return [
            "supported",
            "unsupported",
        ]


# Known failures:
# - Device.GetZesEngineGetActivity:
#     No sysfs access for NPU activity data
# - ExternalMemoryZe.GpuZeFillToNpuZeCopy:
#     No GPU support for test
# - ExternalMemoryZe.NpuZeFillToGpuZeCopy:
#     No GPU support for test
# - ExternalMemoryDmaHeap.DmaHeapToNpu/2KB:
#     requires access to /dev/dma_heap/system
# - ExternalMemoryDmaHeap.DmaHeapToNpu/16MB:
#     requires access to /dev/dma_heap/system
# - ExternalMemoryDmaHeap.DmaHeapToNpu/255MB:
#     requires access to /dev/dma_heap/system
# - DriverCache.CheckWhenSpaceLessThanAllBlobs:
#     bug in the test, will be fixed in upstream
# - CommandQueuePriority.\
#        executeManyLowPriorityJobsExpectHighPriorityJobCompletesFirst
#     failing on Arrow Lake and Lunar Lake
def is_known_failure(
    category,
    test_name,
):
    if (
        "Gpu" in test_name
        or "DmaHeap" in category
        or (category == "Device" and test_name == "GetZesEngineGetActivity")
        or (
            category == "DriverCache"
            and test_name == "CheckWhenSpaceLessThanAllBlobs"
        )
        or (
            category == "CommandQueuePriority"
            and test_name
            == "executeManyLowPriorityJobsExpectHighPriorityJobCompletesFirst"
        )
    ):
        return True
    else:
        return False


def main():
    config_path = os.environ.get("NPU_UMD_TEST_CONFIG")

    if not config_path:
        raise SystemExit("NPU_UMD_TEST_CONFIG needs to be defined.")

    gtest_output = subprocess.run(
        ["intel-npu-driver.npu-umd-test", "-l", "--config", Path(config_path)],
        capture_output=True,
        text=True,
    )

    for line in gtest_output.stdout.strip().splitlines():
        if "." in line:
            (
                category,
                test_name,
            ) = line.split(
                ".",
                1,
            )

            extra_flags = get_extra_flags(category)
            metric_streamer_allowed_states = (
                get_metric_streamer_allowed_states(category)
            )
            ivpu_bo_create_allowed_states = get_ivpu_bo_create_allowed_states(
                category,
                test_name,
            )
            known_failure = is_known_failure(
                category,
                test_name,
            )

            records = {}
            records["name"] = test_name
            records["category"] = category
            records["extra_flags"] = " ".join(extra_flags)
            records["metric_streamer_allowed_states"] = (
                metric_streamer_allowed_states
            )
            records["ivpu_bo_create_allowed_states"] = (
                ivpu_bo_create_allowed_states
            )

            if not known_failure:
                print_as_resource(records)


if __name__ == "__main__":
    main()
