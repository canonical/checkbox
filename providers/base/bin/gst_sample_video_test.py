import argparse as ap
import os
import subprocess as sp


def parse_args() -> ap.Namespace:
    p = ap.ArgumentParser()
    p.add_argument("timeout", type=int)
    return p.parse_args()


def pick_sink() -> str:
    xdg_session_type = os.environ["XDG_SESSION_TYPE"]
    if xdg_session_type == "wayland":
        return "waylandsink"  # existed since 20.04
    elif xdg_session_type == "x11":
        return "xvimagesink"  # this exists on all versions all the way back to 16.04
    else:
        raise RuntimeError(
            f"Not in a graphical session! XDG_SESSION_TYPE={xdg_session_type}"
        )


def main():
    args = parse_args()

    if args.timeout <= 0:
        raise ValueError(f"A positive timeout is required, got {args.timeout}")

    print(f"Running Gst pipeline for {args.timeout} seconds".center(80, "-"))

    elems = ["videotestsrc", "videoconvert", pick_sink()]
    str_pipeline = " ! ".join(elems)
    print(f"Pipeline: {str_pipeline}")
    try:
        sp.check_call(
            ["gst-launch-1.0", "-v", *str_pipeline.split()],
            timeout=args.timeout,
        )
    except sp.TimeoutExpired:
        # this is expected
        pass


if __name__ == "__main__":
    main()
