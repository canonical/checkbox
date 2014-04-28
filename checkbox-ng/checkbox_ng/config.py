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

    # TODO: Add a validator to check if URL looks fine
    c3_url = config.Variable(
        section="sru",
        help_text=_("URL of the certification website"),
        default="https://certification.canonical.com/submissions/submit/")

    fallback_file = config.Variable(
        section="sru",
        help_text=_("Location of the fallback file"))

    whitelist = config.Variable(
        section="sru",
        help_text=_("Optional whitelist with which to run SRU testing"))

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


class CertificationConfig(CheckBoxConfig):
    """
    Configuration for canonical-certification
    """

    class Meta(CheckBoxConfig.Meta):
        # TODO: properly depend on xdg and use real code that also handles
        # XDG_CONFIG_HOME.
        #
        # NOTE: filename_list is composed of canonical-certification, checkbox
        # and plainbox variables, mixed so that:
        # - canonical-certification takes precedence over checkbox
        # - checkbox takes precedence over plainbox
        # - ~/.config takes precedence over /etc
        filename_list = list(
            itertools.chain(
                *zip(
                    itertools.islice(
                        CheckBoxConfig.Meta.filename_list, 0, None, 2),
                    itertools.islice(
                        CheckBoxConfig.Meta.filename_list, 1, None, 2),
                    ('/etc/xdg/canonical-certification.conf',
                        os.path.expanduser(
                            '~/.config/canonical-certification.conf')))))


class CDTSConfig(CheckBoxConfig):
    """
    Configuration for canonical-driver-test-suite (CDTS)
    """

    class Meta(CheckBoxConfig.Meta):
        # TODO: properly depend on xdg and use real code that also handles
        # XDG_CONFIG_HOME.
        #
        # NOTE: filename_list is composed of canonical-certification, checkbox
        # and plainbox variables, mixed so that:
        # - CDTS takes precedence over checkbox
        # - checkbox takes precedence over plainbox
        # - ~/.config takes precedence over /etc
        filename_list = list(
            itertools.chain(
                *zip(
                    itertools.islice(
                        CheckBoxConfig.Meta.filename_list, 0, None, 2),
                    itertools.islice(
                        CheckBoxConfig.Meta.filename_list, 1, None, 2),
                    ('/etc/xdg/canonical-driver-test-suite.conf',
                        os.path.expanduser(
                            '~/.config/canonical-driver-test-suite.conf')))))
