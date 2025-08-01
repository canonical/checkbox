# This file is part of Checkbox.
#
# Copyright 2016-2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
"""
Definition of sub-command classes for checkbox-cli
"""
from argparse import ArgumentTypeError
from argparse import RawDescriptionHelpFormatter
from argparse import SUPPRESS
from collections import defaultdict
from string import Formatter
from tempfile import TemporaryDirectory
import fnmatch
import itertools
import contextlib
import gettext
import json
import logging
import operator
import os
import re
import shlex
import sys
import tarfile
import time

from plainbox.abc import IJobResult
from plainbox.impl.color import Colorizer
from plainbox.impl.session.resume import (
    IncompatibleJobError,
    CorruptedSessionError,
)
from plainbox.impl.execution import UnifiedRunner
from plainbox.impl.highlevel import Explorer
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.runner import slugify
from plainbox.impl.secure.sudo_broker import sudo_password_provider
from plainbox.impl.secure.qualifiers import select_units
from plainbox.impl.session.assistant import SA_RESTARTABLE
from plainbox.impl.session.restart import detect_restart_strategy
from plainbox.impl.session.storage import WellKnownDirsHelper
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import get_all_transports
from plainbox.impl.transport import SECURE_ID_PATTERN
from plainbox.impl.unit.testplan import TestPlanUnitSupport
from plainbox.impl.config import Configuration

from checkbox_ng.config import load_configs
from checkbox_ng.launcher.stages import MainLoopStage, ReportsStage
from checkbox_ng.launcher.startprovider import (
    EmptyProviderSkeleton,
    IQN,
    ProviderSkeleton,
)
from checkbox_ng.launcher.run import Action
from checkbox_ng.launcher.run import NormalUI
from checkbox_ng.resume_menu import ResumeMenu
from checkbox_ng.urwid_ui import CategoryBrowser
from checkbox_ng.urwid_ui import ManifestBrowser
from checkbox_ng.urwid_ui import ReRunBrowser
from checkbox_ng.urwid_ui import ResumeInstead
from checkbox_ng.urwid_ui import TestPlanBrowser
from checkbox_ng.utils import (
    newline_join,
    generate_resume_candidate_description,
    request_comment,
)

_ = gettext.gettext

_logger = logging.getLogger("checkbox-ng.launcher.subcommands")


class Submit:
    def register_arguments(self, parser):
        def secureid(secure_id):
            if not re.match(SECURE_ID_PATTERN, secure_id):
                raise ArgumentTypeError(
                    _("must be 15-character (or more) alphanumeric string")
                )
            return secure_id

        parser.add_argument(
            "secure_id",
            metavar=_("SECURE-ID"),
            type=secureid,
            help=_("associate submission with a machine using this SECURE-ID"),
        )
        parser.add_argument(
            "submission",
            metavar=_("SUBMISSION"),
            help=_("The path to the results file"),
        )
        parser.add_argument(
            "-s",
            "--staging",
            action="store_true",
            help=_("Use staging environment"),
        )
        parser.add_argument(
            "-m", "--message", help=_("Submission description")
        )

    def invoked(self, ctx):
        transport_cls = None
        mode = "rb"
        options_string = "secure_id={0}".format(ctx.args.secure_id)
        url = (
            "https://certification.canonical.com/"
            "api/v1/submission/{}/".format(ctx.args.secure_id)
        )
        submission_file = ctx.args.submission
        if ctx.args.staging:
            url = (
                "https://certification.staging.canonical.com/"
                "api/v1/submission/{}/".format(ctx.args.secure_id)
            )
        elif os.getenv("C3_URL"):
            url = "{}/{}/".format(os.getenv("C3_URL"), ctx.args.secure_id)
        from checkbox_ng.certification import SubmissionServiceTransport

        transport_cls = SubmissionServiceTransport
        transport = transport_cls(url, options_string)
        if ctx.args.message:
            tmpdir = TemporaryDirectory()
            with tarfile.open(ctx.args.submission) as tar:
                tar.extractall(tmpdir.name)
            with open(os.path.join(tmpdir.name, "submission.json")) as f:
                json_payload = json.load(f)
            with open(os.path.join(tmpdir.name, "submission.json"), "w") as f:
                json_payload["description"] = ctx.args.message
                json.dump(json_payload, f, sort_keys=True, indent=4)
            new_subm_file = os.path.join(
                tmpdir.name, os.path.basename(ctx.args.submission)
            )
            with tarfile.open(new_subm_file, mode="w:xz") as tar:
                tar.add(tmpdir.name, arcname="")
            submission_file = new_subm_file
        try:
            with open(submission_file, mode) as subm_file:
                result = transport.send(subm_file)
        except (TransportError, OSError) as exc:
            raise SystemExit(exc)
        else:
            if result and "url" in result:
                # TRANSLATORS: Do not translate the {} format marker.
                print(
                    _("Successfully sent, submission status" " at {0}").format(
                        result["url"]
                    )
                )
            elif result and "status_url" in result:
                # TRANSLATORS: Do not translate the {} format marker.
                print(
                    _("Successfully sent, submission status" " at {0}").format(
                        result["status_url"]
                    )
                )
            else:
                # TRANSLATORS: Do not translate the {} format marker.
                print(
                    _("Successfully sent, server response" ": {0}").format(
                        result
                    )
                )


class StartProvider:
    def register_arguments(self, parser):
        parser.add_argument(
            "name",
            metavar=_("name"),
            type=IQN,
            # TRANSLATORS: please keep the YYYY.example... text unchanged or at
            # the very least translate only YYYY and some-name. In either case
            # some-name must be a reasonably-ASCII string (should be safe for a
            # portable directory name)
            help=_("provider name, eg: YYYY.example.org:some-name"),
        )
        parser.add_argument(
            "--empty",
            action="store_const",
            const=EmptyProviderSkeleton,
            default=ProviderSkeleton,
            dest="skeleton",
            help=_("create an empty provider"),
        )

    def invoked(self, ctx):
        ctx.args.skeleton(ctx.args.name).instantiate(
            ".",
            name=ctx.args.name,
            gettext_domain=re.sub("[.:]", "_", ctx.args.name),
        )


class Launcher(MainLoopStage, ReportsStage):
    @property
    def sa(self):
        return self.ctx.sa

    @property
    def C(self):
        return self._C

    def get_sa_api_version(self):
        # value of this never changed and was a part of configuration/launcher
        # that the operator could provide. Nobody used it so let's use the
        # value it is right now.
        return "0.99"

    def get_sa_api_flags(self):
        # the goal of flags was to fine tune clients of the core of checkbox,
        # but since there is one program using the core of checkbox (called
        # checkbox), we can hardcode those
        return [SA_RESTARTABLE]

    def invoked(self, ctx):
        if ctx.args.version:
            import checkbox_ng

            print(checkbox_ng.__version__)
            return
        if ctx.args.verify:
            # validation is always run, so if there were any errors the program
            # exited by now, so validation passed
            print(_("Launcher seems valid."))
            return
        self.configuration = load_configs(ctx.args.launcher)
        logging_level = {
            "normal": logging.WARNING,
            "verbose": logging.INFO,
            "debug": logging.DEBUG,
        }[self.configuration.get_value("ui", "verbosity")]
        if not ctx.args.verbose and not ctx.args.debug:
            # Command line args take precendence
            logging.basicConfig(level=logging_level)
        try:
            self._C = Colorizer()
            self.ctx = ctx
            # now we have all the correct flags and options, so we need to
            # replace the previously built SA with the defaults
            self._configure_restart(ctx)
            self._prepare_transports()
            self.resume_candidates = list(ctx.sa.get_resumable_sessions())
            if not self._auto_resume_session(self.resume_candidates):
                something_got_chosen = False
                ctx.sa.use_alternate_configuration(self.configuration)
                while not something_got_chosen:
                    try:
                        self._start_new_session()
                        self._pick_jobs_to_run()
                        something_got_chosen = True
                    except ResumeInstead:
                        self.sa.finalize_session()
                        something_got_chosen = self._manually_resume_session(
                            self.resume_candidates
                        )

            if not self.ctx.sa.get_static_todo_list():
                return 0
            if "submission_files" in self.configuration.get_value(
                "launcher", "stock_reports"
            ):
                print("Reports will be saved to: {}".format(self.base_dir))
            # we initialize the nb of attempts for all the selected jobs...
            for job_id in self.ctx.sa.get_dynamic_todo_list():
                job_state = self.ctx.sa.get_job_state(job_id)
                job_state.attempts = self.configuration.get_value(
                    "ui", "max_attempts"
                )
            # ... before running them
            self._run_jobs(self.ctx.sa.get_dynamic_todo_list())
            if self.is_interactive and not self.configuration.get_value(
                "ui", "auto_retry"
            ):
                while True:
                    if not self._maybe_rerun_jobs():
                        break
            elif self.configuration.get_value("ui", "auto_retry"):
                while True:
                    if not self._maybe_auto_rerun_jobs():
                        break
            self._export_results()
            ctx.sa.finalize_session()
            failed = ctx.sa.get_summary()["fail"] != 0
            crashed = ctx.sa.get_summary()["crash"] != 0
            return 0 if not failed and not crashed else 1
        except KeyboardInterrupt:
            return 1

    @property
    def is_interactive(self):
        """
        Flag indicating that this is an interactive invocation.

        We can then interact with the user when we encounter OUTCOME_UNDECIDED.
        """
        return (
            self.configuration.get_value("ui", "type") == "interactive"
            and sys.stdin.isatty()
            and sys.stdout.isatty()
        )

    def _configure_restart(self, ctx):
        try:
            _ = detect_restart_strategy(session_type="local")
        except LookupError as exc:
            _logger.warning(exc)
            _logger.warning(gettext.gettext("Automatic restart disabled!"))
            return

        snap_name = os.getenv("SNAP_NAME")
        if snap_name:
            # NOTE: This implies that any snap wishing to include a
            # Checkbox snap to be autostarted creates a snapcraft
            # app called "checkbox-cli"
            respawn_cmd = ["/snap/bin/{}.checkbox-cli".format(snap_name)]
        else:
            respawn_cmd = [sys.argv[0]]  # entry-point to checkbox
        respawn_cmd.append("launcher")
        if ctx.args.launcher:
            respawn_cmd.append(os.path.abspath(ctx.args.launcher))
        respawn_cmd.append("--resume")

        def join_cmd(args):
            try:
                return shlex.join(args)
            except AttributeError:
                return " ".join(shlex.quote(x) for x in args)

        ctx.sa.configure_application_restart(
            lambda session_id: [join_cmd(respawn_cmd + [session_id])]
        )

    @contextlib.contextmanager
    def _resumed_session(self, session_id):
        """
        Used to temporarily resume a session to inspect it, abandoning it
        before exiting the context
        """
        try:
            # reload the list of resumable_session in SA
            yield self.sa.resume_session(session_id)
        finally:
            self.ctx.reset_sa()

    def _should_autoresume_last_run(self, resume_candidates):
        try:
            last_abandoned_session = resume_candidates[0]
        except IndexError:
            return False
        try:
            with self._resumed_session(last_abandoned_session.id) as metadata:
                app_blob = json.loads(metadata.app_blob.decode("UTF-8"))

                if not app_blob.get("testplan_id"):
                    return False

                self.sa.select_test_plan(app_blob["testplan_id"])
                self.sa.bootstrap()

                if not metadata.running_job_name:
                    return False

                job_state = self.sa.get_job_state(metadata.running_job_name)
                if job_state.job.plugin != "shell":
                    return False
                return True
        except (CorruptedSessionError, IncompatibleJobError) as ije:
            # last resumable session is incompatible, produce a helpful log
            _logger.error(
                "Checkbox tried to resume last session (%s), but the "
                "content of Checkbox Providers has changed.",
                last_abandoned_session.id,
            )
            _logger.error(str(ije))
            _logger.error(
                "To resume it either revert the latest Checkbox snap refresh"
            )
            _logger.error(
                "or roll back the relevant provider debian package first"
            )

            input("\nPress enter to start Checkbox.")
            return False

    def _auto_resume_session(self, resume_candidates):
        """
        Check if there was a request to auto-resume a session.

        The ID of the session to be resumed is kept in the object, in the
        args context.
        Returns True if a session was resumed, False otherwise.
        Can raises various exceptions if there are problem with resuming
        the session.
        """
        if self.ctx.args.session_id:
            requested_sessions = [
                s
                for s in resume_candidates
                if (s.id == self.ctx.args.session_id)
            ]
            if requested_sessions:
                # session_ids are unique, so there should be only 1
                self._resume_session(
                    requested_sessions[0].id, IJobResult.OUTCOME_UNDECIDED
                )
                return True
            else:
                raise RuntimeError("Requested session is not resumable!")
        elif self.ctx.args.clear_old_sessions:
            return False
        elif self._should_autoresume_last_run(resume_candidates):
            last_session = resume_candidates[0]
            self._resume_session(last_session.id, None)
            return True
        return False

    def _manually_resume_session(self, resume_candidates):
        """
        Run the interactive resume menu.
        Returns True if a session was resumed, False otherwise.
        """
        entries = [
            (
                candidate.id,
                generate_resume_candidate_description(candidate),
            )
            for candidate in resume_candidates
        ]
        while True:
            # let's loop until someone selects something else than "delete"
            # in other words, after each delete action let's go back to the
            # resume menu

            resume_params = ResumeMenu(entries).run()
            if resume_params.action == "delete":
                self.ctx.sa.finalize_session()
                self.ctx.sa.delete_sessions([resume_params.session_id])
                self.resume_candidates = list(
                    self.ctx.sa.get_resumable_sessions()
                )

                # the entries list is just a copy of the resume_candidates,
                # and it's not updated when we delete a session, so we need
                # to update it manually
                entries = [
                    en for en in entries if en[0] != resume_params.session_id
                ]

                if not entries:
                    # if everything got deleted let's go back to the test plan
                    # selection menu
                    return False
            else:
                break

        if resume_params.session_id:
            self._resume_session_via_resume_params(resume_params)
            return True
        return False

    def _run_resume_ui_loop(self, resume_candidates):
        for candidate in resume_candidates:
            cmd = self._pick_action_cmd(
                [
                    Action("r", _("resume this session"), "resume"),
                    Action("n", _("next session"), "next"),
                    Action("c", _("create new session"), "create"),
                    Action("d", _("delete old sessions"), "delete"),
                ],
                _("Do you want to resume session {0!a}?").format(candidate.id),
            )
            if cmd == "next":
                continue
            elif cmd == "create" or cmd is None:
                return False
            elif cmd == "resume":
                self._resume_session(candidate)
                return True
            elif cmd == "delete":
                ids = [candidate.id for candidate in resume_candidates]
                self._delete_old_sessions(ids)
                return False

    def _resume_session_via_resume_params(self, resume_params):
        outcome = {
            "pass": IJobResult.OUTCOME_PASS,
            "fail": IJobResult.OUTCOME_FAIL,
            "skip": IJobResult.OUTCOME_SKIP,
            "rerun": IJobResult.OUTCOME_UNDECIDED,
        }[resume_params.action]
        return self._resume_session(
            resume_params.session_id, outcome, resume_params.comments
        )

    def _get_autoresume_outcome_last_job(self, metadata):
        """
        Calculates the result of the latest running job given its flags. This
        is used to automatically resume a session and assign an outcome to the
        job that interrupted the session. If the interruption is due to a
        noreturn job (for example, reboot), the job will be marked as passed,
        else, if the job made Checkbox crash, it will be marked as crash. If
        the job has a recorded outcome (so the session was interrupted after
        assigning the outcome and before starting a new job) it will be used
        instead.
        """
        job_state = self.sa.get_job_state(metadata.running_job_name)
        if job_state.result.outcome:
            return job_state.result.outcome
        elif "noreturn" in (job_state.job.flags or set()):
            return IJobResult.OUTCOME_PASS
        return IJobResult.OUTCOME_CRASH

    def load_configs_from_app_blob(self, app_blob):
        """
        Load the configs taking into consideration the app_blob. This recovers
        the original launcher that was provided to the session and loads the
        configs from disk
        """
        if "launcher" in app_blob:
            resumed_launcher = Configuration.from_text(
                app_blob["launcher"], "Resume launcher"
            )
        else:
            resumed_launcher = Configuration()
        config = load_configs(cfg=resumed_launcher)
        self.ctx.sa.use_alternate_configuration(config)

    def _resume_session(
        self, session_id: str, outcome: "IJobResult|None", comments=[]
    ):
        """
        Resumes the session with the given session_id assigning to the latest
        running job the given outcome. If outcome is not provided it will be
        calculated from the function _get_autoresume_outcome_last_job
        """
        metadata = self.ctx.sa.resume_session(session_id)
        if "testplanless" not in metadata.flags:
            app_blob = json.loads(metadata.app_blob.decode("UTF-8"))
            test_plan_id = app_blob["testplan_id"]
            self.load_configs_from_app_blob(app_blob)
            self.ctx.sa.select_test_plan(test_plan_id)
            self.ctx.sa.bootstrap()
            if outcome is None:
                outcome = self._get_autoresume_outcome_last_job(metadata)

        last_job = metadata.running_job_name
        is_cert_blocker = (
            self.ctx.sa.get_job_state(last_job).effective_certification_status
            == "blocker"
        )
        # If we resumed maybe not rerun the same, probably broken job
        result_dict = {"comments": comments, "outcome": outcome}
        if outcome == IJobResult.OUTCOME_PASS:
            result_dict["comments"] = newline_join(
                result_dict["comments"], "Passed after resuming execution"
            )

        elif outcome == IJobResult.OUTCOME_FAIL:
            if is_cert_blocker and not comments:
                result_dict["comments"] = request_comment("why it failed")
            else:
                result_dict["comments"] = newline_join(
                    result_dict["comments"], "Failed after resuming execution"
                )
        elif outcome == IJobResult.OUTCOME_SKIP:
            if is_cert_blocker and not comments:
                result_dict["comments"] = request_comment(
                    "why you want to skip it"
                )
            else:
                result_dict["comments"] = newline_join(
                    result_dict["comments"], "Skipped after resuming execution"
                )
        elif outcome == IJobResult.OUTCOME_CRASH:
            if is_cert_blocker and not comments:
                result_dict["comments"] = request_comment("why it failed")
            else:
                result_dict["comments"] = newline_join(
                    result_dict["comments"], "Crashed after resuming execution"
                )
        elif outcome == IJobResult.OUTCOME_UNDECIDED:
            # if we don't call use_job_result it means we'll rerun the job
            return
        else:
            raise ValueError(
                "Unsupported outcome for resume {}".format(outcome)
            )
        result = MemoryJobResult(result_dict)
        self.ctx.sa.use_job_result(last_job, result)

    def _start_new_session(self):
        print(_("Preparing..."))
        title = self.ctx.args.title or self.configuration.get_value(
            "launcher", "session_title"
        )
        title = title or self.configuration.get_value("launcher", "app_id")
        app_version = self.configuration.get_value("launcher", "app_version")
        if app_version:
            title += " {}".format(app_version)
        runner_kwargs = {
            "normal_user_provider": lambda: self.configuration.get_value(
                "agent", "normal_user"
            ),
            "password_provider": sudo_password_provider.get_sudo_password,
            "stdin": None,
        }
        self.ctx.sa.start_new_session(title, UnifiedRunner, runner_kwargs)
        if self.configuration.get_value("test plan", "forced"):
            tp_id = self.configuration.get_value("test plan", "unit")
            if not tp_id:
                _logger.error(
                    _(
                        "The test plan selection was forced but no unit was provided"
                    )
                )
                raise SystemExit(1)
            if tp_id not in self.ctx.sa.get_test_plans():
                _logger.error(_('The test plan "%s" is not available!'), tp_id)
                raise SystemExit(1)
        elif not self.is_interactive:
            # XXX: this maybe somewhat redundant with validation
            _logger.error(
                _(
                    "Non-interactive session without test plan specified in the "
                    "launcher!"
                )
            )
            raise SystemExit(1)
        else:
            tp_id = self._interactively_pick_test_plan()
            if tp_id is None:
                raise SystemExit(_("No test plan selected."))
        self.ctx.sa.select_test_plan(tp_id)
        description = self.ctx.args.message or self.configuration.get_value(
            "launcher", "session_desc"
        )
        app_blob = {"testplan_id": tp_id, "description": description}
        if self.ctx.args.launcher:
            try:
                with open(self.ctx.args.launcher, "r") as f:
                    app_blob["launcher"] = f.read()
            except FileNotFoundError:
                pass
        self.ctx.sa.update_app_blob(json.dumps(app_blob).encode("UTF-8"))
        bs_jobs = self.ctx.sa.get_bootstrap_todo_list()
        self._run_bootstrap_jobs(bs_jobs)
        self.ctx.sa.finish_bootstrap()

    def _delete_old_sessions(self, ids):
        completed_ids = [s[0] for s in self.ctx.sa.get_old_sessions()]
        self.ctx.sa.delete_sessions(completed_ids + ids)

    def _interactively_pick_test_plan(self):
        test_plan_ids = self.ctx.sa.get_test_plans()
        filtered_tp_ids = set()
        for filter in self.configuration.get_value("test plan", "filter"):
            filtered_tp_ids.update(fnmatch.filter(test_plan_ids, filter))
        tp_info_list = self._generate_tp_infos(filtered_tp_ids)
        if not tp_info_list:
            print(self.C.RED(_("There were no test plans to select from!")))
            return
        selected_tp = TestPlanBrowser(
            _("Select test plan"),
            tp_info_list,
            self.configuration.get_value("test plan", "unit"),
            len(self.resume_candidates),
        ).run()
        return selected_tp

    def _strtobool(self, val):
        return val.lower() in ("y", "yes", "t", "true", "on", "1")

    def _save_manifest(self, interactive):
        manifest_repr = self.ctx.sa.get_manifest_repr()
        if not manifest_repr:
            _logger.info("Skipping saving of the manifest")
            return

        if interactive and ManifestBrowser.has_visible_manifests(
            manifest_repr
        ):
            # Ask the user the values
            to_save_manifest = ManifestBrowser(
                "System Manifest:", manifest_repr
            ).run()
        else:
            # Use the one provided in repr (either non-interactive or no visible manifests)
            to_save_manifest = ManifestBrowser.get_flattened_values(
                manifest_repr
            )

        self.ctx.sa.save_manifest(to_save_manifest)

    def _pick_jobs_to_run(self):
        if self.configuration.get_value("test selection", "forced"):
            if self.configuration.manifest:
                self._save_manifest(interactive=False)
            # by default all tests are selected; so we're done here
            return
        job_list = [
            self.ctx.sa.get_job(job_id)
            for job_id in self.ctx.sa.get_static_todo_list()
        ]
        if not job_list:
            print(self.C.RED(_("There were no tests to select from!")))
            return
        test_info_list = self._generate_job_infos(job_list)
        wanted_set = CategoryBrowser(
            _("Choose tests to run on your system:"), test_info_list
        ).run()
        self._save_manifest(interactive=True)
        # no need to set an alternate selection if the job list not changed
        if len(test_info_list) == len(wanted_set):
            return
        # NOTE: tree.selection is correct but ordered badly. To retain
        # the original ordering we should just treat it as a mask and
        # use it to filter jobs from get_static_todo_list.
        job_id_list = [
            job_id
            for job_id in self.ctx.sa.get_static_todo_list()
            if job_id in wanted_set
        ]
        self.ctx.sa.use_alternate_selection(job_id_list)

    def _handle_last_job_after_resume(self, last_job):
        if last_job is None:
            return
        if self.ctx.args.session_id:
            # session_id is present only if auto-resume is used
            result_dict = {
                "outcome": IJobResult.OUTCOME_PASS,
                "comments": _("Automatically passed after resuming execution"),
            }
            session_share = WellKnownDirsHelper.session_share(
                self.ctx.sa.get_session_id()
            )
            result_path = os.path.join(session_share, "__result")
            if os.path.exists(result_path):
                try:
                    with open(result_path, "rt") as f:
                        result_dict = json.load(f)
                        # the only really important field in the result is
                        # 'outcome' so let's make sure it doesn't contain
                        # anything stupid
                        if result_dict.get("outcome") not in [
                            "pass",
                            "fail",
                            "skip",
                        ]:
                            result_dict["outcome"] = IJobResult.OUTCOME_PASS
                except json.JSONDecodeError as e:
                    pass
            print(
                _(
                    "Automatically resuming session. "
                    "Outcome of the previous job: {}".format(
                        result_dict["outcome"]
                    )
                )
            )
            result = MemoryJobResult(result_dict)
            self.ctx.sa.use_job_result(last_job, result)
            return

        print(
            _("Previous session run tried to execute job: {}").format(last_job)
        )
        last_job_cert_status = self.ctx.sa.get_job_state(
            last_job
        ).effective_certification_status
        result_dict = {"outcome": IJobResult.OUTCOME_NONE, "comments": ""}
        while True:
            cmd = self._pick_action_cmd(
                [
                    Action("c", _("add comment"), "comment"),
                    Action("s", _("skip that job"), "skip"),
                    Action("p", _("mark it as passed and continue"), "pass"),
                    Action("f", _("mark it as failed and continue"), "fail"),
                    Action("r", _("run it again"), "run"),
                ],
                _("What do you want to do with that job?"),
            )
            if cmd == "skip" or cmd is None:
                if (
                    last_job_cert_status == "blocker"
                    and not result_dict["comments"]
                ):
                    print(
                        self.C.RED(
                            _(
                                "This job is required in order to issue a certificate."
                            )
                        )
                    )
                    print(
                        self.C.RED(
                            _(
                                "Please add a comment to explain why you want to skip it."
                            )
                        )
                    )
                    continue
                else:
                    if not result_dict["comments"]:
                        result_dict["comments"] = _(
                            "Skipped after resuming execution"
                        )
                    result_dict["outcome"] = IJobResult.OUTCOME_SKIP
                    result = MemoryJobResult(result_dict)
                    break
            elif cmd == "pass":
                if not result_dict["comments"]:
                    result_dict["comments"] = _(
                        "Passed after resuming execution"
                    )
                result_dict["outcome"] = IJobResult.OUTCOME_PASS
                result = MemoryJobResult(result_dict)
                break
            elif cmd == "fail":
                if (
                    last_job_cert_status == "blocker"
                    and not result_dict["comments"]
                ):
                    print(
                        self.C.RED(
                            _(
                                "This job is required in order to issue a certificate."
                            )
                        )
                    )
                    print(
                        self.C.RED(
                            _("Please add a comment to explain why it failed.")
                        )
                    )
                    continue
                else:
                    if not result_dict["comments"]:
                        result_dict["comments"] = _(
                            "Failed after resuming execution"
                        )
                    result_dict["outcome"] = IJobResult.OUTCOME_FAIL
                    result = MemoryJobResult(result_dict)
                    break
            elif cmd == "comment":
                new_comment = input(
                    self.C.BLUE(_("Please enter your comments:") + "\n")
                )
                if new_comment:
                    result_dict["comments"] += new_comment + "\n"
                continue
            elif cmd == "run":
                result = None
                break
        if result:
            self.ctx.sa.use_job_result(last_job, result)

    def _maybe_auto_rerun_jobs(self):
        rerun_candidates = self.ctx.sa.get_rerun_candidates("auto")
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        # we wait before retrying
        delay = self.configuration.get_value("ui", "delay_before_retry")
        _logger.info(
            _(
                "Waiting {} seconds before retrying failed"
                " jobs...".format(delay)
            )
        )
        time.sleep(delay)
        candidates = self.ctx.sa.prepare_rerun_candidates(rerun_candidates)
        self._run_jobs(candidates)
        return True

    def _maybe_rerun_jobs(self):
        # create a list of jobs that qualify for rerunning
        rerun_candidates = self.ctx.sa.get_rerun_candidates("manual")
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        test_info_list = self._generate_job_infos(rerun_candidates)
        wanted_set = ReRunBrowser(
            _("Select jobs to re-run"), test_info_list, rerun_candidates
        ).run()
        if not wanted_set:
            # nothing selected - nothing to run
            return False
        rerun_candidates = [
            self.ctx.sa.get_job(job_id) for job_id in wanted_set
        ]
        rerun_candidates = self.ctx.sa.prepare_rerun_candidates(
            rerun_candidates
        )
        # include resource jobs that selected jobs depend on
        self._run_jobs(rerun_candidates)
        return True

    def _get_ui_for_job(self, job):
        class CheckboxUI(NormalUI):
            def considering_job(self, job, job_state):
                pass

        show_out = True
        output = self.configuration.get_value("ui", "output")
        if output == "hide-resource-and-attachment":
            if job.plugin in ("local", "resource", "attachment"):
                show_out = False
        elif output in ["hide", "hide-automated"]:
            if job.plugin in ("shell", "local", "resource", "attachment"):
                show_out = False
        if "suppress-output" in job.get_flag_set():
            show_out = False
        if "use-chunked-io" in job.get_flag_set():
            show_out = True
        if self.ctx.args.dont_suppress_output:
            show_out = True
        return CheckboxUI(self.C.c, show_cmd_output=show_out)

    def register_arguments(self, parser):
        parser.add_argument(
            "launcher",
            metavar=_("LAUNCHER"),
            nargs="?",
            help=_("launcher definition file to use"),
        )
        parser.add_argument(
            "--resume", dest="session_id", metavar="SESSION_ID", help=SUPPRESS
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help=_("only validate the launcher"),
        )
        parser.add_argument(
            "--title",
            action="store",
            metavar="SESSION_NAME",
            help=_("title of the session to use"),
        )
        parser.add_argument(
            "-m", "--message", help=_("submission description")
        )
        parser.add_argument(
            "--dont-suppress-output",
            action="store_true",
            default=False,
            help=_("Absolutely always show command output"),
        )
        # the next to options are and should be exact copies of what the
        # top-level command offers - this is here so when someone launches
        # checkbox-cli through launcher, they have those options available
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help=_("print more logging from checkbox"),
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help=_("print debug messages from checkbox"),
        )
        parser.add_argument(
            "--clear-cache",
            action="store_true",
            help=_("remove cached results from the system"),
        )
        parser.add_argument(
            "--clear-old-sessions",
            action="store_true",
            help=_("remove previous sessions' data"),
        )
        parser.add_argument(
            "--version",
            action="store_true",
            help=_("show program's version information and exit"),
        )


class CheckboxUI(NormalUI):
    def considering_job(self, job, job_state):
        pass


class Run(MainLoopStage):
    def register_arguments(self, parser):
        parser.add_argument(
            "PATTERN",
            nargs="*",
            help=_("run jobs matching the given regular expression"),
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help=_("skip tests that require interactivity"),
        )
        parser.add_argument(
            "-f",
            "--output-format",
            default="com.canonical.plainbox::text",
            metavar=_("FORMAT"),
            help=_(
                "save test results in the specified FORMAT"
                " (pass ? for a list of choices)"
            ),
        )
        parser.add_argument(
            "-p",
            "--output-options",
            default="",
            metavar=_("OPTIONS"),
            help=_(
                "comma-separated list of options for the export mechanism"
                " (pass ? for a list of choices)"
            ),
        )
        parser.add_argument(
            "-o",
            "--output-file",
            default="-",
            metavar=_("FILE"),  # type=FileType("wb"),
            help=_(
                "save test results to the specified FILE"
                " (or to stdout if FILE is -)"
            ),
        )
        parser.add_argument(
            "-t",
            "--transport",
            metavar=_("TRANSPORT"),
            choices=[_("?")] + list(get_all_transports().keys()),
            help=_(
                "use TRANSPORT to send results somewhere"
                " (pass ? for a list of choices)"
            ),
        )
        parser.add_argument(
            "--transport-where",
            metavar=_("WHERE"),
            help=_("where to send data using the selected transport"),
        )
        parser.add_argument(
            "--transport-options",
            metavar=_("OPTIONS"),
            help=_(
                "comma-separated list of key-value options (k=v) to "
                "be passed to the transport"
            ),
        )
        parser.add_argument(
            "--title",
            action="store",
            metavar="SESSION_NAME",
            help=_("title of the session to use"),
        )
        parser.add_argument(
            "-m", "--message", help=_("submission description")
        )
        parser.add_argument(
            "--exact",
            action="store_true",
            help="only expand the test-plan fully qualified ID that exactly matches",
        )

    @property
    def C(self):
        return self._C

    @property
    def sa(self):
        return self.ctx.sa

    @property
    def is_interactive(self):
        """
        Flag indicating that this is an interactive invocation.

        We can then interact with the user when we encounter OUTCOME_UNDECIDED.
        """
        return (
            sys.stdin.isatty()
            and sys.stdout.isatty()
            and not self.ctx.args.non_interactive
        )

    def _get_relevant_units(self, patterns, exact=False):
        if exact:
            return patterns
        providers = self.sa.get_selected_providers()
        root = Explorer(providers).get_object_tree()
        # here handle the patterns one by one to not change the order
        matching_units = [
            root.find_children_by_name([pattern]) for pattern in patterns
        ]
        all_ids = [
            [pattern] if not matches else [match.name for match in matches]
            for matching_unit in matching_units
            for (pattern, matches) in matching_unit.items()
        ]
        all_ids = [id for all_id in all_ids for id in all_id]
        return all_ids

    def invoked(self, ctx):
        try:
            self._C = Colorizer()
            self.ctx = ctx

            self._configure_restart()
            config = load_configs()
            self.sa.use_alternate_configuration(config)
            self.sa.start_new_session(
                self.ctx.args.title or "checkbox-run", UnifiedRunner
            )
            tps = self.sa.get_test_plans()
            self._configure_report()
            selection = self._get_relevant_units(
                ctx.args.PATTERN, ctx.args.exact
            )
            submission_message = self.ctx.args.message
            if len(selection) == 1 and selection[0] in tps:
                self.ctx.sa.update_app_blob(
                    json.dumps(
                        {
                            "testplan_id": selection[0],
                            "description": submission_message,
                        }
                    ).encode("UTF-8")
                )
                self.just_run_test_plan(selection[0])
            else:
                self.ctx.sa.update_app_blob(
                    json.dumps({"description": submission_message}).encode(
                        "UTF-8"
                    )
                )
                self.sa.hand_pick_jobs(selection)
                print(self.C.header(_("Running Selected Jobs")))
                self._run_jobs(self.sa.get_dynamic_todo_list())
                # there might have been new jobs instantiated
                while True:
                    self.sa.hand_pick_jobs(selection)
                    todos = self.sa.get_dynamic_todo_list()
                    if not todos:
                        break
                    self._run_jobs(self.sa.get_dynamic_todo_list())
            self.sa.finalize_session()
            self._print_results()
            return 0 if self.sa.get_summary()["fail"] == 0 else 1
        except KeyboardInterrupt:
            return 1

    def just_run_test_plan(self, tp_id):
        self.sa.select_test_plan(tp_id)
        self.sa.bootstrap()
        print(self.C.header(_("Running Selected Test Plan")))
        self._run_jobs(self.sa.get_dynamic_todo_list())

    def _configure_report(self):
        """Configure transport and exporter."""
        if self.ctx.args.output_format == "?":
            print_objs("exporter", self.ctx.sa)
            raise SystemExit(0)
        if self.ctx.args.transport == "?":
            print(", ".join(get_all_transports()))
            raise SystemExit(0)
        if not self.ctx.args.transport:
            if self.ctx.args.transport_where:
                _logger.error(
                    _("--transport-where is useless without --transport")
                )
                raise SystemExit(1)
            if self.ctx.args.transport_options:
                _logger.error(
                    _("--transport-options is useless without --transport")
                )
                raise SystemExit(1)
            if self.ctx.args.output_file != "-":
                self.transport = "file"
                self.transport_where = self.ctx.args.output_file
                self.transport_options = ""
            else:
                self.transport = "stream"
                self.transport_where = "stdout"
                self.transport_options = ""
        else:
            if self.ctx.args.transport not in get_all_transports():
                _logger.error(
                    "The selected transport %r is not available",
                    self.ctx.args.transport,
                )
                raise SystemExit(1)
            self.transport = self.ctx.args.transport
            self.transport_where = self.ctx.args.transport_where
            self.transport_options = self.ctx.args.transport_options
        self.exporter = self.ctx.args.output_format
        self.exporter_opts = self.ctx.args.output_options

    def _print_results(self):
        all_transports = get_all_transports()
        transport = get_all_transports()[self.transport](
            self.transport_where, self.transport_options
        )
        print(self.C.header(_("Results")))
        if self.transport == "file":
            print(_("Saving results to {}").format(self.transport_where))
        elif self.transport == "certification":
            print(_("Sending results to {}").format(self.transport_where))
        self.sa.export_to_transport(
            self.exporter, transport, self.exporter_opts
        )

    def _configure_restart(self):
        strategy = detect_restart_strategy(session_type="local")
        snap_name = os.getenv("SNAP_NAME")
        if snap_name:
            # NOTE: This implies that any snap wishing to include a
            # Checkbox snap to be autostarted creates a snapcraft
            # app called "checkbox-cli"
            respawn_cmd = "/snap/bin/{}.checkbox-cli".format(snap_name)
        else:
            respawn_cmd = sys.argv[0]  # entry-point to checkbox
        respawn_cmd += " --resume {}"  # interpolate with session_id
        self.sa.configure_application_restart(
            lambda session_id: [respawn_cmd.format(session_id)]
        )


class List:
    def register_arguments(self, parser):
        parser.add_argument(
            "GROUP",
            nargs="?",
            choices=Explorer.OBJECT_TYPES,
            help=_("list objects from the specified group"),
        )
        parser.add_argument(
            "-a",
            "--attrs",
            default=False,
            action="store_true",
            help=_("show object attributes"),
        )
        parser.add_argument(
            "-f",
            "--format",
            type=str,
            help=_(
                (
                    "output format, as passed to print function. "
                    "Use '?' to list possible values. "
                    "Use 'json' to print all objects as a json"
                )
            ),
        )

    def invoked(self, ctx):
        # print_objs supports json-printing all-jobs, so we can forward the
        # query if json is requested
        if ctx.args.GROUP == "all-jobs" and ctx.args.format != "json":
            if ctx.args.attrs:
                print_objs("job", ctx.sa, True)

                def filter_fun(u):
                    return u.attrs["template_unit"] == "job"

                print_objs("template", ctx.sa, True, filter_fun)
            jobs = get_all_jobs(ctx.sa)
            if ctx.args.format == "?":
                all_keys = set()
                for job in jobs:
                    all_keys.update(job.keys())
                print(_("Available fields are:"))
                print(", ".join(sorted(list(all_keys))))
                return
            if not ctx.args.format:
                # setting default in parser.add_argument would apply to all
                # the list invocations. We want default to be present only for
                # the 'all-jobs' group.
                ctx.args.format = "id: {full_id}\n{_summary}\n"
            for job in jobs:
                unescaped = ctx.args.format.replace("\\n", "\n").replace(
                    "\\t", "\t"
                )

                class DefaultKeyedDict(defaultdict):
                    def __missing__(self, key):
                        return _("<missing {}>").format(key)

                # formatters are allowed to use special field 'unit_type' so
                # let's add it to the job representation
                assert "unit_type" not in job.keys()
                if job.get("template_unit") == "job":
                    job["unit_type"] = "template_job"
                else:
                    job["unit_type"] = "job"
                print(
                    Formatter().vformat(
                        unescaped, (), DefaultKeyedDict(None, job)
                    ),
                    end="",
                )
            return
        elif ctx.args.format and ctx.args.format != "json":
            print(_("--format applies only to 'all-jobs' group.  Ignoring..."))
        print_objs(
            ctx.args.GROUP,
            ctx.sa,
            ctx.args.attrs,
            json_repr=ctx.args.format == "json",
        )


class Expand:
    def __init__(self):
        self.override_list = []

    @property
    def sa(self):
        return self.ctx.sa

    def register_arguments(self, parser):
        parser.formatter_class = RawDescriptionHelpFormatter
        parser.description = (
            "Expand a given test plan: display all the jobs, templates and "
            "manifest entries that are defined in this test plan and that "
            " would be executed if ran. This is useful to visualize the full "
            "list of units called for complex test plans that consist of many "
            "nested parts with different 'include' and 'exclude' sections.\n\n"
            "NOTE: the elements listed here are not sorted by execution "
            "order. To see the execution order, please use the "
            "'list-bootstrapped' command instead."
        )
        parser.add_argument(
            "TEST_PLAN", help=_("test-plan ID or fully qualified ID to expand")
        )
        parser.add_argument(
            "-f",
            "--format",
            type=str,
            default="text",
            help=_("output format: 'text' or 'json' (default: %(default)s)"),
        )
        parser.add_argument(
            "--exact",
            action="store_true",
            help="only expand the test-plan that exactly matches the fully qualified ID",
        )

    def _get_relevant_manifest_units(self, jobs_and_templates_list):
        """
        Get all manifest units that are cited in the jobs_and_templates_list
        resource expressions
        """
        # get all manifest units
        manifest_units = filter(
            lambda unit: unit.unit == "manifest entry",
            self.sa._context.unit_list,
        )
        # get all jobs/templates that have a requires and do require a manifest
        # entry
        job_requires = [
            requires
            for requires in map(
                lambda x: x.get_record_value("requires"),
                jobs_and_templates_list,
            )
            if requires and "manifest" in requires
        ]

        # only return manifest entries that are actually required by any job in
        # the list
        # Note: This doesn't take into consideration the manifest namespace so
        #       it may be inaccurate (overinclusive) when manifests are aliased
        return filter(
            lambda manifest_unit: any(
                "manifest.{}".format(manifest_unit.partial_id) in require
                for require in job_requires
            ),
            manifest_units,
        )

    def invoked(self, ctx):
        self.ctx = ctx
        session_title = "checkbox-expand-{}".format(ctx.args.TEST_PLAN)
        self.sa.start_new_session(session_title)
        tps = self.sa.get_test_plans()
        testplan_id = get_testplan_id_by_id(
            tps, ctx.args.TEST_PLAN, self.sa, ctx.args.exact
        )
        if testplan_id not in tps:
            raise SystemExit("Test plan not found")
        self.sa.select_test_plan(testplan_id)
        all_jobs_and_templates = [
            unit
            for unit in self.sa._context.state.unit_list
            if unit.unit in ["job", "template"]
        ]
        tp = self.sa._context._test_plan_list[0]
        tp_us = TestPlanUnitSupport(tp)
        self.override_list = tp_us.override_list

        jobs_and_templates_list = select_units(
            all_jobs_and_templates,
            [tp.get_mandatory_qualifier()] + [tp.get_qualifier()],
        )
        relevant_manifest_units = self._get_relevant_manifest_units(
            jobs_and_templates_list
        )

        units_to_print = itertools.chain(
            relevant_manifest_units, iter(jobs_and_templates_list)
        )
        obj_list = []
        for unit in units_to_print:
            obj = unit._raw_data.copy()
            obj["unit"] = unit.unit
            obj["id"] = unit.id  # To get the fully qualified id
            # these two don't make sense for manifest units
            if unit.unit != "manifest entry":
                obj["certification-status"] = (
                    self.get_effective_certification_status(unit)
                )
                if unit.template_id:
                    obj["template-id"] = unit.template_id
            obj_list.append(obj)

        obj_list.sort(key=lambda x: x.get("template-id", x["id"]) or x["id"])

        if ctx.args.format == "json":
            json.dump(obj_list, sys.stdout, sort_keys=True)
        else:
            for obj in obj_list:
                if obj["unit"] == "template":
                    print("Template '{}'".format(obj["template-id"]))
                elif obj["unit"] == "manifest entry":
                    print("Manifest '{}'".format(obj["id"]))
                elif obj["unit"] == "job":
                    print("Job '{}'".format(obj["id"]))
                else:
                    raise AssertionError(
                        "Unknown unit type {}".format(obj["unit"])
                    )

    def get_effective_certification_status(self, unit):
        if unit.unit == "template":
            unit_id = unit.template_id
        else:
            unit_id = unit.id
        for regex, override_field_list in self.override_list:
            if re.match(regex, unit_id):
                for field, value in override_field_list:
                    if field == "certification_status":
                        return value
        if hasattr(unit, "certification_status"):
            return unit.certification_status
        return "non-blocker"


class ListBootstrapped:
    @property
    def sa(self):
        return self.ctx.sa

    def register_arguments(self, parser):
        parser.add_argument(
            "--exact",
            action="store_true",
            help="only bootstrap test-plan that exactly match fully qualified ID",
        )
        parser.add_argument("TEST_PLAN", help=_("test-plan id to bootstrap"))
        parser.add_argument(
            "-f",
            "--format",
            type=str,
            default="{full_id}\n",
            help=_(
                (
                    "output format, as passed to print function. "
                    "Use '?' to list possible values"
                )
            ),
        )

    def invoked(self, ctx):
        self.ctx = ctx
        self.sa.start_new_session("checkbox-listing-ephemeral")

        tps = self.sa.get_test_plans()
        testplan_id = get_testplan_id_by_id(
            tps, ctx.args.TEST_PLAN, self.sa, ctx.args.exact
        )
        if testplan_id not in tps:
            raise SystemExit("Test plan not found")
        self.sa.select_test_plan(testplan_id)
        self.sa.bootstrap()
        jobs = []
        for job in self.sa.get_static_todo_list():
            job_unit = self.sa.get_job(job)
            attrs = job_unit._raw_data.copy()
            attrs["full_id"] = job_unit.id
            attrs["id"] = job_unit.partial_id
            attrs["certification_status"] = self.ctx.sa.get_job_state(
                job
            ).effective_certification_status
            jobs.append(attrs)
        if ctx.args.format == "?":
            all_keys = set()
            for job in jobs:
                all_keys.update(job.keys())
            print(_("Available fields are:"))
            print(", ".join(sorted(list(all_keys))))
            return
        if ctx.args.format:
            for job in jobs:
                unescaped = ctx.args.format.replace("\\n", "\n").replace(
                    "\\t", "\t"
                )

                class DefaultKeyedDict(defaultdict):
                    def __missing__(self, key):
                        return _("<missing {}>").format(key)

                print(
                    Formatter().vformat(
                        unescaped, (), DefaultKeyedDict(None, job)
                    ),
                    end="",
                )
        else:
            for job_id in jobs:
                print(job_id)


class TestPlanExport:
    @property
    def sa(self):
        return self.ctx.sa

    def register_arguments(self, parser):
        parser.add_argument("TEST_PLAN", help=_("test-plan id to bootstrap"))
        parser.add_argument("-n", "--nofake", action="store_true")

    def invoked(self, ctx):
        self.ctx = ctx
        if ctx.args.nofake:
            self.sa.start_new_session("tp-export-ephemeral")
        else:
            from plainbox.impl.execution import FakeJobRunner

            self.sa.start_new_session("tp-export-ephemeral", FakeJobRunner)
            self.sa._context.state._fake_resources = True
        tps = self.sa.get_test_plans()
        if ctx.args.TEST_PLAN not in tps:
            raise SystemExit("Test plan not found")
        self.sa.select_test_plan(ctx.args.TEST_PLAN)
        self.sa.bootstrap()
        path = self.sa.export_to_file(
            "com.canonical.plainbox::tp-export",
            [],
            self.sa._manager.storage.location,
            slugify(self.sa._manager.test_plans[0].name),
        )
        print(path)


def get_testplan_id_by_id(tps, testplan_id, sa, exact=False):
    """
    Searches for a testplan that matches the given testplan_id

    The input id may not match the testplan id because it is missing the
    namespace. When the search is not exact, this searches any test plan that
    has the same id ignoring the namespace.
    """
    if exact:
        return testplan_id
    if testplan_id in tps:
        # no need to search for the testplan id
        return testplan_id
    providers = sa.get_selected_providers()
    root = Explorer(providers).get_object_tree()

    relevant = root.find_children_by_name([testplan_id], exact).values()
    relevant = [unit for units in relevant for unit in units]
    if len(relevant) > 1:
        raise SystemExit(
            "More than one testplan match the id {}. Use either:\n- {}".format(
                testplan_id, "\n- ".join(unit.name for unit in relevant)
            )
        )
    if relevant:
        return relevant[0].name
    return testplan_id  # parent will fail


def get_all_jobs(sa):
    providers = sa.get_selected_providers()
    root = Explorer(providers).get_object_tree()

    def get_jobs(obj):
        jobs = []
        if obj.group == "job" or (
            obj.group == "template" and obj.attrs["template_unit"] == "job"
        ):
            attrs = dict(obj._impl._raw_data.copy())
            attrs["full_id"] = obj.name
            jobs.append(attrs)
        for child in obj.children:
            jobs += get_jobs(child)
        return jobs

    return sorted(get_jobs(root), key=operator.itemgetter("full_id"))


def print_objs(group, sa, show_attrs=False, filter_fun=None, json_repr=False):
    # note: group is unit type (including internal units like File)
    providers = sa.get_selected_providers()
    obj = Explorer(providers).get_object_tree()

    def _show(obj, indent):
        if group is None or obj.group == group:
            # object must satisfy filter_fun (if supplied) to be printed
            if filter_fun and not filter_fun(obj):
                return
            # Display the object name and group
            print("{}{} {!r}".format(indent, obj.group, obj.name))
            indent += "  "
            if show_attrs:
                for key, value in obj.attrs.items():
                    print("{}{:15}: {!r}".format(indent, key, value))
        if obj.children:
            if group is None:
                print("{}{}".format(indent, _("children")))
                indent += "  "
            for child in obj.children:
                _show(child, indent)

    if not json_repr:
        return _show(obj, "")

    assert not filter_fun, "The json exporter doesn't support filtering"

    # all-jobs is a meta-group that include all jobs + all templates
    # note: if group is none, everything should be printed
    groups = {group} if group != "all-jobs" else {"job", "template"}

    to_print = []
    childrens = obj.children
    while childrens:
        obj = childrens.pop()
        childrens += obj.children or []
        if group and obj.group not in groups:
            continue
        obj_repr = {"unit": obj.group, "name": obj.name}
        if show_attrs:
            obj_repr.update(obj.attrs)
        to_print.append(obj_repr)
    json.dump(to_print, sys.stdout)


class Show:
    def register_arguments(self, parser):
        parser.add_argument(
            "IDs", nargs="+", help=_("Show the definitions of objects")
        )
        parser.add_argument(
            "--exact",
            action="store_true",
            help=_(
                "Only show units that exactly match the fully qualified ID"
            ),
        )

    def invoked(self, ctx):
        providers = ctx.sa.get_selected_providers()
        self._searched_names = ctx.args.IDs
        root = Explorer(providers).get_object_tree()
        relevant = root.find_children_by_name(ctx.args.IDs, ctx.args.exact)

        failed = [id for id, founds in relevant.items() if not founds]
        to_prints = [unit for units in relevant.values() for unit in units]

        for to_print in to_prints:
            self._print_obj(to_print)

        if failed:
            raise SystemExit("Failed to find: {}".format(", ".join(failed)))

    def _print_obj(self, obj):
        if "origin" in obj.attrs:
            try:
                print("origin:", obj.attrs["origin"])
                path, line_range = obj.attrs["origin"].rsplit(":", maxsplit=1)
                start_index, end_index = [
                    int(i) for i in line_range.split("-")
                ]
                with open(path, "rt", encoding="utf-8") as pxu:
                    # origin uses human-like numbering (starts with 1), so we need
                    # to substract 1. The range in origin is inclusive,
                    # so the end_index is right
                    record = pxu.readlines()[start_index - 1 : end_index]
                    print("".join(record))
            except (ValueError, KeyError):
                print(
                    "Could not read the record for {}!".format(obj.attrs["id"])
                )
            except OSError as exc:
                print(
                    "Could not read '{}' containing record for '{}'!".format(
                        path, obj.attrs["id"]
                    )
                )
        else:
            # provider and service does not have origin
            for k, v in obj.attrs.items():
                print("{}: {}".format(k, v))
