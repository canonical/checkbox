import torch


print(torch.__version__)


if not torch.cuda.is_available():
    raise AssertionError("CUDA is not available")
