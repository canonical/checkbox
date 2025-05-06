import os
import subprocess as sp
import typing as T
from math import sqrt
from sys import argv


def get_expected_refresh_rate(
    xdg_session_type: str,
) -> float:
    if xdg_session_type == "x11":
        xrandr_out = sp.check_output(["xrandr"], universal_newlines=True)
        fps_str_idx = 1
    else:
        xrandr_out = sp.check_output(["gnome-randr"], universal_newlines=True)
        fps_str_idx = 2

    curr_display_mode = None  # type: str | None
    for line in xrandr_out.splitlines():
        if "*" in line:
            curr_display_mode = line
            break

    assert curr_display_mode is not None, "No selected display mode was found"

    return float(
        curr_display_mode.split()[fps_str_idx]
        .replace("*", "")
        .replace("+", "")
    )


def select_glmark2_exec(xdg_session_type: str):
    cpu_arch = sp.check_output(
        ["uname", "-m"], universal_newlines=True
    ).strip()

    if cpu_arch in ("x86_64", "amd64"):
        # x86 devices should run the version that uses the full opengl api
        glmark2_executable = "glmark2"
    else:
        # TODO: explicity check for aarch64?
        glmark2_executable = "glmark2-es2"

    if xdg_session_type == "wayland":
        glmark2_executable += "-wayland"

    return glmark2_executable


def unbiased_coef_of_variation(n: int, mean: float, stdev: float) -> float:
    # assuming normal distribution
    # https://en.wikipedia.org/wiki/Coefficient_of_variation#Estimation
    return (1 + (1 / (4 * n))) * (stdev / mean)


def get_stats(nums: T.List[int]) -> T.Tuple[float, float]:
    if len(nums) == 0:
        return 0.0, 0.0

    mean = sum(nums) / len(nums)

    if len(nums) == 1:
        # this is technically the stdev for a single sample,
        # but if we only have 1 sample, something went wrong
        stdev = 0.0
    else:
        stdev = sqrt(sum((n - mean) ** 2 for n in nums) / (len(nums) - 1))

    return mean, stdev


def main() -> int:
    XDG_SESSION_TYPE = os.getenv("XDG_SESSION_TYPE")

    if XDG_SESSION_TYPE is None:
        raise ValueError("XDG_SESSION_TYPE is not set")
    if XDG_SESSION_TYPE not in ("wayland", "x11"):
        raise ValueError(
            "Unsupported XDG_SESSION_TYPE: {}".format(XDG_SESSION_TYPE)
        )

    glmark2_executable = select_glmark2_exec(XDG_SESSION_TYPE)
    # flush stdout here since opening a GUI window will cause
    # stdout to wait until the window is closed to flush everything
    print(
        "Running {} with forced vsync.".format(glmark2_executable), flush=True
    )
    print("Make sure the glmark2 window is always on top.", flush=True)

    # the --swap-mode fifo option is available on all glmark2 variants
    # and is the official way to enable vsync
    glmark2_out = sp.check_output(
        [glmark2_executable, *argv[1:]],
        universal_newlines=True,
        # kinda ugly, but dict union | isn't introduced until 3.9
        env={**os.environ, "vblank_mode": "3"},
    )

    fps_counts = []  # type: list[int]
    for line in glmark2_out.splitlines():
        if "FPS" not in line:
            continue
        words = line.split()
        fps_str_idx = words.index("FPS:") + 1
        fps_counts.append(int(words[fps_str_idx]))

    mean, stdev = get_stats(fps_counts)
    expected_fps = get_expected_refresh_rate(XDG_SESSION_TYPE)

    print("Raw FPS values:", fps_counts)
    print(
        "Mean: {}, Standard Deviation: {}".format(
            round(mean, 2), round(stdev, 2)
        )
    )

    failed = False
    if len(fps_counts) < 10:
        print(
            "[ ERR ] Not enough FPS samples.",
            "Only received {} samples, but needed 10.".format(len(fps_counts)),
            "Did {} finish?".format(glmark2_executable),
        )
        # fail early here to avoid division by 0
        return 1

    coef_of_var = unbiased_coef_of_variation(len(fps_counts), mean, stdev)
    print("Coefficient of variation: {}".format(coef_of_var))
    if coef_of_var >= 0.2:
        # typically the threshold is 1, but that pretty much accepts everything
        print(
            "[ ERR ] Too much variance. Expected coef_of_var < 0.2",
            "but got {}".format(coef_of_var),
        )
        failed = True
    if abs(mean - expected_fps) > 0.05 * expected_fps:
        print("[ WARN ] Mean is too far from screen refresh rate.")
        print(
            "Expected the average fps to be within 5% of refresh rate: "
            "[{}, {}]".format(
                round(expected_fps * 0.95, 2), round(expected_fps * 1.05, 2)
            )
        )

    if not failed:
        print("OK!")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())
