# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
plainbox.impl.test_ctrl
=======================

Test definitions for plainbox.impl.ctrl module
"""

from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.ctrl import CheckBoxSessionStateController
from plainbox.impl.ctrl import gen_rfc822_records_from_io_log
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.job import JobDefinition
from plainbox.impl.job import JobOutputTextSource
from plainbox.impl.resource import Resource
from plainbox.impl.resource import ResourceExpression
from plainbox.impl.secure.rfc822 import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.session import JobReadinessInhibitor
from plainbox.impl.session import SessionState
from plainbox.vendor import mock


class CheckBoxSessionStateControllerTests(TestCase):

    def setUp(self):
        self.ctrl = CheckBoxSessionStateController()

    def test_get_dependency_set(self):
        # Job with no dependencies
        job_a = JobDefinition({})
        self.assertEqual(
            self.ctrl.get_dependency_set(job_a), set())
        # Job with direct dependencies
        job_b = JobDefinition({
            'depends': 'j1, j2'
        })
        self.assertEqual(
            self.ctrl.get_dependency_set(job_b),
            {('direct', 'j1'), ('direct', 'j2')})
        # Job with resouce dependencies
        job_c = JobDefinition({
            'requires': 'j3.attr == 1'
        })
        self.assertEqual(
            self.ctrl.get_dependency_set(job_c),
            {('resource', 'j3')})
        # Job with both direct and resource dependencies
        job_d = JobDefinition({
            'depends': 'j4',
            'requires': 'j5.attr == 1'
        })
        self.assertEqual(
            self.ctrl.get_dependency_set(job_d),
            {('direct', 'j4'), ('resource', 'j5')})
        # Job with both direct and resource dependencies
        # on the same job (j6)
        job_e = JobDefinition({
            'depends': 'j6',
            'requires': 'j6.attr == 1'
        })
        self.assertEqual(
            self.ctrl.get_dependency_set(job_e),
            {('direct', 'j6'), ('resource', 'j6')})

    def test_get_inhibitor_list_PENDING_RESOURCE(self):
        # verify that jobs that require a resource that hasn't been
        # invoked yet produce the PENDING_RESOURCE inhibitor
        j1 = JobDefinition({
            'name': 'j1',
            'requires': 'j2.attr == "ok"'
        })
        j2 = JobDefinition({
            'name': 'j2'
        })
        session_state = mock.MagicMock(spec=SessionState)
        session_state.job_state_map['j2'].job = j2
        session_state.resource_map = {}
        self.assertEqual(
            self.ctrl.get_inhibitor_list(session_state, j1),
            [JobReadinessInhibitor(
                JobReadinessInhibitor.PENDING_RESOURCE,
                j2, ResourceExpression('j2.attr == "ok"'))])

    def test_get_inhibitor_list_FAILED_RESOURCE(self):
        # verify that jobs that require a resource that has been
        # invoked and produced resources but the expression dones't
        # evaluate to True produce the FAILED_RESOURCE inhibitor
        j1 = JobDefinition({
            'name': 'j1',
            'requires': 'j2.attr == "ok"'
        })
        j2 = JobDefinition({
            'name': 'j2'
        })
        session_state = mock.MagicMock(spec=SessionState)
        session_state.job_state_map['j2'].job = j2
        session_state.resource_map = {
            'j2': [Resource({'attr': 'not-ok'})]
        }
        self.assertEqual(
            self.ctrl.get_inhibitor_list(session_state, j1),
            [JobReadinessInhibitor(
                JobReadinessInhibitor.FAILED_RESOURCE,
                j2, ResourceExpression('j2.attr == "ok"'))])

    def test_get_inhibitor_list_good_resource(self):
        # verify that jobs that require a resource that has been invoked and
        # produced resources for which the expression evaluates to True don't
        # have any inhibitors
        j1 = JobDefinition({
            'name': 'j1',
            'requires': 'j2.attr == "ok"'
        })
        j2 = JobDefinition({
            'name': 'j2'
        })
        session_state = mock.MagicMock(spec=SessionState)
        session_state.resource_map = {
            'j2': [Resource({'attr': 'ok'})]
        }
        session_state.job_state_map['j2'].job = j2
        self.assertEqual(
            self.ctrl.get_inhibitor_list(session_state, j1), [])

    def test_get_inhibitor_list_PENDING_DEP(self):
        # verify that jobs that depend on another job that hasn't
        # been invoked yet produce the PENDING_DEP inhibitor
        j1 = JobDefinition({
            'name': 'j1',
            'depends': 'j2'
        })
        j2 = JobDefinition({
            'name': 'j2'
        })
        session_state = mock.MagicMock(spec=SessionState)
        jsm_j2 = session_state.job_state_map['j2']
        jsm_j2.job = j2
        jsm_j2.result.outcome = IJobResult.OUTCOME_NONE
        self.assertEqual(
            self.ctrl.get_inhibitor_list(session_state, j1),
            [JobReadinessInhibitor(
                JobReadinessInhibitor.PENDING_DEP, j2, None)])

    def test_get_inhibitor_list_FAILED_DEP(self):
        # verify that jobs that depend on another job that ran but
        # didn't result in OUTCOME_PASS produce the FAILED_DEP
        # inhibitor.
        j1 = JobDefinition({
            'name': 'j1',
            'depends': 'j2'
        })
        j2 = JobDefinition({
            'name': 'j2'
        })
        session_state = mock.MagicMock(spec=SessionState)
        jsm_j2 = session_state.job_state_map['j2']
        jsm_j2.job = j2
        jsm_j2.result.outcome = IJobResult.OUTCOME_FAIL
        self.assertEqual(
            self.ctrl.get_inhibitor_list(session_state, j1),
            [JobReadinessInhibitor(
                JobReadinessInhibitor.FAILED_DEP, j2, None)])

    def test_get_inhibitor_list_good_dep(self):
        # verify that jobs that depend on another job that ran and has outcome
        # equal to OUTCOME_PASS don't have any inhibitors
        j1 = JobDefinition({
            'name': 'j1',
            'depends': 'j2'
        })
        j2 = JobDefinition({
            'name': 'j2'
        })
        session_state = mock.MagicMock(spec=SessionState)
        jsm_j2 = session_state.job_state_map['j2']
        jsm_j2.job = j2
        jsm_j2.result.outcome = IJobResult.OUTCOME_PASS
        self.assertEqual(
            self.ctrl.get_inhibitor_list(session_state, j1), [])

    def test_observe_result__normal(self):
        job = mock.Mock(spec=JobDefinition)
        result = mock.Mock(spec=IJobResult)
        session_state = mock.MagicMock(spec=SessionState)
        self.ctrl.observe_result(session_state, job, result)
        # Ensure that result got stored
        self.assertIs(
            session_state.job_state_map[job.name].result, result)
        # Ensure that signals got fired
        session_state.on_job_state_map_changed.assert_called_once()
        session_state.on_job_result_changed.assert_called_once_with(
            job, result)

    def test_observe_result__resource(self):
        job = mock.Mock(spec=JobDefinition, plugin='resource')
        result = mock.Mock(spec=IJobResult)
        result.get_io_log.return_value = [
            (0, 'stdout', b'attr: value1\n'),
            (0, 'stdout', b'\n'),
            (0, 'stdout', b'attr: value2\n')]
        session_state = mock.MagicMock(spec=SessionState)
        self.ctrl.observe_result(session_state, job, result)
        # Ensure that result got stored
        self.assertIs(
            session_state.job_state_map[job.name].result, result)
        # Ensure that signals got fired
        session_state.on_job_state_map_changed.assert_called_once_with()
        session_state.on_job_result_changed.assert_called_once_with(
            job, result)
        # Ensure that new resource was defined
        session_state.set_resource_list.assert_called_once_with(
            job.name, [
                Resource({'attr': 'value1'}), Resource({'attr': 'value2'})])

    @mock.patch('plainbox.impl.ctrl.logger')
    def test_observe_result__broken_resource(self, mock_logger):
        job = mock.Mock(spec=JobDefinition, plugin='resource')
        result = mock.Mock(spec=IJobResult)
        result.get_io_log.return_value = [(0, 'stdout', b'barf\n')]
        session_state = mock.MagicMock(spec=SessionState)
        self.ctrl.observe_result(session_state, job, result)
        # Ensure that result got stored
        self.assertIs(
            session_state.job_state_map[job.name].result, result)
        # Ensure that signals got fired
        session_state.on_job_state_map_changed.assert_called_once_with()
        session_state.on_job_result_changed.assert_called_once_with(
            job, result)
        # Ensure that a warning was logged
        mock_logger.warning.assert_called_once_with(
            "local script %s returned invalid RFC822 data: %s",
            job, RFC822SyntaxError(
                None, 1, "Unexpected non-empty line"))

    @mock.patch('plainbox.impl.ctrl.gen_rfc822_records_from_io_log')
    def test_observe_result__local_typical(self, mock_gen):
        """
        verify side effects of using observe_result() that would define a new
        job
        """
        # Create a session that knows about no jobs yet
        # and happily adds jobs when add_job() gets called
        session_state = mock.MagicMock(spec=SessionState)
        session_state.add_job.side_effect = (
            lambda new_job, recompute: new_job)
        # Create a job of which result we'll be observing
        job = mock.Mock(spec=JobDefinition, name='job', plugin='local')
        # Create a result for the job we'll be observing
        result = mock.Mock(spec=IJobResult, name='result')
        # Mock what rfc822 parser returns
        mock_gen.return_value = [mock.Mock(spec=RFC822Record, name='record')]
        # Pretend that we are observing a 'result' of 'job'
        self.ctrl.observe_result(session_state, job, result)
        # Ensure that result got stored
        self.assertIs(
            session_state.job_state_map[job.name].result, result)
        # Ensure that new job was defined
        session_state.add_job.assert_called_once_with(
            job.create_child_job_from_record(), recompute=False)
        # Ensure that we didn't try to change the origin of the new job
        self.assertFalse(
            job.create_child_job_from_record().update_origin.called)
        # Ensure that signals got fired
        session_state.on_job_state_map_changed.assert_called_once_with()
        session_state.on_job_result_changed.assert_called_once_with(
            job, result)

    @mock.patch('plainbox.impl.ctrl.gen_rfc822_records_from_io_log')
    @mock.patch('plainbox.impl.ctrl.logger')
    def test_observe_result__local_imperfect_clash(
            self, mock_logger, mock_gen):
        """
        verify side effects of using observe_result() that would define a
        already existing job with the non-identical definition.

        We basically hope to see the old job being there intact and a warning
        to be logged.
        """
        # Create a session that already knows about 'existing_job'
        # and raises a DependencyDuplicateError when add_job() gets called.
        existing_job = mock.Mock(spec=JobDefinition, name='existing_job')
        existing_job.name = 'generated'
        clashing_job = mock.Mock(spec=JobDefinition, name='existing_job')
        clashing_job.name = 'generated'
        session_state = mock.MagicMock(spec=SessionState, name='session_state')
        session_state.add_job.side_effect = DependencyDuplicateError(
            existing_job, clashing_job)
        # Create a job of which result we'll be observing
        job = mock.Mock(spec=JobDefinition, name='job', plugin='local')
        # Have job return clashing_job when create_child_job_record() is called
        job.create_child_job_from_record.return_value = clashing_job
        # Create a result for the job we'll be observing
        result = mock.Mock(spec=IJobResult, name='result')
        # Mock what rfc822 parser returns
        mock_gen.return_value = [mock.Mock(spec=RFC822Record, name='record')]
        # Pretend that we are observing a 'result' of 'job'
        self.ctrl.observe_result(session_state, job, result)
        # Ensure that result got stored
        self.assertIs(
            session_state.job_state_map[job.name].result, result)
        # Ensure that we tried to define a new job by calling add_job() with
        # the clashing_job as argument
        session_state.add_job.assert_called_once_with(
            clashing_job, recompute=False)
        # Ensure that existing job origin was *not* updated
        self.assertFalse(existing_job.update_origin.called)
        # Ensure that signals got fired
        session_state.on_job_state_map_changed.assert_called_once_with()
        session_state.on_job_result_changed.assert_called_once_with(
            job, result)
        # Ensure that a warning was logged
        mock_logger.warning.assert_called_once_with(
            ("Local job %s produced job %r that collides with"
             " an existing job %s (from %s), the new job was"
             " discarded"),
            job, clashing_job, existing_job, existing_job.origin)

    @mock.patch('plainbox.impl.ctrl.gen_rfc822_records_from_io_log')
    def test_observe_result__local_perfect_clash(self, mock_gen):
        """
        verify side effects of using observe_result() that would define a
        already existing job with the exactly identical definition.

        We basically hope to see the old job being there but the origin field
        should be updated to reflect the new association between 'existing_job'
        and 'job'
        """
        # Create a session that already knows about 'existing_job'
        # and returns existing_job when add_job() gets called.
        existing_job = mock.Mock(spec=JobDefinition, name='existing_job')
        existing_job.name = 'generated'
        session_state = mock.MagicMock(spec=SessionState, name='session_state')
        session_state.add_job.side_effect = (
            lambda new_job, recompute: existing_job)
        # Create a job of which result we'll be observing
        job = mock.Mock(spec=JobDefinition, name='job', plugin='local')
        # Create a result for the job we'll be observing
        result = mock.Mock(spec=IJobResult, name='result')
        # Mock what rfc822 parser returns
        mock_gen.return_value = [mock.Mock(spec=RFC822Record, name='record')]
        # Pretend that we are observing a 'result' of 'job'
        self.ctrl.observe_result(session_state, job, result)
        # Ensure that result got stored
        self.assertIs(
            session_state.job_state_map[job.name].result, result)
        # Ensure that we tried to define a new job using
        # whatever create_child_job_from_record() returns.
        session_state.add_job.assert_called_once_with(
            job.create_child_job_from_record(), recompute=False)
        # Ensure that the origin of the existing_job was copied
        # from the origin of the generated job
        existing_job.update_origin.assert_called_once_with(
            job.create_child_job_from_record().origin)
        # Ensure that signals got fired
        session_state.on_job_state_map_changed.assert_called_once_with()
        session_state.on_job_result_changed.assert_called_once_with(
            job, result)


class FunctionTests(TestCase):
    """
    unit tests for gen_rfc822_records_from_io_log()
    """

    def test_parse_typical(self):
        """
        verify typical operation without any parsing errors
        """
        # Setup a mock job and result, give some io log to the result
        job = mock.Mock(spec=JobDefinition)
        result = mock.Mock(spec=IJobResult)
        result.get_io_log.return_value = [
            (0, 'stdout', b'attr: value1\n'),
            (0, 'stdout', b'\n'),
            (0, 'stdout', b'attr: value2\n')]
        # Parse the IO log records
        records = list(gen_rfc822_records_from_io_log(job, result))
        # Ensure that we saw both records
        self.assertEqual(records, [
            RFC822Record(
                {'attr': 'value1'}, Origin(JobOutputTextSource(job), 1, 1)),
            RFC822Record(
                {'attr': 'value2'}, Origin(JobOutputTextSource(job), 3, 3)),
        ])

    @mock.patch('plainbox.impl.ctrl.logger')
    def test_parse_error(self, mock_logger):
        # Setup a mock job and result, give some io log to the result
        job = mock.Mock(spec=JobDefinition)
        result = mock.Mock(spec=IJobResult)
        result.get_io_log.return_value = [
            (0, 'stdout', b'attr: value1\n'),
            (0, 'stdout', b'\n'),
            (0, 'stdout', b'error\n'),
            (0, 'stdout', b'\n'),
            (0, 'stdout', b'attr: value2\n')]
        # Parse the IO log records
        records = list(gen_rfc822_records_from_io_log(job, result))
        # Ensure that only the first record was generated
        self.assertEqual(records, [
            RFC822Record(
                {'attr': 'value1'}, Origin(JobOutputTextSource(job), 1, 1)),
        ])
        # Ensure that a warning was logged
        mock_logger.warning.assert_called_once_with(
            "local script %s returned invalid RFC822 data: %s",
            job, RFC822SyntaxError(
                None, 3, "Unexpected non-empty line"))
