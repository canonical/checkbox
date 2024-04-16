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
from itertools import product
from contextlib import suppress

from loguru import logger
from metabox.core.aggregator import aggregator
from metabox.core.configuration import read_config
from metabox.core.configuration import guess_source_uri
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
        logger.add(sys.stdout, format=self._formatter, level=args.log_level)
        logger.level("TRACE", color="<w><dim>")
        logger.level("DEBUG", color="<w><dim>")
        # session config
        if not args.config.exists():
            raise SystemExit("Config file not found!")
        else:
            self.config = read_config(args.config)
            self.config = guess_source_uri(self.config)
            validate_config(self.config)
        # effective set of machine configs required by scenarios
        self.combo = set()
        self.scn_variants = None
        self.machine_provider = None
        self.failed = False
        self.tags = set(self.args.tags or [])
        self.exclude_tags = set(self.args.exclude_tags or [])
        self.hold_on_fail = self.args.hold_on_fail
        self.debug_machine_setup = self.args.debug_machine_setup
        self.dispose = not self.args.do_not_dispose
        self.use_existing = self.args.use_existing
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
            if v.mode == "remote":
                controller_config = self.config["controller"].copy()
                agent_config = self.config["agent"].copy()
                controller_release, agent_release = v.releases
                controller_config["alias"] = controller_release
                agent_config["alias"] = agent_release
                revisions = self._get_revisions_jobs()
                for controller_revision, agent_revision in revisions:
                    controller_config["revision"] = controller_revision
                    self.combo.add(
                        MachineConfig("controller", controller_config)
                    )
                    agent_config["revision"] = agent_revision
                    self.combo.add(MachineConfig("agent", agent_config))
            elif v.mode == "local":
                local_config = self.config["local"].copy()
                local_config["alias"] = v.releases[0]
                self.combo.add(MachineConfig("local", local_config))

    def _filter_scn_by_tags(self):
        filtered_suite = []
        for scn in self.scn_variants:
            # Add scenario name,file,dir,mode and releases as implicit tags
            scn_tags = set(scn.name.split("."))
            scn_tags.add(scn.mode)
            scn_tags.update(scn.releases)
            scn_tags.update(getattr(scn, "tags", set()))
            matched_tags = scn_tags.intersection(self.tags)
            if (matched_tags or not self.tags) and not scn_tags.intersection(
                self.exclude_tags
            ):
                filtered_suite.append(scn)
        return filtered_suite

    def _override_filter_or_get(self, override, root_key, inner_key):
        with suppress(KeyError):
            values = set(override[root_key][inner_key])
            requested = set(self.config[root_key][inner_key])
            # get all values that are in this run config and
            #  requested by the scenario override
            return list(values & requested)
        return self.config[root_key][inner_key]

    def _get_revisions_jobs(self):
        """
        If revision testing is requested, returns revisions to test
        for controller or/and agent
        """
        controller_revisions = ["current"]
        agent_revisions = ["current"]
        if self.config["controller"].get("revision_testing", False):
            controller_revisions.append("origin/main")
        if self.config["agent"].get("revision_testing", False):
            agent_revisions.append("origin/main")
        return product(controller_revisions, agent_revisions)

    def setup(self):
        self.scenarios = aggregator.all_scenarios()
        self.scn_variants = []
        # Generate all scenario variants
        scenarios_modes_origins = (
            (scenario_cls, mode, origin)
            for scenario_cls in self.scenarios
            for (mode, origin) in product(
                scenario_cls.modes, scenario_cls.origins
            )
        )

        for scenario_cls, mode, origin in scenarios_modes_origins:
            mode_to_role = {
                "remote": "controller",
                "local": "local",
                "agent": "agent",
            }
            role = mode_to_role[mode]
            if role not in self.config:
                logger.debug(
                    "Skipping a scenario: [{}] {}", mode, scenario_cls.name
                )
                continue
            if origin != self.config[role]["origin"]:
                logger.debug(
                    "Skipping a scenario: [{}][{}] {}",
                    mode,
                    origin,
                    scenario_cls.name,
                )
                continue
            scn_config = scenario_cls.config_override
            if mode == "remote":
                controller_releases = self._override_filter_or_get(
                    scn_config, "controller", "releases"
                )
                agent_releases = self._override_filter_or_get(
                    scn_config, "agent", "releases"
                )
                releases = list(
                    (mode, r_alias, s_alias)
                    for (r_alias, s_alias) in product(
                        controller_releases,
                        agent_releases,
                    )
                )
                revisions = self._get_revisions_jobs()
                # names to kwargs
                revisions = (
                    {
                        "controller_revision": controller_revision,
                        "agent_revision": agent_revision,
                    }
                    for (controller_revision, agent_revision) in revisions
                )
                releases = product(releases, revisions)
            elif mode == "local":
                releases = (
                    # empty dict because local mode has no kwargs yet
                    ((mode, alias), {})
                    for alias in self._override_filter_or_get(
                        scn_config, mode, "releases"
                    )
                )
            else:
                raise ValueError("Unknown mode {}".format(mode))
            for args, kwargs in releases:
                logger.debug(
                    "Adding scenario: [{}][{}] {}",
                    mode,
                    origin,
                    scenario_cls.name,
                )
                self.scn_variants.append(scenario_cls(*args, **kwargs))
        if self.args.tags or self.args.exclude_tags:
            if self.args.tags:
                logger.info(
                    "Including scenario tag(s): %s"
                    % ", ".join(sorted(self.args.tags))
                )
            if self.args.exclude_tags:
                logger.info(
                    "Excluding scenario tag(s): %s"
                    % ", ".join(sorted(self.args.exclude_tags))
                )
            self.scn_variants = self._filter_scn_by_tags()
        if not self.scn_variants:
            logger.warning("No match found!")
            raise SystemExit(1)
        self._gather_all_machine_spec()
        logger.debug("Combo: {}", self.combo)
        self.machine_provider = LxdMachineProvider(
            self.config,
            self.combo,
            self.debug_machine_setup,
            self.dispose,
            use_existing=self.use_existing,
        )
        self.machine_provider.setup()

    def _load(self, mode, release_alias):
        config = self.config[mode].copy()
        config["alias"] = release_alias
        config["role"] = mode
        return self.machine_provider.get_machine_by_config(
            MachineConfig(mode, config)
        )

    def _get_scenario_description(self, scn):
        scenario_description_fmt = "[{mode}][{release_version}] {name}"
        if scn.mode == "local":
            return scenario_description_fmt.format(
                mode=scn.mode, release_version=scn.releases, name=scn.name
            )
        controller_rv = scn.releases[0]
        agent_rv = scn.releases[1]
        if scn.controller_revision != "current":
            controller_rv += " {}".format(scn.controller_revision)
        if scn.agent_revision != "current":
            agent_rv += " {}".format(scn.agent_revision)
        return scenario_description_fmt.format(
            mode=scn.mode,
            release_version="({}, {})".format(controller_rv, agent_rv),
            name=scn.name,
        )

    def run(self):
        startTime = time.perf_counter()
        total = len(self.scn_variants)
        for idx, scn in enumerate(self.scn_variants, 1):
            if scn.mode == "remote":
                scn.controller_machine = self._load(
                    "controller", scn.releases[0]
                )
                scn.agent_machine = self._load("agent", scn.releases[1])
                scn.controller_machine.rollback_to("provisioned")
                scn.agent_machine.rollback_to("provisioned")
                if scn.launcher:
                    scn.controller_machine.put(scn.LAUNCHER_PATH, scn.launcher)
                scn.agent_machine.start_user_session()
            elif scn.mode == "local":
                scn.local_machine = self._load("local", scn.releases[0])
                scn.local_machine.rollback_to("provisioned")
                if scn.launcher:
                    scn.local_machine.put(scn.LAUNCHER_PATH, scn.launcher)
                scn.local_machine.start_user_session()

            scenario_description = self._get_scenario_description(scn)
            logger.info(
                "Starting scenario ({}/{}): {}".format(
                    idx, total, scenario_description
                )
            )
            scn.run()
            if not scn.has_passed():
                self.failed = True
                logger.error(scenario_description + " scenario has failed.")

                # let's escape < from the output to avoid confusing loguru
                # loguru assumes that <> is used for colorizing
                output = scn.get_output_streams().strip().replace("<", "\<")

                logger.error("Scenario output:\n" + output)
                if self.hold_on_fail:
                    if scn.mode == "remote":
                        msg = (
                            "You may hop onto the target machines by issuing "
                            "the following commands:\n{}\n{}\n"
                            "Press enter to continue testing"
                        ).format(
                            scn.controller_machine.get_connecting_cmd(),
                            scn.agent_machine.get_connecting_cmd(),
                        )
                    elif scn.mode == "local":
                        msg = (
                            "You may hop onto the target machine by issuing "
                            "the following command:\n{}\n"
                            "Press enter to continue testing"
                        ).format(scn.local_machine.get_connecting_cmd())
                    print(msg)
                    input()
            else:
                logger.success(scenario_description + " scenario has passed.")
            self.machine_provider.cleanup()
        del self.machine_provider
        stopTime = time.perf_counter()
        timeTaken = stopTime - startTime
        print("-" * 80)
        form = "scenario" if total == 1 else "scenarios"
        status = "Ran {} {} in {:.3f}s".format(total, form, timeTaken)
        if self.wasSuccessful():
            logger.success(status)
        else:
            logger.error(status)

    def _run_single_scn(self, scenario_cls, mode, *releases):
        pass

    def wasSuccessful(self):
        return self.failed is False
