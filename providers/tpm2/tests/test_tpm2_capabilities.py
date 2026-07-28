import io
import os
import subprocess
import unittest
from unittest.mock import patch

import tpm2_capabilities

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_DATA = os.path.join(HERE, "test_data")

with open(os.path.join(TEST_DATA, "tpm2_getcap_algorithms.txt"), "rb") as _f:
    ALGS_SAMPLE = _f.read()
with open(os.path.join(TEST_DATA, "tpm2_getcap_pcrs.txt"), "rb") as _f:
    PCRS_SAMPLE = _f.read()


def _fake_check_output(cmd, *args, **kwargs):
    if cmd == ["tpm2_getcap", "algorithms"]:
        return ALGS_SAMPLE
    if cmd == ["tpm2_getcap", "pcrs"]:
        return PCRS_SAMPLE
    raise AssertionError("unexpected command: {}".format(cmd))


def _fake_check_call_all_ok(cmd, *args, **kwargs):
    # tpm2_testparms: pretend every requested variant is supported
    return 0


def _fake_check_call_all_fail(cmd, *args, **kwargs):
    raise subprocess.CalledProcessError(1, cmd)


class TestBuildCapabilities(unittest.TestCase):
    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_ok,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_classification_from_sample(self, _out, _call):
        caps = tpm2_capabilities.build_capabilities()

        # Assymetric: rsa + ecc from sample, plus variants added by
        # check_call succeeding for every tpm2_testparms probe.
        self.assertIn("rsa", caps["assymetric"])
        self.assertIn("ecc", caps["assymetric"])
        self.assertIn("rsa2048", caps["assymetric"])
        self.assertIn("ecc256", caps["assymetric"])

        # Symmetric: aes from sample; aes variants added.
        self.assertIn("aes", caps["symmetric"])
        self.assertIn("aes128", caps["symmetric"])

        # Hash algorithms in the sample.
        self.assertEqual(caps["hash"], {"sha1", "sha256", "sha384"})

        # Keyed hash.
        self.assertEqual(
            caps["keyed_hash"], {"hmac", "xor", "keyedhash", "cmac"}
        )

        # Mask generation functions.
        self.assertEqual(caps["mask_generation_functions"], {"mgf1"})

        # Signature schemes present in sample.
        self.assertEqual(
            caps["signature_schemes"],
            {"rsassa", "rsapss", "ecdsa", "ecdaa", "ecschnorr"},
        )

        # Asymmetric encryption schemes.
        self.assertEqual(
            caps["assymetric_encryption_scheme"],
            {"oaep", "rsaes", "ecdh"},
        )

        # Key derivation functions.
        self.assertEqual(
            caps["key_derivation_functions"],
            {"kdf1_sp800_56a", "kdf2", "kdf1_sp800_108"},
        )

        # AES modes.
        self.assertEqual(
            caps["aes_modes"], {"ctr", "ofb", "cbc", "cfb", "ecb"}
        )

        # PCR banks: only sha256 has 0..23 in the sample.
        self.assertEqual(caps["pcr_banks"], {"sha256"})

    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_fail,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_variants_removed_when_testparms_fails(self, _out, _call):
        caps = tpm2_capabilities.build_capabilities()
        # When tpm2_testparms fails for every probed variant, none of the
        # variants are added to the sets. The base entries themselves are
        # also removed by the existing removal logic.
        for variant in ("rsa", "rsa1024", "rsa2048", "rsa4096"):
            self.assertNotIn(variant, caps["assymetric"])
        for variant in ("ecc", "ecc192", "ecc256", "ecc384"):
            self.assertNotIn(variant, caps["assymetric"])
        for variant in ("aes", "aes128", "aes192", "aes256"):
            self.assertNotIn(variant, caps["symmetric"])

    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=FileNotFoundError,
    )
    def test_missing_tpm2_tools_raises(self, _out):
        with self.assertRaises(SystemExit):
            tpm2_capabilities.build_capabilities()


class TestParseArgs(unittest.TestCase):
    def test_resource_flag(self):
        args = tpm2_capabilities.parse_args(["--resource"])
        self.assertTrue(args.resource)
        self.assertFalse(args.resource_pcr_banks)

    def test_resource_pcr_banks_flag(self):
        args = tpm2_capabilities.parse_args(["--resource-pcr-banks"])
        self.assertTrue(args.resource_pcr_banks)

    def test_positional_pair(self):
        args = tpm2_capabilities.parse_args(["hash", "sha256"])
        self.assertEqual(args.capability, "hash")
        self.assertEqual(args.value, "sha256")

    def test_no_args_errors(self):
        with self.assertRaises(SystemExit):
            tpm2_capabilities.parse_args([])

    def test_single_positional_errors(self):
        with self.assertRaises(SystemExit):
            tpm2_capabilities.parse_args(["hash"])

    def test_resource_with_positional_errors(self):
        with self.assertRaises(SystemExit):
            tpm2_capabilities.parse_args(["--resource", "hash", "sha256"])

    def test_both_resource_flags_error(self):
        with self.assertRaises(SystemExit):
            tpm2_capabilities.parse_args(
                ["--resource", "--resource-pcr-banks"]
            )


class TestMain(unittest.TestCase):
    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_ok,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_resource_output_contains_all_keys(self, _out, _call):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            tpm2_capabilities.main(["--resource"])
        output = buf.getvalue()
        for key in (
            "assymetric",
            "symmetric",
            "hash",
            "keyed_hash",
            "mask_generation_functions",
            "signature_schemes",
            "assymetric_encryption_scheme",
            "key_derivation_functions",
            "aes_modes",
            "pcr_banks",
        ):
            self.assertIn("{}:".format(key), output)
        self.assertIn("pcr_banks: sha256", output)

    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_ok,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_resource_pcr_banks_output(self, _out, _call):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            tpm2_capabilities.main(["--resource-pcr-banks"])
        # Only sha256 has 24 PCRs in the sample.
        self.assertEqual(buf.getvalue().strip(), "pcr_bank: sha256")

    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_ok,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_check_supported_ok(self, _out, _call):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            tpm2_capabilities.main(["hash", "sha256"])
        self.assertIn("hash supports sha256", buf.getvalue())

    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_ok,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_check_unsupported_exits(self, _out, _call):
        with self.assertRaises(SystemExit) as ctx:
            tpm2_capabilities.main(["hash", "sha512"])
        self.assertIn("does not support", str(ctx.exception))

    @patch(
        "tpm2_capabilities.subprocess.check_call",
        side_effect=_fake_check_call_all_ok,
    )
    @patch(
        "tpm2_capabilities.subprocess.check_output",
        side_effect=_fake_check_output,
    )
    def test_check_unknown_capability_exits(self, _out, _call):
        with self.assertRaises(SystemExit) as ctx:
            tpm2_capabilities.main(["nope", "sha256"])
        self.assertIn("Unknown capability", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
