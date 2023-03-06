# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
This module implements a mechanism to auto-register metabox scenarios.
"""

import pkgutil

import metabox.scenarios
from loguru import logger


class _ScenarioAggregator:
    def __init__(self):
        self._scenarios = []

    def add_scenario(self, scenario_cls):
        """Add a scenario to the collection."""
        logger.debug("Registering a scenario: {}", scenario_cls.name)
        logger.debug("For following modes: {}", scenario_cls.modes)
        self._scenarios.append(scenario_cls)

    @staticmethod
    def load_all():
        """Import all modules so the scenarios can be auto-loaded."""
        path = metabox.scenarios.__path__
        for loader, name, _ in pkgutil.walk_packages(path):
            loader.find_module(name).load_module(name)

    def all_scenarios(self):
        """Return all available scenarios."""
        return self._scenarios


aggregator = _ScenarioAggregator()
