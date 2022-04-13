# This file is part of Checkbox.
#
# Copyright 2021-2022 Canonical Ltd.
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
"""
This module defines class for handling Checkbox configs.

If we ever need to add validators to config variables, the addition should be
done in VarSpec (the fourth 'field').
"""
import copy
import io
import logging
import os
import shlex

from configparser import ConfigParser
from collections import namedtuple, OrderedDict

logger = logging.getLogger(__name__)


class Configuration:
    """
    Checkbox configuration storing objects.

    Checkbox configs store various information on how to run the Checkbox.
    For instance what reports to generate, should the session be interactive,
    and many others. Look at CONFIG_SPEC for details.
    """
    def __init__(self, source=None):
        """Create a new configuration object filled with default values."""
        self.sections = OrderedDict()
        self._origins = dict()
        self._problems = []
        # sources is similar to origins, but instead of keeping an info on
        # each variable, we note what configs got read in general
        self._sources = [source] if source else []
        for section, contents in CONFIG_SPEC:
            if isinstance(contents, ParametricSection):
                # we don't know what the actual section name will be,
                # so let's wait with the creation until we know the full name
                continue
            if isinstance(contents, DynamicSection):
                self.sections[section] = DynamicSection()
            else:
                self.sections[section] = OrderedDict()
            self._origins[section] = dict()
            for name, spec in sorted(contents.items()):
                self.sections[section][name] = spec.default
                self._origins[section][name] = ''

    @property
    def environment(self):
        """Return contents of the environment section."""
        return self.sections['environment']

    @property
    def manifest(self):
        """Return contents of the manifest section."""
        return self.sections['manifest']

    @property
    def sources(self):
        """Return list of sources for this configuration."""
        return self._sources

    def get_strategy_kwargs(self):
        """Return custom restart strategy parameters."""
        kwargs = copy.deepcopy(self.sections['restart'])
        # [restart] section has the kwargs for the strategy initializer
        # and the 'strategy' which is not one, let's pop it
        kwargs.pop('strategy')
        return kwargs

    def notice_problem(self, problem):
        """ Record and log problem encountered when building configuration."""
        self._problems.append(problem)
        logger.warning(problem)

    def get_problems(self):
        """Return a list of problem as strings."""
        return self._problems

    def get_value(self, section, name):
        """Return a value of given `name` from given `section`,"""
        return self.sections[section][name]

    def get_origin(self, section, name):
        """Return origin of the value."""
        return self._origins[section][name]

    def update_from_another(self, configuration, origin):
        """
        Update this configuration with values from `configuration`.

        Only the values that are not defaults from 'configuration` are taken
        into account.
        """
        for section, variables in configuration.sections.items():
            for name in variables.keys():
                new_origin = configuration.get_origin(section, name)
                if new_origin:
                    if ':' in section and section not in self.sections.keys():
                        self.sections[section] = OrderedDict()
                        self._origins[section] = dict()
                    self.sections[section][name] = configuration.get_value(
                        section, name)
                    self._origins[section][name] = origin or new_origin
        self._sources += configuration.sources
        self._problems += configuration.get_problems()

    def dyn_set_value(self, section, name, value, origin):
        """Set a value of a var from a dynamic section."""
        if section == 'environment':
            name = name.upper()
        self.sections[section][name] = value
        self._origins[section][name] = origin

    def set_value(self, section, name, value, origin):
        """Set a new value for variable and update its origin."""
        # we are kind off guaranteed that section will be found in the spec
        # but let's make linters happy
        if section in self._DYNAMIC_SECTIONS:
            self.dyn_set_value(section, name, value, origin)
            return
        parametrized = False
        if ':' in section:
            parametrized = True
            prefix, _ = section.split(':')
        if parametrized:
            # TODO: do the check here for typing
            pass

        index = -1
        for i, (sect_name, spec) in enumerate(CONFIG_SPEC):
            if sect_name == section:
                index = i
            if isinstance(spec, ParametricSection):
                if parametrized and sect_name == prefix:
                    if name not in spec:
                        problem = (
                            "Unexpected variable '{}' in section [{}] "
                            "Origin: {}").format(name, section, origin)
                        self.notice_problem(problem)
                        return
                    index = i
        if index == -1:
            # this should happen only for parametric sections
            problem = "Unexpected section [{}]. Origin: {}".format(
                section, origin)
            self.notice_problem(problem)
            return

        assert index > -1
        kind = CONFIG_SPEC[index][1][name].kind
        try:
            if kind == list:
                value = shlex.split(value.replace(',', ' '))
            else:
                value = kind(value)
            if parametrized:
                # we couldn't have known the param names eariler (in __init__)
                # but now we do know them, so let's create the dict to hold
                # the values
                if section not in self.sections.keys():
                    self.sections[section] = OrderedDict()
                    self._origins[section] = dict()
            self.sections[section][name] = value
            self._origins[section][name] = origin
        except TypeError:
            problem = (
                "Problem with setting field {} in section [{}] "
                "'{}' cannot be used as {}. Origin: {}").format(
                    name, section, value, kind, origin)
            self.notice_problem(problem)

    def get_parametric_sections(self, prefix):
        """
        Return a dict of parametrised section that share the same prefix.

        The resulting dict is keyed by the parameter, the values are dicts
        with the declared variables.

        E.g.
        If there's two sections: [report:myrep] and [report:other]
        The resulting dict will have two keys: myrep and other.
        """
        result = dict()
        # check if there is such section declared in the SPEC
        for sect_name, section in CONFIG_SPEC:
            if not isinstance(section, ParametricSection):
                continue
            if sect_name == prefix:
                break
        else:
            raise ValueError("No such section in the spec ({}".format(prefix))
        for sect_name, section in self.sections.items():
            sect_prefix, _, sect_param = sect_name.partition(':')
            if sect_prefix == prefix:
                result[sect_param] = section
        return result

    @classmethod
    def from_text(cls, text, origin):
        """
        Create a new configuration with values from the text.

        Behaves just the same as the from_ini_file method, but accepts string
        as the param.
        """
        return cls.from_ini_file(io.StringIO(text), origin)

    @classmethod
    def from_path(cls, path):
        """Create a new configuration with values stored in a file at path."""
        cfg = Configuration()
        if not os.path.isfile(path):
            cfg.notice_problem("{} file not found".format(path))
            return cfg
        with open(path, 'rt') as ini_file:
            return cls.from_ini_file(ini_file, path)

    @classmethod
    def from_ini_file(cls, ini_file, origin):
        """
        Create a new configuration with values from the ini file.

        ini_file should be a file object.

        This function is designed not to fail (raise), so if some entry in the
        ini file is misdefined then it should be ignored and the default value
        should be kept. Each such problem is kept in the self._problems list.
        """
        cfg = Configuration(origin)
        parser = ConfigParser(delimiters='=')
        parser.read_string(ini_file.read())
        for sect_name, section in parser.items():
            if sect_name == 'DEFAULT':
                for var_name in section:
                    problem = "[DEFAULT] section is not supported"
                    cfg.notice_problem(problem)
                continue
            if ':' in sect_name:
                for var_name, var in section.items():
                    cfg.set_value(sect_name, var_name, var, origin)
                continue
            if sect_name not in cfg.sections:
                problem = "Unexpected section [{}]. Origin: {}".format(
                    sect_name, origin)
                cfg.notice_problem(problem)
                continue
            for var_name, var in section.items():
                is_dyn = sect_name in cls._DYNAMIC_SECTIONS
                if var_name not in cfg.sections[sect_name] and not is_dyn:
                    problem = (
                        "Unexpected variable '{}' in section [{}] "
                        "Origin: {}").format(var_name, sect_name, origin)
                    cfg.notice_problem(problem)
                    continue
                cfg.set_value(sect_name, var_name, var, origin)
        return cfg

    _DYNAMIC_SECTIONS = ('environment', 'manifest')


VarSpec = namedtuple('VarSpec', ['kind', 'default', 'help'])


class ParametricSection(dict):
    """ Dict for storing parametric section's contents."""


class DynamicSection(dict):
    """
    Dict for storing dynamic section's contents.

    This is an extra type to record the fact that this is a different section
    compared to the predefined ones. It works and isn't very complex, but
    a different way of storing this information might be more elegant.
    """


# in order to maintain the section order the CONFIG_SPEC is a list of pairs,
# where the first value is the name of the section and the other is a dict
# of variable specs.
CONFIG_SPEC = [
    ('config', {
        'config_filename': VarSpec(
            str, 'checkbox.conf',
            'Name of the configuration file to look for.'),
    }),
    ('launcher', {
        'launcher_version': VarSpec(
            int, 1, "Version of launcher to use"),
        'app_id': VarSpec(
            str, 'checkbox-cli', "Identifier of the application"),
        'app_version': VarSpec(
            str, '', "Version of the application"),
        'stock_reports': VarSpec(
            list, ['text', 'certification', 'submission_files'],
            "List of stock reports to use"),
        'local_submission': VarSpec(
            bool, True, ("Send/generate submission report locally when using "
                         "checkbox remote")),
        'session_title': VarSpec(
            str, 'session title',
            ("A title to be applied to the sessions created using this "
                "launcher that can be used in report generation")),
        'session_desc': VarSpec(
            str, '', ("A string that can be applied to sessions created using "
                      "this launcher. Useful for storing some contextual "
                      "infomation about the session")),
    }),
    ('test plan', {
        'filter': VarSpec(
            list, ['*'],
            "Constrain interactive choice to test plans matching this glob"),
        'unit': VarSpec(str, '', "Select this test plan by default."),
        'forced': VarSpec(
            bool, False, "Don't allow the user to change test plan."),
    }),
    ('test selection', {
        'forced': VarSpec(
            bool, False, "Don't allow the user to alter test selection."),
        'exclude': VarSpec(
            list, [], "Exclude test matching patterns from running."),
    }),
    ('ui', {
        'type': VarSpec(str, 'interactive', "Type of user interface to use."),
        'output': VarSpec(str, 'show', "Silence or restrict command output."),
        'dont_suppress_output': VarSpec(
            bool, False,
            "Don't suppress the output of certain job plugin types."),
        'verbosity': VarSpec(str, 'normal', "Verbosity level."),
        'auto_retry': VarSpec(
            bool, False,
            "Automatically retry failed jobs at the end of the session."),
        'max_attempts': VarSpec(
            int, 3,
            "Number of attempts to run a job when in auto-retry mode."),
        'delay_before_retry': VarSpec(
            int, 1, ("Delay (in seconds) before "
                     "retrying failed jobs in auto-retry mode.")),
    }),
    ('daemon', {
        'normal_user': VarSpec(
            str, '', "Username to use for jobs that don't specify user."),
    }),
    ('restart', {
        'strategy': VarSpec(str, '', "Use alternative restart strategy."),
    }),
    ('report', ParametricSection({
        'exporter': VarSpec(
            str, '', "Name of the exporter to use"),
        'transport': VarSpec(
            str, '', "Name of the transport to use"),
        'forced': VarSpec(
            bool, False, "Don't ask the user if they want the report."),
    })),
    ('transport', ParametricSection({
        'type': VarSpec(
            str, '', "Type of transport to use."),
        'stream': VarSpec(
            str, 'stdout', "Stream to use - stdout or stderr."),
        'path': VarSpec(
            str, '', "Path to where the report should be saved to."),
        'secure_id': VarSpec(
            str, '',  "Secure ID to use."),
        'staging': VarSpec(
            bool, False, "Pushes to staging C3 instead of normal C3."),
    })),
    ('exporter', ParametricSection({
        'unit': VarSpec(str, '', "ID of the exporter to use."),
        'options': VarSpec(list, [], "Flags to forward to the exporter."),
    })),
    ('environment', DynamicSection()),
    ('manifest', DynamicSection()),
]
