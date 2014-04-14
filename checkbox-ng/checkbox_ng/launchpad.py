# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Brendan Donegan <brendan.donegan@canonical.com>
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
:mod:`checkbox_ng.launchpad` -- plainbox transport to Launchpad database
=============================================================================

This module contains a PlainBox transport that knows how to send the
submission XML data to the Launchpad hardware database.
"""
from datetime import datetime
from gettext import gettext as _
from io import BytesIO
from logging import getLogger
from socket import gethostname
import bz2
import hashlib

import requests

from checkbox_support.lib.dmi import Dmi
from plainbox.impl.transport import TransportBase, TransportError

logger = getLogger("checkbox.ng.launchpad")


class InvalidSubmissionDataError(TransportError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class LaunchpadTransport(TransportBase):
    """
    Transport for sending data to Launchpad database.
     - POSTs data to a http(s) endpoint
     - Adds a header with a hardware identifier
     - Data is expected to be in checkbox xml-compatible format.
       This means it will work best with a stream produced by the
       xml exporter.
   """

    def __init__(self, where, options):
        """
        Initialize the Launchpad Transport.
        """
        super().__init__(where, options)


    def _get_resource_attr(self, session_state, resource, attr):
        resource_result = session_state.resource_map.get(resource)
        if not resource_result:
            raise InvalidSubmissionDataError(
                _("Cannot get {0} resource job").format(resource))
        attr_value = getattr(resource_result[0], attr)
        if attr_value is None:
            raise InvalidSubmissionDataError(
                _("{0} has no attribute {1}").format(resource, attr))
        return attr_value

    def _get_launchpad_form_fields(self, session_state):
        form_fields = {}
        form_fields['field.private'] = 'False'
        form_fields['field.contactable'] = 'False'
        form_fields['field.live_cd'] = 'False'
        form_fields['field.format'] = 'VERSION_1'
        form_fields['field.actions.upload'] = 'Upload'
        form_fields['field.date_created'] = datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S")
        arch = self._get_resource_attr(
            session_state, '2013.com.canonical.certification::dpkg',
            'architecture')
        form_fields['field.architecture'] = arch
        distro = self._get_resource_attr(
            session_state, '2013.com.canonical.certification::lsb',
            'distributor_id')
        form_fields['field.distribution'] = distro
        series = self._get_resource_attr(
            session_state, '2013.com.canonical.certification::lsb', 'codename')
        form_fields['field.distroseries'] = series
        dmi_resources = session_state.resource_map.get(
            '2013.com.canonical.certification::dmi')
        if dmi_resources is None:
            raise InvalidSubmissionDataError(
                _("DMI resources not found"))
        system_id = ""
        for resource in dmi_resources:
            if resource.category == 'CHASSIS':
                chassis_type = Dmi.chassis_name_to_type[resource.product]
                vendor = getattr(resource, 'vendor', "")
                model = getattr(resource, 'model', "")
                fingerprint = hashlib.md5()
                for field in ["Computer", "unknown", chassis_type,
                              vendor, model]:
                    fingerprint.update(field.encode('utf-8'))
                system_id = fingerprint.hexdigest()
        if not system_id:
            raise InvalidSubmissionDataError(_("System ID not found"))
        form_fields['field.system'] = system_id
        fingerprint = hashlib.md5()
        fingerprint.update(system_id.encode('utf-8'))
        fingerprint.update(str(datetime.utcnow()).encode('utf-8'))
        form_fields['field.submission_key'] = fingerprint.hexdigest()
        return form_fields

    def send(self, data, config=None, session_state=None):
        """ Sends data to the specified server.

        :param data:
            Data containing the xml dump to be sent to the server. This
            can be either bytes or a file-like object (BytesIO works fine too).
            If this is a file-like object, it will be read and streamed "on
            the fly".

        :param config:
             optional PlainBoxConfig object. If http_proxy and https_proxy
             values are set in this config object, they will be used to send
             data via the specified protocols. Note that the transport also
             honors the http_proxy and https_proxy environment variables.
             Proxy string format is http://[user:password@]<proxy-ip>:port

        :param session_state:

        :returns: a dictionary with responses from the server if submission
            was successful.

        :raises ValueError: If no session state was provided.
        :raises TransportError: 
            - If sending timed out.
            - If connection failed outright.
            - If the server returned
              a non-success result code
            - If a required resource job is missing from the submission
              or a resource job is missing a required attribute. The following
              resource/attribute pairs are needed:
                - dpkg: architecture
                - lsb: distributor_id
                - lsb: codename
                - dmi: product
        """
        proxies = None
        if config:
            proxies = {
                proto[:-len("_proxy")]: config.environment[proto]
                for proto in ['http_proxy', 'https_proxy']
                if proto in config.environment
            }

        if session_state is None:
            raise ValueError("LaunchpadTransport requires a session "
                             "state to be provided.")

        logger.debug("Sending to %s, email is %s",
                     self.url, self.options['field.emailaddress'])
        lp_headers = {"x-launchpad-hwdb-submission": ""}

        form_fields = self._get_launchpad_form_fields(session_state)
        form_fields['field.emailaddress'] = self.options['field.emailaddress']

        compressed_payload = bz2.compress(data.encode('utf-8'))
        file = BytesIO(compressed_payload)
        file.name = "{}.xml.bz2".format(gethostname())
        file.size = len(compressed_payload)
        submission_data = {'field.submission_data': file}
        try:
            response = requests.post(self.url, data=form_fields,
                                     files=submission_data,
                                     headers=lp_headers,
                                     proxies=proxies)
        except requests.exceptions.Timeout as exc:
            raise TransportError(
                _("Request to {0} timed out: {1}").format(self.url, exc))
        except requests.exceptions.InvalidSchema as exc:
            raise TransportError(
                _("Invalid destination URL: {0}").format(exc))
        except requests.exceptions.ConnectionError as exc:
            raise TransportError(
                _("Unable to connect to {0}: {1}").format(self.url, exc))
        if response is not None:
            try:
                # This will raise HTTPError for status != 20x
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                raise TransportError(str(exc))
            logger.debug(_("Success! Server said %s"), response.text)
            status = _('The submission was uploaded to Launchpad successfully')
            if (response.headers['x-launchpad-hwdb-submission'] != (
                    'OK data stored')):
                status = response.headers['x-launchpad-hwdb-submission']
            return {'status': status}
        # XXX: can response be None?
        return {}
