#!/usr/bin/env python3
import argparse
import subprocess
import shlex


def parse_args():
    parser = argparse.ArgumentParser(
        prog="TGPIO Testing Tool",
        description="This is a tool to help you perform the TGPIO testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-r",
        "--run",
        type=str,
        choices=["server", "receive"],
        help="The ptp device node to test",
        required=True,
    )
    parser.add_argument(
        "-d",
        "--device",
        type=str,
        help="The ptp device node to test",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--pin",
        type=str,
        help="The pin number to test",
        required=True,
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        help="The timeout in seconds",
        default=10,
    )
    return parser.parse_args()


def server_mode(device: str, pin: str):
    cmd = "testptp -d {} -i {} -L {},2 -p 1000000000".format(device, pin, pin)
    subprocess.check_call(shlex.split(cmd))


def receive_timestamp(device: str, pin: str, timeout: int = 10):
    cmd = "testptp -d {} -i {} -L {},1 -e 100 -o {} -E".format(
        device, pin, pin, timeout
    )
    try:
        output = subprocess.check_output(shlex.split(cmd))
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "[ERROR] Failed to receive timestamps: {}".format(str(e))
        )

    event_times = [
        int(line.split(":")[-1].split(",")[0].strip())
        for line in output.splitlines()
        if "Event time time" in line
    ]
    cnt = len(event_times)
    deltas = [
        y - x for (x, y) in zip(iter(event_times), iter(event_times[1:]))
    ]
    if any(delta != 1 for delta in deltas):
        raise SystemExit(
            "[ERROR] Some events didn't take exactly 1 second\n"
            "Timestamps: {}\n"
            "Deltas:{}".format(str(event_times), str(deltas))
        )
    if cnt < timeout - 1 or timeout + 1 < cnt:
        raise SystemExit("[ERROR] The number for Event time time is incorrect")
    print("[PASS] Time Delta is 1")


def main():
    args = parse_args()
    if args.run == "server":
        server_mode(args.device, args.pin)
    elif args.run == "receive":
        receive_timestamp(args.device, args.pin, args.timeout)
    else:
        raise SystemExit("[ERROR] Invalid run type")


if __name__ == "__main__":
    main()
