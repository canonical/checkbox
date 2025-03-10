# This file is part of Checkbox.
#
# Copyright 2015-2024 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the session assistant module class."""
import json

from unittest import mock
from functools import partial

from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.session.assistant import (
    SessionAssistant,
    UsageExpectation,
    SessionMetaData,
)
from plainbox.impl.unit.job import JobDefinition
from plainbox.vendor import morris


@mock.patch("plainbox.impl.session.assistant.get_providers")
class SessionAssistantTests(morris.SignalTestCase):
    """Tests for the SessionAssitant class."""

    APP_ID = "app-id"
    APP_VERSION = "1.0"
    API_VERSION = "0.99"
    API_FLAGS = []

    def setUp(self):
        """Common set-up code."""
        self.sa = SessionAssistant(
            self.APP_ID, self.APP_VERSION, self.API_VERSION, self.API_FLAGS
        )
        # Monitor the provider_selected signal since some tests check it
        self.watchSignal(self.sa.provider_selected)
        # Create a few mocked providers that tests can use.
        # The all-important plainbox provider
        self.p1 = mock.Mock(spec_set=Provider1, name="p1")
        self.p1.namespace = "com.canonical.plainbox"
        self.p1.name = "com.canonical.plainbox:special"
        # An example 3rd party provider
        self.p2 = mock.Mock(spec_set=Provider1, name="p2")
        self.p2.namespace = "pl.zygoon"
        self.p2.name = "pl.zygoon:example"
        # A Canonical certification provider
        self.p3 = mock.Mock(spec_set=Provider1, name="p3")
        self.p3.namespace = "com.canonical.certification"
        self.p3.name = "com.canonical.certification:stuff"

    def _get_mock_providers(self):
        """Get some mocked provides for testing."""
        return [self.p1, self.p2, self.p3]

    def test_expected_call_sequence(self, mock_get_providers):
        """Track the sequence of allowed method calls."""
        mock_get_providers.return_value = self._get_mock_providers()
        # SessionAssistant.start_new_session() must now be allowed
        self.assertIn(
            self.sa.start_new_session,
            UsageExpectation.of(self.sa).allowed_calls,
        )

        # patch system_information to avoid the actual collection of
        # system_information in tests
        with mock.patch(
            "plainbox.impl.session.state.SessionState.system_information"
        ):
            # Call SessionAssistant.start_new_session()
            self.sa.start_new_session("just for testing")

        # SessionAssistant.start_new_session() must no longer allowed
        self.assertNotIn(
            self.sa.start_new_session,
            UsageExpectation.of(self.sa).allowed_calls,
        )
        # SessionAssistant.select_test_plan() must now be allowed
        self.assertIn(
            self.sa.select_test_plan,
            UsageExpectation.of(self.sa).allowed_calls,
        )
        # Use the manager to tidy up after the tests when normally you wouldnt
        # be allowed to
        self.sa._manager.destroy()

    @mock.patch(
        "plainbox.impl.session.assistant.UsageExpectation",
        new=mock.MagicMock(),
    )
    @mock.patch("plainbox.impl.session.assistant._logger")
    def test_finalize_session_incomplete(
        self, logger_mock, mock_get_providers
    ):
        self_mock = mock.MagicMock()
        self_mock._metadata.flags = [SessionMetaData.FLAG_INCOMPLETE]

        SessionAssistant.finalize_session(self_mock)

        self.assertNotIn(
            SessionMetaData.FLAG_INCOMPLETE, self_mock._metadata.flags
        )

    @mock.patch(
        "plainbox.impl.session.assistant.UsageExpectation",
        new=mock.MagicMock(),
    )
    @mock.patch("plainbox.impl.session.assistant._logger")
    def test_finalize_session_bootstrapping(
        self, logger_mock, mock_get_providers
    ):
        self_mock = mock.MagicMock()
        self_mock._metadata.flags = [SessionMetaData.FLAG_BOOTSTRAPPING]

        SessionAssistant.finalize_session(self_mock)

        self.assertNotIn(
            SessionMetaData.FLAG_BOOTSTRAPPING, self_mock._metadata.flags
        )

    @mock.patch("plainbox.impl.session.assistant.WellKnownDirsHelper")
    def test_delete_sessions(self, mock_well_known_dirs_helper, _):
        wkdh = mock_well_known_dirs_helper

        mock_storage_deleted = mock.MagicMock()
        mock_storage_deleted.id = 1

        mock_storage_not_deleted = mock.MagicMock()
        mock_storage_not_deleted.id = 2

        wkdh.get_storage_list.return_value = [
            mock_storage_deleted,
            mock_storage_not_deleted,
        ]

        SessionAssistant.delete_sessions(mock.MagicMock(), [1])

        self.assertTrue(mock_storage_deleted.remove.called)
        self.assertFalse(mock_storage_not_deleted.remove.called)

    def test_note_metadata_starting_job(self, _):
        self_mock = mock.MagicMock()

        SessionAssistant.note_metadata_starting_job(
            self_mock, {"id": 123}, mock.MagicMock()
        )

        self.assertTrue(self_mock._manager.checkpoint.called)

    @mock.patch("plainbox.impl.session.assistant.UsageExpectation")
    def test_resume_session_autoload_session_not_found(
        self, ue_mock, get_providers_mock
    ):
        self_mock = mock.MagicMock()
        self_mock._resume_candidates = {}
        self_mock.get_resumable_sessions.return_value = []

        with self.assertRaises(KeyError):
            SessionAssistant.resume_session(self_mock, "session_id")

    @mock.patch("plainbox.impl.session.assistant.SessionManager")
    @mock.patch("plainbox.impl.session.assistant.JobRunnerUIDelegate")
    @mock.patch("plainbox.impl.session.assistant._SilentUI")
    @mock.patch("plainbox.impl.session.assistant.detect_restart_strategy")
    @mock.patch("plainbox.impl.session.assistant.UsageExpectation")
    def test_resume_session_autoload_session_found(
        self,
        ue_mock,
        session_manager_mock,
        jrd_mock,
        _sui_mock,
        detect_restart_strategy_mock,
        get_providers_mock,
    ):
        self_mock = mock.MagicMock()
        session_mock = mock.MagicMock(id="session_id")

        def get_resumable_sessions():
            self_mock._resume_candidates = {"session_id": session_mock}

        self_mock.get_resumable_sessions.return_value = [session_mock]

        _ = SessionAssistant.resume_session(self_mock, "session_id")

    @mock.patch("plainbox.impl.session.state.select_units")
    @mock.patch("plainbox.impl.unit.testplan.TestPlanUnit")
    def test_bootstrap(self, mock_tpu, mock_su, mock_get_providers):
        self_mock = mock.MagicMock()
        SessionAssistant.bootstrap(self_mock)
        # Bootstrapping involves updating the list of desired jobs twice:
        # - one time to get the resource jobs
        # - one time to generate jobs out of the resource jobs
        self.assertEqual(
            self_mock._context.state.update_desired_job_list.call_count, 2
        )

    @mock.patch("plainbox.impl.session.state.select_units")
    def test_hand_pick_jobs(self, mock_su, mock_get_providers):
        self_mock = mock.MagicMock()
        SessionAssistant.hand_pick_jobs(self_mock, [])
        self.assertEqual(
            self_mock._context.state.update_desired_job_list.call_count, 1
        )

    @mock.patch("plainbox.impl.session.state.select_units")
    @mock.patch("plainbox.impl.unit.testplan.TestPlanUnit")
    def test_get_bootstrap_todo_list(
        self, mock_tpu, mock_su, mock_get_providers
    ):
        self_mock = mock.MagicMock()
        SessionAssistant.get_bootstrap_todo_list(self_mock)
        self.assertEqual(
            self_mock._context.state.update_desired_job_list.call_count, 1
        )

    @mock.patch("plainbox.impl.session.assistant.UsageExpectation")
    def test_use_alternate_configuration(self, ue_mock, mock_get_providers):
        self_mock = mock.MagicMock()

        def get_value(section, value):
            if section == "test selection" and value == "exclude":
                return [r".*some.*", r".*other.*"]
            elif section == "test selection" and value == "match":
                return [r".*target", r".*another_target"]
            raise AssertionError(
                "Need more configuration sections/config to mock,"
                " test asked for [{}][{}]".format(section, value)
            )

        config_mock = mock.MagicMock()
        config_mock.get_value.side_effect = get_value

        SessionAssistant.use_alternate_configuration(self_mock, config_mock)

        self.assertEqual(len(self_mock._exclude_qualifiers), 2)
        self.assertEqual(len(self_mock._match_qualifiers), 2)

    @mock.patch("plainbox.impl.session.assistant.UsageExpectation")
    @mock.patch("plainbox.impl.session.assistant.select_units")
    def test_finish_bootstrap_match_nominal(
        self, select_units_mock, ue_mock, get_providers_mock
    ):
        self_mock = mock.MagicMock()
        # this is just to test that the subfunction is called if this arr is
        # defined, assumes the select_units function is mocked
        self_mock._match_qualifiers = [1, 2, 3]

        SessionAssistant.finish_bootstrap(self_mock)

        # called once to get all the jobs for the selected testplan
        # and another time to prune it for match`
        self.assertEqual(select_units_mock.call_count, 2)

    @mock.patch("plainbox.impl.session.assistant.UsageExpectation")
    @mock.patch("plainbox.impl.session.assistant.select_units")
    def test_finish_bootstrap_match_no_match(
        self, select_units_mock, ue_mock, get_providers_mock
    ):
        self_mock = mock.MagicMock()
        self_mock._match_qualifiers = []

        SessionAssistant.finish_bootstrap(self_mock)

        # called once to get all the jobs for the selected testplan
        # and another time to prune it for match
        self.assertEqual(select_units_mock.call_count, 1)

    @mock.patch("plainbox.impl.session.assistant.UsageExpectation")
    @mock.patch("plainbox.impl.session.assistant.select_units")
    def test_finish_bootstrap_match_rejected_jobs(
        self, select_units_mock, ue_mock, get_providers_mock
    ):
        self_mock = mock.MagicMock()
        self_mock._metadata.rejected_jobs = []
        # this is just to test that the subfunction is called if this arr is
        # defined, assumes the select_units function is mocked
        self_mock._match_qualifiers = [1, 2, 3]

        job1_id = "com.canonical.certification::job_1"
        job2_id = "com.canonical.certification::job_2"
        job1 = JobDefinition({"id": job1_id})
        job2 = JobDefinition({"id": job2_id})
        select_units_mock.side_effect = [[job1, job2], [job2]]

        SessionAssistant.finish_bootstrap(self_mock)

        # called once to get all the jobs for the selected testplan
        # and another time to prune it for match`
        self.assertEqual(select_units_mock.call_count, 2)

        # job1 is rejected, so the metadata is updated accordingly
        self.assertEqual(self_mock._metadata.rejected_jobs, [job1_id])
        self.assertTrue(self_mock._metadata.custom_joblist)

    @mock.patch(
        "plainbox.impl.session.assistant.UsageExpectation",
        new=mock.MagicMock(),
    )
    def test_use_alternate_selection(self, mock_get_providers):
        self_mock = mock.MagicMock()

        job1_id = "com.canonical.certification::job_1"
        job2_id = "com.canonical.certification::job_2"
        job3_id = "com.canonical.certification::job_3"
        job1 = JobDefinition({"id": job1_id})
        job2 = JobDefinition({"id": job2_id})
        job3 = JobDefinition({"id": job3_id})

        self_mock._metadata.rejected_jobs = ["already-rejected-job"]
        self_mock.get_mandatory_jobs.return_value = [job1_id]
        self_mock.get_static_todo_list.return_value = [
            job1_id,
            job2_id,
            job3_id,
        ]
        self_mock._context.get_unit.side_effect = [job2]
        selection = [job2_id]

        SessionAssistant.use_alternate_selection(self_mock, selection)
        # job1 is not part of the selection, but it's a mandatory job, so it
        # should not be added to the rejected jobs, because it's going to be run.
        self.assertEqual(
            self_mock._metadata.rejected_jobs,
            ["already-rejected-job", job3_id],
        )
        self_mock._context.get_unit.assert_called_once_with(job2_id, "job")

    @mock.patch(
        "plainbox.impl.session.assistant.UsageExpectation",
        new=mock.MagicMock(),
    )
    @mock.patch(
        "plainbox.impl.session.assistant.open",
        # set this to check that values are correctly loaded from disk
        new=mock.mock_open(
            read_data=json.dumps(
                {
                    "_hidden_unset_manifest": "True",
                    "disk_selected_manifest_disk": "True",
                }
            )
        ),
    )
    @mock.patch("os.path.isfile", return_value=True)
    def test_get_manifest_repr(self, isfile, _):
        def get_manifest_unit(id):
            to_r = mock.MagicMock(
                id=id,
                is_hidden=id.startswith("_"),
                value_type="bool",
            )
            to_r.Meta.name = "manifest entry"
            to_r.prompt.return_value = "prompt"
            return to_r

        self_mock = mock.MagicMock()
        self_mock._parse_value = partial(
            SessionAssistant._parse_value, self_mock
        )
        # make testing easier down below
        self_mock._strtobool = lambda x: x

        selected_unit = get_manifest_unit("selected_manifest")
        selected_disk_unit = get_manifest_unit("disk_selected_manifest_disk")
        selected_but_hidden = get_manifest_unit("_hidden_manifest")
        selected_but_hidden_unset = get_manifest_unit("_hidden_unset_manifest")
        unselected_unit = get_manifest_unit("unselected_manifest")

        done_job_mock = mock.MagicMock(id="done")
        done_job_mock.result.outcome = "pass"

        to_run_job_mock = mock.MagicMock(id="to_run")
        to_run_job_mock.result.outcome = None
        to_run_job_mock.get_resource_program.return_value = mock.MagicMock(
            expression_list=[
                mock.MagicMock(
                    manifest_id_list=[
                        "selected_manifest",
                        "disk_selected_manifest_disk",
                        "_hidden_manifest",
                        "_hidden_unset_manifest",
                    ]
                )
            ]
        )

        to_run_no_resource = mock.MagicMock(id="no_resource")
        to_run_no_resource.result.outcome = None
        to_run_no_resource.get_resource_program.return_value = []

        run_list = [done_job_mock, to_run_job_mock]
        job_state_map = {job.id: job for job in run_list}

        self_mock._context.state.job_state_map = job_state_map
        self_mock._context.state.run_list = run_list
        self_mock._context.unit_list = [
            selected_unit,
            selected_disk_unit,
            selected_but_hidden,
            selected_but_hidden_unset,
            unselected_unit,
        ]
        self_mock._config.manifest = {"_hidden_manifest": "True"}
        manifest_info_dict = SessionAssistant.get_manifest_repr(self_mock)

        self.assertEqual(len(manifest_info_dict), 1)
        self.assertEqual(
            {
                (x["id"], x["value"])
                for x in list(manifest_info_dict.values())[0]
            },
            {
                # this is non-hidden and doesn't have a disk value
                ("selected_manifest", None),
                # this is non-hidden and does have a disk value
                ("disk_selected_manifest_disk", "True"),
                # this is hidden and has a config value which is True
                ("_hidden_manifest", "True"),
                # this is hidden but doesn't have a config value, only the
                # config can set hidden manifests, so this must be default
                (
                    "_hidden_unset_manifest",
                    selected_but_hidden_unset.default_value(),
                ),
            },
        )
        self.assertTrue(selected_but_hidden_unset.default_value.called)

    def test__strtobool(self, _):
        strtobool = SessionAssistant._strtobool
        self.assertTrue(
            all(strtobool(None, x) for x in ("true", "t", "True", "yes"))
        )
        self.assertFalse(
            any(strtobool(None, x) for x in ("false", "f", "False", "no"))
        )

        with self.assertRaises(ValueError):
            strtobool(None, "value")

    def test__parse_value(self, _):
        self_mock = mock.MagicMock()

        SessionAssistant._parse_value(
            self_mock, mock.MagicMock(value_type="bool"), "t"
        )

        self.assertTrue(self_mock._strtobool.called)

        self.assertEqual(
            SessionAssistant._parse_value(
                self_mock, mock.MagicMock(value_type="natural"), "1"
            ),
            1,
        )

        with self.assertRaises(SystemExit):
            SessionAssistant._parse_value(
                self_mock,
                mock.MagicMock(value_type="natural"),
                "abc",
            )

        with self.assertRaises(KeyError):
            SessionAssistant._parse_value(
                self_mock,
                mock.MagicMock(value_type="weird new invention"),
                "abc",
            )
