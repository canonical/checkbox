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

stressor_attributes["apparmor"]["root"] = True
stressor_attributes["binderfs"]["root"] = True
stressor_attributes["cgroup"]["root"] = True
stressor_attributes["chroot"]["root"] = True
stressor_attributes["dfp"]["root"] = True
stressor_attributes["fanotify"]["root"] = True
stressor_attributes["icmp-flood"]["root"] = True
stressor_attributes["idle-page"]["root"] = True
stressor_attributes["klog"]["root"] = True
stressor_attributes["loop"]["root"] = True
stressor_attributes["lsm"]["root"] = True
stressor_attributes["memhotplug"]["root"] = True
stressor_attributes["module"]["root"] = True
stressor_attributes["mseal"]["root"] = True
stressor_attributes["netlink-proc"]["root"] = True
stressor_attributes["netlink-task"]["root"] = True
stressor_attributes["physmmap"]["root"] = True
stressor_attributes["physpage"]["root"] = True
stressor_attributes["plugin"]["root"] = True
stressor_attributes["quota"]["root"] = True
stressor_attributes["ramfs"]["root"] = True
stressor_attributes["rawpkt"]["root"] = True
stressor_attributes["rawsock"]["root"] = True
stressor_attributes["rawudp"]["root"] = True
stressor_attributes["rdrand"]["root"] = True
stressor_attributes["seccomp"]["root"] = True
stressor_attributes["secretmem"]["root"] = True
stressor_attributes["smi"]["root"] = True
stressor_attributes["softlockup"]["root"] = True
stressor_attributes["statmount"]["root"] = True
stressor_attributes["swap"]["root"] = True
stressor_attributes["tsc"]["root"] = True
stressor_attributes["tun"]["root"] = True
stressor_attributes["umount"]["root"] = True
stressor_attributes["uprobe"]["root"] = True
stressor_attributes["userfaultfd"]["root"] = True
stressor_attributes["usersyscall"]["root"] = True
stressor_attributes["ioport"]["root"] = True
stressor_attributes["ipsec-mb"]["root"] = True
stressor_attributes["x86cpuid"]["root"] = True
stressor_attributes["x86syscall"]["root"] = True

stressor_attributes["bad-ioctl"].update(root=True, pathological=True)
stressor_attributes["bind-mount"].update(root=True, pathological=True)
stressor_attributes["cpu-online"].update(root=True, pathological=True)
stressor_attributes["mlockmany"].update(root=True, pathological=True)
stressor_attributes["oom-pipe"].update(root=True, pathological=True)
stressor_attributes["sysinval"].update(root=True, pathological=True)
stressor_attributes["watchdog"].update(root=True, pathological=True)

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
