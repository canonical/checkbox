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
from plainbox.impl.secure.qualifiers import WhiteList
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

    def get_whitelist_from_file(self, filename, stream=None):
        """
        Load a whitelist from a file, with special behavior.

        :param filename:
            name of the file to load
        :param stream:
            (optional) pre-opened stream pointing at the whitelist
        :returns:
            The loaded whitelist or None if loading fails for any reason

        This function implements special loading behavior for whitelists that
        makes them inherit the implicit namespace of the provider they may be a
        part of. Before loading the whitelist directly from the file, all known
        providers are interrogated to see if any of them has a whitelist that
        was loaded from the same file (as indicated by os.path.realpath())

        The stream argument can be provided if the caller already has an open
        file object, which is typically the case when working with argparse.
        """
        # Look up a whitelist with the same name in any of the providers
        wanted_realpath = os.path.realpath(filename)
        for provider in self.provider_list:
            for whitelist in provider.whitelist_list:
                if (whitelist.origin is not None
                        and whitelist.origin.source is not None
                        and isinstance(whitelist.origin.source,
                                       FileTextSource)
                        and os.path.realpath(
                            whitelist.origin.source.filename) ==
                        wanted_realpath):
                    logger.debug(
                        _("Using whitelist %r obtained from provider %r"),
                        whitelist.name, provider)
                    return whitelist
        # Or load it directly
        try:
            if stream is not None:
                return WhiteList.from_string(stream.read(), filename=filename)
            else:
                return WhiteList.from_file(filename)
        except Exception as exc:
            logger.warning(
                _("Unable to load whitelist %r: %s"), filename, exc)

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
        # Add whitelists
        for whitelist_file in ns.whitelist:
            qualifier = self.get_whitelist_from_file(
                whitelist_file.name, whitelist_file)
            if qualifier is not None:
                qualifier_list.append(qualifier)
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
