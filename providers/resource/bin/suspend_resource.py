#!/usr/bin/env python3


def get_mem_sleep_types():
    with open("/sys/power/mem_sleep", "r") as fp:
        types = fp.read().strip()
    return types.split()


def get_supported_suspend_types(types):
    supported_types = {}
    for t in types:
        if t.startswith("[") and t.endswith("]"):
            supported_types[t[1:-1]] = "yes"
        elif t:
            supported_types[t] = "no"
    return supported_types


def main():
    types = get_mem_sleep_types()
    supported_types = get_supported_suspend_types(types)
    for type, active in supported_types.items():
        print("type:", type)
        print("active:", active)
        print()


if __name__ == "__main__":
    main()
