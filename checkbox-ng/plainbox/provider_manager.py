# This file is part of Checkbox.
#
# Copyright 2012, 2013, 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.provider_manager` -- CLI tools for managing providers
====================================================================

This module has strict API stability requirements. The only public API is the
:func:`setup()` function and the argument handling semantics that is documented
therein.
"""

import argparse
import inspect
import logging
import os
import shutil
import tarfile

from plainbox import __version__ as version
from plainbox.i18n import docstring
from plainbox.i18n import gettext as _, gettext_noop as N_
from plainbox.impl.commands import ToolBase, CommandBase
from plainbox.impl.job import Problem
from plainbox.impl.job import ValidationError as JobValidationError
from plainbox.impl.logging import setup_logging
from plainbox.impl.providers.v1 import get_user_PROVIDERPATH_entry
from plainbox.impl.secure.config import ValidationError \
    as ConfigValidationError
from plainbox.impl.secure.providers.v1 import Provider1, Provider1Definition
from plainbox.impl.secure.rfc822 import RFC822SyntaxError

__all__ = ['setup']


_logger = logging.getLogger("plainbox.provider_manager")


class ManageCommand(CommandBase):
    """
    Base class for all management commands.

    This class encapsulates the provider definition that its subclasses are
    going to work with. Using the :meth:`get_provider()` method you can load
    the provider that is being worked on even if it's not in PROVIDERPATH.
    """

    gettext_domain = "plainbox"

    def __init__(self, definition):
        """
        Initialize a new ManageCommand instance with the specified provider.

        :param provider:
            A Provider1Definition that describes the provider to encapsulate
        """
        self._definition = definition

    @property
    def definition(self):
        """
        a Provider1Definition object that describes the current provider
        """
        return self._definition

    def get_provider(self):
        """
        Get a Provider1 that describes the current provider
        """
        return Provider1(
            self.definition.location, self.definition.name,
            self.definition.version, self.definition.description,
            secure=False, gettext_domain=self.definition.gettext_domain)


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    install this provider in the system

    This command installs the provider to the specified prefix.

    System-wide installations should typically use ``--prefix=/usr``.For
    packaging you will want to use the ``--root=`` argument to place all of the
    copied and generated files into your packaging system staging area. This
    will not affect generated content which only respects the prefix argument.

    @EPILOG@

    The following directories are recursively copied to the installation
    directory: jobs, whitelists, bin, data. Missing directories are silently
    ignored. A new, generated ``.provider`` file will be created at an
    appropriate location, based on the meta-data from the ``manage.py`` script.
    """))
class InstallCommand(ManageCommand):

    _INCLUDED_ITEMS = ['jobs', 'whitelists', 'bin', 'data']

    def register_parser(self, subparsers):
        """
        Overridden method of CommandBase.

        :param subparsers:
            The argparse subparsers objects in which command line argument
            specification should be created.

        This method is invoked by the command line handling code to register
        arguments specific to this sub-command. It must also register itself as
        the command class with the ``command`` default.
        """
        parser = self.add_subcommand(subparsers)
        parser.add_argument(
            "--prefix", default="/usr/local", help=_("installation prefix"))
        parser.add_argument(
            "--root", default="",
            help=_("install everything relative to this alternate root"
                   " directory"))
        parser.set_defaults(command=self)

    def invoked(self, ns):
        """
        Overridden method of CommandBase.

        :param ns:
            The argparse namespace object with parsed argument data

        :returns:
            the exit code of ./manage.py install

        This method is invoked when all of the command line arguments
        associated with this commands have been parsed and are ready for
        execution.
        """
        share_pathname = ns.root + os.path.join(
            ns.prefix, "share", "plainbox-providers-1")
        provider_lib_pathname = ns.root + os.path.join(
            ns.prefix, "lib", "plainbox-providers-1", self._definition.name)
        provider_pathname = os.path.join(
            share_pathname, "{}.provider".format(
                self.definition.name.replace(':', '.')))
        # Make top-level directories
        os.makedirs(share_pathname, exist_ok=True)
        os.makedirs(provider_lib_pathname, exist_ok=True)
        # Create the .provider file
        parser_obj = self.definition.get_parser_obj()
        parser_obj.set('PlainBox Provider', 'location', os.path.join(
            ns.prefix, "lib", "plainbox-providers-1",
            self.definition.name.replace(':', '.')))
        with open(provider_pathname, 'wt', encoding='UTF-8') as stream:
            parser_obj.write(stream)
        # Copy all of the content
        for name in self._INCLUDED_ITEMS:
            src_name = os.path.join(self.definition.location, name)
            dst_name = os.path.join(provider_lib_pathname, name)
            if os.path.exists(src_name):
                shutil.copytree(src_name, dst_name)


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    create a source tarball

    This commands creates a source distribution (tarball) of all of the
    essential provider files. This command takes no arguments and places the
    resulting tarball in the dist/ directory, relative to the ``manage.py``
    file. The tarball name is derived from provider name and version.

    @EPILOG@

    The items included in the tarball are:

    - the manage.py script itself
    - the README.md file
    - the jobs directory, and everything in it
    - the whitelists directory, and everything in it
    - the bin directory, as above
    - the data directory as above

    Any of the missing items are silently ignored.
    """))
class SourceDistributionCommand(ManageCommand):

    name = "sdist"

    _INCLUDED_ITEMS = ['manage.py', 'README.md', 'jobs', 'whitelists', 'bin',
                       'data']

    def register_parser(self, subparsers):
        """
        Overridden method of CommandBase.

        :param subparsers:
            The argparse subparsers objects in which command line argument
            specification should be created.

        This method is invoked by the command line handling code to register
        arguments specific to this sub-command. It must also register itself as
        the command class with the ``command`` default.
        """
        self.add_subcommand(subparsers)

    @property
    def dist_dir(self):
        return os.path.join(self.definition.location, "dist")

    @property
    def toplevel_name(self):
        return "{}-{}".format(
            self.definition.name.replace(":", "."),
            self.definition.version)

    @property
    def tarball_name(self):
        return os.path.join(
            self.dist_dir, "{}.tar.gz".format(self.toplevel_name))

    def invoked(self, ns):
        """
        Overridden method of CommandBase.

        :param ns:
            The argparse namespace object with parsed argument data

        :returns:
            the exit code of ./manage.py sdist

        This method is invoked when all of the command line arguments
        associated with this commands have been parsed and are ready for
        execution.
        """
        if not os.path.isdir(self.dist_dir):
            os.mkdir(self.dist_dir)
        with tarfile.open(self.tarball_name, mode="w:gz") as tarball:
            for name in self._INCLUDED_ITEMS:
                src_name = os.path.join(self.definition.location, name)
                dst_name = os.path.join(self.toplevel_name, name)
                if os.path.exists(src_name):
                    tarball.add(src_name, dst_name)


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    install/remove this provider, only for development

    This commands creates or removes the ``.provider`` file describing the
    provider associated with this ``manage.py`` script. Unlike ``manage.py
    install`` the provider is installed without copying anything to a
    system-wide location and does not need to be re-executed after every
    change.

    The generated file removed by passing the ``--uninstall| -u`` option.

    @EPILOG@

    By default the .provider file is created in
    ``$XDG_DATA_HOME/plainbox-providers-1/`` directory. The filename is derived
    from the name of the provider (version is not included in the filename).

    Note that the full path of the source directory is placed in the generated
    file so you will need to re-run develop if you move this directory around.
    """))
class DevelopCommand(ManageCommand):

    def register_parser(self, subparsers):
        """
        Overridden method of CommandBase.

        :param subparsers:
            The argparse subparsers objects in which command line argument
            specification should be created.

        This method is invoked by the command line handling code to register
        arguments specific to this sub-command. It must also register itself as
        the command class with the ``command`` default.
        """
        parser = self.add_subcommand(subparsers)
        parser.add_argument(
            "-u", "--uninstall", default=False, action="store_true",
            help=_("remove the generated .provider file"))
        parser.add_argument(
            "-f", "--force", default=False, action="store_true",
            help=_("overwrite existing provider files"))

    def invoked(self, ns):
        pathname = os.path.join(
            get_user_PROVIDERPATH_entry(), "{}.provider".format(
                self.definition.name.replace(':', '.')))
        if ns.uninstall:
            if os.path.isfile(pathname):
                _logger.info(_("Removing provider file: %s"), pathname)
                os.unlink(pathname)
        else:
            if os.path.isfile(pathname) and not ns.force:
                print(_("Provider file already exists: {}").format(pathname))
                return 1
            else:
                _logger.info(_("Creating provider file: %s"), pathname)
                os.makedirs(os.path.dirname(pathname), exist_ok=True)
                with open(pathname, 'wt', encoding='UTF-8') as stream:
                    self.definition.write(stream)


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    display basic information about this provider

    This command displays various essential facts about the provider associated
    with the ``manage.py`` script. Displayed data includes provider name and
    other meta-data, all of the jobs and whitelist, with their precise
    locations.
    """))
class InfoCommand(ManageCommand):

    def register_parser(self, subparsers):
        """
        Overridden method of CommandBase.

        :param subparsers:
            The argparse subparsers objects in which command line argument
            specification should be created.

        This method is invoked by the command line handling code to register
        arguments specific to this sub-command. It must also register itself as
        the command class with the ``command`` default.
        """
        self.add_subcommand(subparsers)

    def invoked(self, ns):
        provider = self.get_provider()
        print(_("[Provider MetaData]"))
        print(_("\tname: {}").format(provider.name))
        print(_("\tversion: {}").format(provider.version))
        print(_("\tgettext domain: {}").format(provider.gettext_domain))
        print(_("[Job Definitions]"))
        job_list, problem_list = provider.load_all_jobs()
        for job in job_list:
            print(_("\t{!a}, from {}").format(
                job.name, job.origin.relative_to(provider.base_dir)))
        if problem_list:
            print(_("\tSome jobs could not be parsed correctly"))
            print(_("\tPlease run `manage.py validate` for details"))
        print(_("[White Lists]"))
        try:
            whitelist_list = provider.get_builtin_whitelists()
        except RFC822SyntaxError as exc:
            print("{}:{}: {}".format(
                os.path.relpath(exc.filename, provider.base_dir),
                exc.lineno, exc.msg))
            print(_("Errors prevent whitelists from being displayed"))
        else:
            for whitelist in whitelist_list:
                print(_("\t{!a}, from {}").format(
                    whitelist.name,
                    whitelist.origin.relative_to(provider.base_dir)))


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    perform various static analysis and validation

    This command inspects all of the jobs defined in the provider associated
    with the ``manage.py`` script. It checks for both syntax issues and
    semantic issues. Anything reported as incorrect will likely result in a
    run-time failure.

    @EPILOG@

    Refer to the online documentation for plainbox to understand how correct
    job definitions look like and how to resolve problems reported by
    ``verify``.

    The exit code can be used to determine if there were any failures. If you
    have any, ``manage.py validate`` is something that could run in a CI loop.
    """))
class ValidateCommand(ManageCommand):

    def register_parser(self, subparsers):
        """
        Overridden method of CommandBase.

        :param subparsers:
            The argparse subparsers objects in which command line argument
            specification should be created.

        This method is invoked by the command line handling code to register
        arguments specific to this sub-command. It must also register itself as
        the command class with the ``command`` default.
        """
        self.add_subcommand(subparsers)

    def get_job_list(self, provider):
        job_list, problem_list = provider.load_all_jobs()
        if problem_list:
            for exc in problem_list:
                print("{}:{}: {}".format(
                    os.path.relpath(exc.filename, provider.base_dir),
                    exc.lineno, exc.msg))
            print(_("NOTE: subsequent jobs from problematic"
                    " files are ignored"))
        return job_list

    def validate_jobs(self, job_list):
        problem_list = []
        for job in job_list:
            try:
                job.validate()
            except JobValidationError as exc:
                problem_list.append((job, exc))
        return problem_list

    def invoked(self, ns):
        provider = self.get_provider()
        job_list = self.get_job_list(provider)
        problem_list = self.validate_jobs(job_list)
        explain = {
            Problem.missing: _("missing definition of required field"),
            Problem.wrong: _("incorrect value supplied"),
            Problem.useless: _("useless field in this context"),
        }
        for job, error in problem_list:
            print(_("{}: job {!a}, field {!a}: {}").format(
                job.origin.relative_to(provider.base_dir),
                job.name, error.field.name, explain[error.problem]))
        if problem_list:
            return 1
        else:
            print(_("All jobs seem to be valid"))


class ProviderManagerTool(ToolBase):
    """
    Command line tool that is covertly used by each provider's manage.py script

    This tool is a typical plainbox command line tool with a few sub-commands.
    There are separate sub-commands for certain key activities related to
    providers, those are:

    `manage.py info`:
        This command loads and validates the provider at a basic level.
        It displays the essential meta-data followed by a list of all the
        jobs and whitelists.

    `manage.py validate`:
        This command loads the provider and performs basic job validation,
        looking at each job definition and ensuring it could be used at
        a normal test run.

    `manage.py develop`:
        This command ensures that plainbox can see this provider. It creates a
        definition file in $XDG_DATA_HOME/plainbox-providers-1/{name}.provider
        with all the meta-data and location pointing at the directory with the
        manage.py script

    `manage.py install`:
        This command installs all of the files required by this provider to
        the provided --prefix, relative to the provided --root directory. It
        can be used by installers or package build process to create final
        provider packages

    `manage.py sdist`:
        This command creates a tarball with all of the source files required
        to install this provider. It can be used to release open-source
        providers and archive them.
    """

    _SUB_COMMANDS = [
        InfoCommand,
        ValidateCommand,
        DevelopCommand,
        InstallCommand,
        SourceDistributionCommand,
    ]

    def __init__(self, definition):
        super().__init__()
        self._definition = definition

    @property
    def definition(self):
        return self._definition

    def create_parser_object(self):
        parser = argparse.ArgumentParser(
            prog=self.get_exec_name(),
            usage=_("manage.py [--help] [--version] [options] <command>"))
        parser.add_argument(
            "--version", action="version", version=self.get_exec_version())
        return parser

    @classmethod
    def get_exec_name(cls):
        """
        Get the name of this executable
        """
        return "manage.py"

    @classmethod
    def get_exec_version(cls):
        """
        Get the version reported by this executable
        """
        return "{}.{}.{}".format(*version[:3])

    def add_subcommands(self, subparsers):
        """
        Add top-level subcommands to the argument parser.
        """
        for cmd_cls in self._SUB_COMMANDS:
            cmd_cls(self.definition).register_parser(subparsers)

    def get_gettext_domain(self):
        return "plainbox"

    def get_locale_dir(self):
        return os.getenv("PLAINBOX_LOCALE_DIR", None)


def setup(**kwargs):
    """
    The setup method that is being called from generated manage.py scripts.

    This setup method is similar in spirit to the setup.py's setup() call
    present in most python projects. It takes any keyword arguments and tries
    to make the best of it.

    :param kwargs:
        arbitrary keyword arguments, see below for what we currently look up
    :raises:
        SystemExit with the exit code of the program. This is done regardless
        of normal / abnormal termination.

    The following keyword parameters are supported:

        name:
            name of the provider (IQN compatible). Typically something like
            ``2013.org.example:some-name`` where the ``some-name`` is a simple
            identifier and a private namespace for whoever owned
            ``org.example`` in ``2013``

        version:
            version string, required

        description:
            description (may be long/multi line), optional

        gettext_domain:
            gettext translation domain for job definition strings, optional
    """
    setup_logging()
    manage_py = inspect.stack()[1][0].f_globals['__file__']
    base_dir = os.path.dirname(os.path.abspath(manage_py))
    definition = Provider1Definition()
    try:
        definition.location = base_dir
        definition.name = kwargs.get('name', None)
        definition.version = kwargs.get('version', None)
        definition.description = kwargs.get('description', None)
        definition.gettext_domain = kwargs.get('gettext_domain', "")
    except ConfigValidationError as exc:
        raise SystemExit(_("{}: bad value of {!r}, {}").format(
            manage_py, exc.variable.name, exc.message))
    else:
        raise SystemExit(ProviderManagerTool(definition).main())
