#!/usr/bin/env python3

import os
import subprocess
import platform
from collections import defaultdict

classes_list = ["cpu", "cpu-cache", "memory", "os", "pipe", "scheduler", "vm"]


# root -> stressor requires root permission
# pathological -> option is required or the test will refuse to run
# unsupported -> stressor is disabled. COMMENT WHY
extra_attributes = ["root", "pathological", "unsupported"]
stressor_attributes = defaultdict(lambda: defaultdict(bool))

stressors_requiring_root = [
    "apparmor",
    "binderfs",
    "cgroup",
    "chroot",
    "dfp",
    "fanotify",
    "icmp-flood",
    "idle-page",
    "klog",
    "loop",
    "lsm",
    "memhotplug",
    "module",
    "mseal",
    "netlink-proc",
    "netlink-task",
    "physmmap",
    "physpage",
    "plugin",
    "quota",
    "ramfs",
    "rawpkt",
    "rawsock",
    "rawudp",
    "rdrand",
    "seccomp",
    "secretmem",
    "smi",
    "softlockup",
    "statmount",
    "swap",
    "tsc",
    "tun",
    "umount",
    "uprobe",
    "userfaultfd",
    "usersyscall",
    "ioport",
    "ipsec-mb",
    "x86cpuid",
    "x86syscall",
    "bad-ioctl",
    "bind-mount",
    "mlockmany",
    "oom-pipe",
    "sysinval",
    "watchdog",
]
for stressor in stressors_requiring_root:
    stressor_attributes[stressor]["root"] = True

stressor_attributes["bad-ioctl"]["pathological"] = True
stressor_attributes["bind-mount"]["pathological"] = True
stressor_attributes["cpu-online"]["pathological"] = True
stressor_attributes["mlockmany"]["pathological"] = True
stressor_attributes["oom-pipe"]["pathological"] = True
stressor_attributes["sysinval"]["pathological"] = True
stressor_attributes["watchdog"]["pathological"] = True

if platform.machine().lower() not in ["x86_64", "amd64"]:
    # stressors are x86 specific
    stressor_attributes["ioport"]["unsupported"] = True
    stressor_attributes["ipsec-mb"]["unsupported"] = True
    stressor_attributes["x86cpuid"]["unsupported"] = True
    stressor_attributes["x86syscall"]["unsupported"] = True


def main():
    # STRESS_NG_EXTRA_UNSUPPORTED is a space-separated list of stressors to
    # skip, for instance "ioport x86cpuid x86syscall"
    extra_unsupported = os.getenv("STRESS_NG_EXTRA_UNSUPPORTED", "").split()
    for unsupported in extra_unsupported:
        stressor_attributes[unsupported]["unsupported"] = True

    stressors_list = []

    for stress_ng_class in classes_list:
        cmd_get_stressors = [
            "stress-ng",
            "--class",
            "{}?".format(stress_ng_class),
        ]
        try:
            output = subprocess.run(
                cmd_get_stressors,
                capture_output=True,
                universal_newlines=True,
                check=True,
            ).stdout
        except Exception as err:
            raise SystemExit(err)

        # the `stress-ng --class` command returns something like this:
        # class 'cpu' stressors: af-alg atomic bitonicsort ...
        class_stressor_list = output.split(": ", 1)[1].split()

        for class_stressor in class_stressor_list:
            if class_stressor in stressors_list:
                continue
            stressors_list.append(class_stressor)

    stressors_list.sort()
    for stressor in stressors_list:
        print("stressor: {}".format(stressor))
        for extra_attribute in extra_attributes:
            print(
                "{}: {}".format(
                    extra_attribute,
                    stressor_attributes[stressor][extra_attribute],
                )
            )
        print()


if __name__ == "__main__":
    main()
