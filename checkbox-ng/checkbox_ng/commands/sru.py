# This file is part of Checkbox.
#
#
# Copyright 2013 Canonical Ltd.
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
:mod:`checkbox_ng.commands.sru` -- sru sub-command
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
import sys

from gettext import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.inv_check_config import CheckConfigInvocation
from plainbox.impl.ingredients import CanonicalCommand
from plainbox.impl.secure.config import ValidationError, Unset


class sru(CanonicalCommand):

    """
    Run stable release update (sru) tests.

    Stable release updates are periodic fixes for nominated bugs that land in
    existing supported Ubuntu releases. To ensure a certain level of quality
    all SRU updates affecting hardware enablement are automatically tested
    on a pool of certified machines.
    """

    def __init__(self, config):
        """Init method to store the config settings."""
        self.config = config
        if not self.config.test_plan:
            self.config.test_plan = "2013.com.canonical.certification::sru"

    def register_arguments(self, parser):
        """Method called to register command line arguments."""
        parser.add_argument(
            '--secure_id', metavar=_("SECURE-ID"),
            # NOTE: --secure-id is optional only when set in a config file
            required=self.config.secure_id is Unset,
            help=_("Canonical hardware identifier"))
        parser.add_argument(
            '-T', '--test-plan',
            action="store",
            metavar=_("TEST-PLAN-ID"),
            default=None,
            # TRANSLATORS: this is in imperative form
            help=_("load the specified test plan"))
        parser.add_argument(
            '--staging', action='store_true', default=False,
            help=_("Send the data to non-production test server"))
        parser.add_argument(
            "--check-config",
            action="store_true",
            help=_("run check-config before starting"))

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        # Copy command-line arguments over configuration variables
        try:
            if ctx.args.secure_id:
                self.config.secure_id = ctx.args.secure_id
            if ctx.args.test_plan:
                self.config.test_plan = ctx.args.test_plan
            if ctx.args.staging:
                self.config.staging = ctx.args.staging
        except ValidationError as exc:
            print(_("Configuration problems prevent running SRU tests"))
            print(exc)
            return 1
        ctx.sa.use_alternate_configuration(self.config)
        # Run check-config, if requested
        if ctx.args.check_config:
            retval = CheckConfigInvocation(lambda: self.config).run()
            if retval != 0:
                return retval
        self.transport = self._create_transport(
            ctx.sa, self.config.secure_id, self.config.staging)
        self.ctx = ctx
        try:
            self._collect_info(ctx.rc, ctx.sa)
            self._save_results(ctx.rc, ctx.sa)
            self._send_results(
                ctx.rc, ctx.sa, self.config.secure_id, self.config.staging)
        except KeyboardInterrupt:
            return 1

    def _save_results(self, rc, sa):
        rc.reset()
        rc.padding = (1, 1, 0, 1)
        path = sa.export_to_file(
            "2013.com.canonical.plainbox::hexr", (), '/tmp')
        rc.para(_("Results saved to {0}").format(path))

    def _send_results(self, rc, sa, secure_id, staging):
        rc.reset()
        rc.padding = (1, 1, 0, 1)
        rc.para(_("Sending hardware report to Canonical Certification"))
        rc.para(_("Server URL is: {0}").format(self.transport.url))
        result = sa.export_to_transport(
            "2013.com.canonical.plainbox::hexr", self.transport)
        if 'url' in result:
            rc.para(result['url'])

    def _create_transport(self, sa, secure_id, staging):
        return sa.get_canonical_certification_transport(
            secure_id, staging=staging)

    def _collect_info(self, rc, sa):
        sa.select_providers('*')
        sa.start_new_session(_("Hardware Collection Session"))
        sa.select_test_plan(self.config.test_plan)
        sa.bootstrap()
        for job_id in sa.get_static_todo_list():
            job = sa.get_job(job_id)
            builder = sa.run_job(job_id, 'silent', False)
            result = builder.get_result()
            sa.use_job_result(job_id, result)
            rc.para("- {0}: {1}".format(job.id, result))
            if result.comments:
                rc.padding = (0, 0, 0, 2)
                rc.para("{0}".format(result.comments))
                rc.reset()


class SRUCommand(PlainBoxCommand):

    """
    Command for running Stable Release Update (SRU) tests.

    Stable release updates are periodic fixes for nominated bugs that land in
    existing supported Ubuntu releases. To ensure a certain level of quality
    all SRU updates affecting hardware enablement are automatically tested
    on a pool of certified machines.
    """

    gettext_domain = "checkbox-ng"

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        # This command does funky things to the command line parser and it
        # needs to load the config subsystem *early* so let's just load it now.
        self.config = config_loader()

    def invoked(self, ns):
        """Method called when the command is invoked."""
        return sru(self.config).main(sys.argv[2:], exit=False)

    def register_parser(self, subparsers):
        """Method called to register command line arguments."""
        parser = subparsers.add_parser(
            "sru", help=_("run automated stable release update tests"))
        parser.set_defaults(command=self)
        sru(self.config).register_arguments(parser)
