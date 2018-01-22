# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.commands.inv_checkbox` -- mix-in for checkbox invocations
=============================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import os
from logging import getLogger
import itertools

from plainbox.i18n import gettext as _
from plainbox.impl.secure.origin import CommandLineTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.secure.rfc822 import FileTextSource

logger = getLogger("plainbox.commands.checkbox")


class CheckBoxInvocationMixIn:

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        self.config_loader = config_loader
        self._provider_list = None
        self._config = None

    @property
    def provider_list(self):
        if self._provider_list is None:
            self._provider_list = self.provider_loader()
        return self._provider_list

    @property
    def config(self):
        if self._config is None:
            self._config = self.config_loader()
        return self._config

    def get_job_list(self, ns):
        """
        Load and return a list of JobDefinition instances
        """
        return list(
            itertools.chain(*[p.job_list for p in self.provider_list]))

    def _get_matching_job_list(self, ns, job_list):
        logger.debug("_get_matching_job_list(%r, %r)", ns, job_list)
        qualifier_list = []
        # Add the test plan
        if ns.test_plan is not None:
            # Uh, dodgy, recreate a list of providers from the list of jobs we
            # know about here. This code needs to be re-factored to use the
            # upcoming provider store class.
            for provider in {job.provider for job in job_list}:
                for unit in provider.id_map[ns.test_plan]:
                    if unit.Meta.name == 'test plan':
                        qualifier_list.append(unit.get_qualifier())
                        break
            else:
                logger.debug(_("There is no test plan: %s"), ns.test_plan)
        # Add all the --include jobs
        for pattern in ns.include_pattern_list:
            origin = Origin(CommandLineTextSource('-i', pattern), None, None)
            try:
                qualifier = RegExpJobQualifier(
                    '^{}$'.format(pattern), origin, inclusive=True)
            except Exception as exc:
                logger.warning(
                    _("Incorrect pattern %r: %s"), pattern, exc)
            else:
                qualifier_list.append(qualifier)
        # Add all the --exclude jobs
        for pattern in ns.exclude_pattern_list:
            origin = Origin(CommandLineTextSource('-x', pattern), None, None)
            try:
                qualifier = RegExpJobQualifier(
                    '^{}$'.format(pattern), origin, inclusive=False)
            except Exception as exc:
                logger.warning(
                    _("Incorrect pattern %r: %s"), pattern, exc)
            else:
                qualifier_list.append(qualifier)
        logger.debug("select_jobs(%r, %r)", job_list, qualifier_list)
        return select_jobs(job_list, qualifier_list)
