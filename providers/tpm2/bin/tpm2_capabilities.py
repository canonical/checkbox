#!/usr/bin/env python3

import argparse
import subprocess

import yaml

# From TCG Algorithm Registry: Definition of TPM2_ALG_ID Constants
# https://trustedcomputinggroup.org/wp-content/uploads/TCG-_Algorithm_Registry_r1p32_pub.pdf
# https://github.com/tpm2-software/tpm2-tools/blob/master/lib/tpm2_alg_util.c

TPM2_ALG_RSA = 0x0001
TPM2_ALG_TDES = 0x0003
TPM2_ALG_SHA1 = 0x0004
TPM2_ALG_HMAC = 0x0005
TPM2_ALG_AES = 0x0006
TPM2_ALG_MGF1 = 0x0007
TPM2_ALG_KEYEDHASH = 0x0008
TPM2_ALG_XOR = 0x000A
TPM2_ALG_SHA256 = 0x000B
TPM2_ALG_SHA384 = 0x000C
TPM2_ALG_SHA512 = 0x000D
TPM2_ALG_NULL = 0x0010
TPM2_ALG_SM3_256 = 0x0012
TPM2_ALG_SM4 = 0x0013
TPM2_ALG_RSASSA = 0x0014
TPM2_ALG_RSAES = 0x0015
TPM2_ALG_RSAPSS = 0x0016
TPM2_ALG_OAEP = 0x0017
TPM2_ALG_ECDSA = 0x0018
TPM2_ALG_ECDH = 0x0019
TPM2_ALG_ECDAA = 0x001A
TPM2_ALG_SM2 = 0x001B
TPM2_ALG_ECSCHNORR = 0x001C
TPM2_ALG_ECMQV = 0x001D
TPM2_ALG_KDF1_SP800_56A = 0x0020
TPM2_ALG_KDF2 = 0x0021
TPM2_ALG_KDF1_SP800_108 = 0x0022
TPM2_ALG_ECC = 0x0023
TPM2_ALG_SYMCIPHER = 0x0025
TPM2_ALG_CAMELLIA = 0x0026
TPM2_ALG_CMAC = 0x003F
TPM2_ALG_CTR = 0x0040
TPM2_ALG_SHA3_256 = 0x0027
TPM2_ALG_SHA3_384 = 0x0028
TPM2_ALG_SHA3_512 = 0x0029
TPM2_ALG_OFB = 0x0041
TPM2_ALG_CBC = 0x0042
TPM2_ALG_CFB = 0x0043
TPM2_ALG_ECB = 0x0044

# Mandatory algorithms
# https://trustedcomputinggroup.org/wp-content/uploads/PC-Client-Specific-Platform-TPM-Profile-for-TPM-2p0-v1p05p_r14_pub.pdf
# Mandatory algorithms for PCRs are defined in Section 4.6

# TPM2_ALG_RSA
# TPM2_ALG_SHA1
# TPM2_ALG_HMAC
# TPM2_ALG_AES
# TPM2_ALG_MGF1
# TPM2_ALG_KEYEDHASH
# TPM2_ALG_XOR
# TPM2_ALG_SHA256
# TPM2_ALG_SHA384
# TPM2_ALG_RSASSA
# TPM2_ALG_RSAES
# TPM2_ALG_RSAPSS
# TPM2_ALG_OAEP
# TPM2_ALG_ECDSA
# TPM2_ALG_ECDH
# TPM2_ALG_ECC
# TPM2_ALG_SYMCIPHER


def build_capabilities():
    """Query the TPM and return a dict of supported capability groups."""
    tpm2_cap = {
        "assymetric": set(),
        "symmetric": set(),
        "hash": set(),
        "keyed_hash": set(),
        "mask_generation_functions": set(),
        "signature_schemes": set(),
        "assymetric_encryption_scheme": set(),
        "key_derivation_functions": set(),
        "aes_modes": set(),
        "pcr_banks": set(),
    }

    try:
        algs_caps = subprocess.check_output(["tpm2_getcap", "algorithms"])
        pcrs_caps = subprocess.check_output(["tpm2_getcap", "pcrs"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit(
            "Please make sure you have installed tpm-tools and tpm chip."
        )

    algs_list = yaml.load(algs_caps, Loader=yaml.FullLoader)
    pcrs_list = yaml.load(pcrs_caps, Loader=yaml.FullLoader)

    for alg, prop in algs_list.items():
        # Assymetric
        if prop["value"] in (TPM2_ALG_RSA, TPM2_ALG_ECC):
            tpm2_cap["assymetric"].add(alg)

        # Symmetric
        if prop["value"] in (
            TPM2_ALG_TDES,
            TPM2_ALG_AES,
            TPM2_ALG_CAMELLIA,
            TPM2_ALG_SYMCIPHER,
        ):
            tpm2_cap["symmetric"].add(alg)

        # Hash
        if prop["value"] in (
            TPM2_ALG_SHA1,
            TPM2_ALG_SHA256,
            TPM2_ALG_SHA384,
            TPM2_ALG_SHA512,
            TPM2_ALG_SM3_256,
            TPM2_ALG_SHA3_256,
            TPM2_ALG_SHA3_384,
            TPM2_ALG_SHA3_512,
        ):
            tpm2_cap["hash"].add(alg)

        # Keyed hash
        if prop["value"] in (
            TPM2_ALG_HMAC,
            TPM2_ALG_XOR,
            TPM2_ALG_CMAC,
            TPM2_ALG_KEYEDHASH,
        ):
            tpm2_cap["keyed_hash"].add(alg)

        # Mask Generation Functions
        if prop["value"] in (TPM2_ALG_MGF1,):
            tpm2_cap["mask_generation_functions"].add(alg)

        # Signature Schemes
        if prop["value"] in (
            TPM2_ALG_RSASSA,
            TPM2_ALG_RSAPSS,
            TPM2_ALG_ECDSA,
            TPM2_ALG_ECDAA,
            TPM2_ALG_ECSCHNORR,
            TPM2_ALG_SM2,
            TPM2_ALG_SM4,
        ):
            tpm2_cap["signature_schemes"].add(alg)

        # Assymetric Encryption Scheme
        if prop["value"] in (TPM2_ALG_OAEP, TPM2_ALG_RSAES, TPM2_ALG_ECDH):
            tpm2_cap["assymetric_encryption_scheme"].add(alg)

        # Key derivation functions
        if prop["value"] in (
            TPM2_ALG_KDF1_SP800_56A,
            TPM2_ALG_KDF2,
            TPM2_ALG_KDF1_SP800_108,
            TPM2_ALG_ECMQV,
        ):
            tpm2_cap["key_derivation_functions"].add(alg)

        # AES Modes
        if prop["value"] in (
            TPM2_ALG_CTR,
            TPM2_ALG_OFB,
            TPM2_ALG_CBC,
            TPM2_ALG_CFB,
            TPM2_ALG_ECB,
        ):
            tpm2_cap["aes_modes"].add(alg)

    if "aes" in tpm2_cap["symmetric"]:
        for alg_type in ("aes", "aes128", "aes192", "aes256"):
            try:
                subprocess.check_call(
                    ["tpm2_testparms", alg_type], stderr=subprocess.DEVNULL
                )
                tpm2_cap["symmetric"].add(alg_type)
            except subprocess.CalledProcessError:
                try:
                    tpm2_cap["symmetric"].remove(alg_type)
                except KeyError:
                    pass

    if "ecc" in tpm2_cap["assymetric"]:
        for alg_type in (
            "ecc",
            "ecc192",
            "ecc224",
            "ecc256",
            "ecc384",
            "ecc521",
        ):
            try:
                subprocess.check_call(
                    ["tpm2_testparms", alg_type], stderr=subprocess.DEVNULL
                )
                tpm2_cap["assymetric"].add(alg_type)
            except subprocess.CalledProcessError:
                try:
                    tpm2_cap["assymetric"].remove(alg_type)
                except KeyError:
                    pass

    if "rsa" in tpm2_cap["assymetric"]:
        for alg_type in ("rsa", "rsa1024", "rsa2048", "rsa4096"):
            try:
                subprocess.check_call(
                    ["tpm2_testparms", alg_type], stderr=subprocess.DEVNULL
                )
                tpm2_cap["assymetric"].add(alg_type)
            except subprocess.CalledProcessError:
                try:
                    tpm2_cap["assymetric"].remove(alg_type)
                except KeyError:
                    pass

    for pcr in pcrs_list["selected-pcrs"]:
        for pcr_bank, pcr_ids in pcr.items():
            if set(range(24)).issubset(set(pcr_ids)):
                tpm2_cap["pcr_banks"].add(pcr_bank)

    return tpm2_cap


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Query TPM2 capabilities. With --resource, print all "
            "capabilities as a Checkbox resource. With both CAPABILITY "
            "and VALUE, check whether VALUE is supported for CAPABILITY."
        )
    )
    parser.add_argument(
        "--resource",
        action="store_true",
        help="Print all capabilities as a Checkbox resource unit",
    )
    parser.add_argument(
        "--resource-pcr-banks",
        action="store_true",
        help=(
            "Print each available PCR bank as a separate Checkbox "
            "resource record"
        ),
    )
    parser.add_argument(
        "capability",
        nargs="?",
        help=(
            "Capability group to query "
            "(e.g. hash, assymetric, pcr_banks)"
        ),
    )
    parser.add_argument(
        "value",
        nargs="?",
        help="Value to check within that capability (e.g. sha256, rsa)",
    )
    args = parser.parse_args(argv)

    modes = [args.resource, args.resource_pcr_banks]
    if any(modes):
        if sum(modes) > 1:
            parser.error(
                "--resource and --resource-pcr-banks are mutually exclusive"
            )
        if args.capability is not None or args.value is not None:
            parser.error(
                "resource flags cannot be combined with capability/value"
            )
    else:
        if args.capability is None or args.value is None:
            parser.error(
                "use --resource, --resource-pcr-banks, or "
                "[capability] [supported-values] to test"
            )

    return args


def main(argv=None):
    args = parse_args(argv)
    tpm2_cap = build_capabilities()

    if args.resource:
        # print as resource unit
        for k, v in tpm2_cap.items():
            print("{}: {}".format(k, " ".join(sorted(v))))
        return

    if args.resource_pcr_banks:
        # print each PCR bank as a separate resource record
        banks = sorted(tpm2_cap["pcr_banks"])
        print(
            "\n\n".join("pcr_bank: {}".format(bank) for bank in banks)
        )
        return

    try:
        if args.value in tpm2_cap[args.capability]:
            print("{} supports {}".format(args.capability, args.value))
        else:
            raise SystemExit(
                "{} does not support {}".format(args.capability, args.value)
            )
    except KeyError:
        raise SystemExit('Unknown capability "{}"'.format(args.capability))


if __name__ == "__main__":
    main()
