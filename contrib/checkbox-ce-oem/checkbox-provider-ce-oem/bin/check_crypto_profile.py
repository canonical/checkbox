#!/usr/bin/python3
import argparse


def read_crypto_info():
    with open("/proc/crypto", "r") as fp:
        data = fp.read()

    return data


def crypto_info_parser(crypto_raw):
    crypto_info = dict()
    mandatory_keys = ["name", "priority", "type", "driver"]

    for data in crypto_raw.strip("\n").split("\n\n"):
        tmp_dict = {}
        for item in data.strip().split("\n"):
            key, value = item.split(":")
            tmp_dict.update({key.strip(): value.strip()})

        if not all([tmp_dict.get(key) for key in mandatory_keys]):
            continue

        if not tmp_dict.get("priority", "").isnumeric():
            print(
                "Crypto priority is not numeric string. Actual: {}".format(
                    tmp_dict.get("priority")
                )
            )
            continue
        else:
            priority = int(tmp_dict.get("priority", 0))
        name = tmp_dict.get("name")

        if name not in crypto_info.keys():
            crypto_info.update({name: {}})

        if priority not in crypto_info[name].keys():
            crypto_info[name][priority] = []

        crypto_info[name][priority].append(
            (tmp_dict.get("type"), tmp_dict.get("driver"))
        )

    return crypto_info


def check_algo_support(crypto_info, algo_key):
    if algo_key in crypto_info.keys():
        print("Passed")
    else:
        raise SystemExit("{} crypto type is not supported".format(algo_key))


def check_driver_and_algo_type(crypto_info, crypto_type, driver_pattern):

    result = False
    for priority in sorted(crypto_info.keys(), reverse=True):
        print("## priority: {}".format(priority))
        for data in crypto_info[priority]:

            print(
                "\n### Crypto information. type: {}, driver: {}".format(
                    data[0], data[1]
                )
            )

            if data[0] in crypto_type and driver_pattern in data[1]:
                return True

    return result


def check_crypto_test(args):
    crypto_name = args.crypto_name
    crypto_types = args.crypto_type
    driver_pattern = args.driver_pattern

    crypto_info = crypto_info_parser(read_crypto_info())

    print(
        "\n# Checking Crypto {} name with {} type is supported: ".format(
            crypto_name, crypto_types
        )
    )

    check_algo_support(crypto_info, crypto_name)

    print("\n# Checking driver and type:")
    if check_driver_and_algo_type(
        crypto_info[crypto_name], crypto_types, driver_pattern
    ):
        print("Passed")
    else:
        raise SystemExit(
            "the drivers of {} crypto does not match '{}' pattern".format(
                crypto_name, driver_pattern
            )
        )


def dump_crypto_information(args):
    if args.type == "caam":
        check_crypto = [
            {
                "name": "sha256",
                "type": ["ahash", "shash"],
                "driver_pattern": "caam",
            },
            {
                "name": "cbc(aes)",
                "type": ["skcipher"],
                "driver_pattern": "caam",
            },
            {"name": "gcm(aes)", "type": ["aead"], "driver_pattern": "caam"},
            {"name": "stdrng", "type": ["rng"], "driver_pattern": "caam"},
        ]
    elif args.type == "mcrc":
        check_crypto = [
            {
                "name": "crc64",
                "type": ["ahash", "shash"],
                "driver_pattern": "mcrc",
            }
        ]
    elif args.type == "sa2ul":
        check_crypto = [
            {
                "name": "sha256",
                "type": ["ahash", "shash"],
                "driver_pattern": "sa2ul",
            },
            {
                "name": "cbc(aes)",
                "type": ["skcipher"],
                "driver_pattern": "sa2ul",
            },
            {
                "name": "authenc(hmac(sha256),cbc(aes))",
                "type": ["aead"],
                "driver_pattern": "sa2ul",
            },
        ]
    else:
        print("name: unsupported crypto accelerator {}".format(args.type))
        return

    for data in check_crypto:
        for key, value in data.items():
            if isinstance(value, list):
                value = " ".join(value)
            print("{}: {}".format(key, value))
        print()


def main():
    parser = argparse.ArgumentParser()
    sub_parser = parser.add_subparsers(
        help="action", dest="action_type", required=True
    )

    check_parser = sub_parser.add_parser("check")
    check_parser.add_argument(
        "-t", "--crypto-type", required=True, nargs="+", type=str
    )
    check_parser.add_argument("-n", "--crypto-name", required=True, type=str)
    check_parser.add_argument(
        "-d", "--driver-pattern", required=True, type=str
    )
    check_parser.set_defaults(action_type=check_crypto_test)

    resource_parser = sub_parser.add_parser("resource")
    resource_parser.add_argument(
        "-t",
        "--type",
        choices=["caam", "sa2ul", "mcrc"],
        required=True,
        help="Validate specific crypto driver module",
    )
    resource_parser.set_defaults(action_type=dump_crypto_information)

    args = parser.parse_args()
    args.action_type(args)


if __name__ == "__main__":
    main()
