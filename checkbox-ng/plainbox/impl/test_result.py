# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_result
=========================

Test definitions for plainbox.impl.result module
"""
import json

from unittest import TestCase

from plainbox.impl.result import JobResult
from plainbox.impl.testing_utils import make_job
from plainbox.impl.session import SessionStateEncoder


class JobResultTests(TestCase):

    def setUp(self):
        self.job = make_job("A")

    def test_smoke(self):
        result = JobResult({'job': self.job})
        self.assertEqual(str(result), "A: None")
        self.assertEqual(repr(result), (
            "<JobResult job:<JobDefinition name:'A' plugin:'dummy'>"
            " outcome:None>"))
        self.assertIs(result.job, self.job)
        self.assertIsNone(result.outcome)
        self.assertIsNone(result.comments)
        self.assertEqual(result.io_log, ())
        self.assertIsNone(result.return_code)

    def test_everything(self):
        result = JobResult({
            'job': self.job,
            'outcome': JobResult.OUTCOME_PASS,
            'comments': "it said blah",
            'io_log': ((0, 'stdout', b'blah\n'),),
            'return_code': 0
        })
        self.assertEqual(str(result), "A: pass")
        self.assertEqual(repr(result), (
            "<JobResult job:<JobDefinition name:'A' plugin:'dummy'>"
            " outcome:'pass'>"))
        self.assertIs(result.job, self.job)
        self.assertEqual(result.outcome, JobResult.OUTCOME_PASS)
        self.assertEqual(result.comments, "it said blah")
        self.assertEqual(result.io_log, ((0, 'stdout', b'blah\n'),))
        self.assertEqual(result.return_code, 0)

    def test_encode(self):
        result = JobResult({
            'job': self.job,
            'outcome': JobResult.OUTCOME_PASS,
            'comments': "it said blah",
            'io_log': ((0, 'stdout', 'blah\n'),),
            'return_code': 0
        })
        result_enc = result._get_persistance_subset()
        self.assertEqual(result_enc['data']['job'], result.job)
        self.assertEqual(result_enc['data']['outcome'], result.outcome)
        self.assertEqual(result_enc['data']['comments'], result.comments)
        self.assertEqual(result_enc['data']['return_code'], result.return_code)
        with self.assertRaises(KeyError):
            result_enc['io_log']

    def test_decode(self):
        raw_json = """{
                "_class_id": "JOB_RESULT",
                "data": {
                    "comments": null,
                    "job": {
                        "_class_id": "JOB_DEFINITION",
                        "data": {
                            "name": "__audio__",
                            "plugin": "local"
                        }
                    },
                    "outcome": "pass",
                    "return_code": 0
                }
            }"""
        result_dec = json.loads(raw_json, object_hook=SessionStateEncoder().dict_to_object)
        self.assertIsInstance(result_dec, JobResult)
        self.assertEqual(result_dec.job.name, "__audio__")
        self.assertEqual(result_dec.outcome, JobResult.OUTCOME_PASS)
        self.assertIsNone(result_dec.comments)
        self.assertEqual(result_dec.io_log, ())
        self.assertEqual(result_dec.return_code, 0)
