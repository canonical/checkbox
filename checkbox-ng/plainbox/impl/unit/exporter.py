# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Exporter Entry Unit."""
import json
import logging
import os.path
import re

import pkg_resources

from plainbox.i18n import gettext as _
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

logger = logging.getLogger("plainbox.unit.exporter")


__all__ = ('ExporterUnit', )


class ExporterUnit(UnitWithId):

    """
    Unit representing a session exporter.

    This unit is used to define mechanisms for exporting session state data
    into any format.
    """

    def __str__(self):
        return self.summary

    def __repr__(self):
        return "<ExporterUnit id:{!r} entry_point:{!r}>".format(
            self.id, self.entry_point)

    @property
    def support(self):
        if not self.check():
            return ExporterUnitSupport(self)
        else:
            return None

    @property
    def summary(self):
        """
        Summary of this exporter.

        .. note::
            This value is not translated, see :meth:`tr_summary()` for
            a translated equivalent.
        """
        return self.get_record_value('summary', '')

    def tr_summary(self):
        """Get the translated version of :meth:`summary`."""
        return self.get_translated_record_value('summary', '')

    @property
    def entry_point(self):
        """Exporter EntryPoint to call."""
        return self.get_record_value('entry_point')

    @property
    def file_extension(self):
        """Filename extension when the exporter stream is saved to a file."""
        return self.get_record_value('file_extension')

    @property
    def options(self):
        """Configuration options to send to the exporter class."""
        return self.get_record_value('options')

    @property
    def data(self):
        """Data to send to the exporter class."""
        return self.get_record_value('data')

    class Meta:

        name = 'exporter'

        class fields(SymbolDef):

            """Symbols for each field that an Exporter can have."""

            summary = 'summary'
            entry_point = 'entry_point'
            file_extension = 'file_extension'
            options = 'options'
            data = 'data'

        field_validators = {
            fields.summary: [
                PresentFieldValidator(severity=Severity.advice),
                TranslatableFieldValidator,
                # We want the summary to be a single line
                CorrectFieldValueValidator(
                    lambda summary: summary.count("\n") == 0,
                    Problem.wrong, Severity.warning,
                    message=_("please use only one line"),
                    onlyif=lambda unit: unit.summary is not None),
                # We want the summary to be relatively short
                CorrectFieldValueValidator(
                    lambda summary: len(summary) <= 80,
                    Problem.wrong, Severity.warning,
                    message=_("please stay under 80 characters"),
                    onlyif=lambda unit: unit.summary is not None),
            ],
            fields.entry_point: [
                PresentFieldValidator,
                UntranslatableFieldValidator,
                CorrectFieldValueValidator(
                    lambda entry_point: pkg_resources.load_entry_point(
                        'plainbox', 'plainbox.exporter', entry_point),
                    Problem.wrong, Severity.error),
            ],
            fields.file_extension: [
                PresentFieldValidator,
                UntranslatableFieldValidator,
                CorrectFieldValueValidator(
                    lambda extension: re.search("^[\w\.\-]+$", extension),
                    Problem.syntax_error, Severity.error),
            ],
            fields.options: [
                UntranslatableFieldValidator,
            ],
            fields.data: [
                UntranslatableFieldValidator,
                CorrectFieldValueValidator(
                    lambda value, unit: json.loads(value),
                    Problem.syntax_error, Severity.error,
                    onlyif=lambda unit: unit.data),
                CorrectFieldValueValidator(
                    lambda value, unit: os.path.isfile(os.path.join(
                        unit.provider.data_dir,
                        json.loads(value)['template'])),
                    Problem.wrong, Severity.error,
                    message=_("Jinja2 template not found"),
                    onlyif=lambda unit: unit.entry_point == 'jinja2'),
            ],
        }


class ExporterUnitSupport():

    """
    Helper class that distills exporter data into more usable form.

    This class serves to offload some of the code from :class:`ExporterUnit`
    branch. It takes a single exporter unit and extracts all the interesting
    information out of it. Subsequently it exposes that data so that some
    methods on the exporter unit class itself can be implemented in an easier
    way.
    """

    def __init__(self, exporter):
        self._data = self._get_data(exporter)
        self._data_dir = exporter.provider.data_dir
        self.exporter_cls = self._get_exporter_cls(exporter)
        self._option_list = self._get_option_list(exporter)
        self.file_extension = exporter.file_extension
        self.summary = exporter.tr_summary()
        if exporter.entry_point == 'jinja2':
            self._template = self._data['template']

    @property
    def data(self):
        return self._data

    @property
    def data_dir(self):
        return self._data_dir

    @property
    def option_list(self):
        return self._option_list

    @property
    def template(self):
        return self._template

    def _get_data(self, exporter):
        """Data to send to the exporter class."""
        if exporter.data:
            return json.loads(exporter.data)
        else:
            return {}

    def _get_option_list(self, exporter):
        """Option list to send to the exporter class."""
        if exporter.options:
            return re.split(r'[;,\s]+', exporter.options)
        else:
            return []

    def _get_exporter_cls(self, exporter):
        """Return the exporter class."""
        return pkg_resources.load_entry_point(
            'plainbox', 'plainbox.exporter', exporter.entry_point)
