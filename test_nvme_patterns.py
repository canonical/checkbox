#!/usr/bin/env python3
"""Test NVMe name extraction patterns for DGX and Quanta systems"""
import re

def extract_nvme_name(devpath):
    """Extract NVMe device name from DEVPATH using the fix logic"""
    # First try to match nvmeXcYnZ (cloud NVMe device)
    match = re.search(r'/(nvme\d+c\d+n\d+)(?:/|$)', devpath)
    if match:
        return match.group(1)
    # Then try to match nvmeXnY (standard namespace device)
    match = re.search(r'/(nvme\d+n\d+)(?:/|$)', devpath)
    if match:
        return match.group(1)
    # Fallback: match nvmeX (controller) and append n1
    match = re.search(r'/nvme/nvme(\d+)(?:/|$)', devpath)
    if match:
        nvme_num = match.group(1)
        return f"nvme{nvme_num}n1"
    return None

# Test cases from Quanta system (cloud NVMe)
quanta_cases = [
    ("/devices/pci0000:79/0000:79:06.0/0000:7c:00.0/nvme/nvme0/nvme0c0n1", "nvme0c0n1"),
    ("/devices/pci0000:79/0000:79:08.0/0000:7d:00.0/nvme/nvme1/nvme1c1n1", "nvme1c1n1"),
]

# Test cases from DGX system (standard NVMe)
dgx_cases = [
    ("/devices/pci0000:00/0000:00:01.1/0000:02:00.0/nvme/nvme2/nvme2n1", "nvme2n1"),
    ("/devices/pci0000:00/0000:00:02.0/0000:03:00.0/nvme/nvme0", "nvme0n1"),
]

print("Testing Quanta (Cloud NVMe) patterns:")
print("=" * 60)
for devpath, expected in quanta_cases:
    result = extract_nvme_name(devpath)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    print(f"{status}: {devpath}")
    print(f"  Expected: {expected}, Got: {result}")
    print()

print("\nTesting DGX (Standard NVMe) patterns:")
print("=" * 60)
for devpath, expected in dgx_cases:
    result = extract_nvme_name(devpath)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    print(f"{status}: {devpath}")
    print(f"  Expected: {expected}, Got: {result}")
    print()

# Summary
all_cases = quanta_cases + dgx_cases
passed = sum(1 for devpath, expected in all_cases if extract_nvme_name(devpath) == expected)
total = len(all_cases)

print("\n" + "=" * 60)
print(f"SUMMARY: {passed}/{total} tests passed")
if passed == total:
    print("✓ All patterns work correctly - no regression!")
else:
    print("✗ Some patterns failed - regression detected!")
