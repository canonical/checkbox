#!/usr/bin/python3
import argparse
import ast
from collections import OrderedDict


def read_crypto_info():
    with open("/proc/crypto", "r") as fp:
        data = fp.read()

    return data


def crypto_info_parser(crypto_raw):
    crypto_info = OrderedDict()

    for data in crypto_raw.strip("\n").split("\n\n"):
        tmp_dict = {}
        for item in data.strip().split("\n"):
            key, value = item.split(":")
            tmp_dict.update({key.strip(): value.strip()})

        name = tmp_dict.pop("name")
        priority = int(tmp_dict.pop("priority"))
        driver = tmp_dict.pop("driver")
        type = tmp_dict.pop("type")
        key = "{}_{}".format(type, name)
        if crypto_info.get(key) is None:
            crypto_info.update({key: {}})
        if crypto_info[key].get(priority) is None:
            crypto_info[key][priority] = []
        crypto_info[key][priority].append(driver)

    return crypto_info


def check_algo_support(crypto_info, algo_key):
    if algo_key in crypto_info.keys():
        print("Passed")
        return True
    else:
        print("Failed")
        return False


def check_match_drivers(crypto_info, algo_key, driver_pattern):
    match_drivers = []

    print("all supported driver for {}".format(algo_key))
    print("  Priority\tDriver")
    for priority, drivers in crypto_info[algo_key].items():
        for driver in drivers:
            print("- {}\t\t{}".format(priority, driver))
            if driver_pattern in driver:
                match_drivers.append(driver)

    print(
        "\n# Checking drivers match to '{}' pattern: ".format(driver_pattern),
        end=""
    )
    if match_drivers:
        print("Passed")
    else:
        print("Failed")

    return match_drivers


def check_crypto_driver_priority(crypto_type, crypto_name, driver_pattern):
    crypto_info = crypto_info_parser(read_crypto_info())
    algo_key = "{}_{}".format(crypto_type, crypto_name)
    print(
        "\n# Checking AF_ALG {} type with {} algorithm is supported: ".format(
            crypto_type, crypto_name
        ),
        end=""
    )

    if check_algo_support(crypto_info, algo_key) is False:
        return False

    match_drivers = check_match_drivers(crypto_info, algo_key, driver_pattern)
    if not match_drivers:
        return False

    max_priority = max(crypto_info[algo_key].keys())

    priority_drivers = crypto_info[algo_key][max_priority]
    target_dr = [dr for dr in match_drivers if dr in priority_drivers]

    print("\n# Checking matched driver is highest priority: ", end="")
    if target_dr:
        print("Passed")
        return True
    else:
        print("Failed")
        return False


class TestCryptoDriver():

    @staticmethod
    def check_caam_drivers(crypto_profiles):
        result = True
        check_list = [
            ("hash", "sha256", "caam"),
            ("skcipher", "cbc(aes)", "caam"),
            ("aead", "gcm(aes)", "caam"),
            ("rng", "stdrng", "caam")
        ]

        check_profiles = crypto_profiles if crypto_profiles else check_list
        for profile in check_profiles:
            if not check_crypto_driver_priority(*profile):
                result = False

        if result:
            print("All CAAM crypto drivers is supported")
        else:
            raise SystemExit("Some CAAM crypto drivers is not supported")

    @staticmethod
    def check_mcrc_drivers(crypto_profiles):
        result = True
        check_list = [("shash", "crc64", "mcrc")]

        check_profiles = crypto_profiles if crypto_profiles else check_list
        for profile in check_profiles:
            if not check_crypto_driver_priority(*profile):
                result = False

        if result:
            print("TI mcrc driver is supported")
        else:
            raise SystemExit("TI mcrc is not supported")

    @staticmethod
    def check_sa2ul_drivers(crypto_profiles):
        result = True
        check_list = [
            ("ahash", "sha256", "sa2ul"),
            ("skcipher", "cbc(aes)", "sa2ul"),
            ("aead", "authenc(hmac(sha256),cbc(aes))", "sa2ul")
        ]

        check_profiles = crypto_profiles if crypto_profiles else check_list
        for profile in check_profiles:
            if not check_crypto_driver_priority(*profile):
                result = False

        if result:
            print("All SA2UL crypto drivers is supported")
        else:
            raise SystemExit("Some SA2UL crypto drivers is not supported")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--type",
        choices=["caam", "sa2ul", "mcrc"],
        required=True,
        help="Validate specific crypto driver module"
    )
    parser.add_argument(
        "-p",
        "--crypto-profile",
        type=str,
        help=(
            "The expected crypto information with list format."
            "format: '[('crypto_type', 'crypto_name', 'driver_pattern') ...]'"
            "e.g. '[('aead', 'gcm(aes)', 'caam'), ('rng', 'stdrng', 'caam')]'"
        ),
        default="[]"
    )
    args = parser.parse_args()
    func = getattr(TestCryptoDriver, "check_{}_drivers".format(args.type))
    func(ast.literal_eval(args.crypto_profile))


if __name__ == "__main__":
    main()
