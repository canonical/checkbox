import os
import subprocess as sp
import typing as T
from math import sqrt


def select_glmark2_exec():
    cpu_arch = sp.check_output(
        ["uname", "-m"], universal_newlines=True
    ).strip()
    XDG_SESSION_TYPE = os.getenv("XDG_SESSION_TYPE")

    if XDG_SESSION_TYPE is None:
        raise ValueError("XDG_SESSION_TYPE is not set")
    if XDG_SESSION_TYPE not in ("wayland", "x11"):
        raise ValueError(
            "Unsupported XDG_SESSION_TYPE: {}".format(XDG_SESSION_TYPE)
        )

    if cpu_arch in ("x86_64", "amd64"):
        # x86 duts should run the version that uses the full opengl api
        glmark2_executable = "glmark2"
    else:
        # TODO: explicity check for aarch64?
        glmark2_executable = "glmark2-es2"

    if XDG_SESSION_TYPE == "wayland":
        glmark2_executable += "-wayland"

    return glmark2_executable


def get_stats(nums: T.List[int]) -> T.Tuple[float, float]:
    if len(nums) == 0:
        return 0.0, 0.0

    mean = sum(nums) / len(nums)

    if len(nums) == 1:
        stdev = 0.0
    else:
        stdev = sqrt(sum((n - mean) ** 2 for n in nums) / (len(nums) - 1))

    return mean, stdev


def main():
    glmark2_executable = select_glmark2_exec()
    print(
        "Running {} with forced vsync.".format(glmark2_executable),
        'If glmark2 prints a warning about "Unable to set swap interval",',
        "you can safely ignore it.",
    )
    print("Make sure the glmark2 window is always on top.")
    glmark2_out = sp.check_output(
        [glmark2_executable, "--annotate", "--swap-mode", "fifo"],
        universal_newlines=True,
    )
    # the --swap-mode fifo option is available on all glmark2 variants
    # and is the official way to enable vsync

    fps_counts = []  # type: list[int]
    for line in glmark2_out.splitlines():
        if "FPS" not in line:
            continue
        fps_counts.append(int(line.split()[3]))

    print(fps_counts)
    mean, stdev = get_stats(fps_counts)

    print("Mean: {}, Standard Deviation: {}".format(mean, stdev))
    if stdev**2 > 0.05 * mean:
        print("Too much variance")
    else:
        print("Ok!")


if __name__ == "__main__":
    main()
