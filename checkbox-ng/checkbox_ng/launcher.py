# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
:mod:`checkbox_ng.launcher` -- launcher definition
==================================================
"""

from gettext import gettext as _
import logging

from plainbox.impl.secure import config
from plainbox.impl.transport import get_all_transports


logger = logging.getLogger("checkbox.ng.launcher")


class LauncherDefinition(config.Config):
    """
    Launcher definition.

    Launchers are small executables using one of the available user interfaces
    as the interpreter. This class contains all the available options that can
    be set inside the launcher, that will affect the user interface at runtime.
    """

    title = config.Variable(
        section="welcome",
        help_text=_("Application Title"))

    text = config.Variable(
        section="welcome",
        help_text=_("Welcome Message"))

    whitelist_filter = config.Variable(
        section="suite",
        # TODO: valid regexp text validator
        help_text=_("Pattern that whitelists need to match to be displayed"))

    input_type = config.Variable(
        section="submission",
        # TODO: probably a choice validator
        help_text=_("Type of the input field?"))

    ok_btn_text = config.Variable(
        section="submission",
        help_text=_("Label on the 'send' button"))

    submit_to_hexr = config.Variable(
        section="submission",
        kind=bool,
        # TODO: default?
        help_text=_("If enabled then test results will be also sent to HEXR"))

    xml_export_path = config.Variable(
        section="exporter",
        help_text=_("Filename of the exported XML documente"))

    submit_to = config.Variable(
        section="transport",
        validator_list=[config.ChoiceValidator(get_all_transports().keys())],
        help_text=_("Where to submit the test results to"))

    config_filename = config.Variable(
        section="config",
        help_text=_("Name of custom configuration file"))
