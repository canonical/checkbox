# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.checkbox` -- CheckBox integration
=====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import collections
import io
import logging
import os

from plainbox.impl import get_plainbox_dir
from plainbox.impl.applogic import RegExpJobQualifier, CompositeQualifier
from plainbox.impl.job import JobDefinition
from plainbox.impl.rfc822 import load_rfc822_records


logger = logging.getLogger("plainbox.checkbox")


# NOTE: using CompositeQualifier seems strange but it's a tested proven
# component so all we have to ensure is that we read the whitelist files
# correctly.
class WhiteList(CompositeQualifier):
    """
    A qualifier that understands checkbox whitelist files.

    A whitelist file is a plain text, line oriented file. Each line represents
    a regular expression pattern that can be matched against the name of a job.

    The file can contain simple shell-style comments that begin with the pound
    or hash key (#). Those are ignored. Comments can span both a fraction of a
    line as well as the whole line.

    For historical reasons each pattern has an implicit '^' and '$' prepended
    and appended (respectively) to the actual pattern specified in the file.
    """

    def __init__(self, pattern_list):
        """
        Initialize a whitelist object with the specified list of patterns.

        The patterns must be already mangled with '^' and '$'.
        """
        inclusive = [RegExpJobQualifier(pattern) for pattern in pattern_list]
        exclusive = ()
        super(WhiteList, self).__init__(inclusive, exclusive)

    @classmethod
    def from_file(cls, pathname):
        """
        Load and initialize the WhiteList object from the specified file.

        :param pathname: file to load
        :returns: a fresh WhiteList object
        """
        pattern_list = cls._load_patterns(pathname)
        return cls(pattern_list)

    @classmethod
    def _load_patterns(self, pathname):
        """
        Load whitelist patterns from the specified file
        """
        pattern_list = []
        # Load the file
        with open(pathname, "rt", encoding="UTF-8") as stream:
            for line in stream:
                # Strip shell-style comments if there are any
                try:
                    index = line.index("#")
                except ValueError:
                    pass
                else:
                    line = line[:index]
                # Strip whitespace
                line = line.strip()
                # Skip empty lines (especially after stripping comments)
                if line == "":
                    continue
                # Surround the pattern with ^ and $
                # so that it wont just match a part of the job name.
                regexp_pattern = r"^{pattern}$".format(pattern=line)
                # Accumulate patterns into the list
                pattern_list.append(regexp_pattern)
        return pattern_list


class CheckBoxNotFound(LookupError):
    """
    Exception used to report that CheckBox cannot be located
    """

    def __repr__(self):
        return "CheckBoxNotFound()"

    def __str__(self):
        return "CheckBox cannot be found"


def _get_checkbox_dir():
    """
    Return the root directory of the checkbox source checkout

    Historically plainbox used a git submodule with checkbox tree (converted to
    git). This ended with the merge of plainbox into the checkbox tree.
    
    Now it's the other way around and the checkbox tree can be located two
    directories "up" from the plainbox module, in a checkbox-old directory.
    """
    return os.path.normpath(
        os.path.join(
            get_plainbox_dir(), "..", "..", "checkbox-old"))


class CheckBox:
    """
    Helper class for interacting with CheckBox

    PlainBox relies on CheckBox for actual jobs, scripts and library features
    required by the scripts. This class allows one to interact with CheckBox
    without having to bother with knowing how to set up the environment.

    This class also abstracts away the differences between dealing with
    CheckBox that is installed from system packages and CheckBox that is
    available from a checkout directory.
    """

    # Helper for locating certain directories
    CheckBoxDirs = collections.namedtuple(
        "CheckBoxDirs", "SHARE_DIR SCRIPTS_DIR JOBS_DIR DATA_DIR")

    # Temporary helper to compute "src" value below
    source_dir = _get_checkbox_dir()

    _DIRECTORY_MAP = collections.OrderedDict((
        # Layout for source checkout
        ("src", CheckBoxDirs(
            source_dir,
            os.path.join(source_dir, "scripts"),
            os.path.join(source_dir, "jobs"),
            os.path.join(source_dir, "data"))),
        # Layout for installed version
        ("deb", CheckBoxDirs(
            "/usr/share/checkbox/",
            "/usr/share/checkbox/scripts",
            "/usr/share/checkbox/jobs",
            "/usr/share/checkbox/data"))))

    # Remove temporary helper that was needed above
    del source_dir

    def __init__(self, mode=None):
        """
        Initialize checkbox integration.

        :param mode:
            If specified it determines which checkbox installation to use.
            None (default) enables auto-detection. Applicable values are
            ``src``, ``deb1`` and ``deb2``. The first value selects checkbox as
            present in the code repository. The last two values are both for
            intended for a checkbox package that was installed from the Ubuntu
            repository. They are different as checkbox packaging changed across
            releases.

        :raises CheckBoxNotFound:
            if checkbox cannot be located anywhere
        :raises ValueError:
            if ``mode`` is not supported
        """
        # Auto-detect if not explicitly configured
        if mode is None:
            for possible_mode, dirs in self._DIRECTORY_MAP.items():
                if all(os.path.exists(dirname) for dirname in dirs):
                    logger.info("Using checkbox in mode %s", possible_mode)
                    mode = possible_mode
                    break
            else:
                raise CheckBoxNotFound()
        # Ensure mode is known
        if mode not in self._DIRECTORY_MAP:
            raise ValueError("Unsupported mode")
        else:
            self._mode = mode
            self._dirs = self._DIRECTORY_MAP[mode]

    @property
    def CHECKBOX_SHARE(self):
        """
        Return the required value of CHECKBOX_SHARE environment variable.

        .. note::
            This variable is only required by one script.
            It would be nice to remove this later on.
        """
        return self._dirs.SHARE_DIR

    @property
    def extra_PYTHONPATH(self):
        """
        Return additional entry for PYTHONPATH, if needed.

        This entry is required for CheckBox scripts to import the correct
        CheckBox python libraries.

        .. note::
            The result may be None
        """
        # NOTE: When CheckBox is installed then all the scripts should not use
        # 'env' to locate the python interpreter (otherwise they might use
        # virtualenv which is not desirable for Debian packages). When we're
        # using CheckBox from source then the source directory (which contains
        # the 'checkbox' package) should be added to PYTHONPATH for all the
        # imports to work.
        if self._mode == "src":
            return _get_checkbox_dir()
        else:
            return None

    @property
    def extra_PATH(self):
        """
        Return additional entry for PATH

        This entry is required to lookup CheckBox scripts.
        """
        # NOTE: This is always the script directory. The actual logic for
        # locating it is implemented in the property accessors.
        return self.scripts_dir

    @property
    def jobs_dir(self):
        """
        Return an absolute path of the jobs directory
        """
        return self._dirs.JOBS_DIR

    @property
    def whitelists_dir(self):
        """
        Return an absolute path of the whitelist directory
        """
        return os.path.join(self._dirs.DATA_DIR, "whitelists")

    @property
    def scripts_dir(self):
        """
        Return an absolute path of the scripts directory

        .. note::
            The scripts may not work without setting PYTHONPATH and
            CHECKBOX_SHARE.
        """
        return self._dirs.SCRIPTS_DIR

    def get_builtin_whitelists(self):
        logger.debug("Loading built-in whitelists...")
        whitelist_list = []
        for name in os.listdir(self.whitelists_dir):
            if name.endswith(".whitelist"):
                whitelist_list.append(
                    WhiteList.from_file(os.path.join(
                        self.whitelists_dir, name)))
        return whitelist_list

    def get_builtin_jobs(self):
        logger.debug("Loading built-in jobs...")
        job_list = []
        for name in os.listdir(self.jobs_dir):
            if name.endswith(".txt") or name.endswith(".txt.in"):
                job_list.extend(
                    self.load_jobs(
                        os.path.join(self.jobs_dir, name)))
        return job_list

    def load_jobs(self, somewhere):
        """
        Load job definitions from somewhere
        """
        if isinstance(somewhere, str):
            # Load data from a file with the given name
            filename = somewhere
            with open(filename, 'rt', encoding='UTF-8') as stream:
                return self.load_jobs(stream)
        if isinstance(somewhere, io.TextIOWrapper):
            stream = somewhere
            logger.debug("Loading jobs definitions from %r...", stream.name)
            record_list = load_rfc822_records(stream)
            job_list = []
            for record in record_list:
                job = JobDefinition.from_rfc822_record(record)
                job._checkbox = self
                logger.debug("Loaded %r", job)
                job_list.append(job)
            return job_list
        else:
            raise TypeError(
                "Unsupported type of 'somewhere': {!r}".format(
                    type(somewhere)))
