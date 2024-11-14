#!/usr/bin/env python3

import sys
import torch
import intel_extension_for_pytorch as ipex

print(torch.__version__)
print(ipex.__version__)

try:
    [
        print(f"[{i}]: {torch.xpu.get_device_properties(i)}")
        for i in range(torch.xpu.device_count())
    ]
    sys.exit(0)
except Exception:
    print("Encountered an error getting XPU device properties", file=sys.stderr)
    sys.exit(1)
