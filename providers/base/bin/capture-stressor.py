#!/usr/bin/python3

import subprocess

classes_list = ["cpu", "cpu-cache", "memory", "os", "pipe", "scheduler", "vm"]

stressors_list = []

for stress_ng_class in classes_list:
    cmd_get_stressors = ["stress-ng", "--class", "{}?".format(stress_ng_class)]
    try:
        output = subprocess.run(
            cmd_get_stressors,
            capture_output=True,
            universal_newlines=True,
            check=True,
        ).stdout
    except Exception as err:
        raise SystemExit(err)

    class_stressor_list = output.split(": ")[1].split()

    for class_stressor in class_stressor_list:
        if class_stressor in stressors_list:
            continue
        stressors_list.append(class_stressor)

stressors_list.sort()
for stressor in stressors_list:
    print("stressor: {}".format(stressor))
    print()
