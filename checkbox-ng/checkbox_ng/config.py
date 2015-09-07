# This file is part of Checkbox.
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
:mod:`checkbox_ng.config` -- CheckBoxNG configuration
=====================================================
"""

from gettext import gettext as _
import itertools
import os

from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.secure import config


SECURE_ID_PATTERN = r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$"


class CheckBoxConfig(PlainBoxConfig):
    """
    Configuration for checkbox-ng
    """

    secure_id = config.Variable(
        section="sru",
        help_text=_("Secure ID of the system"),
        validator_list=[config.PatternValidator(SECURE_ID_PATTERN)])

    submit_to_c3 = config.Variable(
        section="submission",
        help_text=_("Whether to send the submission data to c3"))

    submit_to_hexr = config.Variable(
        section="submission",
        help_text=_("Whether to also send the submission data to HEXR"),
        kind=bool)

    # TODO: Add a validator to check if email looks fine
    email_address = config.Variable(
        section="sru",
        help_text=_("Email address to log into the Launchpad HWDB"))

    # TODO: Add a validator to check if URL looks fine
    c3_url = config.Variable(
        section="sru",
        help_text=_("URL of the certification website"),
        default="https://certification.canonical.com/submissions/submit/")

    # TODO: Add a validator to check if URL looks fine
    lp_url = config.Variable(
        section="sru",
        help_text=_("URL of the launchpad hardware database"),
        default="https://launchpad.net/+hwdb/+submit")

    fallback_file = config.Variable(
        section="sru",
        help_text=_("Location of the fallback file"))

    whitelist = config.Variable(
        section="sru",
        help_text=_("Optional whitelist with which to run SRU testing"))

    test_plan = config.Variable(
        section="sru",
        help_text=_("Optional test plan with which to run SRU testing"))

    staging = config.Variable(
        section="sru",
        kind=bool,
        default=False,
        help_text=_("Send the data to non-production test server"))

    class Meta(PlainBoxConfig.Meta):
        # TODO: properly depend on xdg and use real code that also handles
        # XDG_CONFIG_HOME.
        #
        # NOTE: filename_list is composed of checkbox and plainbox variables,
        # mixed so that:
        # - checkbox takes precedence over plainbox
        # - ~/.config takes precedence over /etc
        filename_list = list(
            itertools.chain(
                *zip(
                    PlainBoxConfig.Meta.filename_list, (
                        '/etc/xdg/checkbox.conf',
                        os.path.expanduser('~/.config/checkbox.conf')))))
