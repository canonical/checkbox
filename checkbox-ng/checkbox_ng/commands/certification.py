# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`checkbox_ng.commands.certification` -- Certification sub-command
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from gettext import gettext as _
from logging import getLogger

from plainbox.impl.commands.check_config import CheckConfigInvocation
from plainbox.impl.secure.config import Unset, ValidationError
from requests.exceptions import ConnectionError, InvalidSchema, HTTPError

from checkbox_ng.certification import CertificationTransport
from checkbox_ng.certification import InvalidSecureIDError
from checkbox_ng.commands.cli import CliCommand
from checkbox_ng.commands.oldcli import CliInvocation


logger = getLogger("checkbox.ng.commands.certification")


class CertificationInvocation(CliInvocation):
    """
    Helper class instantiated to perform a particular invocation of the
    certification command. Unlike the certification command itself, this
    class is instantiated each time.
    """

    def save_results(self, session):
        super().save_results(session)
        if self.config.secure_id is Unset:
            again = True
            if not self.is_interactive:
                again = False
            while again:
                if self.ask_user(
                    _("\nSubmit results to certification.canonical.com?"),
                    # TRANSLATORS: These are meant to stand for yes and no
                    (_('y'), _('n'))
                ).lower() == _("y"):
                    try:
                        self.config.secure_id = input(_("Secure ID: "))
                    except ValidationError:
                        print(
                            _("ERROR: Secure ID must be 15 or 18-character"
                              " alphanumeric string"))
                    else:
                        again = False
                        self.submit_results(session)
                else:
                    again = False
        else:
            # Automatically try to submit results if the secure_id is valid
            self.submit_results(session)

    def submit_results(self, session):
        # TRANSLATORS: Do not translate the {} format markers.
        print(_("Submitting results to {0} for secure_id {1})").format(
            self.config.c3_url, self.config.secure_id))
        options_string = "secure_id={0}".format(self.config.secure_id)
        # Create the transport object
        try:
            transport = CertificationTransport(
                self.config.c3_url, options_string)
        except InvalidSecureIDError as exc:
            print(exc)
            return False
        with open(self.submission_file) as stream:
            try:
                # Send the data, reading from the fallback file
                result = transport.send(stream, self.config)
                if 'url' in result:
                    # TRANSLATORS: Do not translate the {} format marker.
                    print(_("Successfully sent, submission status"
                            " at {0}").format(result['url']))
                else:
                    # TRANSLATORS: Do not translate the {} format marker.
                    print(_("Successfully sent, server response"
                            ": {0}").format(result))

            except InvalidSchema as exc:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Invalid destination URL: {0}").format(exc))
            except ConnectionError as exc:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Unable to connect to destination"
                        " URL: {0}").format(exc))
            except HTTPError as exc:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Server returned an error when "
                        "receiving or processing: {0}").format(exc))
            except IOError as exc:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Problem reading a file: {0}").format(exc))


class CertificationCommand(CliCommand):
    """
    Command for running certification tests using the command line UI.

    This class allows submissions to the certification database.
    """

    def invoked(self, ns):
        # Copy command-line arguments over configuration variables
        try:
            if ns.secure_id:
                self.config.secure_id = ns.secure_id
            if ns.c3_url:
                self.config.c3_url = ns.c3_url
        except ValidationError as exc:
            print(_("Configuration problems prevent running tests"))
            print(exc)
            return 1
        # Run check-config, if requested
        if ns.check_config:
            retval = CheckConfigInvocation(self.config).run()
            return retval
        return CertificationInvocation(self.provider_list, self.config,
                                       self.settings, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(self.settings['subparser_name'],
                                       help=self.settings['subparser_help'])
        parser.set_defaults(command=self)
        parser.add_argument(
            "--check-config",
            action="store_true",
            help=_("run check-config"))
        parser.add_argument(
            '--not-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        group = parser.add_argument_group(_("certification-specific options"))
        # Set defaults from based on values from the config file
        group.set_defaults(c3_url=self.config.c3_url)
        if self.config.secure_id is not Unset:
            group.set_defaults(secure_id=self.config.secure_id)
        group.add_argument(
            '--secure-id', metavar="SECURE-ID",
            action='store',
            # TRANSLATORS: Do not translate %(default)s
            help=(_("associate submission with a machine using this"
                    " SECURE-ID (%(default)s)")))
        group.add_argument(
            '--destination', metavar="URL",
            dest='c3_url',
            action='store',
            # TRANSLATORS: Do not translate %(default)s
            help=(_("POST the test report XML to this URL"
                    " (%(default)s)")))
        group.add_argument(
            '--staging',
            dest='c3_url',
            action='store_const',
            const='https://certification.staging.canonical.com'
                  '/submissions/submit/',
            # TRANSLATORS: Do not translate --destination
            help=_('override --destination to use the staging certification '
                   'website'))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
