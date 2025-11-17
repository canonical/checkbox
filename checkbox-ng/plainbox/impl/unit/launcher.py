# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
:mod:`plainbox.impl.unit.launcher` -- launcher unit
====================================================

Launcher units represent launcher configuration files that are shipped with a
provider.
"""

import logging
from pathlib import Path

from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.validation import Problem, Severity

__all__ = ["LauncherUnit"]

logger = logging.getLogger("plainbox.unit.launcher")


class LauncherUnit(UnitWithId):
    """
    Launcher Unit

    This unit represents a launcher configuration file that can be used
    to configure test runs. Launchers are .conf files stored in the
    launchers/ directory of a provider.
    """

    @property
    def checksum(self):
        """
        Calculating checksums of launchers is not supported
        """
        return str(hash(self._data["path"]))

    @property
    def text(self):
        # str is necessary because text is lazy loaded
        return str(self.get_record_value("text"))

    @classmethod
    def from_path(cls, path: str, text: str, **kwargs):
        return cls(
            {
                "unit": "launcher",
                "path": str(path),
                "id": str(Path(path).stem),
                "text": text,
            },
            **kwargs
        )

    def __str__(self):
        """
        Same as .name
        """
        return self.id

    def __repr__(self):
        return "<LauncherUnit id:{!r} name:{!r}>".format(self.id, self.name)

    @property
    def path(self):
        """
        Absolute path of the launcher configuration file
        """
        return self.get_record_value("path")

    @property
    def name(self):
        """
        Name of the launcher (filename without .conf extension)
        """
        return self.id

    class Meta:

        name = N_("launcher")

        class fields(SymbolDef):
            """
            Symbols for each field that a LauncherUnit can have
            """

            path = "path"

        field_validators = {
            fields.path: [
                CorrectFieldValueValidator(
                    lambda path: Path(path).stem != "checkbox",
                    Problem.wrong,
                    Severity.error,
                    message=_("launcher name can not be named 'checkbox'"),
                )
            ]
        }
