# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
import textwrap
from importlib.resources import read_text

from metabox.core.actions import AssertPrinted
from metabox.core.actions import Put
from metabox.core.actions import Start
from metabox.core.scenario import Scenario
from metabox.core.utils import tag

from . import config_files


@tag("config", "transport")
class TransportSecureIDSetInLauncherOnly(Scenario):
    modes = ["controller"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        [ui]
        type = silent
        [test plan]
        unit = 2021.com.canonical.certification::basic-automated-passing
        forced = yes
        [test selection]
        forced = yes
        [transport:launcher_transport]
        type = submission-service
        staging = yes
        secure_id = launcher
        [exporter:json]
        unit = com.canonical.plainbox::json
        [report:launcher_report]
        transport = launcher_transport
        exporter = json
        """
    )
    steps = [Start(), AssertPrinted("launcher is not a valid secure_id")]


@tag("config", "transport")
class TransportSecureIDSetInConfigOnly(Scenario):
    modes = ["controller"]
    checkbox_conf_xdg = read_text(config_files, "custom_transport.conf")
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        [ui]
        type = silent
        [test plan]
        unit = 2021.com.canonical.certification::basic-automated-passing
        forced = yes
        [test selection]
        forced = yes
        """
    )
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg, target="agent"),
        Start(),
        AssertPrinted("config is not a valid secure_id"),
    ]


@tag("config", "transport")
class TransportSecureIDOverwrittenByLauncher(Scenario):
    modes = ["controller"]
    checkbox_conf_xdg = read_text(config_files, "custom_transport.conf")
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        [ui]
        type = silent
        [test plan]
        unit = 2021.com.canonical.certification::basic-automated-passing
        forced = yes
        [test selection]
        forced = yes
        [transport:launcher_transport]
        type = submission-service
        staging = yes
        secure_id = launcher
        [exporter:json]
        unit = com.canonical.plainbox::json
        [report:launcher_report]
        transport = launcher_transport
        exporter = json
        """
    )
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg, target="agent"),
        Start(),
        AssertPrinted("launcher is not a valid secure_id"),
    ]
