#!/usr/bin/python3

import unittest
import os

from run_ffmpeg import has_profile_and_entrypoint, get_all_trace_contents


class TestRunFFmpeg(unittest.TestCase):
    def test_has_profile_and_entrypoint(self):

        cases = {
            "1 entry + prof": {
                "entrypoint": "1",
                "profile": "3",
                "entry_in_text": "1",
                "prof_in_text": "3",
                "expected_result": True,
            },
            "Multi entry + prof": {
                "entrypoint": "1,2,3,4,5",
                "profile": "3,7,11",
                "entry_in_text": "4",
                "prof_in_text": "7",
                "expected_result": True,
            },
            "Multi entry + 1 prof": {
                "entrypoint": "1,2,3,4,5",
                "profile": "11",
                "entry_in_text": "4",
                "prof_in_text": "11",
                "expected_result": True,
            },
            "1 entry + multi prof": {
                "entrypoint": "1",
                "profile": "3,7,11",
                "entry_in_text": "1",
                "prof_in_text": "3",
                "expected_result": True,
            },
            "multi entry + 1 prof": {
                "entrypoint": "1,2,3",
                "profile": "3",
                "entry_in_text": "3",
                "prof_in_text": "3",
                "expected_result": True,
            },
            "Wrong profile": {
                "entrypoint": "1",
                "profile": "11",
                "entry_in_text": "1",
                "prof_in_text": "7",
                "expected_result": False,
            },
            "No libva.trace text": {
                "entrypoint": "1",
                "profile": "11",
                "expected_result": False,
            },
        }

        all_tests_pass = True
        for case in cases:
            if "prof_in_text" in cases[case]:
                # sub in our text values for profile and entrypoint
                prof_in_text = cases[case]["prof_in_text"]
                entry_in_text = cases[case]["entry_in_text"]
                text = f"""
                This is a multiline string
                Which should contain the needed substrings
                entrypoint = {entry_in_text}
                to confirm hardware encode/decode
                profile = {prof_in_text}
                for single entrypoints and profiles
                """
            else:
                # The value returned by get_all_trace_contents if no traces
                text = ""

            profile = cases[case]["profile"]
            entrypoint = cases[case]["entrypoint"]
            result = has_profile_and_entrypoint(text, profile, entrypoint)

            expected_result = cases[case]["expected_result"]
            if result is expected_result:
                print(f"PASS: {case}")
            else:
                all_tests_pass = False
                print(f"FAIL: {case}")

        self.assertTrue(all_tests_pass)

    def test_get_all_trace_contents(self):
        test_file_num = 3
        base_phrase = "I test therefore I am"
        base_filename = "fake_libva.trace"

        control = []
        for i in range(test_file_num):
            filename = base_filename + f"{i}"
            phrase = base_phrase + f"{i}"
            with open(filename, "w") as f:
                f.write(phrase)
                # The newline is added to separate different traces
                control.append(phrase + "\n")

        # Test the expected lines are in the trace contents string
        result = get_all_trace_contents("./", trace_filename=base_filename)
        for line in control:
            self.assertIn(line, result)

        # Ensure duplicates are not added
        filelines = []
        for line in result.splitlines():
            filelines.append(line + "\n")

        self.assertEqual(set(filelines), set(control))

        # Remove test files
        for i in range(test_file_num):
            filename = base_filename + f"{i}"
            os.remove(filename)

        result = get_all_trace_contents("./", trace_filename=base_filename)

        # No trace files should return a blank string
        self.assertEqual(result, "")
