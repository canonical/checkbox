#!/usr/bin/env python3


def get_mem_sleep_types():
    with open("/sys/power/mem_sleep", "r") as fp:
        types = fp.read().strip()
    return types.split()


def get_supported_suspend_type(types: list[str]):
    for type in types:
        if type.startswith("[") and type.endswith("]"):
            return type[1:-1]
    return None


def main():
    types = get_mem_sleep_types()
    suspend_type = get_supported_suspend_type(types)
    print("type: {}".format(suspend_type))


if __name__ == "__main__":
    main()
