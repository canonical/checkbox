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
    result = subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(result.stdout)
    if result.returncode:
        raise SystemExit(
            "[ERROR] Failed to receive timestamp: {}".format(result.stderr)
        )

    cnt = 0
    prev_event_time = -1
    for line in result.stdout.splitlines():
        if "Event time time" not in line:
            continue
        cnt += 1
        event_time = int(line.split(":")[-1].split(",")[0].strip())
        if prev_event_time == -1:
            prev_event_time = event_time
            continue
        delta = event_time - prev_event_time
        if delta != 1:
            raise SystemExit("[ERROR] Time Delta is not 1")
        prev_event_time = event_time
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
