# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""Tests for the hexr exporter."""

from io import BytesIO
from unittest import TestCase
from xml.etree import ElementTree

from plainbox.impl.exporter.jinja2 import CERTIFICATION_NS
from plainbox.impl.exporter.jinja2 import Jinja2SessionStateExporter
from plainbox.impl.exporter.jinja2 import do_strip_ns
from plainbox.impl.providers.special import get_stubbox
from plainbox.impl.resource import Resource
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.session import SessionManager
from plainbox.impl.unit.exporter import ExporterUnitSupport
from plainbox.impl.unit.job import JobDefinition
from plainbox.public import get_providers
from plainbox.vendor import mock


class FilterTests(TestCase):

    """Tests for additional filters."""

    def test_do_strip_ns(self):
        env = mock.Mock()
        self.assertEqual(do_strip_ns(env, "ns::id", "ns::"), "id")

    def test_do_strip_ns__defaults(self):
        env = mock.Mock()
        self.assertEqual(
            do_strip_ns(env, "2013.com.canonical.certification::id"), "id")


class HexrExporterTests(TestCase):

    """Tests for Jinja2SessionStateExporter using the HEXR template."""

    maxDiff = None

    def setUp(self):
        """Common initialization."""
        exporter_unit = self._get_all_exporter_units()[
            '2013.com.canonical.plainbox::hexr']
        self.exporter = Jinja2SessionStateExporter(
            system_id='SYSTEM_ID', timestamp='TIMESTAMP',
            client_version='CLIENT_VERSION', client_name='CLIENT_NAME',
            exporter_unit=exporter_unit)
        self.manager = SessionManager.create()
        self.manager.add_local_device_context()

    def _get_all_exporter_units(self):
        exporter_map = {}
        for provider in get_providers():
            for unit in provider.unit_list:
                if unit.Meta.name == 'exporter':
                    exporter_map[unit.id] = ExporterUnitSupport(unit)
        return exporter_map

    def _populate_session(self):
        self._make_representative_jobs()
        self._make_cert_resources()
        self._make_cert_attachments()

    def _make_representative_jobs(self):
        # Add all of the jobs from representative.pxu so that we don't have to
        # create verbose fakes. Each job gets a simple passing result.
        state = self.manager.default_device_context.state
        stubbox = get_stubbox(validate=False, check=True)
        for job in stubbox.job_list:
            if not job.partial_id.startswith('representative/plugin/'):
                continue
            state.add_unit(job)
            result = self._make_result_for(job)
            state.update_job_result(job, result)
            last_job = job
            last_result = result
        # Add a comment to one job (the last one)
        state.update_job_result(
            last_job, last_result.get_builder(
                comments='COMMENTS').get_result())

    def _make_result_for(self, job):
        builder = JobResultBuilder(outcome='pass')
        if job.plugin == 'local':
            pass
        elif job.plugin == 'resource':
            pass
        else:
            builder.io_log = [
                (0, 'stdout', b'IO-LOG-STDOUT\n'),
                (1, 'stderr', b'IO-LOG-STDERR\n')
            ]
        return builder.get_result()

    def _make_cert_resources(self):
        # Create some specific resources that this exporter relies on. The
        # corresponding jobs are _not_ loaded but this is irrelevant.
        state = self.manager.default_device_context.state
        ns = CERTIFICATION_NS
        state.set_resource_list(ns + 'cpuinfo', [Resource({
            'PROP-1': 'VALUE-1',
            'PROP-2': 'VALUE-2',
            'count': '2',  # NOTE: this has to be a number :/
        })])
        state.set_resource_list(ns + 'dpkg', [Resource({
            'architecture': 'dpkg.ARCHITECTURE',
        })])
        state.set_resource_list(ns + 'lsb', [Resource({
            'codename': 'lsb.CODENAME',
            'description': 'lsb.DESCRIPTION',
            'release': 'lsb.RELEASE',
            'distributor_id': 'lsb.DISTRIBUTOR_ID',
        })])
        state.set_resource_list(ns + 'uname', [Resource({
            'release': 'uname.RELEASE',
        })])
        state.set_resource_list(ns + 'package', [Resource({
            'name': 'package.0.NAME',
            'version': 'package.0.VERSION',
        }), Resource({
            'name': 'package.1.NAME',
            'version': 'package.1.VERSION',
        })])
        state.set_resource_list(ns + 'requirements', [Resource({
            'name': 'requirement.0.NAME',
            'link': 'requirement.0.LINK',
        }), Resource({
            'name': 'requirement.1.NAME',
            'link': 'requirement.1.LINK',
        })])

    def _make_cert_empty_resources(self):
        # Create empty resources, as experienced when the tested system
        # freezes and corrupts the content of the session. (lp:1479719)
        state = self.manager.default_device_context.state
        ns = CERTIFICATION_NS
        state.set_resource_list(ns + 'cpuinfo', [])
        state.set_resource_list(ns + 'dpkg', [])
        state.set_resource_list(ns + 'lsb', [])
        state.set_resource_list(ns + 'uname', [])
        state.set_resource_list(ns + 'package', [])
        state.set_resource_list(ns + 'requirements', [])

    def _make_cert_attachments(self):
        state = self.manager.default_device_context.state
        partial_id_list = ['dmi_attachment', 'sysfs_attachment',
                           'udev_attachment']
        for partial_id in partial_id_list:
            job = JobDefinition({
                'id': CERTIFICATION_NS + partial_id,
                'plugin': 'attachment'
            })
            result = JobResultBuilder(io_log=[
                (0, 'stdout', 'STDOUT-{}\n'.format(
                    partial_id).encode('utf-8')),
                (1, 'stderr', 'STDERR-{}\n'.format(
                    partial_id).encode('utf-8'))]
            ).get_result()
            state.add_unit(job)
            state.update_job_result(job, result)

    def _inject_evil_input(self):
        evil = '"\'<&>'
        self.exporter._system_id = evil
        self.exporter._timestamp = evil
        self.exporter._client_name = evil
        self.exporter._client_version = evil
        state = self.manager.default_device_context.state
        for resource_id in state.resource_map:
            resource_list = state.resource_map[resource_id]
            for resource in resource_list:
                for key in resource:
                    if resource_id.endswith('cpuinfo') and key == 'count':
                        # don't change resources for the <hardware> section
                        continue
                    resource[key] = evil
        new_job_state_map = {}
        for index, job_id in enumerate(sorted(state.job_state_map)):
            job_state = state.job_state_map[job_id]
            if (job_state.job.partial_id.endswith('_attachment')
                    or job_state.job.partial_id == 'cpuinfo'):
                # don't change attachments for the <hardware> section
                evil_id = job_id
            else:
                evil_id = '{}-{}-{}'.format(evil, index, job_state.job.plugin)
            # NOTE: using private API
            job_state.job._data['id'] = evil_id
            job_state.result = job_state.result.get_builder(
                comments=evil,
                io_log=[(0, 'stdout', evil.encode("UTF-8"))],
            ).get_result()
            new_job_state_map[evil_id] = job_state
        # NOTE: using private API
        state._job_state_map = new_job_state_map

    def tearDown(self):
        """Common teardown."""
        self.manager.destroy()

    def test_smoke(self):
        """The XML document has the right data in the right spot."""
        self._populate_session()
        stream = BytesIO()
        self.exporter.dump_from_session_manager(self.manager, stream)
        smoke_actual = stream.getvalue().decode("utf-8")
        self.assertMultiLineEqual(_smoke_expected, smoke_actual)

    def test_without_any_data(self):
        """The XML document can be produced without any data in the session."""
        stream = BytesIO()
        self.exporter.dump_from_session_manager(self.manager, stream)
        empty_actual = stream.getvalue().decode("utf-8")
        self.assertMultiLineEqual(_empty_expected, empty_actual)

    def test_escaping(self):
        """Evil input doesn't break the correctness of the XML document."""
        self._populate_session()
        self._inject_evil_input()
        stream = BytesIO()
        self.exporter.dump_from_session_manager(self.manager, stream)
        evil_actual = stream.getvalue().decode("utf-8")
        self.assertMultiLineEqual(_evil_expected, evil_actual)

    def test_empty_resources(self):
        """Empty resources don't break the correctness of the XML document."""
        self._make_representative_jobs()
        self._make_cert_empty_resources()
        self._make_cert_attachments()
        stream = BytesIO()
        self.exporter.dump_from_session_manager(self.manager, stream)
        empty_resources_actual = stream.getvalue().decode("utf-8")
        self.assertMultiLineEqual(_empty_resources_expected, empty_resources_actual)

    def test_xml_parsability(self):
        """Each produced output can be parsed with an XML parser."""
        stream1 = BytesIO(_smoke_expected.encode("utf-8"))
        ElementTree.parse(stream1)
        stream2 = BytesIO(_empty_expected.encode("utf-8"))
        ElementTree.parse(stream2)
        stream3 = BytesIO(_evil_expected.encode("utf-8"))
        ElementTree.parse(stream3)


_smoke_expected = """\
<?xml version="1.0"?>
<system version="1.0">
  <context>
    <info command="2013.com.canonical.plainbox::representative/plugin/attachment">IO-LOG-STDOUT
</info>
  </context>
  <hardware>
    <dmi>STDOUT-dmi_attachment
</dmi>
    <sysfs-attributes>STDOUT-sysfs_attachment
</sysfs-attributes>
    <udev>STDOUT-udev_attachment
</udev>
    <processors>
      <processor id="0" name="0">
        <property name="count" type="str">2</property>
        <property name="PROP-1" type="str">VALUE-1</property>
        <property name="PROP-2" type="str">VALUE-2</property>
      </processor>
      <processor id="1" name="1">
        <property name="count" type="str">2</property>
        <property name="PROP-1" type="str">VALUE-1</property>
        <property name="PROP-2" type="str">VALUE-2</property>
      </processor>
    </processors>
  </hardware>
  <questions>
    <question name="2013.com.canonical.plainbox::representative/plugin/manual">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/qml">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/shell">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/user-interact">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/user-interact-verify">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/user-verify">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>COMMENTS</comment>
    </question>
  </questions>
  <software>
    <lsbrelease>
      <property name="codename" type="str">lsb.CODENAME</property>
      <property name="description" type="str">lsb.DESCRIPTION</property>
      <property name="distributor_id" type="str">lsb.DISTRIBUTOR_ID</property>
      <property name="release" type="str">lsb.RELEASE</property>
    </lsbrelease>
    <packages>
      <package id="0" name="package.0.NAME">
        <property name="version" type="str">package.0.VERSION</property>
      </package>
      <package id="1" name="package.1.NAME">
        <property name="version" type="str">package.1.VERSION</property>
      </package>
    </packages>
    <requirements>
      <requirement id=" 0" name="requirement.0.NAME">
        <property name="link" type="str">requirement.0.LINK</property>
      </requirement>
      <requirement id=" 1" name="requirement.1.NAME">
        <property name="link" type="str">requirement.1.LINK</property>
      </requirement>
    </requirements>
  </software>
  <summary>
    <client name="CLIENT_NAME" version="CLIENT_VERSION"/>
    <date_created value="TIMESTAMP"/>
    <architecture value="dpkg.ARCHITECTURE"/>
    <distribution value="lsb.DISTRIBUTOR_ID"/>
    <distroseries value="lsb.RELEASE"/>
    <kernel-release value="uname.RELEASE"/>
    <private value="False"/>
    <contactable value="False"/>
    <live_cd value="False"/>
    <system_id value="SYSTEM_ID"/>
  </summary>
</system>"""


_empty_expected = """\
<?xml version="1.0"?>
<system version="1.0">
  <context>
  </context>
  <hardware>
    <!-- the dmi_attachment job is not available, not producing the <dmi> section -->
    <!-- the sysfs_attachment job is not available, not producing the <sysfs-attributes> tag -->
    <!-- the udev_attachment job is not available, not producing the <udev> tag -->
    <!-- cpuinfo resource is not available, not producing the <processors> section -->
  </hardware>
  <questions>
  </questions>
  <software>
    <!-- lsb resource is not available, not producing the <lsbrelease> tag -->
    <!-- package resource is not available, not producing the <packages> tag -->
    <!-- requirements resource is not available, not producing the <requirements> tag -->
  </software>
  <summary>
    <client name="CLIENT_NAME" version="CLIENT_VERSION"/>
    <date_created value="TIMESTAMP"/>
    <!-- dpkg resource is not available, not producing the <architecture> tag -->
    <!-- lsb resource is not available, not producing <distribution> and <distroseries> tags -->
    <!-- uname resource is not available, not producing the <kernel-release> tag -->
    <private value="False"/>
    <contactable value="False"/>
    <live_cd value="False"/>
    <system_id value="SYSTEM_ID"/>
  </summary>
</system>"""

_escaped_evil_text = '&#34;&#39;&lt;&amp;&gt;'
_evil_expected = """\
<?xml version="1.0"?>
<system version="1.0">
  <context>
    <info command="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-3-attachment">&#34;&#39;&lt;&amp;&gt;</info>
  </context>
  <hardware>
    <dmi>&#34;&#39;&lt;&amp;&gt;</dmi>
    <sysfs-attributes>&#34;&#39;&lt;&amp;&gt;</sysfs-attributes>
    <udev>&#34;&#39;&lt;&amp;&gt;</udev>
    <processors>
      <processor id="0" name="0">
        <property name="count" type="str">2</property>
        <property name="PROP-1" type="str">{evil}</property>
        <property name="PROP-2" type="str">{evil}</property>
      </processor>
      <processor id="1" name="1">
        <property name="count" type="str">2</property>
        <property name="PROP-1" type="str">{evil}</property>
        <property name="PROP-2" type="str">{evil}</property>
      </processor>
    </processors>
  </hardware>
  <questions>
    <question name="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-10-user-interact-verify">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>&#34;&#39;&lt;&amp;&gt;</comment>
    </question>
    <question name="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-11-user-verify">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>&#34;&#39;&lt;&amp;&gt;</comment>
    </question>
    <question name="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-5-manual">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>&#34;&#39;&lt;&amp;&gt;</comment>
    </question>
    <question name="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-6-qml">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>&#34;&#39;&lt;&amp;&gt;</comment>
    </question>
    <question name="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-8-shell">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>&#34;&#39;&lt;&amp;&gt;</comment>
    </question>
    <question name="2013.com.canonical.plainbox::&#34;&#39;&lt;&amp;&gt;-9-user-interact">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>&#34;&#39;&lt;&amp;&gt;</comment>
    </question>
  </questions>
  <software>
    <lsbrelease>
      <property name="codename" type="str">{evil}</property>
      <property name="description" type="str">{evil}</property>
      <property name="distributor_id" type="str">{evil}</property>
      <property name="release" type="str">{evil}</property>
    </lsbrelease>
    <packages>
      <package id="0" name="{evil}">
        <property name="version" type="str">{evil}</property>
      </package>
      <package id="1" name="{evil}">
        <property name="version" type="str">{evil}</property>
      </package>
    </packages>
    <requirements>
      <requirement id=" 0" name="{evil}">
        <property name="link" type="str">{evil}</property>
      </requirement>
      <requirement id=" 1" name="{evil}">
        <property name="link" type="str">{evil}</property>
      </requirement>
    </requirements>
  </software>
  <summary>
    <client name="{evil}" version="{evil}"/>
    <date_created value="{evil}"/>
    <architecture value="{evil}"/>
    <distribution value="{evil}"/>
    <distroseries value="{evil}"/>
    <kernel-release value="{evil}"/>
    <private value="False"/>
    <contactable value="False"/>
    <live_cd value="False"/>
    <system_id value="{evil}"/>
  </summary>
</system>""".format(evil=_escaped_evil_text)

_empty_resources_expected = """\
<?xml version="1.0"?>
<system version="1.0">
  <context>
    <info command="2013.com.canonical.plainbox::representative/plugin/attachment">IO-LOG-STDOUT
</info>
  </context>
  <hardware>
    <dmi>STDOUT-dmi_attachment
</dmi>
    <sysfs-attributes>STDOUT-sysfs_attachment
</sysfs-attributes>
    <udev>STDOUT-udev_attachment
</udev>
    <!-- cpuinfo resource is not available, not producing the <processors> section -->
  </hardware>
  <questions>
    <question name="2013.com.canonical.plainbox::representative/plugin/manual">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/qml">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/shell">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/user-interact">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/user-interact-verify">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>IO-LOG-STDOUT
IO-LOG-STDERR
</comment>
    </question>
    <question name="2013.com.canonical.plainbox::representative/plugin/user-verify">
      <answer type="multiple_choice">pass</answer>
      <answer_choices>
        <value type="str">none</value>
        <value type="str">pass</value>
        <value type="str">fail</value>
        <value type="str">skip</value>
      </answer_choices>
      <comment>COMMENTS</comment>
    </question>
  </questions>
  <software>
    <!-- lsb resource is not available, not producing the <lsbrelease> tag -->
    <packages>
    </packages>
    <requirements>
    </requirements>
  </software>
  <summary>
    <client name="CLIENT_NAME" version="CLIENT_VERSION"/>
    <date_created value="TIMESTAMP"/>
    <!-- dpkg resource is not available, not producing the <architecture> tag -->
    <!-- lsb resource is not available, not producing <distribution> and <distroseries> tags -->
    <!-- uname resource is not available, not producing the <kernel-release> tag -->
    <private value="False"/>
    <contactable value="False"/>
    <live_cd value="False"/>
    <system_id value="SYSTEM_ID"/>
  </summary>
</system>"""
