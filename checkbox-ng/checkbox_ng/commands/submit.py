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

from argparse import ArgumentTypeError, FileType
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

    def __init__(self, config, ns):
        self.config = config
        self.ns = ns

    def run(self):
        options_string = "secure_id={0}".format(self.ns.secure_id)
        transport = CertificationTransport(self.config.c3_url, options_string)

        try:
            result = transport.send(self.ns.submission)
        except TransportError as exc:
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
    submit test results to Canonical certification website

    This command sends the XML results file to the Certification website.
    """))
class SubmitCommand(PlainBoxCommand):

    gettext_domain = "checkbox-ng"

    def __init__(self, config):
        self.config = config

    def invoked(self, ns):
        return SubmitInvocation(self.config, ns).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        parser.set_defaults(command=self)
        if self.config.secure_id is not Unset:
            parser.set_defaults(secure_id=self.config.secure_id)

        def secureid(secure_id):
            if not re.match(SECURE_ID_PATTERN, secure_id):
                raise ArgumentTypeError(
                    _("must be 15 or 18-character alphanumeric string"))
            return secure_id

        parser.add_argument(
            'secure_id', metavar=_("SECURE-ID"),
            type=secureid,
            help=_("associate submission with a machine using this SECURE-ID"))
        parser.add_argument(
            'submission', type=FileType('r'),
            help=_("The path to the results xml file"))
