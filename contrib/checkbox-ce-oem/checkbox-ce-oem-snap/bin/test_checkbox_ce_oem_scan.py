"""Unit tests for checkbox_ce_oem_scan (the urwid-free scanning core)."""

import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

_SCRIPT = Path(__file__).parent / "checkbox_ce_oem_scan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "checkbox_ce_oem_scan", _SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["checkbox_ce_oem_scan"] = mod
    spec.loader.exec_module(mod)
    return mod


gl = _load_module()


class TestFindRepoRoot(unittest.TestCase):
    def test_finds_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "providers").mkdir()
            (root / "contrib").mkdir()
            deep = root / "a" / "b" / "c"
            deep.mkdir(parents=True)
            self.assertEqual(gl.find_repo_root(deep), root)

    def test_raises_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                gl.find_repo_root(Path(tmp))


class TestFindDefaultRepoRoots(unittest.TestCase):
    def test_prefers_checkbox_ce_oem_and_checkboxnn_snaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_base = Path(tmp)
            for name in ("checkbox-ce-oem", "checkbox22", "checkbox24"):
                (snap_base / name / "current").mkdir(parents=True)
            # A non-matching directory must be ignored.
            (snap_base / "other-snap" / "current").mkdir(parents=True)

            roots = gl.find_default_repo_roots(snap_base=snap_base)

            self.assertEqual(
                roots,
                [
                    snap_base / "checkbox-ce-oem" / "current",
                    snap_base / "checkbox22" / "current",
                    snap_base / "checkbox24" / "current",
                ],
            )

    def test_skips_missing_snap_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_base = Path(tmp)
            # Only checkbox26 is installed; checkbox-ce-oem is not.
            (snap_base / "checkbox26" / "current").mkdir(parents=True)

            roots = gl.find_default_repo_roots(snap_base=snap_base)

            self.assertEqual(roots, [snap_base / "checkbox26" / "current"])

    def test_falls_back_to_repo_root_when_no_snaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_base = Path(tmp) / "snap"  # does not exist
            with unittest.mock.patch.object(
                gl, "find_repo_root", return_value=Path("/fake/repo")
            ) as mock_find:
                roots = gl.find_default_repo_roots(snap_base=snap_base)
            mock_find.assert_called_once()
            self.assertEqual(roots, [Path("/fake/repo")])


class TestParsePxuBlocks(unittest.TestCase):
    def test_simple_job(self):
        content = "id: my-job\nplugin: shell\nsummary: A test\n"
        blocks = gl.parse_pxu_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["id"], "my-job")
        self.assertEqual(blocks[0]["summary"], "A test")

    def test_multiline_value(self):
        content = "id: x\ncommand: foo\n bar\n"
        blocks = gl.parse_pxu_blocks(content)
        self.assertIn("bar", blocks[0]["command"])

    def test_skips_comments(self):
        content = "# comment\nid: x\n"
        blocks = gl.parse_pxu_blocks(content)
        self.assertNotIn("# comment", blocks[0])

    def test_multiple_blocks(self):
        content = "id: a\n\nid: b\n"
        self.assertEqual(len(gl.parse_pxu_blocks(content)), 2)


class TestParseIds(unittest.TestCase):
    def test_basic(self):
        raw = "  pattern-one\n  pattern-two\n"
        self.assertEqual(gl._parse_ids(raw), ["pattern-one", "pattern-two"])

    def test_strips_inline_options(self):
        raw = "  job-id certification-status=blocker\n"
        self.assertEqual(gl._parse_ids(raw), ["job-id"])

    def test_ignores_comments(self):
        raw = "# comment\njob-id\n"
        self.assertEqual(gl._parse_ids(raw), ["job-id"])

    def test_empty(self):
        self.assertEqual(gl._parse_ids(""), [])


class TestGetProviderNamespace(unittest.TestCase):
    def test_finds_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prov = root / "myprovider"
            prov.mkdir()
            manage = prov / "manage.py"
            manage.write_text('setup(namespace="com.example.test")\n')
            pxu = prov / "units" / "jobs.pxu"
            pxu.parent.mkdir()
            pxu.touch()
            self.assertEqual(
                gl.get_provider_namespace(pxu, root),
                "com.example.test",
            )

    def test_returns_unknown_when_no_manage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pxu = root / "jobs.pxu"
            pxu.touch()
            self.assertEqual(gl.get_provider_namespace(pxu, root), "unknown")

    def test_finds_namespace_from_provider_file(self):
        """Installed/snap providers ship a `<name>.provider` ini file
        (written by `manage.py install`) instead of manage.py."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prov = root / "checkbox-provider-ce-oem"
            prov.mkdir()
            provider_file = prov / "checkbox-provider-ce-oem.provider"
            provider_file.write_text(
                "[PlainBox Provider]\n"
                "name = com.canonical.contrib:checkbox-provider-ce-oem\n"
                "namespace = com.canonical.contrib\n"
                "version = 1.0\n"
            )
            pxu = prov / "units" / "jobs.pxu"
            pxu.parent.mkdir()
            pxu.touch()
            self.assertEqual(
                gl.get_provider_namespace(pxu, root),
                "com.canonical.contrib",
            )

    def test_provider_file_falls_back_to_name_prefix(self):
        """When a `.provider` file has no dedicated `namespace` key, the
        namespace falls back to the part of `name` before the colon."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prov = root / "myprov"
            prov.mkdir()
            provider_file = prov / "myprov.provider"
            provider_file.write_text(
                "[PlainBox Provider]\n"
                "name = org.example:myprov\n"
                "version = 1.0\n"
            )
            pxu = prov / "units" / "jobs.pxu"
            pxu.parent.mkdir()
            pxu.touch()
            self.assertEqual(
                gl.get_provider_namespace(pxu, root), "org.example"
            )


class TestBuildCache(unittest.TestCase):
    def _make_repo(self, tmp):
        root = Path(tmp)
        (root / "providers").mkdir()
        (root / "contrib").mkdir()
        prov = root / "providers" / "myprov"
        prov.mkdir()
        manage = prov / "manage.py"
        manage.write_text('setup(namespace="com.example")\n')
        units = prov / "units"
        units.mkdir()
        pxu = units / "jobs.pxu"
        pxu.write_text(
            "unit: job\nid: my-job\nsummary: A job\n"
            "environ: MYVAR\n"
            "requires: manifest.has_thing == 'True'\n"
            "\nunit: test plan\nid: ce-oem-my-plan\n"
            "_name: My Plan\n"
            "include: my-job\n"
            "\nunit: manifest entry\nid: has_thing\n"
            "_name: The thing\n_prompt: Does it have it?\n"
            "value-type: bool\n"
        )
        return root

    def test_parses_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            cache = gl.build_cache([root])
            self.assertIn("com.example::my-job", cache["jobs"])
            job = cache["jobs"]["com.example::my-job"]
            self.assertEqual(job["summary"], "A job")
            self.assertIn("MYVAR", job["environ"])
            self.assertIn("has_thing", job["manifest"])
            self.assertEqual(job["manifest"], sorted(job["manifest"]))

    def test_job_has_bare_id_requires_and_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            cache = gl.build_cache([root])
            job = cache["jobs"]["com.example::my-job"]
            self.assertEqual(job["bare_id"], "my-job")
            self.assertEqual(job["requires"], "manifest.has_thing == 'True'")
            self.assertEqual(
                job["source_file"], "providers/myprov/units/jobs.pxu"
            )

    def test_manifest_entry_has_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            cache = gl.build_cache([root])
            entry = cache["manifest_entries"]["has_thing"]
            self.assertEqual(
                entry["source_file"], "providers/myprov/units/jobs.pxu"
            )

    def test_purpose_kept_separate_from_description(self):
        """`_description` wins for job["description"], but job["purpose"]
        always holds the raw `_purpose` text — real ce-oem jobs (e.g.
        gadget/check-snap-interface-conf) define both: a short `_purpose`
        naming what an environ var is for, and a longer `_description`
        with usage detail that would otherwise shadow it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            pxu = root / "providers" / "myprov" / "units" / "envjob.pxu"
            pxu.write_text(
                "unit: job\nid: env-job\nsummary: Env job\n"
                "environ: SOME_FILE\n"
                "_purpose: Check if SOME_FILE has been defined\n"
                "_description:\n"
                "    Usage details go here.\n"
            )
            cache = gl.build_cache([root])
            job = cache["jobs"]["com.example::env-job"]
            self.assertEqual(
                job["purpose"], "Check if SOME_FILE has been defined"
            )
            self.assertEqual(
                job["description"].strip(), "Usage details go here."
            )

    def test_parses_test_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            cache = gl.build_cache([root])
            self.assertIn("com.example::ce-oem-my-plan", cache["test_plans"])
            plan = cache["test_plans"]["com.example::ce-oem-my-plan"]
            self.assertEqual(plan["name"], "My Plan")
            self.assertIn("my-job", plan["include"])

    def test_parses_manifest_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            cache = gl.build_cache([root])
            self.assertIn("has_thing", cache["manifest_entries"])
            entry = cache["manifest_entries"]["has_thing"]
            self.assertEqual(entry["full_id"], "com.example::has_thing")
            self.assertEqual(entry["name"], "The thing")
            self.assertEqual(entry["value_type"], "bool")

    def test_hidden_manifest_entry_excluded(self):
        """Manifest entries with a bare id starting with '_' are hidden."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            pxu = root / "providers" / "myprov" / "units" / "hidden.pxu"
            pxu.write_text(
                "unit: manifest entry\nid: _internal_flag\n"
                "_name: Internal\nvalue-type: bool\n"
            )
            cache = gl.build_cache([root])
            self.assertNotIn("_internal_flag", cache["manifest_entries"])

    def test_installed_provider_layout_gets_correct_namespace(self):
        """A snap-style install (`.provider` file, no manage.py) must
        resolve the real namespace instead of falling back to
        "unknown"."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prov = root / "checkbox-provider-ce-oem"
            units = prov / "units"
            units.mkdir(parents=True)
            (prov / "checkbox-provider-ce-oem.provider").write_text(
                "[PlainBox Provider]\n"
                "name = com.canonical.contrib:checkbox-provider-ce-oem\n"
                "namespace = com.canonical.contrib\n"
                "version = 1.0\n"
            )
            (units / "jobs.pxu").write_text(
                "unit: manifest entry\nid: has_gpio\n_name: GPIO\n"
                "value-type: bool\n"
                "\nunit: job\nid: my-job\nsummary: A job\n"
                "requires: manifest.has_gpio == 'True'\n"
            )
            cache = gl.build_cache([root])
            entry = cache["manifest_entries"]["has_gpio"]
            self.assertEqual(
                entry["full_id"], "com.canonical.contrib::has_gpio"
            )
            job = cache["jobs"]["com.canonical.contrib::my-job"]
            self.assertEqual(job["provider"], "com.canonical.contrib")

    def test_scans_multiple_roots_first_wins(self):
        """When two roots define the same job/plan/manifest id, the one
        from the first root in the list is kept."""
        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                root1 = self._make_repo(tmp1)
                root2 = self._make_repo(tmp2)
                # Give the second root's job a different summary so we
                # can tell which one "won".
                pxu2 = root2 / "providers" / "myprov" / "units" / "jobs.pxu"
                pxu2.write_text("unit: job\nid: my-job\nsummary: From root2\n")
                cache = gl.build_cache([root1, root2])
                job = cache["jobs"]["com.example::my-job"]
                self.assertEqual(job["summary"], "A job")
                self.assertEqual(cache["repo_path"], [str(root1), str(root2)])


class TestCacheStaleness(unittest.TestCase):
    def test_stale_when_missing(self):
        self.assertTrue(
            gl.is_cache_stale(Path("/tmp/nonexistent_xyz.json"), [Path(".")])
        )

    def test_fresh_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pxu = root / "a.pxu"
            pxu.write_text("id: x\n")
            import time

            time.sleep(0.01)
            cache_f = root / "cache.json"
            cache_f.write_text("{}")
            self.assertFalse(gl.is_cache_stale(cache_f, [root]))

    def test_stale_when_pxu_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_f = root / "cache.json"
            cache_f.write_text("{}")
            import time

            time.sleep(0.01)
            pxu = root / "a.pxu"
            pxu.write_text("id: x\n")
            self.assertTrue(gl.is_cache_stale(cache_f, [root]))

    def test_version_mismatch_triggers_rebuild(self):
        """load_or_build_cache rebuilds when stored _version != _CACHE_VERSION."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pxu = root / "a.pxu"
            pxu.write_text("")
            import time

            time.sleep(0.01)
            cp = gl.cache_path([root])
            # Write a cache with a wrong version that looks fresh.
            cp.write_text(
                json.dumps(
                    {
                        "_version": -999,
                        "jobs": {},
                        "test_plans": {},
                        "manifest_entries": {},
                    }
                )
            )
            # Touch the pxu with an older mtime so staleness check passes.
            import os

            old = cp.stat().st_mtime + 1
            os.utime(cp, (old, old))
            # load_or_build_cache should rebuild; rebuilt cache has correct version.
            data = gl.load_or_build_cache([root], force=False)
            self.assertEqual(data["_version"], gl._CACHE_VERSION)
            cp.unlink(missing_ok=True)


class TestDiscoverTopLevelPlans(unittest.TestCase):
    def _plan(self, pid, nested=None, include=None):
        return {
            "id": pid,
            "name": pid,
            "include": include or [],
            "exclude": [],
            "nested_part": nested or [],
            "bootstrap_include": [],
            "source_file": "some-file.pxu",
        }

    def _cache(self):
        return {
            "jobs": {},
            "manifest_entries": {},
            "test_plans": {
                "ns::ce-oem-iot-desktop-2404": self._plan(
                    "ce-oem-iot-desktop-2404", nested=["ns::ce-oem-iot-sub"]
                ),
                "ns::ce-oem-iot-server-2204-04": self._plan(
                    "ce-oem-iot-server-2204-04"
                ),
                # not a top-level id: doesn't match the prefix pattern
                "ns::ce-oem-iot-sub": self._plan("ce-oem-iot-sub"),
                # wrong prefix entirely
                "ns::other-plan": self._plan("other-plan"),
            },
        }

    def test_matches_platform_version_ids(self):
        result = gl.discover_top_level_plans(self._cache())
        ids = [pid for _, pid, _ in result]
        self.assertIn("ce-oem-iot-desktop-2404", ids)
        self.assertIn("ce-oem-iot-server-2204-04", ids)

    def test_excludes_non_matching_ids(self):
        result = gl.discover_top_level_plans(self._cache())
        ids = [pid for _, pid, _ in result]
        self.assertNotIn("ce-oem-iot-sub", ids)
        self.assertNotIn("other-plan", ids)

    def test_custom_prefix(self):
        cache = self._cache()
        cache["test_plans"]["ns::custom-prefix-desktop-2404"] = self._plan(
            "custom-prefix-desktop-2404"
        )
        result = gl.discover_top_level_plans(
            cache, plan_prefix="custom-prefix"
        )
        ids = [pid for _, pid, _ in result]
        self.assertEqual(ids, ["custom-prefix-desktop-2404"])

    def test_sorted(self):
        result = gl.discover_top_level_plans(self._cache())
        self.assertEqual(result, sorted(result))


class TestExpandPlan(unittest.TestCase):
    def _cache(self):
        return {
            "manifest_entries": {},
            "test_plans": {
                "ns::my-plan": {
                    "id": "my-plan",
                    "name": "",
                    "include": ["job-a", "job-b"],
                    "exclude": ["job-b"],
                    "nested_part": [],
                },
            },
            "jobs": {
                "ns::job-a": {
                    "id": "ns::job-a",
                    "environ": [],
                    "manifest": [],
                    "summary": "",
                    "description": "",
                    "command": "",
                    "provider": "ns",
                    "unit_type": "job",
                },
                "ns::job-b": {
                    "id": "ns::job-b",
                    "environ": [],
                    "manifest": [],
                    "summary": "",
                    "description": "",
                    "command": "",
                    "provider": "ns",
                    "unit_type": "job",
                },
            },
        }

    def test_includes_matching_jobs(self):
        result = gl.expand_plan("ns::my-plan", self._cache())
        self.assertIn("ns::job-a", result)

    def test_excludes_excluded_jobs(self):
        result = gl.expand_plan("ns::my-plan", self._cache())
        self.assertNotIn("ns::job-b", result)

    def test_raises_on_unknown_plan(self):
        with self.assertRaises(ValueError):
            gl.expand_plan("ns::no-such-plan", self._cache())


class TestGetRelatedJobs(unittest.TestCase):
    def _cache_with_jobs(self):
        return {
            "manifest_entries": {},
            "test_plans": {},
            "jobs": {
                "ns::j1": {
                    "id": "ns::j1",
                    "summary": "J1",
                    "description": "",
                    "environ": ["MYVAR"],
                    "manifest": ["has_gpio"],
                    "command": "",
                    "provider": "ns",
                    "unit_type": "job",
                },
                "ns::j2": {
                    "id": "ns::j2",
                    "summary": "J2",
                    "description": "",
                    "environ": [],
                    "manifest": [],
                    "command": "",
                    "provider": "ns",
                    "unit_type": "job",
                },
            },
        }

    def test_related_by_manifest(self):
        cache = self._cache_with_jobs()
        result = gl.get_related_jobs(
            "manifest", "has_gpio", {"ns::j1", "ns::j2"}, cache
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "ns::j1")

    def test_related_by_environ(self):
        cache = self._cache_with_jobs()
        result = gl.get_related_jobs(
            "environ", "MYVAR", {"ns::j1", "ns::j2"}, cache
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "ns::j1")

    def test_includes_purpose_defaulting_to_empty(self):
        cache = self._cache_with_jobs()
        result = gl.get_related_jobs(
            "environ", "MYVAR", {"ns::j1", "ns::j2"}, cache
        )
        self.assertEqual(result[0]["purpose"], "")

    def test_only_searches_job_ids_subset(self):
        # get_related_jobs now searches ALL cache jobs regardless of job_ids,
        # so ns::j1 (which uses has_gpio) is always returned even if not in job_ids.
        cache = self._cache_with_jobs()
        result = gl.get_related_jobs("manifest", "has_gpio", {"ns::j2"}, cache)
        self.assertEqual([r["id"] for r in result], ["ns::j1"])


class TestMatches(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(gl._matches("exact-id", "exact-id"))

    def test_glob_wildcard(self):
        self.assertTrue(gl._matches("com.canonical.*", "com.canonical.foo"))

    def test_no_match(self):
        self.assertFalse(gl._matches("foo", "bar"))

    def test_dot_not_wildcard_without_star(self):
        self.assertFalse(gl._matches("a.b", "axb"))


class TestNormalize(unittest.TestCase):
    def test_index_prefix(self):
        self.assertEqual(gl._normalize("test/1_step"), "test/INDEX_step")

    def test_no_change(self):
        self.assertEqual(gl._normalize("plain-id"), "plain-id")


class TestExpandPlanRecursive(unittest.TestCase):
    """Verify multi-level nested_part recursion and visited cycle-breaking."""

    def _cache(self):
        return {
            "manifest_entries": {},
            "test_plans": {
                "ns::plan-a": {
                    "id": "plan-a",
                    "name": "",
                    "include": [],
                    "exclude": [],
                    "nested_part": ["ns::plan-b"],
                },
                "ns::plan-b": {
                    "id": "plan-b",
                    "name": "",
                    "include": [],
                    "exclude": [],
                    "nested_part": ["ns::plan-c"],
                },
                "ns::plan-c": {
                    "id": "plan-c",
                    "name": "",
                    "include": ["job-c"],
                    "exclude": [],
                    "nested_part": [],
                },
            },
            "jobs": {
                "ns::job-c": {
                    "id": "ns::job-c",
                    "environ": [],
                    "manifest": [],
                    "summary": "",
                    "description": "",
                    "command": "",
                    "provider": "ns",
                    "unit_type": "job",
                },
            },
        }

    def test_deep_nesting_resolves_leaf_jobs(self):
        result = gl.expand_plan("ns::plan-a", self._cache())
        self.assertIn("ns::job-c", result)

    def test_cycle_does_not_loop_forever(self):
        cache = self._cache()
        # create a cycle: plan-c references plan-a
        cache["test_plans"]["ns::plan-c"]["nested_part"] = ["ns::plan-a"]
        result = gl.expand_plan("ns::plan-a", cache)
        self.assertIn("ns::job-c", result)


class TestDumpInventoryJson(unittest.TestCase):
    def _cache(self):
        return {
            "jobs": {
                "ns::job-a": {
                    "id": "ns::job-a",
                    "bare_id": "job-a",
                    "summary": "Job A",
                    "description": "Does A",
                    "environ": ["SOME_VAR"],
                    "command": "run-a",
                    "requires": "manifest.has_thing == 'True'",
                    "source_file": "units/a.pxu",
                },
                "ns::job-b": {
                    "id": "ns::job-b",
                    "bare_id": "job-b",
                    "summary": "Job B",
                    "description": "Does B",
                    "environ": [],
                    "command": "run-b",
                    "requires": "",
                    "source_file": "units/b.pxu",
                },
            },
            "manifest_entries": {
                "has_thing": {
                    "full_id": "ns::has_thing",
                    "name": "Has thing",
                    "prompt": "Does it have the thing?",
                    "value_type": "bool",
                    "source_file": "units/manifest.pxu",
                }
            },
            "test_plans": {},
        }

    def test_top_level_fields(self):
        data = gl.dump_inventory_json(
            self._cache(),
            {"ns::job-a", "ns::job-b"},
            version="24.04",
            plan_full_ids=("ns::ce-oem-iot-desktop-2404",),
            checkbox_repository="https://github.com/canonical/checkbox",
            checkbox_commit="abc123",
        )
        self.assertEqual(data["version"], "24.04")
        self.assertEqual(
            data["plan_full_ids"], ["ns::ce-oem-iot-desktop-2404"]
        )
        self.assertEqual(
            data["checkbox_repository"],
            "https://github.com/canonical/checkbox",
        )
        self.assertEqual(data["checkbox_commit"], "abc123")

    def test_manifest_record_shape(self):
        data = gl.dump_inventory_json(
            self._cache(),
            {"ns::job-a", "ns::job-b"},
            version="24.04",
            plan_full_ids=("ns::plan",),
            checkbox_repository="",
            checkbox_commit="",
        )
        self.assertEqual(len(data["manifests"]), 1)
        entry = data["manifests"][0]
        self.assertEqual(entry["key"], "has_thing")
        self.assertEqual(entry["full_id"], "ns::has_thing")
        self.assertEqual(entry["name"], "Has thing")
        self.assertEqual(entry["prompt"], "Does it have the thing?")
        self.assertEqual(entry["value_type"], "bool")
        self.assertEqual(entry["source_file"], "units/manifest.pxu")
        self.assertEqual(len(entry["related_jobs"]), 1)
        job = entry["related_jobs"][0]
        self.assertEqual(
            set(job.keys()),
            {
                "full_id",
                "bare_id",
                "summary",
                "description",
                "environ",
                "command",
                "requires",
                "source_file",
            },
        )
        self.assertEqual(job["full_id"], "ns::job-a")
        self.assertEqual(job["bare_id"], "job-a")

    def test_environment_record_shape(self):
        data = gl.dump_inventory_json(
            self._cache(),
            {"ns::job-a", "ns::job-b"},
            version="24.04",
            plan_full_ids=("ns::plan",),
            checkbox_repository="",
            checkbox_commit="",
        )
        self.assertEqual(len(data["environments"]), 1)
        env = data["environments"][0]
        self.assertEqual(env["key"], "SOME_VAR")
        self.assertEqual(len(env["related_jobs"]), 1)
        self.assertEqual(env["related_jobs"][0]["full_id"], "ns::job-a")

    def test_missing_job_id_raises(self):
        with self.assertRaises(KeyError):
            gl.dump_inventory_json(
                self._cache(),
                {"ns::does-not-exist"},
                version="24.04",
                plan_full_ids=("ns::plan",),
                checkbox_repository="",
                checkbox_commit="",
            )


class TestMain(unittest.TestCase):
    def _make_repo(self, tmp):
        root = Path(tmp)
        (root / "providers").mkdir()
        (root / "contrib").mkdir()
        prov = root / "providers" / "myprov"
        units = prov / "units"
        units.mkdir(parents=True)
        (prov / "manage.py").write_text('setup(namespace="com.example")\n')
        (units / "jobs.pxu").write_text(
            "unit: job\nid: my-job\nsummary: A job\n"
            "environ: MYVAR\n"
            "requires: manifest.has_thing == 'True'\n"
            "\nunit: test plan\nid: ce-oem-iot-desktop-24-04\n"
            "_name: Desktop 24.04\n"
            "include: my-job\n"
            "\nunit: manifest entry\nid: has_thing\n"
            "_name: The thing\n_prompt: Does it have it?\n"
            "value-type: bool\n"
        )
        return root

    def test_writes_one_json_per_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            out_dir = Path(tmp) / "out"
            rc = gl.main(
                [
                    "--providers-dir",
                    str(root),
                    "--output-dir",
                    str(out_dir),
                    "--checkbox-repository",
                    "https://example.com/repo",
                    "--checkbox-commit",
                    "deadbeef",
                ]
            )
            self.assertEqual(rc, 0)
            out_file = out_dir / "24.04.json"
            self.assertTrue(out_file.is_file())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "24.04")
            self.assertEqual(
                data["checkbox_repository"], "https://example.com/repo"
            )
            self.assertEqual(data["checkbox_commit"], "deadbeef")
            self.assertEqual(len(data["manifests"]), 1)

    def test_no_matching_plans_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            out_dir = Path(tmp) / "out"
            rc = gl.main(
                [
                    "--providers-dir",
                    str(root),
                    "--plan-prefix",
                    "no-such-prefix",
                    "--output-dir",
                    str(out_dir),
                ]
            )
            self.assertEqual(rc, 1)

    def test_missing_providers_dir_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = gl.main(
                [
                    "--providers-dir",
                    str(Path(tmp) / "does-not-exist"),
                    "--output-dir",
                    str(Path(tmp) / "out"),
                ]
            )
            self.assertEqual(rc, 1)
