# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`checkbox_ng.commands.submit` -- the submit sub-command
============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import ArgumentTypeError
from plainbox.i18n import docstring
from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
import re

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.secure.config import Unset
from plainbox.impl.transport import TransportError

from checkbox_ng.certification import CertificationTransport
from checkbox_ng.config import SECURE_ID_PATTERN


class SubmitInvocation:
    """
    Helper class instantiated to perform a particular invocation of the submit
    command. Unlike the SRU command itself, this class is instantiated each
    time.
    """

    def __init__(self, ns):
        self.ns = ns

    def run(self):
        options_string = "secure_id={0}".format(self.ns.secure_id)
        transport = CertificationTransport(self.ns.url, options_string)

        try:
            with open(self.ns.submission, "r", encoding='utf-8') as subm_file:
                result = transport.send(subm_file)
        except (TransportError, OSError) as exc:
            raise SystemExit(exc)
        else:
            if 'url' in result:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Successfully sent, submission status"
                        " at {0}").format(result['url']))
            else:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Successfully sent, server response"
                        ": {0}").format(result))


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    submit test results to the Canonical certification website

    This command sends the XML results file to the Certification website.
    """))
class SubmitCommand(PlainBoxCommand):

    gettext_domain = "checkbox-ng"

    def __init__(self, config_loader):
        self.config = config_loader()

    def invoked(self, ns):
        return SubmitInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser("submit", help=_(
            "submit test results to the Canonical certification website"))
        self.register_arguments(parser)

    def register_arguments(self, parser):
        parser.set_defaults(command=self)
        parser.add_argument(
            'submission', help=_("The path to the results xml file"))
        self.register_optional_arguments(parser, required=True)

    def register_optional_arguments(self, parser, required=False):
        if self.config.secure_id is not Unset:
            parser.set_defaults(secure_id=self.config.secure_id)

        def secureid(secure_id):
            if not re.match(SECURE_ID_PATTERN, secure_id):
                raise ArgumentTypeError(
                    _("must be 15 or 18-character alphanumeric string"))
            return secure_id

        required_check = False
        if required:
            required_check = self.config.secure_id is Unset
        parser.add_argument(
            '--secure_id', metavar=_("SECURE-ID"),
            required=required_check,
            type=secureid,
            help=_("associate submission with a machine using this SECURE-ID"))

        # Interpret this setting here
        # Please remember the Unset.__bool__() return False
        # After Interpret the setting,
        # self.config.submit_to_c3 should has value or be Unset.
        try:
            if (self.config.submit_to_c3 and
                (self.config.submit_to_c3.lower() in ('yes', 'true') or
                    int(self.config.submit_to_c3) == 1)):
                # self.config.c3_url has a default value written in config.py
                parser.set_defaults(url=self.config.c3_url)
            else:
                # if submit_to_c3 is castable to int but not 1
                # this is still set as Unset
                # otherwise url requirement will be None
                self.config.submit_to_c3 = Unset
        except ValueError:
            # When submit_to_c3 is something other than 'yes', 'true',
            # castable to integer, it raises ValueError.
            # e.g. 'no', 'false', 'asdf' ...etc.
            # In this case, it is still set as Unset.
            self.config.submit_to_c3 = Unset

        required_check = False
        if required:
            required_check = self.config.submit_to_c3 is Unset
        parser.add_argument(
            '--url', metavar=_("URL"),
            required=required_check,
            help=_("destination to submit to"))
