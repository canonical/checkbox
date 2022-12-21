# content of conftest.py
import inspect
import logging
from pathlib import Path

import pytest
from loguru._logger import Core
from metabox.core.machine import MachineConfig
from metabox.core.runner import Runner
from metabox.core.scenario import Scenario


def pytest_addoption(parser):
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
    if (
        inspect.isclass(obj) and issubclass(obj, Scenario) and
        "Scenario" not in obj.__name__
    ):
        variants = []
        for scn in collector.config.runner.scn_variants:
            print(name, scn.name)
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
    logger = logging.getLogger('ws4py')
    logger.disabled = True
    runner = Runner(config.option)
    runner.collect()
    config.runner = runner


def pytest_collection_finish(session):
    if session.config.option.collectonly:
        return
    runner = session.config.runner
    runner.scn_variants = [i.scn for i in session.items]
    runner.setup()


class MetaboxItem(pytest.Item):
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
