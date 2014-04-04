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

from logging import getLogger

from plainbox.impl.commands.check_config import CheckConfigInvocation
from plainbox.impl.secure.config import Unset, ValidationError
from requests.exceptions import ConnectionError, InvalidSchema, HTTPError

from checkbox_ng.certification import CertificationTransport
from checkbox_ng.certification import InvalidSecureIDError
from checkbox_ng.commands.cli import CliCommand, CliInvocation


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
                    "\nSubmit results to certification.canonical.com?",
                    ('y', 'n')
                ).lower() == "y":
                    try:
                        self.config.secure_id = input("Secure ID: ")
                    except ValidationError:
                        print(
                            "ERROR: Secure ID must be 15 or 18-character"
                            " alphanumeric string")
                    else:
                        again = False
                        self.submit_results(session)
                else:
                    again = False
        else:
            # Automatically try to submit results if the secure_id is valid
            self.submit_results(session)

    def submit_results(self, session):
        print("Submitting results to {0} for secure_id {1}".format(
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
                    print("Successfully sent, submission status at {0}".format(
                          result['url']))
                else:
                    print("Successfully sent, server response: {0}".format(
                          result))

            except InvalidSchema as exc:
                print("Invalid destination URL: {0}".format(exc))
            except ConnectionError as exc:
                print("Unable to connect to destination URL: {0}".format(exc))
            except HTTPError as exc:
                print(("Server returned an error when "
                       "receiving or processing: {0}").format(exc))
            except IOError as exc:
                print("Problem reading a file: {0}".format(exc))


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
            print("Configuration problems prevent running tests")
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
            help="Run check-config")
        parser.add_argument(
            '--not-interactive', action='store_true',
            help="Skip tests that require interactivity")
        group = parser.add_argument_group("certification-specific options")
        # Set defaults from based on values from the config file
        group.set_defaults(c3_url=self.config.c3_url)
        if self.config.secure_id is not Unset:
            group.set_defaults(secure_id=self.config.secure_id)
        group.add_argument(
            '--secure-id', metavar="SECURE-ID",
            action='store',
            help=("Associate submission with a machine using this"
                  " SECURE-ID (%(default)s)"))
        group.add_argument(
            '--destination', metavar="URL",
            dest='c3_url',
            action='store',
            help=("POST the test report XML to this URL"
                  " (%(default)s)"))
        group.add_argument(
            '--staging',
            dest='c3_url',
            action='store_const',
            const='https://certification.staging.canonical.com'
                  '/submissions/submit/',
            help='Override --destination to use the staging certification '
                 'website')
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
