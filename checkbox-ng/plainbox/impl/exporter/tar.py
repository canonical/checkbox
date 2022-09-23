# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
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

"""
:mod:`plainbox.impl.exporter.tar` -- Tar exporter
=================================================

.. warning::
    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import os
import tarfile
import time
from tempfile import SpooledTemporaryFile

from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.exporter.jinja2 import Jinja2SessionStateExporter
from plainbox.impl.providers import get_providers
from plainbox.impl.unit.exporter import ExporterUnitSupport


class TARSessionStateExporter(SessionStateExporterBase):
    """Session state exporter creating Tar archives."""

    SUPPORTED_OPTION_LIST = ()

    def dump_from_session_manager(self, manager, stream):
        """
        Extract data from session manager and dump it into the stream.

        :param session_manager:
            SessionManager instance that manages session to be exported by
            this exporter
        :param stream:
            Byte stream to write to.

        """
        preset = None
        mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        mem_mib = mem_bytes/(1024.**2)
        # On systems with less than 1GiB of RAM, create the submission tarball
        # without any compression level (i.e preset=0).
        # See https://docs.python.org/3/library/lzma.html
        # With preset 9 for example, the overhead for an LZMACompressor object
        # can be as high as 800 MiB.
        if mem_mib < 1200:
            preset = 0

        job_state_map = manager.default_device_context.state.job_state_map
        with tarfile.TarFile.open(None, 'w:xz', stream, preset=preset) as tar:
            for fmt in ('html', 'json', 'junit'):
                unit = self._get_all_exporter_units()[
                    'com.canonical.plainbox::{}'.format(fmt)]
                exporter = Jinja2SessionStateExporter(exporter_unit=unit)
                with SpooledTemporaryFile(max_size=102400, mode='w+b') as _s:
                    exporter.dump_from_session_manager(manager, _s)
                    tarinfo = tarfile.TarInfo(name="submission.{}".format(fmt))
                    tarinfo.size = _s.tell()
                    tarinfo.mtime = time.time()
                    _s.seek(0)  # Need to rewind the file, puagh
                    tar.addfile(tarinfo, _s)
            for job_id in manager.default_device_context.state.job_state_map:
                job_state = job_state_map[job_id]
                try:
                    recordname = job_state.result.io_log_filename
                except AttributeError:
                    continue
                for stdstream in ('stdout', 'stderr'):
                    filename = recordname.replace('record.gz', stdstream)
                    folder = 'test_output'
                    if job_state.job.plugin == 'attachment':
                        folder = 'attachment_files'
                    if os.path.exists(filename) and os.path.getsize(filename):
                        arcname = os.path.basename(filename)
                        if stdstream == 'stdout':
                            arcname = os.path.splitext(arcname)[0]
                        tar.add(filename, os.path.join(folder, arcname),
                                recursive=False)

    def dump(self, session, stream):
        pass

    def _get_all_exporter_units(self):
        exporter_map = {}
        for provider in get_providers():
            for unit in provider.unit_list:
                if unit.Meta.name == 'exporter':
                    exporter_map[unit.id] = ExporterUnitSupport(unit)
        return exporter_map
