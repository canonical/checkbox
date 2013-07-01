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
import io
import json

from tempfile import TemporaryDirectory
from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import IOLogRecordWriter
from plainbox.impl.result import IOLogRecordReader
from plainbox.impl.result import JobResult
from plainbox.impl.testing_utils import make_io_log, make_job
from plainbox.impl.session import SessionStateEncoder


class JobResultTests(TestCase):

    def test_smoke(self):
        result = JobResult({})
        self.assertEqual(str(result), "None")
        self.assertEqual(repr(result), "<JobResult outcome:None>")
        self.assertIsNone(result.outcome)
        self.assertIsNone(result.comments)
        self.assertEqual(result.io_log, ())
        self.assertIsNone(result.return_code)

    def test_everything(self):
        with TemporaryDirectory() as scratch_dir:
            result = JobResult({
                'outcome': JobResult.OUTCOME_PASS,
                'comments': "it said blah",
                'io_log': make_io_log(((0, 'stdout', b'blah\n'),),
                                      scratch_dir),
                'return_code': 0
            })
            self.assertEqual(str(result), "pass")
            self.assertEqual(repr(result), (
                "<JobResult outcome:'pass'>"))
            self.assertEqual(result.outcome, JobResult.OUTCOME_PASS)
            self.assertEqual(result.comments, "it said blah")
            self.assertEqual(result.io_log, ((0, 'stdout', b'blah\n'),))
            self.assertEqual(result.return_code, 0)

    def test_encode(self):
        result = JobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'comments': "it said blah",
            'io_log': ((0, 'stdout', 'blah\n'),),
            'return_code': 0
        })
        result_enc = result._get_persistance_subset()
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
                    "outcome": "pass",
                    "return_code": 0
                }
            }"""
        result_dec = json.loads(
            raw_json, object_hook=SessionStateEncoder().dict_to_object)
        self.assertIsInstance(result_dec, IJobResult)
        self.assertEqual(result_dec.outcome, IJobResult.OUTCOME_PASS)
        self.assertIsNone(result_dec.comments)
        self.assertEqual(result_dec.io_log, ())
        self.assertEqual(result_dec.return_code, 0)


class IOLogRecordWriterTests(TestCase):

    _RECORD = IOLogRecord(0.123, 'stdout', b'some\ndata')
    _TEXT = '[0.123,"stdout","c29tZQpkYXRh"]\n'

    def test_smoke_write(self):
        stream = io.StringIO()
        writer = IOLogRecordWriter(stream)
        writer.write_record(self._RECORD)
        self.assertEqual(stream.getvalue(), self._TEXT)
        writer.close()
        with self.assertRaises(ValueError):
            stream.getvalue()

    def test_smoke_read(self):
        stream = io.StringIO(self._TEXT)
        reader = IOLogRecordReader(stream)
        record1 = reader.read_record()
        self.assertEqual(record1, self._RECORD)
        record2 = reader.read_record()
        self.assertEqual(record2, None)
        reader.close()
        with self.assertRaises(ValueError):
            stream.getvalue()

    def test_iter_read(self):
        stream = io.StringIO(self._TEXT)
        reader = IOLogRecordReader(stream)
        record_list = list(reader)
        self.assertEqual(record_list, [self._RECORD])
