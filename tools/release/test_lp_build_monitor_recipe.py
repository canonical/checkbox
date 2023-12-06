import unittest

from unittest.mock import MagicMock, patch

import lp_build_monitor_recipe


class TestHelperFunctions(unittest.TestCase):
    def test_get_new_builds(self):
        # all builds that were created after started_datetime are returned
        build_recipe = MagicMock()

        build_selected = MagicMock()
        build_selected.date_first_dispatched = 10

        build_not_selected = MagicMock()
        build_not_selected.date_first_dispatched = 0

        build_recipe.builds = [build_selected, build_not_selected]
        selected = lp_build_monitor_recipe.get_new_builds(build_recipe, 6)

        self.assertEqual(selected, [build_selected])

    @patch("time.sleep", new=MagicMock())
    @patch("lp_build_monitor_recipe.print")
    def test_wait_every_build_started(self, print_mock):
        build_recipe_mock = MagicMock()
        build_recipe_mock.getPendingBuildInfo.side_effect = [
            [{"distroseries": "Xenial"}, {"distroseries": "Bionic"}],
            [{"distroseries": "Xenial"}],
            [],
        ]

        lp_build_monitor_recipe.wait_every_build_started(build_recipe_mock)

        # the function waited for getPendingBuildInfo to return an empty list
        self.assertEqual(build_recipe_mock.getPendingBuildInfo.call_count, 3)
        # the user was notified of every pending build
        self.assertTrue(print_mock.call_count >= 3)


class TestMonitorRetryBuilds(unittest.TestCase):
    @patch("time.sleep")
    @patch("lp_build_monitor_recipe.get_new_builds")
    def test_monitor_retry_builds_success(
        self, get_new_builds_mock, time_sleep_mock
    ):
        build_mock = MagicMock()
        build_mock.buildstate = "Successfully built"

        get_new_builds_mock.return_value = [build_mock]

        lp_build_monitor_recipe.monitor_retry_builds(MagicMock(), MagicMock())
        self.assertFalse(time_sleep_mock.called)

    @patch("time.sleep")
    @patch("lp_build_monitor_recipe.get_new_builds")
    def test_monitor_retry_builds_retry_failures(
        self, get_new_builds_mock, time_sleep_mock
    ):
        build_mock = MagicMock()
        build_mock.can_be_retried = True
        # A build is updated via the lp_refresh function, lets do the same
        # here but inject our test values
        build_status_evolution = [
            "Successfully built",
            "Uploading build",
            "Currently building",
            "Failed to build",
            "Dependency wait",
            "Chroot problem",
        ]

        def lp_refresh_side_effect():
            if build_status_evolution:
                build_mock.buildstate = build_status_evolution.pop()

        build_mock.lp_refresh.side_effect = lp_refresh_side_effect

        get_new_builds_mock.return_value = [build_mock]

        lp_build_monitor_recipe.monitor_retry_builds(MagicMock(), MagicMock())

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 6)
        # we didnt fload LP with requests, waiting once per progress
        self.assertEqual(time_sleep_mock.call_count, 5)
        # each time a failure was detected, the build was retried
        self.assertEqual(build_mock.retry.call_count, 3)

    @patch("time.sleep")
    @patch("lp_build_monitor_recipe.get_new_builds")
    def test_monitor_retry_builds_more_wait(
        self, get_new_builds_mock, time_sleep_mock
    ):
        build_mock = MagicMock()
        # A build is updated via the lp_refresh function, lets do the same
        # here but inject our test values
        build_status_evolution = [
            "Successfully built",
            "Uploading build",
            "Gathering build output",
            "Currently building",
            "Needs building",
        ]

        def lp_refresh_side_effect():
            if build_status_evolution:
                build_mock.buildstate = build_status_evolution.pop()

        build_mock.lp_refresh.side_effect = lp_refresh_side_effect

        get_new_builds_mock.return_value = [build_mock]

        lp_build_monitor_recipe.monitor_retry_builds(MagicMock(), MagicMock())

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 5)
        # we didnt fload LP with requests, waiting once per progress
        self.assertEqual(time_sleep_mock.call_count, 4)

    @patch("time.sleep")
    @patch("lp_build_monitor_recipe.get_new_builds")
    def test_monitor_retry_builds_unrecoverable_failures(
        self, get_new_builds_mock, time_sleep_mock
    ):
        build_mock = MagicMock()
        build_mock.can_be_retried = False
        build_mock.web_link = "https://some.web.build/build"
        # A build is updated via the lp_refresh function, lets do the same
        # here but inject our test values
        build_status_evolution = [
            "-- invalid value --",
            "Failed to upload",
        ]

        def lp_refresh_side_effect():
            if build_status_evolution:
                build_mock.buildstate = build_status_evolution.pop()

        build_mock.lp_refresh.side_effect = lp_refresh_side_effect

        get_new_builds_mock.return_value = [build_mock]

        with self.assertRaises(SystemExit):
            lp_build_monitor_recipe.monitor_retry_builds(
                MagicMock(), MagicMock()
            )

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 1)
        # each time a failure was detected, the build was retried
        self.assertEqual(build_mock.retry.call_count, 0)
        # we don't update a build that can't be retried at all
        self.assertEqual(len(build_status_evolution), 1)


class TestMain(unittest.TestCase):
    @patch("time.sleep", new=MagicMock())
    @patch(
        "lp_build_monitor_recipe.get_date_utc_now",
        new=MagicMock(return_value=10),
    )
    @patch("lp_build_monitor_recipe.get_build_recipe")
    def test_success(self, get_build_recipe_mock):
        recipe_mock = get_build_recipe_mock()
        # we are asking this to build on 3 platforms
        recipe_mock.distroseries = ["Xenial", "Bionic", "Jammy"]
        # every build starts and pends for some time
        pending_build_info = [
            [
                {"distroseries": "Xenial"},
                {"distroseries": "Bionic"},
                {"distroseries": "Jammy"},
            ],
            [
                {"distroseries": "Xenial"},
            ],
            [],
        ]
        recipe_mock.getPendingBuildInfo.side_effect = pending_build_info
        # the builds started and some failed and must be retried
        build_mock = MagicMock()
        build_mock.date_first_dispatched = 11  # more than now, 10
        build_mock.can_be_retried = True
        # A build is updated via the lp_refresh function, lets do the same
        # here but inject our test values
        build_status_evolution = [
            "Successfully built",
            "Successfully built",
            "Successfully built",
            "Uploading build",
            "Gathering build output",
            "Currently building",
            "Failed to build",
        ]

        def lp_refresh_side_effect():
            if build_status_evolution:
                build_mock.buildstate = build_status_evolution.pop()

        build_mock.lp_refresh.side_effect = lp_refresh_side_effect
        recipe_mock.builds = [build_mock, build_mock, build_mock]

        lp_build_monitor_recipe.main(["checkbox", "some_recipe"])

        self.assertEqual(recipe_mock.requestBuild.call_count, 3)
        # after 3 calls all builds were started correctly
        self.assertEqual(recipe_mock.getPendingBuildInfo.call_count, 3)
        # only 1 build failed and was retried
        self.assertEqual(build_mock.retry.call_count, 1)

    @patch("time.sleep", new=MagicMock())
    @patch(
        "lp_build_monitor_recipe.get_date_utc_now",
        new=MagicMock(return_value=10),
    )
    @patch("lp_build_monitor_recipe.get_build_recipe")
    def test_failure(self, get_build_recipe_mock):
        recipe_mock = get_build_recipe_mock()
        # we are asking this to build on 3 platforms
        recipe_mock.distroseries = ["Xenial", "Bionic", "Jammy"]
        # every build starts and pends for some time
        pending_build_info = [
            [],
        ]
        recipe_mock.getPendingBuildInfo.side_effect = pending_build_info
        # the builds started and some failed and must be retried
        build_mock = MagicMock()
        build_mock.date_first_dispatched = 11  # more than now, 10
        build_mock.web_link = ""
        build_mock.can_be_retried = False
        # A build is updated via the lp_refresh function, lets do the same
        # here but inject our test values
        build_status_evolution = [
            "Successfully built",
            "Successfully built",
            "Uploading build",
            "Gathering build output",
            "Currently building",
            "Failed to build",
        ]

        def lp_refresh_side_effect():
            if build_status_evolution:
                build_mock.buildstate = build_status_evolution.pop()

        build_mock.lp_refresh.side_effect = lp_refresh_side_effect
        recipe_mock.builds = [build_mock, build_mock, build_mock]

        with self.assertRaises(SystemExit):
            lp_build_monitor_recipe.main(["checkbox", "some_recipe"])

        self.assertEqual(recipe_mock.requestBuild.call_count, 3)
        self.assertEqual(recipe_mock.getPendingBuildInfo.call_count, 1)
        # all the build that didnt unrecoverably fail were followed to
        # completion
        self.assertFalse(build_status_evolution)
