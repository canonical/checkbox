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

"""Tests for the session assistant module class."""

import tempfile

from plainbox.impl.providers.special import get_stubbox
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.session.assistant import UsageExpectation
from plainbox.vendor import mock
from plainbox.vendor import morris


@mock.patch('plainbox.impl.session.assistant.get_providers')
class SessionAssistantTests(morris.SignalTestCase):

    """Tests for the SessionAssitant class."""

    APP_ID = 'app-id'

    def setUp(self):
        """Common set-up code."""
        self.sa = SessionAssistant(self.APP_ID)
        # NOTE: setup a custom repository so that all tests are done in
        # isolation from the user account. While we're doing that, let's check
        # that this this function is allowed just after setting up the session.
        # We cannot really do that in tests later.
        self.repo_dir = tempfile.TemporaryDirectory()
        self.assertIn(
            self.sa.use_alternate_repository,
            UsageExpectation.of(self.sa).allowed_calls)
        self.sa.use_alternate_repository(self.repo_dir.name)
        self.assertNotIn(
            self.sa.use_alternate_repository,
            UsageExpectation.of(self.sa).allowed_calls)
        # Monitor the provider_selected signal since some tests check it
        self.watchSignal(self.sa.provider_selected)
        # Create a few mocked providers that tests can use.
        # The all-important plainbox provider
        self.p1 = mock.Mock(spec_set=Provider1, name='p1')
        self.p1.namespace = '2013.com.canonical.plainbox'
        self.p1.name = '2013.com.canonical.plainbox:special'
        # An example 3rd party provider
        self.p2 = mock.Mock(spec_set=Provider1, name='p2')
        self.p2.namespace = '2015.pl.zygoon'
        self.p2.name = '2015.pl.zygoon:example'
        # A Canonical certification provider
        self.p3 = mock.Mock(spec_set=Provider1, name='p3')
        self.p3.namespace = '2013.com.canonical.certification'
        self.p3.name = '2013.com.canonical.certification:stuff'
        # The stubbox provider, non-mocked, with lots of useful jobs
        self.stubbox = get_stubbox()

    def tearDown(self):
        """Common tear-down code."""
        self.repo_dir.cleanup()

    def _get_mock_providers(self):
        """Get some mocked provides for testing."""
        return [self.p1, self.p2, self.p3]

    def _get_test_providers(self):
        """Get the stubbox provider, it's fully functional."""
        return [self.stubbox]

    def test_select_providers__loads_plainbox(self, mock_get_providers):
        """Check that select_providers() loads special plainbox providers."""
        mock_get_providers.return_value = self._get_mock_providers()
        selected_providers = self.sa.select_providers()
        # We're expecting to see just [p1]
        self.assertEqual(selected_providers, [self.p1])
        # p1 is always auto-loaded
        self.assertSignalFired(self.sa.provider_selected, self.p1, auto=True)
        # p2 is not loaded
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p2, auto=True)
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p2, auto=False)
        # p3 is not loaded
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p3, auto=True)
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p3, auto=False)

    def test_select_providers__loads_by_id(self, mock_get_providers):
        """Check that select_providers() loads providers with given name."""
        mock_get_providers.return_value = self._get_mock_providers()
        selected_providers = self.sa.select_providers(self.p2.name)
        # We're expecting to see both providers [p1, p2]
        self.assertEqual(selected_providers, [self.p1, self.p2])
        # p1 is always auto-loaded
        self.assertSignalFired(
            self.sa.provider_selected, self.p1, auto=True)
        # p2 is loaded on demand
        self.assertSignalFired(
            self.sa.provider_selected, self.p2, auto=False)
        # p3 is not loaded
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p3, auto=False)
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p3, auto=True)

    def test_select_providers__loads_by_pattern(self, mock_get_providers):
        """Check that select_providers() loads providers matching a pattern."""
        mock_get_providers.return_value = self._get_mock_providers()
        selected_providers = self.sa.select_providers("*canonical*")
        # We're expecting to see both canonical providers [p1, p3]
        self.assertEqual(selected_providers, [self.p1, self.p3])
        # p1 is always auto-loaded
        self.assertSignalFired(
            self.sa.provider_selected, self.p1, auto=True)
        # p2 is not loaded
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p2, auto=False)
        self.assertSignalNotFired(
            self.sa.provider_selected, self.p2, auto=True)
        # p3 is loaded on demand
        self.assertSignalFired(
            self.sa.provider_selected, self.p3, auto=False)

    def test_select_providers__reports_bogus_names(self, mock_get_providers):
        """Check that select_providers() reports wrong names and patterns."""
        mock_get_providers.return_value = self._get_mock_providers()
        with self.assertRaises(ValueError) as boom:
            self.sa.select_providers("*bimbo*")
        self.assertEqual(str(boom.exception), "nothing selected with: *bimbo*")

    def test_expected_call_sequence(self, mock_get_providers):
        """Track the sequence of allowed method calls."""
        mock_get_providers.return_value = self._get_test_providers()
        # SessionAssistant.select_providers() must be allowed
        self.assertIn(self.sa.select_providers,
                      UsageExpectation.of(self.sa).allowed_calls)
        # Call SessionAssistant.select_providers()
        self.sa.select_providers()
        # SessionAssistant.select_providers() must no longer be allowed
        self.assertNotIn(self.sa.select_providers,
                         UsageExpectation.of(self.sa).allowed_calls)
        # SessionAssistant.start_new_session() must now be allowed
        self.assertIn(self.sa.start_new_session,
                      UsageExpectation.of(self.sa).allowed_calls)
        # Call SessionAssistant.start_new_session()
        self.sa.start_new_session("just for testing")
        # SessionAssistant.start_new_session() must no longer allowed
        self.assertNotIn(self.sa.start_new_session,
                         UsageExpectation.of(self.sa).allowed_calls)
        # SessionAssistant.select_test_plan() must now be allowed
        self.assertIn(self.sa.select_test_plan,
                      UsageExpectation.of(self.sa).allowed_calls)
