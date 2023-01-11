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
import sys
import time

from loguru import logger
from metabox.core.aggregator import aggregator
from metabox.core.configuration import read_config
from metabox.core.configuration import validate_config
from metabox.core.lxd_provider import LxdMachineProvider
from metabox.core.machine import MachineConfig

logger = logger.opt(colors=True)


class Runner:
    """Metabox scenario discovery and runner."""

    def __init__(self, args):
        self.args = args
        # logging
        logger.remove()
        logger.add(
            sys.stdout,
            format=self._formatter,
            level=args.scenario_log_level)
        logger.level("TRACE", color="<w><dim>")
        logger.level("DEBUG", color="<w><dim>")
        # session config
        if not args.config or not args.config.exists():
            raise SystemExit('Config file not found!')
        else:
            self.config = read_config(args.config)
            validate_config(self.config)
        # effective set of machine configs required by scenarios
        self.combo = set()
        self.scn_variants = []
        self.machine_provider = None
        self.failed = False
        try:
            self.tags = set(self.args.tags or [])
        except AttributeError:
            self.tags = []
        try:
            self.exclude_tags = set(self.args.exclude_tags or [])
        except AttributeError:
            self.exclude_tags = []
        try:
            self.hold_on_fail = self.args.hold_on_fail
        except AttributeError:
            self.hold_on_fail = False
        self.debug_machine_setup = self.args.debug_machine_setup
        self.dispose = not self.args.do_not_dispose
        aggregator.load_all()

    def _formatter(self, record):
        if record["level"].no < 10:
            return "<level>{message}</level>\n"
        else:
            return (
                "{time:HH:mm:ss} | <level>{level: <8}</level> "
                "<level>{message}</level>\n"
            )

    def _gather_all_machine_spec(self):
        for v in self.scn_variants:
            if v.mode == 'remote':
                remote_config = self.config['remote'].copy()
                service_config = self.config['service'].copy()
                remote_release, service_release = v.releases
                remote_config['alias'] = remote_release
                service_config['alias'] = service_release
                self.combo.add(MachineConfig('remote', remote_config))
                self.combo.add(MachineConfig('service', service_config))
            elif v.mode == 'local':
                local_config = self.config['local'].copy()
                local_config['alias'] = v.releases[0]
                self.combo.add(MachineConfig('local', local_config))

    def _filter_scn_by_tags(self):
        filtered_suite = []
        for scn in self.scn_variants:
            # Add scenario name,file,dir,mode and releases as implicit tags
            scn_tags = set(scn.name.split('.'))
            scn_tags.add(scn.mode)
            scn_tags.update(scn.releases)
            scn_tags.update(getattr(scn, 'tags', set()))
            matched_tags = scn_tags.intersection(self.tags)
            if (
                (matched_tags or not self.tags) and not
                scn_tags.intersection(self.exclude_tags)
            ):
                filtered_suite.append(scn)
        return filtered_suite

    def collect(self):
        self.scenarios = aggregator.all_scenarios()
        # Generate all scenario variants
        for scenario_cls in self.scenarios:
            for mode in scenario_cls.mode:
                if mode not in self.config:
                    logger.debug(
                        "Skipping a scenario: [{}] {}",
                        mode, scenario_cls.name)
                    continue
                scn_config = scenario_cls.config_override
                if mode == 'remote':
                    try:
                        remote_releases = scn_config['remote']['releases']
                    except KeyError:
                        remote_releases = self.config['remote']['releases']
                    try:
                        service_releases = scn_config['service']['releases']
                    except KeyError:
                        service_releases = self.config['service']['releases']
                    for r_alias in self.config['remote']['releases']:
                        if r_alias not in remote_releases:
                            continue
                        for s_alias in self.config['service']['releases']:
                            if s_alias not in service_releases:
                                continue
                            self.scn_variants.append(
                                scenario_cls(mode, r_alias, s_alias))
                elif mode == 'local':
                    try:
                        local_releases = scn_config[mode]['releases']
                    except KeyError:
                        local_releases = self.config[mode]['releases']
                    for alias in self.config[mode]['releases']:
                        if alias not in local_releases:
                            continue
                        self.scn_variants.append(scenario_cls(mode, alias))
        if self.tags or self.exclude_tags:
            if self.tags:
                logger.info('Including scenario tag(s): %s' % ', '.join(
                    sorted(self.tags)))
            if self.exclude_tags:
                logger.info('Excluding scenario tag(s): %s' % ', '.join(
                    sorted(self.exclude_tags)))
            self.scn_variants = self._filter_scn_by_tags()
            if not self.scn_variants:
                logger.warning('No match found!')
                raise SystemExit(1)

    def setup(self):
        self._gather_all_machine_spec()
        logger.debug("Combo: {}", self.combo)
        self.machine_provider = LxdMachineProvider(
            self.config, self.combo,
            self.debug_machine_setup, self.dispose)
        self.machine_provider.setup()

    def _load(self, mode, release_alias):
        config = self.config[mode].copy()
        config['alias'] = release_alias
        config['role'] = mode
        return self.machine_provider.get_machine_by_config(
                        MachineConfig(mode, config))

    def run(self):
        startTime = time.perf_counter()
        for scn in self.scn_variants:
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
            logger.info("Starting scenario: {}".format(scn.name))
            scn.run()
            if not scn.has_passed():
                self.failed = True
                logger.error("[{}][{}] {} scenario has failed.".format(
                    scn.mode, scn.releases, scn.name))
                if self.hold_on_fail:
                    if scn.mode == "remote":
                        msg = (
                            "You may hop onto the target machines by issuing "
                            "the following commands:\n{}\n{}\n"
                            "Press enter to continue testing").format(
                                scn.remote_machine.get_connecting_cmd(),
                                scn.service_machine.get_connecting_cmd())
                    elif scn.mode == "local":
                        msg = (
                            "You may hop onto the target machine by issuing "
                            "the following command:\n{}\n"
                            "Press enter to continue testing").format(
                                scn.local_machine.get_connecting_cmd())
                    print(msg)
                    input()
            else:
                logger.success("[{}][{}] {} scenario has passed.".format(
                    scn.mode, scn.releases, scn.name))
            self.machine_provider.cleanup()
        del self.machine_provider
        stopTime = time.perf_counter()
        timeTaken = stopTime - startTime
        print('-' * 80)
        total = len(self.scn_variants)
        status = "Ran {} scenario{} in {:.3f}s".format(
            total, total != 1 and "s" or "", timeTaken)
        if self.wasSuccessful():
            logger.success(status)
        else:
            logger.error(status)

    def _run_single_scn(self, scenario_cls, mode, *releases):
        pass

    def wasSuccessful(self):
        return self.failed is False
