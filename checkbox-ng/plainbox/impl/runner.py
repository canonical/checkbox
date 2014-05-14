# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.impl.runner` -- job runner
=========================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import collections
import datetime
import gzip
import io
import logging
import os
import string
import time

from plainbox.vendor import extcmd

from plainbox.abc import IJobRunner, IJobResult
from plainbox.i18n import gettext as _
from plainbox.impl.ctrl import RootViaPTL1ExecutionController
from plainbox.impl.ctrl import RootViaPkexecExecutionController
from plainbox.impl.ctrl import RootViaSudoExecutionController
from plainbox.impl.ctrl import UserJobExecutionController
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import IOLogRecordWriter
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.signal import Signal


logger = logging.getLogger("plainbox.runner")


def slugify(_string):
    """
    Slugify - like Django does for URL - transform a random string to a valid
    slug that can be later used in filenames
    """
    valid_chars = frozenset(
        "-_.{}{}".format(string.ascii_letters, string.digits))
    return ''.join(c if c in valid_chars else '_' for c in _string)


class IOLogRecordGenerator(extcmd.DelegateBase):
    """
    Delegate for extcmd that generates io_log entries.
    """

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase

        Called when a command is being invoked.

        Begins tracking time (relative time entries)
        """
        self.last_msg = datetime.datetime.utcnow()

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase

        Creates a new IOLogRecord and passes it to :meth:`on_new_record()`.
        Maintains a timestamp of the last message so that approximate delay
        between each piece of output can be recorded as well.
        """
        now = datetime.datetime.utcnow()
        delay = now - self.last_msg
        self.last_msg = now
        record = IOLogRecord(delay.total_seconds(), stream_name, line)
        self.on_new_record(record)

    @Signal.define
    def on_new_record(self, record):
        """
        Internal signal method of :class:`IOLogRecordGenerator`

        Called when a new record is generated and needs to be processed.
        """
        # TRANSLATORS: io means input-output
        logger.debug(_("io log generated %r"), record)


class CommandOutputWriter(extcmd.DelegateBase):
    """
    Delegate for extcmd that writes output to a file on disk.

    The file itself is only opened once on_begin() gets called by extcmd. This
    makes it safe to instantiate this without worrying about dangling
    resources.
    """

    def __init__(self, stdout_path, stderr_path):
        """
        Initialize new writer.

        Just records output paths.
        """
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase

        Called when a command is being invoked
        """
        self.stdout = open(self.stdout_path, "wb")
        self.stderr = open(self.stderr_path, "wb")

    def on_end(self, returncode):
        """
        Internal method of extcmd.DelegateBase

        Called when a command finishes running
        """
        self.stdout.close()
        self.stderr.close()

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase

        Called for each line of output.
        """
        if stream_name == 'stdout':
            self.stdout.write(line)
        elif stream_name == 'stderr':
            self.stderr.write(line)


class FallbackCommandOutputPrinter(extcmd.DelegateBase):
    """
    Delegate for extcmd that prints all output to stdout.

    This delegate is only used as a fallback when no delegate was explicitly
    provided to a JobRunner instance.
    """

    def __init__(self, prompt):
        self._prompt = prompt
        self._lineno = collections.defaultdict(int)
        self._abort = False

    def on_line(self, stream_name, line):
        if self._abort:
            return
        self._lineno[stream_name] += 1
        try:
            print("(job {}, <{}:{:05}>) {}".format(
                self._prompt, stream_name, self._lineno[stream_name],
                line.decode('UTF-8').rstrip()))
        except UnicodeDecodeError:
            self._abort = True


class JobRunner(IJobRunner):
    """
    Runner for jobs - executes jobs and produces results

    The runner is somewhat de-coupled from jobs and session. It still carries
    all checkbox-specific logic about the various types of plugins.

    The runner consumes jobs and configuration objects and produces job result
    objects. The runner can operate in dry-run mode, when enabled, most jobs
    are never started. Only jobs listed in DRY_RUN_PLUGINS are executed.
    """

    # List of plugins that are still executed
    _DRY_RUN_PLUGINS = ('local', 'resource', 'attachment')

    def __init__(self, session_dir, provider_list, jobs_io_log_dir,
                 command_io_delegate=None, dry_run=False):
        """
        Initialize a new job runner.

        :param session_dir:
            Base directory of the session. This is currently used to initialize
            execution controllers. Later on it will go away and callers will be
            responsible for passing a list of execution controllers explicitly.
        :param jobs_io_log_dir:
            Base directory where IO log files are created.
        :param command_io_delegate:
            Application specific extcmd IO delegate applicable for
            extcmd.ExternalCommandWithDelegate. Can be Left out, in which case
            :class:`FallbackCommandOutputPrinter` is used instead.
        :param dry_run:
            Flag indicating that the runner is in "dry run mode". When True
            most normal commands won't execute. Useful for testing.
        """
        self._jobs_io_log_dir = jobs_io_log_dir
        self._command_io_delegate = command_io_delegate
        self._dry_run = dry_run
        self._execution_ctrl_list = [
            RootViaPTL1ExecutionController(session_dir, provider_list),
            RootViaPkexecExecutionController(session_dir, provider_list),
            # XXX: maybe this one should be only used on command line
            RootViaSudoExecutionController(session_dir, provider_list),
            UserJobExecutionController(session_dir, provider_list),
        ]

    def get_warm_up_sequence(self, job_list):
        """
        Determine if authentication warm-up may be needed.

        :param job_lits:
            A list of jobs that may be executed
        :returns:
            A list of methods to call to complete the warm-up step.

        Authentication warm-up is related to the plainbox-secure-launcher-1
        program that can be 'warmed-up' to perhaps cache the security
        credentials. This is usually done early in the testing process so that
        we can prompt for passwords before doing anything that takes an
        extended amount of time.
        """
        warm_up_list = []
        for job in job_list:
            ctrl = self._get_ctrl_for_job(job)
            warm_up_func = ctrl.get_warm_up_for_job(job)
            if warm_up_func is not None and warm_up_func not in warm_up_list:
                warm_up_list.append(warm_up_func)
        return warm_up_list

    def run_job(self, job, config=None):
        """
        Run the specified job an return the result

        :param job:
            A JobDefinition to run
        :param config:
            A PlainBoxConfig that may influence how this job is executed. This
            is only used for the environment variables (that should be
            specified in the environment but, for simplicity in certain setups,
            can be pulled from a special section of the configuration file.
        :returns:
            A IJobResult subclass that describes the result
        :raises ValueError:
            In the future, this method will not run jobs that don't themselves
            validate correctly. Right now this is not enforced.

        This method is the entry point for running all kinds of jobs. Typically
        execution blocks while a command, embeded in many jobs, is running in
        another process. How a job is executed depends mostly on the value of
        the :attr:`plainbox.abc.IJobDefinition.plugin` field.

        The result of a job may in some cases be OUTCOME_UNDECIDED, in which
        case the application should ask the user what the outcome is (and
        present sufficient information to make that choice, typically this is
        the job description and the output of the command)
        """
        # TRANSLATORS: %r is the name of the job
        logger.info(_("Running %r"), job)
        func_name = "run_{}_job".format(job.plugin.replace('-', '_'))
        try:
            runner = getattr(self, func_name)
        except AttributeError:
            return MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_IMPLEMENTED,
                'comment': _('This type of job is not supported'),
            })
        else:
            if self._dry_run and job.plugin not in self._DRY_RUN_PLUGINS:
                return self._get_dry_run_result(job)
            else:
                return runner(job, config)

    def run_shell_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'shell'

        The 'shell' job implements the following scenario:

        * Maybe display the description to the user
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Decide on the outcome based on the return code
        * The method ends here

        .. note::
            Shell jobs are an example of perfectly automated tests. Everything
            about them is encapsulated inside the test command and the return
            code from that command is enough to let plainbox know if the test
            passed or not.
        """
        if job.plugin != "shell":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        return self._just_run_command(job, config)

    def run_attachment_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'attachment'

        The 'attachment' job implements the following scenario:

        * Maybe display the description to the user
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Decide on the outcome based on the return code
        * The method ends here

        .. note::
            Attachment jobs play an important role in CheckBox. They are used
            to convert stdout of the command into a file that is embedded
            inside the final representation of a testing session. Attachment
            jobs are used to gather all kinds of essential information (by
            catting log files, sysfs or procfs files)
        """
        if job.plugin != "attachment":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        return self._just_run_command(job, config)

    def run_resource_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'resource'

        The 'resource' job implements the following scenario:

        * Maybe display the description to the user
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Decide on the outcome based on the return code
        * The method ends here

        .. note::
            Resource jobs are similar to attachment, in that their goal is to
            produce some text on standard output. Unlike attachment jobs they
            are typically not added to the final representation of a testing
            session. Instead the output is parsed and added to the internal
            state of a testing session. This state can be queried from special
            resource programs which are embedded in many job definitions.
        """
        if job.plugin != "resource":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        return self._just_run_command(job, config)

    def run_local_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'local'

        The 'local' job implements the following scenario:

        * Maybe display the description to the user
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Decide on the outcome based on the return code
        * The method ends here

        .. note::
            Local jobs are similar to resource jobs, in that the output matters
            more than the return code. Unlike resource jobs and attachment
            jobs, the output is expected to be a job definition in the
            canonical RFC822 format. Local jobs are discouraged (due to some
            complexities they introduce) but only supported way of generating
            additional jobs at runtime.
        """
        if job.plugin != "local":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        return self._just_run_command(job, config)

    def run_manual_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'manual'

        The 'manual' job implements the following scenario:

        * Display the description to the user
        * Ask the user to perform some operation
        * Ask the user to decide on the outcome

        .. note::
            Technically this method almost always returns a result with
            OUTCOME_UNDECIDED to indicate that it could not determine if the
            test passed or not. Manual jobs are basically fully human driven
            and could totally ignore the job runner. This method is provided
            for completeness.

        .. warning::
            Before the interaction callback is fully removed and deprecated it
            may also return other values through that callback.
        """
        if job.plugin != "manual":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        return MemoryJobResult({'outcome': IJobResult.OUTCOME_UNDECIDED})

    def run_user_interact_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'user-interact'

        The 'user-interact' job implements the following scenario:

        * Display the description to the user
        * Ask the user to perform some operation
        * Wait for the user to confirm this is done
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Decide on the outcome based on the return code
        * The method ends here

        .. note::
            User interaction jobs are candidates for further automation as the
            outcome can be already determined automatically but some
            interaction, yet, cannot.

        .. note::
            User interaction jobs are a hybrid between shell jobs and manual
            jobs. They finish automatically, once triggered but still require a
            human to understand and follow test instructions and prepare the
            process. Instructions may range to getting a particular hardware
            setup, physical manipulation (pressing a key, closing the lid,
            plugging in a removable device) or talking to a microphone to get
            some sound recorded.

        .. note::
            The user may want to re-run the test a number of times, perhaps
            because there is some infrequent glitch or simply because he or she
            was distracted the first time it ran. Users should be given that
            option but it must always produce a separate result (simply re-run
            the same API again).
        """
        if job.plugin != "user-interact":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        return self._just_run_command(job, config)

    def run_user_verify_job(self, job, config):
        """
        Method called to run a job with plugin field equal to 'user-verify'

        The 'user-verify' job implements the following scenario:

        * Maybe display the description to the user
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Display the description to the user
        * Display the output of the command to the user
        * Ask the user to decide on the outcome

        .. note::
            User verify jobs are a hybrid between shell jobs and manual jobs.
            They start automatically but require a human to inspect the output
            and decide on the outcome. This may include looking if the screen
            looks okay after a number of resolution changes, if the picture
            quality is good, if the printed IP address matches some
            expectations or if the sound played from the speakers was
            distorted.

        .. note::
            The user may want to re-run the test a number of times, perhaps
            because there is some infrequent glitch or simply because he or she
            was distracted the first time it ran. Users should be given that
            option but it must always produce a separate result (simply re-run
            the same API again).

        .. note::
            Technically this method almost always returns a result with
            OUTCOME_UNDECIDED to indicate that it could not determine if the
            test passed or not.

        .. warning::
            Before the interaction callback is fully removed and deprecated it
            may also return other values through that callback.
        """
        if job.plugin != "user-verify":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        # Run the command
        result_cmd = self._just_run_command(job, config)
        # Maybe ask the user
        result_cmd.outcome = IJobResult.OUTCOME_UNDECIDED
        return result_cmd

    def run_user_interact_verify_job(self, job, config):
        """
        Method called to run a job with plugin field equal to
        'user-interact-verify'

        The 'user-interact-verify' job implements the following scenario:

        * Ask the user to perform some operation
        * Wait for the user to confirm this is done
        * The API states that :meth:`JobRunner.run_job()` should only be
          called at this time.
        * Run the command and wait for it to finish
        * Display the description to the user
        * Display the output of the command to the user
        * Ask the user to decide on the outcome

        .. note::
            User interact-verify jobs are a hybrid between shell jobs and
            manual jobs. They are both triggered explicitly by the user and
            require the user to decide on the outcome. The only function of the
            command they embed is to give some feedback to the user and perhaps
            partially automate certain instructions (instead of asking the user
            to run some command we can run that for them).

        .. note::
            The user may want to re-run the test a number of times, perhaps
            because there is some infrequent glitch or simply because he or she
            was distracted the first time it ran. Users should be given that
            option but it must always produce a separate result (simply re-run
            the same API again).

        .. note::
            Technically this method almost always returns a result with
            OUTCOME_UNDECIDED to indicate that it could not determine if the
            test passed or not.

        .. warning::
            Before the interaction callback is fully removed and deprecated it
            may also return other values through that callback.
        """
        if job.plugin != "user-interact-verify":
            # TRANSLATORS: please keep 'plugin' untranslated
            raise ValueError(_("bad job plugin value"))
        # Run the command
        result_cmd = self._just_run_command(job, config)
        # Maybe ask the user
        result_cmd.outcome = IJobResult.OUTCOME_UNDECIDED
        return result_cmd

    def _get_dry_run_result(self, job):
        """
        Internal method of JobRunner.

        Returns a result that is used when running in dry-run mode (where we
        don't really test anything)
        """
        return MemoryJobResult({
            'outcome': IJobResult.OUTCOME_SKIP,
            'comments': _("Job skipped in dry-run mode")
        })

    def _just_run_command(self, job, config):
        """
        Internal method of JobRunner.

        Runs the command embedded in the job and returns the DiskJobResult that
        describes the result.
        """
        # Run the embedded command
        start_time = time.time()
        return_code, record_path = self._run_command(job, config)
        execution_duration = time.time() - start_time
        # Convert the return of the command to the outcome of the job
        if return_code == 0:
            outcome = IJobResult.OUTCOME_PASS
        else:
            outcome = IJobResult.OUTCOME_FAIL
        # Create a result object and return it
        return DiskJobResult({
            'outcome': outcome,
            'return_code': return_code,
            'io_log_filename': record_path,
            'execution_duration': execution_duration
        })

    def _prepare_io_handling(self, job, config):
        ui_io_delegate = self._command_io_delegate
        # If there is no UI delegate specified create a simple
        # delegate that logs all output to the console
        if ui_io_delegate is None:
            ui_io_delegate = FallbackCommandOutputPrinter(job.id)
        # Compute a shared base filename for all logging activity associated
        # with this job (aka: the slug)
        slug = slugify(job.id)
        # Create a delegate that writes all IO to disk
        output_writer = CommandOutputWriter(
            stdout_path=os.path.join(
                self._jobs_io_log_dir, "{}.stdout".format(slug)),
            stderr_path=os.path.join(
                self._jobs_io_log_dir, "{}.stderr".format(slug)))
        # Create a delegate for converting regular IO to IOLogRecords.
        # It takes no arguments as all the interesting stuff is added as a
        # signal listener.
        io_log_gen = IOLogRecordGenerator()
        # Create the delegate for routing IO
        #
        # Split the stream of data into three parts (each part is expressed as
        # an element of extcmd.Chain()).
        #
        # Send the first copy of the data through bytes->text decoder and
        # then to the UI delegate. This cold be something provided by the
        # higher level caller or the default FallbackCommandOutputPrinter.
        #
        # Send the second copy of the data to the IOLogRecordGenerator instance
        # that converts raw bytes into neat IOLogRecord objects. This generator
        # has a on_new_record signal that can be used to do stuff when a new
        # record is generated.
        #
        # Send the third copy to the output writer that writes everything to
        # disk.
        delegate = extcmd.Chain([ui_io_delegate, io_log_gen, output_writer])
        logger.debug(_("job[%s] extcmd delegate: %r"), job.id, delegate)
        # Attach listeners to io_log_gen (the IOLogRecordGenerator instance)
        # One listener appends each record to an array
        return delegate, io_log_gen

    def _run_command(self, job, config):
        """
        Run the shell command associated with the specified job.

        :returns: (return_code, record_path) where return_code is the number
        returned by the exiting child process while record_path is a pathname
        of a gzipped content readable with :class:`IOLogRecordReader`
        """
        # Bail early if there is nothing do do
        if job.command is None:
            return None, ()
        # Get an extcmd delegate for observing all the IO the way we need
        delegate, io_log_gen = self._prepare_io_handling(job, config)
        # Create a subprocess.Popen() like object that uses the delegate
        # system to observe all IO as it occurs in real time.
        extcmd_popen = extcmd.ExternalCommandWithDelegate(delegate)
        # Stream all IOLogRecord entries to disk
        record_path = os.path.join(
            self._jobs_io_log_dir, "{}.record.gz".format(
                slugify(job.id)))
        with gzip.open(record_path, mode='wb') as gzip_stream, \
                io.TextIOWrapper(
                    gzip_stream, encoding='UTF-8') as record_stream:
            writer = IOLogRecordWriter(record_stream)
            io_log_gen.on_new_record.connect(writer.write_record)
            # Start the process and wait for it to finish getting the
            # result code. This will actually call a number of callbacks
            # while the process is running. It will also spawn a few
            # threads although all callbacks will be fired from a single
            # thread (which is _not_ the main thread)
            logger.debug(
                _("job[%s] starting command: %s"), job.id, job.command)
            # Run the job command using extcmd
            return_code = self._run_extcmd(job, config, extcmd_popen)
            logger.debug(
                _("job[%s] command return code: %r"), job.id, return_code)
        return return_code, record_path

    def _run_extcmd(self, job, config, extcmd_popen):
        ctrl = self._get_ctrl_for_job(job)
        return ctrl.execute_job(job, config, extcmd_popen)

    def _get_ctrl_for_job(self, job):
        """
        Get the execution controller most applicable to run this job

        :param job:
            A job definition to run
        :returns:
            An execution controller instance
        :raises LookupError:
            if no execution controller capable of running the specified job can
            be found
        """
        # Compute the score of each controller
        ctrl_score = [
            (ctrl, ctrl.get_score(job))
            for ctrl in self._execution_ctrl_list]
        # Sort scores
        ctrl_score.sort(key=lambda pair: pair[1])
        # Get the best score
        ctrl, score = ctrl_score[-1]
        # Ensure that the controller is viable
        if score < 0:
            raise LookupError(
                _("No exec controller supports job {}").format(job))
        logger.debug(
            _("Selected execution controller %s (score %d) for job %r"),
            ctrl.__class__.__name__, score, job.id)
        return ctrl
