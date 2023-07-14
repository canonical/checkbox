import textwrap
from importlib.resources import read_text

from metabox.core.actions import AssertPrinted
from metabox.core.actions import Start
from metabox.core.actions import Put
from metabox.core.actions import RunCmd
from metabox.core.scenario import Scenario
from metabox.core.utils import tag

from . import config_files


@tag("daemon", "normal_user")
class DaemonNormalUserSetInLauncherNoConfig(Scenario):
    modes = ["controller"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        [daemon]
        normal_user = launcher_user
        """
    )
    steps = [
        RunCmd("sudo useradd launcher_user"),
        Start(),
        AssertPrinted("user:launcher_user"),
    ]


@tag("daemon", "normal_user")
class DaemonNormalUserSetInConfig(Scenario):
    modes = ["controller"]
    checkbox_conf_xdg = read_text(config_files, "daemon_section_only.conf")
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        """
    )
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg, target="agent"),
        RunCmd("sudo useradd config_user"),
        Start(),
        AssertPrinted("user:config_user"),
    ]


@tag("daemon", "normal_user")
class DaemonNormalUserOverwittenByLauncher(Scenario):
    modes = ["controller"]
    checkbox_conf_xdg = read_text(config_files, "daemon_section_only.conf")
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        [daemon]
        normal_user = launcher_user
        """
    )
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg, target="agent"),
        RunCmd("sudo useradd launcher_user"),
        Start(),
        AssertPrinted("user:launcher_user"),
    ]


@tag("daemon", "normal_user")
class DaemonNormalUserGuessed(Scenario):
    modes = ["controller"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        """
    )
    steps = [
        Start(),
        AssertPrinted("user:ubuntu"),
    ]


@tag("daemon", "normal_user")
class DaemonNormalUserDoesntExist(Scenario):
    modes = ["controller"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        [daemon]
        normal_user = testuser
        """
    )
    steps = [
        Start(),
        AssertPrinted("User 'testuser' doesn't exist!"),
    ]

@tag("daemon", "agent", "normal_user")
class NewNameForDaemonWorks(Scenario):
    modes = ["controller"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        [agent]
        normal_user = testuser
        """
    )
    steps = [
        Start(),
        AssertPrinted("User 'testuser' doesn't exist!"),
    ]

@tag("daemon", "agent", "normal_user")
class DeprecatedDaemon(Scenario):
    modes = ["controller"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::whoami_as_user_tp
        forced = yes
        [test selection]
        forced = yes
        [daemon]
        """
    )
    steps = [
        Start(),
        AssertPrinted("daemon section name is deprecated. Use agent instead."),
    ]
