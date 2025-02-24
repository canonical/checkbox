import torch
import intel_extension_for_pytorch as ipex


print(torch.__version__)
print(ipex.__version__)


if torch.xpu.device_count() < 1:
    raise AssertionError("no XPUs are available")
