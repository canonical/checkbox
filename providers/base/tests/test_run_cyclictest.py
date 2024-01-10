import unittest
from unittest.mock import patch, MagicMock
from run_cyclictest import (run_it,
                            verify_cyclictest_results,
                            lookup_max_latency,
                            main)


class TestCyclictest(unittest.TestCase):

    @patch('subprocess.run')
    def test_run_it(self, mock_run):
        mock_result = MagicMock(stdout="Some output", stderr="", returncode=0)
        mock_run.return_value = mock_result
        result = run_it(86400)
        self.assertTrue(mock_run.called)
        self.assertEqual(result, mock_result)

    @patch('subprocess.run')
    def test_run_it_raise_systemexit(self, mock_run):
        mock_result = MagicMock(stdout="Some output", stderr="", returncode=0)
        mock_run.return_value = mock_result
        mock_run.side_effect = Exception("Wow")
        with self.assertRaises(SystemExit):
            run_it(86400)

    def test_lookup_max_latency(self):
        latency = lookup_max_latency()
        self.assertEqual(latency, 100)

    def test_verify_cyclictest_results_pass(self):
        mock_result = MagicMock(stdout="# Max Latencies: 00010 00020\n\
                                # Histogram Overflows: 00000 00000\n")
        return_code = verify_cyclictest_results(mock_result)
        self.assertEqual(return_code, 0)

    def test_verify_cyclictest_results_fail_latency(self):
        mock_result = MagicMock(stdout="# Max Latencies: 00200 00200\n\
                                # Histogram Overflows: 00000 00000\n")
        return_code = verify_cyclictest_results(mock_result)
        self.assertEqual(return_code, 1)

    def test_verify_cyclictest_results_fail_overflow(self):
        mock_result = MagicMock(stdout="# Max Latencies: 00010 00020\n\
                                # Histogram Overflows: 00001 00000\n")
        return_code = verify_cyclictest_results(mock_result)
        self.assertEqual(return_code, 1)

    @patch('run_cyclictest.run_it')
    @patch('run_cyclictest.verify_cyclictest_results')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main(self, mock_parse_args, mock_verify, mock_run_it):
        mock_parse_args.return_value = MagicMock(duration=86400)
        mock_run_it.return_value = MagicMock(stdout="Some output",
                                             stderr="",
                                             returncode=0)
        mock_verify.return_value = 0
        return_code = main()
        self.assertEqual(return_code, 0)
        mock_verify.return_value = 1
        self.assertEqual(main(), 1)
