import unittest
from http.client import RemoteDisconnected

from unittest.mock import MagicMock, patch

from httplib2 import Response
from lazr.restfulclient.errors import ServerError

import lp_build_monitor_recipe


class TestPollingRetries(unittest.TestCase):
    @patch("time.sleep")
    def test_pending_query_recovers(self, sleep_mock):
        recipe = MagicMock()
        recipe.getPendingBuildInfo.side_effect = [TimeoutError(), []]
        lp_build_monitor_recipe.wait_every_source_build_started(recipe)
        self.assertEqual(recipe.getPendingBuildInfo.call_count, 2)
        sleep_mock.assert_called_once_with(60)
        recipe.requestBuild.assert_not_called()

    @patch("time.sleep")
    def test_refresh_recovers_without_losing_build(self, sleep_mock):
        build = MagicMock()
        build.lp_refresh.side_effect = [RemoteDisconnected(), None]
        build.buildstate = "Successfully built"
        self.assertEqual(
            lp_build_monitor_recipe.monitor_retry_builds([build]), []
        )
        self.assertEqual(build.lp_refresh.call_count, 2)
        build.retry.assert_not_called()
        sleep_mock.assert_called_once_with(60)

    @patch("time.sleep")
    def test_transient_errors(self, sleep_mock):
        for error, delay in [
            (TimeoutError("timed out"), 60),
            (RemoteDisconnected("closed"), 60),
            (ServerError(Response({"status": "502"}), b""), 60),
            (ServerError(Response({"status": "504"}), b""), 60),
            (
                ServerError(
                    Response({"status": "503", "retry-after": "900"}), b""
                ),
                900,
            ),
        ]:
            with self.subTest(error=type(error), delay=delay):
                sleep_mock.reset_mock()
                query = MagicMock(side_effect=[error, "finished"])
                result = lp_build_monitor_recipe.retry_polling(query)()
                self.assertEqual(result, "finished")
                self.assertEqual(query.call_count, 2)
                sleep_mock.assert_called_once_with(delay)

    @patch("time.sleep")
    def test_failure_limit_resets_after_success(self, sleep_mock):
        query = MagicMock(
            side_effect=[TimeoutError()] * 9
            + ["finished"]
            + [TimeoutError()] * 10
        )
        poll = lp_build_monitor_recipe.retry_polling(query)
        self.assertEqual(poll(), "finished")
        with self.assertRaisesRegex(SystemExit, "10 consecutive times"):
            poll()
        self.assertEqual(query.call_count, 20)
        self.assertEqual(sleep_mock.call_count, 18)

    @patch("time.sleep")
    def test_non_transient_errors(self, sleep_mock):
        for error in [
            ValueError("unexpected"),
            ServerError(Response({"status": "500"}), b""),
        ]:
            with self.subTest(error=type(error)):
                query = MagicMock(side_effect=error)
                with self.assertRaises(type(error)):
                    lp_build_monitor_recipe.retry_polling(query)()
                query.assert_called_once_with()
        sleep_mock.assert_not_called()

    @patch("lp_build_monitor_recipe.print")
    @patch("time.sleep")
    def test_invalid_retry_after(self, sleep_mock, print_mock):
        query = MagicMock(
            side_effect=[
                ServerError(
                    Response({"status": "503", "retry-after": "invalid"}), b""
                ),
                [],
            ]
        )
        self.assertEqual(lp_build_monitor_recipe.retry_polling(query)(), [])
        sleep_mock.assert_called_once_with(60)
        self.assertIn(
            "Non-numeric Launchpad Retry-After",
            print_mock.call_args_list[0].args[0],
        )

    @patch("time.sleep")
    def test_binary_records_recover_without_requesting_builds(
        self, sleep_mock
    ):
        recipe = MagicMock()
        recipe.name = "checkbox-ng-edge"
        recipe.daily_build_archive.getBuildCounters.side_effect = [
            {"pending": 1},
            {"pending": 0},
        ]
        build = MagicMock()
        build.date_first_dispatched = 10
        build.buildstate = "Successfully built"
        recipe.daily_build_archive.getBuildRecords.side_effect = [
            ServerError(
                Response({"status": "503", "retry-after": "900"}), b""
            ),
            [build],
        ]

        self.assertEqual(
            lp_build_monitor_recipe.monitor_retry_binary_builds(recipe, 0), []
        )
        sleep_mock.assert_any_call(900)
        build.lp_refresh.assert_called_once_with()
        build.retry.assert_not_called()
        recipe.requestBuild.assert_not_called()


class TestHelperFunctions(unittest.TestCase):
    def test_get_all_binary_builds(self):
        # all builds that were created after started_datetime are returned
        build_recipe = MagicMock()
        build_recipe.name = "checkbox-ng-edge"

        build_selected = MagicMock()
        build_selected.date_first_dispatched = 10

        build_selected_pending = MagicMock()
        # pending builds have a None date_first_dispatched
        # we select them because they are "newer" of the start date
        # for sure given that they didn't even start yet
        build_selected_pending.date_first_dispatched = None

        build_not_selected = MagicMock()
        build_not_selected.date_first_dispatched = 0

        build_recipe.daily_build_archive.getBuildRecords.return_value = [
            build_selected,
            build_selected_pending,
            build_not_selected,
        ]
        selected = lp_build_monitor_recipe.get_all_binary_builds(
            build_recipe, 6
        )

        self.assertEqual(selected, [build_selected, build_selected_pending])
        build_recipe.daily_build_archive.getBuildRecords.assert_called_with(
            source_name="checkbox-ng"
        )

    def test_get_all_source_builds(self):
        # all builds that were created after started_datetime are returned
        build_recipe = MagicMock()

        build_selected = MagicMock()
        build_selected.date_first_dispatched = 10

        build_not_selected = MagicMock()
        build_not_selected.date_first_dispatched = 0

        build_recipe.builds = [build_selected, build_not_selected]
        selected = lp_build_monitor_recipe.get_all_source_builds(
            build_recipe, 6
        )

        self.assertEqual(selected, [build_selected])

    @patch("time.sleep", new=MagicMock())
    @patch("lp_build_monitor_recipe.print")
    def test_wait_every_source_build_started(self, print_mock):
        build_recipe_mock = MagicMock()
        build_recipe_mock.getPendingBuildInfo.side_effect = [
            [{"distroseries": "Xenial"}, {"distroseries": "Bionic"}],
            [{"distroseries": "Xenial"}],
            [],
        ]

        lp_build_monitor_recipe.wait_every_source_build_started(
            build_recipe_mock
        )

        # the function waited for getPendingBuildInfo to return an empty list
        self.assertEqual(build_recipe_mock.getPendingBuildInfo.call_count, 3)
        # the user was notified of every pending build
        self.assertTrue(print_mock.call_count >= 3)

    @patch("time.sleep", new=MagicMock())
    @patch("lp_build_monitor_recipe.print")
    def test_monitor_retry_binary_builds(self, print_mock):
        build_recipe_mock = MagicMock()
        build_recipe_mock.name = "checkbox-ng-edge"
        build_recipe_mock.daily_build_archive.getBuildRecords.return_value = []
        build_recipe_mock.daily_build_archive.getBuildCounters.side_effect = [
            {"pending": 10},
            {"pending": 5},
            {"pending": 0},
        ]

        lp_build_monitor_recipe.monitor_retry_binary_builds(
            build_recipe_mock, 0
        )

        # the function waited for getPendingBuildInfo to return an empty list
        self.assertEqual(
            build_recipe_mock.daily_build_archive.getBuildCounters.call_count,
            3,
        )
        self.assertEqual(
            print_mock.call_args_list,
            [
                unittest.mock.call(
                    "Waiting for pending builds in the archive..."
                )
            ]
            * 2,
        )

    @patch("time.sleep")
    def test_monitor_retry_builds_request_timeout(self, sleep_mock):
        build = MagicMock()
        build.lp_refresh.side_effect = TimeoutError("Launchpad timed out")

        with self.assertRaisesRegex(SystemExit, "10 consecutive times"):
            lp_build_monitor_recipe.monitor_retry_builds([build])

        build.retry.assert_not_called()
        self.assertEqual(build.lp_refresh.call_count, 10)
        self.assertEqual(sleep_mock.call_count, 9)

    @patch("time.sleep")
    def test_monitor_retry_binary_builds_request_timeout(self, sleep_mock):
        recipe = MagicMock()
        recipe.daily_build_archive.getBuildCounters.side_effect = TimeoutError(
            "Launchpad timed out"
        )

        with self.assertRaisesRegex(SystemExit, "10 consecutive times"):
            lp_build_monitor_recipe.monitor_retry_binary_builds(recipe, 0)
        self.assertEqual(sleep_mock.call_count, 9)

    def test_recipe_name_to_source_name(self):
        self.assertEqual(
            lp_build_monitor_recipe.recipe_name_to_source_name(
                "checkbox-ng-edge"
            ),
            "checkbox-ng",
        )


class TestMonitorRetryBuilds(unittest.TestCase):
    @patch("time.sleep")
    @patch("lp_build_monitor_recipe.get_all_source_builds")
    def test_monitor_retry_builds_success(
        self, get_all_source_builds_mock, time_sleep_mock
    ):
        build_mock = MagicMock()
        build_mock.buildstate = "Successfully built"

        lp_build_monitor_recipe.monitor_retry_builds([build_mock])
        self.assertFalse(time_sleep_mock.called)

    @patch("time.sleep")
    def test_monitor_retry_builds_retry_failures(self, time_sleep_mock):
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

        lp_build_monitor_recipe.monitor_retry_builds([build_mock])

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 6)
        # we didnt fload LP with requests, waiting once per progress
        self.assertEqual(time_sleep_mock.call_count, 5)
        # each time a failure was detected, the build was retried
        self.assertEqual(build_mock.retry.call_count, 3)

    @patch("time.sleep")
    def test_monitor_retry_builds_robust(self, time_sleep_mock):
        build_mock = MagicMock()
        # A build is updated via the lp_refresh function, lets do the same
        # here but inject our test values
        build_status_evolution = [
            "Successfully built",
            None,  # this may be possible for pending builds
        ]

        def lp_refresh_side_effect():
            if build_status_evolution:
                build_mock.buildstate = build_status_evolution.pop()

        build_mock.lp_refresh.side_effect = lp_refresh_side_effect

        lp_build_monitor_recipe.monitor_retry_builds([build_mock])

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 2)
        # we didnt fload LP with requests, waiting once per progress
        self.assertEqual(time_sleep_mock.call_count, 1)

    @patch("time.sleep")
    def test_monitor_retry_builds_more_wait(self, time_sleep_mock):
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

        lp_build_monitor_recipe.monitor_retry_builds([build_mock])

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 5)
        # we didnt fload LP with requests, waiting once per progress
        self.assertEqual(time_sleep_mock.call_count, 4)

    @patch("time.sleep")
    def test_monitor_retry_builds_unrecoverable_failures(
        self, time_sleep_mock
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

        unrecoverable = lp_build_monitor_recipe.monitor_retry_builds(
            [build_mock]
        )

        # we updated till the build reported a success
        self.assertEqual(build_mock.lp_refresh.call_count, 1)
        # each time a failure was detected, the build was retried
        self.assertEqual(build_mock.retry.call_count, 0)
        # we don't update a build that can't be retried at all
        self.assertEqual(len(build_status_evolution), 1)
        # we get back the build that failed
        self.assertEqual(len(unrecoverable), 1)


class TestMain(unittest.TestCase):
    @patch("lp_build_monitor_recipe.build_monitor_recipe")
    def test_timeout(self, monitor_mock):
        monitor_mock.side_effect = TimeoutError("The read operation timed out")

        with self.assertRaisesRegex(
            SystemExit,
            "^Launchpad request timed out: The read operation timed out$",
        ):
            lp_build_monitor_recipe.main(["checkbox", "some_recipe"])

    @patch("lp_build_monitor_recipe.build_monitor_recipe")
    def test_unexpected_error(self, monitor_mock):
        monitor_mock.side_effect = ValueError("Unexpected error")

        with self.assertRaisesRegex(ValueError, "Unexpected error"):
            lp_build_monitor_recipe.main(["checkbox", "some_recipe"])

    @patch("time.sleep", new=MagicMock())
    @patch(
        "lp_build_monitor_recipe.get_date_utc_now",
        new=MagicMock(return_value=10),
    )
    @patch("lp_build_monitor_recipe.get_source_build_recipe")
    def test_success(self, get_source_build_recipe_mock):
        recipe_mock = get_source_build_recipe_mock()
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

        # Setup of the binary build
        recipe_mock.daily_build_archive.getBuildCounters.side_effect = [
            {"pending": 1},
            {"pending": 0},
        ]

        recipe_mock.name = "checkbox-ng-edge"

        bin_build_mock = MagicMock()
        bin_build_mock.date_first_dispatched = 20
        recipe_mock.daily_build_archive.getBuildRecords.return_value = [
            bin_build_mock
        ]
        bin_build_mock.can_be_retried = False
        bin_build_mock.buildstate = "Successfully built"

        lp_build_monitor_recipe.main(["checkbox", "some_recipe"])

        get_source_build_recipe_mock.assert_called_with(
            "checkbox", "some_recipe", timeout=30
        )
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
    @patch("lp_build_monitor_recipe.get_source_build_recipe")
    def test_failure(self, get_source_build_recipe_mock):
        # Setup of the source build
        recipe_mock = get_source_build_recipe_mock()
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

        # Setup of the binary build
        recipe_mock.daily_build_archive.getBuildCounters.side_effect = [
            {"pending": 1},
            {"pending": 0},
        ]

        recipe_mock.name = "checkbox-ng-edge"

        bin_build_mock = MagicMock()
        bin_build_mock.date_first_dispatched = 20
        recipe_mock.daily_build_archive.getBuildRecords.return_value = [
            bin_build_mock
        ]
        bin_build_mock.can_be_retried = False
        bin_build_mock.web_link = "https://build_link.com"
        bin_build_mock.buildstate = "Failed to build"

        with self.assertRaises(SystemExit):
            lp_build_monitor_recipe.main(["checkbox", "some_recipe"])

        self.assertEqual(recipe_mock.requestBuild.call_count, 3)
        self.assertEqual(recipe_mock.getPendingBuildInfo.call_count, 1)
        # all the build that didnt unrecoverably fail were followed to
        # completion
        self.assertFalse(build_status_evolution)
