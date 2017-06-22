# This file is part of Checkbox.
#
# Copyright 2017 Canonical Ltd.
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
:mod:`plainbox.impl.jobcache`  -- job result caching
==============================================

This module should reduce the time needed to bootstrap a session
by reusing previously obtained results.
"""

import json
import logging
import os
import shutil
from plainbox.impl.result import DiskJobResult
from plainbox.i18n import gettext as _

logger = logging.getLogger("plainbox.jobcache")


class ResourceJobCache:
    """
    Cache storing results of previously run resource jobs
    """

    def __init__(self):
        """
        Load existing entries from the filesystem
        """
        self._cache = {}
        for root, subdirs, files in os.walk(self._get_cache_path()):
            for subdir in subdirs:
                self._try_load_cache_entry(os.path.join(root, subdir))

    def get(self, job_checksum, compute_fn):
        """
        Get a result from cache run compute_fn to acquire it
        """
        if job_checksum not in self._cache.keys():
            logger.debug(_("%s not found in cache"), job_checksum)
            result = compute_fn().get_builder().as_dict()
            self._store(job_checksum, result.copy())
        else:
            logger.info(_("%s found in cache"), job_checksum)
            result = self._cache[job_checksum]
        return DiskJobResult(result)

    def _try_load_cache_entry(self, job_cache_path):
        job_checksum = os.path.basename(job_cache_path)
        logger.debug(_("Loading cache entry %s"), job_checksum)
        try:
            with open(os.path.join(job_cache_path, 'result.json'),
                      'rb') as result_file:
                data = result_file.read()
                cache_entry = json.loads(data.decode("UTF-8"))
                if not os.path.exists(cache_entry['io_log_filename']):
                    logger.warning(_("Error loading cache entry. Missing %s"),
                                   cache_entry['io_log_filename'])
                    return
                logger.debug(_("Cache entry %s loaded"), job_checksum)
                self._cache[job_checksum] = cache_entry
        except Exception as exc:
            logger.warrning(_("Error loading cache entry. %s"), exc)

    def _get_cache_path(self):
        suc = os.environ.get('SNAP_USER_COMMON')
        if suc:
            return os.path.join(
                suc, '.cache', 'plainbox', 'resource_job_cache')
        xdg_cache_home = os.environ.get('XDG_CACHE_HOME')
        if not xdg_cache_home:
            xdg_cache_home = os.path.join(
                os.path.expanduser('~'), '.cache')
        return os.path.join(
            xdg_cache_home, 'plainbox', 'resource_job_cache')

    def _store(self, job_checksum, result):
        logger.info(_("Caching job result for job with checksum %s"),
                    job_checksum)
        job_cache_path = os.path.join(self._get_cache_path(), job_checksum)
        if os.path.exists(job_cache_path):
            # this can happen if the loading failed, so let's clear the path
            try:
                shutil.rmtree(job_cache_path)
            except Exception as exc:
                logger.warning(
                    _("Failed to remove path in Resource Cache: %s %s"),
                    job_cache_path, exc)
                return
        os.makedirs(job_cache_path)
        cached_io_log_path = os.path.join(
            job_cache_path, os.path.basename(result['io_log_filename']))
        shutil.copyfile(result['io_log_filename'], cached_io_log_path)
        result['io_log_filename'] = cached_io_log_path
        data = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=None,
            separators=(',', ':')
        ).encode("UTF-8")
        with open(os.path.join(job_cache_path, 'result.json'),
                  'wb') as result_file:
            result_file.write(data)
        logger.debug(
            _("Wrote %s to %s"),
            data, os.path.join(job_cache_path, 'result.json'))
        self._cache[job_checksum] = result
