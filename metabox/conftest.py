# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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
This pytest configuration file defines a custom test item `MetaboxItem` that
allows running Metabox scenarios.
"""

import inspect
import logging
from pathlib import Path

import pytest
from loguru._logger import Core
from metabox.core.machine import MachineConfig
from metabox.core.runner import Runner
from metabox.core.scenario import Scenario


def pytest_addoption(parser):
    """
    This pytest hook defines command-line options for Metabox, such as
    specifying the configuration file to use, the scenario logging level, and
    whether to delete LXD containers after a run.
    """
    parser.addoption(
        '--config', metavar='CONFIG', type=Path,
        help='Metabox configuration file'
    )
    parser.addoption(
        "--log-lvl", dest="scenario_log_level", choices=Core().levels.keys(),
        default='WARNING',
        help="Set the scenario logging level",
    )
    parser.addoption(
        '--do-not-dispose', action='store_true',
        help="Do not delete LXD containers after the run")
    parser.addoption(
        '--debug-machine-setup', action='store_true',
        help="Turn on verbosity during machine setup. "
             "Only works with --log TRACE")


def pytest_pycollect_makeitem(collector, name, obj):
    """
    This function is a pytest hook that allows for the dynamic creation of test
    items. It creates a pytest item for each Scenario subclass that exists in
    the Metabox project.
    """
    if (
        inspect.isclass(obj) and issubclass(obj, Scenario) and
        "Scenario" not in obj.__name__
    ):
        variants = []
        for scn in collector.config.runner.scn_variants:
            if (
                "{}.{}".format(
                    collector.parent.name, collector.path.stem) in scn.name and
                scn.name.endswith('.' + name)
            ):
                variants.append(
                    MetaboxItem.from_parent(
                        collector,
                        name=f"{name} [{scn.mode}]{scn.releases}",
                        scn=scn)
                    )
        return variants
    elif inspect.isclass(obj) and issubclass(obj, Scenario):
        return []


def pytest_configure(config):
    """
    Initialization of the Runner object with the command-line options passed to
    pytest.
    """
    logger = logging.getLogger('ws4py')
    logger.disabled = True
    runner = Runner(config.option)
    runner.collect()
    config.runner = runner


def pytest_collection_finish(session):
    """
    This hook is called once all tests have been collected.
    It sets up the runner with the collected scenarios.
    """
    if session.config.option.collectonly:
        return
    runner = session.config.runner
    runner.scn_variants = [i.scn for i in session.items]
    runner.setup()


class MetaboxItem(pytest.Item):
    """
    Custom pytest item for running a Scenario.
    It loads the  appropriate machine configurations based on the scenario
    variant and mode, sets up the machines, and runs the scenario.
    It also handles cleanup and reporting of any failures that occur during the
    run.
    """
    def __init__(self, *, scn, **kwargs):
        super().__init__(**kwargs)
        self.scn = scn

    def __repr__(self) -> str:
        return "<Scenario {}>".format(getattr(self, "name", None))

    def _load(self, mode, release_alias):
        config = self.config.runner.config[mode].copy()
        config['alias'] = release_alias
        config['role'] = mode
        return self.config.runner.machine_provider.get_machine_by_config(
            MachineConfig(mode, config))

    def runtest(self):
        scn = self.scn
        if scn.mode == "remote":
            scn.remote_machine = self._load("remote", scn.releases[0])
            scn.service_machine = self._load("service", scn.releases[1])
            scn.remote_machine.rollback_to('provisioned')
            scn.service_machine.rollback_to('provisioned')
            if scn.launcher:
                scn.remote_machine.put(scn.LAUNCHER_PATH, scn.launcher)
            scn.service_machine.start_user_session()
        elif scn.mode == "local":
            scn.local_machine = self._load("local", scn.releases[0])
            scn.local_machine.rollback_to('provisioned')
            if scn.launcher:
                scn.local_machine.put(scn.LAUNCHER_PATH, scn.launcher)
            scn.local_machine.start_user_session()
        scn.run()
        if not scn.has_passed():
            if self.config.option.maxfail:
                if scn.mode == "remote":
                    msg = (
                        "You may hop onto the target machines by issuing "
                        "the following commands:\n{}\n{}").format(
                            scn.remote_machine.get_connecting_cmd(),
                            scn.service_machine.get_connecting_cmd())
                elif scn.mode == "local":
                    msg = (
                        "You may hop onto the target machine by issuing "
                        "the following command:\n{}").format(
                            scn.local_machine.get_connecting_cmd())
                print(msg)
            else:
                self.config.runner.machine_provider.cleanup()
            raise MetaboxException(
                self, self.scn.problems)
        self.config.runner.machine_provider.cleanup()

    def repr_failure(self, excinfo):
        """Called when self.runtest() raises an exception."""
        if isinstance(excinfo.value, MetaboxException):
            err_msg = "Scenario execution failed\n    "
            err_msg += "\n    ".join(excinfo.value.args[1])
            return err_msg

    def reportinfo(self):
        return self.path, 0, f"Scenario: {self.name}"


class MetaboxException(Exception):
    """Custom exception for error reporting."""
