#!/usr/bin/env python3

import yaml
import subprocess
import sys


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

TPM2_CAP = {
    'assymetric': set(),
    'symmetric': set(),
    'hash': set(),
    'keyed_hash': set(),
    'mask_generation_functions': set(),
    'signature_schemes': set(),
    'assymetric_encryption_scheme': set(),
    'key_derivation_functions': set(),
    'aes_modes': set(),
    'pcr_banks': set(),
}

try:
    algs_caps = subprocess.check_output(['tpm2_getcap', 'algorithms'])
    pcrs_caps = subprocess.check_output(['tpm2_getcap', 'pcrs'])
except subprocess.CalledProcessError:
    raise SystemExit

algs_list = yaml.load(algs_caps, Loader=yaml.FullLoader)
pcrs_list = yaml.load(pcrs_caps, Loader=yaml.FullLoader)

for alg, prop in algs_list.items():
    # Assymetric
    if prop['value'] in (TPM2_ALG_RSA, TPM2_ALG_ECC):
        TPM2_CAP['assymetric'].add(alg)

    # Symmetric
    if prop['value'] in (
        TPM2_ALG_TDES, TPM2_ALG_AES, TPM2_ALG_CAMELLIA, TPM2_ALG_SYMCIPHER
    ):
        TPM2_CAP['symmetric'].add(alg)

    # Hash
    if prop['value'] in (
        TPM2_ALG_SHA1, TPM2_ALG_SHA256, TPM2_ALG_SHA384, TPM2_ALG_SHA512,
        TPM2_ALG_SM3_256, TPM2_ALG_SHA3_256, TPM2_ALG_SHA3_384,
        TPM2_ALG_SHA3_512
    ):
        TPM2_CAP['hash'].add(alg)

    # Keyed hash
    if prop['value'] in (
        TPM2_ALG_HMAC, TPM2_ALG_XOR, TPM2_ALG_CMAC, TPM2_ALG_KEYEDHASH
    ):
        TPM2_CAP['keyed_hash'].add(alg)

    # Mask Generation Functions
    if prop['value'] in (TPM2_ALG_MGF1,):
        TPM2_CAP['mask_generation_functions'].add(alg)

    # Signature Schemes
    if prop['value'] in (
        TPM2_ALG_RSASSA, TPM2_ALG_RSAPSS, TPM2_ALG_ECDSA, TPM2_ALG_ECDAA,
        TPM2_ALG_ECSCHNORR, TPM2_ALG_SM2, TPM2_ALG_SM4
    ):
        TPM2_CAP['signature_schemes'].add(alg)

    # Assymetric Encryption Scheme
    if prop['value'] in (TPM2_ALG_OAEP, TPM2_ALG_RSAES, TPM2_ALG_ECDH):
        TPM2_CAP['assymetric_encryption_scheme'].add(alg)

    # Key derivation functions
    if prop['value'] in (
        TPM2_ALG_KDF1_SP800_56A, TPM2_ALG_KDF2, TPM2_ALG_KDF1_SP800_108,
        TPM2_ALG_ECMQV
    ):
        TPM2_CAP['key_derivation_functions'].add(alg)

    # AES Modes
    if prop['value'] in (
        TPM2_ALG_CTR, TPM2_ALG_OFB, TPM2_ALG_CBC, TPM2_ALG_CFB, TPM2_ALG_ECB
    ):
        TPM2_CAP['aes_modes'].add(alg)

if 'aes' in TPM2_CAP['symmetric']:
    for alg_type in ('aes', 'aes128', 'aes192', 'aes256'):
        try:
            subprocess.check_call(
                ['tpm2_testparms', alg_type], stderr=subprocess.DEVNULL)
            TPM2_CAP['symmetric'].add(alg_type)
        except subprocess.CalledProcessError:
            try:
                TPM2_CAP['symmetric'].remove(alg_type)
            except KeyError:
                pass

if 'ecc' in TPM2_CAP['assymetric']:
    for alg_type in ('ecc', 'ecc192', 'ecc224', 'ecc256', 'ecc384', 'ecc521'):
        try:
            subprocess.check_call(
                ['tpm2_testparms', alg_type], stderr=subprocess.DEVNULL)
            TPM2_CAP['assymetric'].add(alg_type)
        except subprocess.CalledProcessError:
            try:
                TPM2_CAP['assymetric'].remove(alg_type)
            except KeyError:
                pass

if 'rsa' in TPM2_CAP['assymetric']:
    for alg_type in ('rsa', 'rsa1024', 'rsa2048', 'rsa4096'):
        try:
            subprocess.check_call(
                ['tpm2_testparms', alg_type], stderr=subprocess.DEVNULL)
            TPM2_CAP['assymetric'].add(alg_type)
        except subprocess.CalledProcessError:
            try:
                TPM2_CAP['assymetric'].remove(alg_type)
            except KeyError:
                pass

for pcr in pcrs_list['selected-pcrs']:
    for pcr_bank, pcr_ids in pcr.items():
        if set(range(24)).issubset(set(pcr_ids)):
            TPM2_CAP['pcr_banks'].add(pcr_bank)

if len(sys.argv) == 1:
    # with no args print as resource unit
    for k, v in TPM2_CAP.items():
        print("{}: {}".format(k, ' '.join(sorted(v))))
    sys.exit(0)

if len(sys.argv) != 3:
    raise SystemExit('ERROR: use [capability] [supported-values] to test')

try:
    if sys.argv[2] in TPM2_CAP[sys.argv[1]]:
        print('{} supports {}'.format(*sys.argv[-2:]))
    else:
        raise SystemExit('{} does not support {}'.format(*sys.argv[-2:]))
except KeyError:
    raise SystemExit('Unknown capability "{}"'.format(sys.argv[1]))
