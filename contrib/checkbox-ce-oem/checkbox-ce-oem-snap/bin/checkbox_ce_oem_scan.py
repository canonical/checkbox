#!/usr/bin/env python3
"""checkbox_ce_oem_scan.py — Scan checkbox CE-OEM providers into a cache.

Pure scanning/discovery core shared by ``gen_launcher.py`` (interactive
TUI) and this module's own standalone CLI (JSON inventory dump). Contains
no ``urwid`` dependency so it can be imported or run in non-interactive
contexts (e.g. CI).

Usage (standalone CLI):
    python3 checkbox_ce_oem_scan.py --providers-dir PATH \\
        --plan-prefix ce-oem-iot --output-dir OUT/
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

# Bump whenever the cache schema changes so stale caches are auto-invalidated.
_CACHE_VERSION = 9

_MAN_RE = re.compile(r"manifest\.([a-zA-Z0-9_]+)")
_SKIP_UNIT_TYPES = frozenset(
    {
        "category",
        "packaging meta-data",
        "exporter",
        "attachment",
    }
)

# Vars jobs may declare in `environ:` that are set by the OS/desktop
# session or the Checkbox runtime itself, never by an ODM integrator.
# Hidden from both the JSON inventory dump and gen_launcher.py's TUI.
_RESERVED_ENVIRON_NAMES = frozenset(
    {
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_TYPE",
        "PLAINBOX_PROVIDER_DATA",
        "PLAINBOX_SESSION_SHARE",
    }
)
_RESERVED_ENVIRON_PREFIXES = ("XDG_", "PLAINBOX_")


def _is_reserved_environ(name: str) -> bool:
    """Return True if *name* is an OS/runtime-reserved environ var.

    These are set by the desktop session or the Checkbox runtime, so
    surfacing them as ODM-configurable launcher values would only
    invite type errors (manifests only support bool) and confusion.
    """
    return name in _RESERVED_ENVIRON_NAMES or name.startswith(
        _RESERVED_ENVIRON_PREFIXES
    )


def find_repo_root(start: Path) -> Path:
    """Walk up from *start* to find the checkbox checkout root.

    The root is the first ancestor directory that contains both a
    ``providers/`` and a ``contrib/`` subdirectory.

    Raises FileNotFoundError if no such directory is found.
    """
    current = start.resolve()
    while current != current.parent:
        if (current / "providers").is_dir() and (current / "contrib").is_dir():
            return current
        current = current.parent
    raise FileNotFoundError(
        f"Cannot locate checkbox repo root from {start}. "
        "Use --providers-dir to specify it explicitly."
    )


# Matches installed checkboxNN content snaps, e.g. checkbox20/22/24/26.
_CHECKBOXNN_RE = re.compile(r"checkbox\d+")


def find_default_repo_roots(snap_base: Path = Path("/snap")) -> list[Path]:
    """Return the default provider repo root(s) to scan.

    Prefers installed checkbox snaps, so both the ce-oem provider and
    the generic provider content shipped with the base checkbox snap
    are covered:

      - ``<snap_base>/checkbox-ce-oem/current``
      - ``<snap_base>/checkboxNN/current`` (NN = digits, e.g. 20/22/24/26)

    *snap_base* defaults to ``/snap`` and is only overridable for tests.

    Falls back to the enclosing git checkout (walking up from this
    script to find a directory containing both ``providers/`` and
    ``contrib/``) when no such snap is installed, so the tool still
    works for developers running it straight from a checkout.

    Raises FileNotFoundError if neither snaps nor a checkout root can
    be found.
    """
    candidates: list[Path] = [snap_base / "checkbox-ce-oem" / "current"]
    if snap_base.exists():
        for entry in sorted(snap_base.iterdir()):
            if _CHECKBOXNN_RE.fullmatch(entry.name):
                candidates.append(entry / "current")
    found = [p for p in candidates if p.is_dir()]
    if found:
        return found
    return [find_repo_root(Path(__file__).parent)]


def get_provider_namespace(pxu_path: Path, repo_root: Path) -> str:
    """Return the namespace declared for the provider owning *pxu_path*.

    Two provider metadata formats are supported, checked at each
    ancestor directory on the way up to *repo_root*:

    - ``manage.py`` (source checkouts): looks for
      ``namespace = "com.canonical.contrib"`` or falls back to
      ``name = "com.canonical.certification:provider-name"`` (namespace
      is the part before the first colon).
    - ``*.provider`` (installed/snap providers, written by
      ``manage.py install``): an ini file with a ``[PlainBox Provider]``
      section containing ``namespace`` (or ``name`` as a fallback, same
      rule as above). This is the format actually shipped inside
      installed checkbox snaps, which do not carry ``manage.py``.

    Returns ``"unknown"`` if neither file is found or the namespace
    cannot be parsed.
    """
    current = pxu_path.parent
    stop = repo_root.parent
    while current != stop and current != current.parent:
        manage = current / "manage.py"
        if manage.exists():
            try:
                text = manage.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"namespace\s*=\s*['\"]([^'\"]+)['\"]", text)
                if m:
                    return m.group(1)
                # Fallback: name="namespace:provider-name" (no explicit namespace=)
                m = re.search(
                    r"""\bname\s*=\s*["']([^"':]+):[^"']+["']""", text
                )
                if m:
                    return m.group(1)
            except OSError:
                pass
            return "unknown"

        provider_files = sorted(current.glob("*.provider"))
        if provider_files:
            ns = _namespace_from_provider_file(provider_files[0])
            return ns if ns else "unknown"

        current = current.parent
    return "unknown"


def _namespace_from_provider_file(provider_file: Path) -> str:
    """Return the namespace declared in an installed ``*.provider`` file.

    Falls back to the part of ``name`` before the first ``:`` when no
    dedicated ``namespace`` key is present, mirroring plainbox's own
    ``Provider1`` fallback rule. Returns ``""`` if the file cannot be
    parsed or has neither key.
    """
    parser = configparser.ConfigParser()
    try:
        parser.read(provider_file, encoding="utf-8")
    except (OSError, configparser.Error):
        return ""
    section = "PlainBox Provider"
    if not parser.has_section(section):
        return ""
    if parser.has_option(section, "namespace"):
        return parser.get(section, "namespace").strip()
    if parser.has_option(section, "name"):
        name = parser.get(section, "name").strip()
        if ":" in name:
            return name.split(":", 1)[0]
    return ""


def parse_pxu_blocks(content: str) -> list[dict]:
    """Parse PXU *content* into a list of unit attribute dicts.

    Each blank-line-separated block becomes one dict.  Continuation lines
    (starting with whitespace) are appended to the current key's value.
    Comment lines (starting with ``#``) are ignored.

    >>> blocks = parse_pxu_blocks("id: foo\\nsummary: bar\\n")
    >>> blocks[0]["id"]
    'foo'
    """
    units = []
    for block in re.split(r"\n\s*\n", content):
        if not block.strip():
            continue
        unit: dict[str, str] = {}
        current_key: str | None = None
        for line in block.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith((" ", "\t")):
                if current_key:
                    unit[current_key] += "\n" + line.strip()
            elif ":" in line:
                key, _, value = line.partition(":")
                current_key = key.strip()
                unit[current_key] = value.strip()
        if unit:
            units.append(unit)
    return units


def _parse_ids(raw: str) -> list[str]:
    """Parse a multi-line ``include``/``exclude``/``nested_part`` field.

    Each non-empty, non-comment line contributes its first whitespace-
    separated token (the ID or glob pattern); inline option pairs like
    ``certification-status=blocker`` are discarded.

    >>> _parse_ids("  job-a certification-status=blocker\\n  job-b\\n")
    ['job-a', 'job-b']
    """
    ids = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line.split()[0])
    return ids


def build_cache(repo_roots: list[Path]) -> dict:
    """Scan every ``*.pxu`` file under *repo_roots* and return the cache dict.

    *repo_roots* may list more than one directory (e.g. both the
    ``checkbox-ce-oem`` and a ``checkboxNN`` snap) to get full test plan
    coverage; results are merged, keeping the first occurrence of any
    job/plan/manifest id seen (roots are scanned in order).

    Skips units of type ``category``, ``packaging meta-data``,
    ``exporter``, ``attachment``, and ``resource``.  Legacy
    ``plugin:``-based job blocks (no ``unit:`` field) are treated as
    ``unit: job``. Hidden manifest entries (bare id starting with
    ``_``) are excluded, since they are internal/derived and not meant
    to be filled in by the user.
    """
    jobs: dict = {}
    test_plans: dict = {}
    manifest_entries: dict = {}

    for repo_root in repo_roots:
        for pxu in repo_root.rglob("*.pxu"):
            try:
                content = pxu.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            ns = get_provider_namespace(pxu, repo_root)
            rel_source = str(pxu.relative_to(repo_root))

            for unit in parse_pxu_blocks(content):
                unit_type = unit.get("unit", "")
                if not unit_type and unit.get("plugin"):
                    unit_type = "job"

                if unit_type == "manifest entry":
                    bare = unit.get("id", "")
                    if not bare:
                        continue
                    bare_clean = bare.split("::")[-1]
                    if bare_clean.startswith("_"):
                        continue  # hidden entry, not user-facing
                    full = bare if "::" in bare else f"{ns}::{bare}"
                    existing = manifest_entries.get(bare_clean)
                    if existing and not existing["full_id"].startswith(
                        "unknown::"
                    ):
                        continue  # keep the good entry
                    manifest_entries[bare_clean] = {
                        "full_id": full,
                        "name": unit.get("_name", ""),
                        "prompt": unit.get("_prompt", ""),
                        "value_type": unit.get("value-type", "bool"),
                        "source_file": rel_source,
                    }
                    continue

                if unit_type == "test plan":
                    plan_id = unit.get("id", "")
                    if not plan_id:
                        continue
                    full = plan_id if "::" in plan_id else f"{ns}::{plan_id}"
                    if full in test_plans:
                        continue  # already seen in an earlier repo root
                    test_plans[full] = {
                        "id": plan_id,
                        "name": unit.get("_name", ""),
                        "include": _parse_ids(unit.get("include", "")),
                        "exclude": _parse_ids(unit.get("exclude", "")),
                        "nested_part": _parse_ids(unit.get("nested_part", "")),
                        "bootstrap_include": _parse_ids(
                            unit.get("bootstrap_include", "")
                        ),
                        "source_file": pxu.name,
                    }
                    continue

                if unit_type in _SKIP_UNIT_TYPES:
                    continue

                if unit_type not in ("job", "template", "resource", ""):
                    continue

                job_id = unit.get("id", "")
                if not job_id:
                    continue

                full = job_id if "::" in job_id else f"{ns}::{job_id}"
                if full in jobs:
                    continue  # already seen in an earlier repo root
                requires = unit.get("requires", "")
                command = unit.get("command", "")
                environ_field = unit.get("environ", "")

                declared_envs = environ_field.split() if environ_field else []
                # Only use vars explicitly declared in the environ: field.
                # Scanning $VAR patterns from command text produces noise.
                # Drop OS/runtime-reserved vars (see _is_reserved_environ):
                # they're never meant to be set by an ODM integrator.
                all_envs = sorted(
                    {e for e in declared_envs if not _is_reserved_environ(e)}
                )

                manifest_keys = list(
                    {k for k in _MAN_RE.findall(requires) if k != "ns"}
                )

                jobs[full] = {
                    "id": full,
                    "bare_id": full.split("::")[-1],
                    "provider": ns,
                    # PXU uses underscore-prefixed translatable fields.
                    "summary": unit.get("_summary", unit.get("summary", "")),
                    "description": unit.get(
                        "_description",
                        unit.get("_purpose", unit.get("description", "")),
                    ),
                    # Kept separate from "description": some jobs define
                    # both `_purpose` (what/why, e.g. what an environ var
                    # is for) and `_description` (usage detail), and
                    # `_description` wins above. `_purpose` alone is what
                    # best explains an environ var, so keep it available.
                    "purpose": unit.get("_purpose", ""),
                    "environ": all_envs,
                    "manifest": sorted(manifest_keys),
                    "unit_type": unit_type or "job",
                    "command": command,
                    "requires": requires,
                    "source_file": rel_source,
                }

    return {
        "generated_at": datetime.now().isoformat(),
        "repo_path": [str(p) for p in repo_roots],
        "jobs": jobs,
        "test_plans": test_plans,
        "manifest_entries": manifest_entries,
    }


def _repo_roots_key(repo_roots: list[Path]) -> str:
    """Return a stable hash for a list of repo roots (used for cache paths)."""
    joined = "|".join(sorted(str(p) for p in repo_roots))
    return hashlib.md5(joined.encode()).hexdigest()[:8]


def cache_path(repo_roots: list[Path]) -> Path:
    """Return the cache file path for *repo_roots*."""
    return Path("/tmp") / f"gen_launcher_{_repo_roots_key(repo_roots)}.json"


def expansion_cache_path(repo_roots: list[Path]) -> Path:
    """Return the plan-expansion cache file path for *repo_roots*."""
    h = _repo_roots_key(repo_roots)
    return Path("/tmp") / f"gen_launcher_{h}_expansions.json"


def load_expansion_cache(
    repo_roots: list[Path],
) -> "dict[str, set[str]]":
    """Load persisted plan expansions; return {} if missing, stale, or corrupt.

    The expansions file stores the mtime of the PXU cache file at the time
    each expansion was written.  If the PXU cache has since been rebuilt
    (mtime changed), all stored expansions are discarded so they are
    re-computed against the updated cache.
    """
    pxu_cache = cache_path(repo_roots)
    exp_file = expansion_cache_path(repo_roots)
    if not exp_file.exists() or not pxu_cache.exists():
        return {}
    try:
        data = json.loads(exp_file.read_text(encoding="utf-8"))
        if data.get("_pxu_mtime") != pxu_cache.stat().st_mtime:
            return {}
        return {k: set(v) for k, v in data.get("expansions", {}).items()}
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def save_expansion_cache(
    repo_roots: list[Path],
    expansions: "dict[str, set[str]]",
) -> None:
    """Persist *expansions* alongside the PXU cache mtime (non-fatal on error)."""
    pxu_cache = cache_path(repo_roots)
    exp_file = expansion_cache_path(repo_roots)
    try:
        data = {
            "_pxu_mtime": pxu_cache.stat().st_mtime,
            "expansions": {k: sorted(v) for k, v in expansions.items()},
        }
        exp_file.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # non-fatal


def is_cache_stale(cache_file: Path, repo_roots: list[Path]) -> bool:
    """Return True if *cache_file* is missing or older than any ``*.pxu``."""
    if not cache_file.exists():
        return True
    mtime = cache_file.stat().st_mtime
    return any(
        pxu.stat().st_mtime > mtime
        for repo_root in repo_roots
        for pxu in repo_root.rglob("*.pxu")
    )


def load_or_build_cache(repo_roots: list[Path], force: bool = False) -> dict:
    """Load the JSON cache or rebuild it if stale/missing/corrupt/outdated."""
    cp = cache_path(repo_roots)
    if not force and not is_cache_stale(cp, repo_roots):
        try:
            data = json.loads(cp.read_text(encoding="utf-8"))
            if data.get("_version") == _CACHE_VERSION:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    print("Building cache (scanning *.pxu)…", end=" ", flush=True)
    data = build_cache(repo_roots)
    data["_version"] = _CACHE_VERSION
    try:
        cp.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # cache write failure is non-fatal
    n_j = len(data["jobs"])
    n_p = len(data["test_plans"])
    print(f"{n_j} jobs, {n_p} plans cached.")
    return data


def discover_top_level_plans(
    cache: dict,
    plan_prefix: str = "ce-oem-iot",
) -> list[tuple[str, str, str]]:
    """Return sorted [(full_id, plan_id, name)] for top-level plans.

    A plan is "top-level" if its bare id matches
    ``{plan_prefix}-<platform>-<version>[-04]``, e.g.
    ``ce-oem-iot-desktop-24-04`` or ``ce-oem-iot-ubuntucore-26``. This
    mirrors odm_program_documentation's versions.py discovery logic
    exactly, so both tools agree on what counts as a top-level CE-OEM
    plan.
    """
    escaped = re.escape(plan_prefix)
    pattern = re.compile(
        rf"^{escaped}-(?P<platform>[a-z]+)-(?P<version>\d+)(?:-04)?$"
    )
    plans = cache["test_plans"]
    return sorted(
        (full_id, p["id"], p["name"])
        for full_id, p in plans.items()
        if pattern.match(p["id"])
    )


def get_nested_plans(
    top_full_id: str,
    cache: dict,
) -> list[tuple[str, str]]:
    """Return [(full_id, plan_id)] for every direct nested_part of *top_full_id*.

    References are resolved first as full IDs, then by bare plan_id.
    Unresolvable references are silently skipped.
    """
    plans = cache["test_plans"]
    top = plans.get(top_full_id)
    if not top:
        return []
    by_bare: dict[str, str] = {p["id"]: fid for fid, p in plans.items()}
    result: list[tuple[str, str]] = []
    for ref in top["nested_part"]:
        if ref in plans:
            result.append((ref, plans[ref]["id"]))
        else:
            bare = ref.split("::")[-1]
            fid = by_bare.get(bare)
            if fid:
                result.append((fid, plans[fid]["id"]))
    return result


def _matches(pattern: str, job_id: str) -> bool:
    """Return True if the checkbox glob *pattern* matches *job_id*.

    ``.*`` acts as a wildcard; all other dots are treated as literals.

    >>> _matches("com.canonical.*", "com.canonical.foo")
    True
    >>> _matches("exact-id", "exact-id")
    True
    >>> _matches("a.b", "axb")
    False
    """
    try:
        parts = pattern.split(".*")
        regex = ".*".join(re.escape(p) for p in parts)
        return bool(re.match("^" + regex + "$", job_id))
    except re.error:
        return pattern == job_id


def _normalize(s: str) -> str:
    """Normalise template index tokens for fuzzy pattern matching.

    Collapses ``/{N}_`` and ``/{var}_`` index prefixes to ``/INDEX_``
    and ``_.*`` / ``_{var}`` suffixes to ``_WILDCARD``.

    >>> _normalize("test/1_step")
    'test/INDEX_step'
    >>> _normalize("plain-id")
    'plain-id'
    """
    s = re.sub(r"/(\d+|\{[^}]+\})_", "/INDEX_", s)
    s = re.sub(r"_(\.\*|\{+[^}]+\}+)", "_WILDCARD", s)
    return s


def _excl_matches(ep: str, jid: str) -> bool:
    """Match exclude pattern ep against job full_id jid."""
    if "::" in ep:
        return _matches(ep, jid)
    return _matches(ep, jid.split("::")[-1]) or _matches(ep, jid)


def expand_plan(
    full_id: str,
    cache: dict,
    on_progress: "Callable[[int, int], None] | None" = None,
) -> set[str]:
    """Recursively expand *full_id* to the effective set of job full_ids.

    Follows ``include``/``exclude``/``nested_part`` fields.

    *on_progress*, if given, is called as ``on_progress(plans_visited, jobs_found)``
    each time a plan node is fully processed.

    Raises ValueError if *full_id* is not present in *cache*.
    """
    plans = cache["test_plans"]
    all_job_ids: list[str] = list(cache["jobs"].keys())
    by_bare: dict[str, str] = {p["id"]: fid for fid, p in plans.items()}
    _counter = [0]  # mutable counter for closures

    def _resolve(ref: str) -> str | None:
        if ref in plans:
            return ref
        return by_bare.get(ref.split("::")[-1])

    def _expand(fid: str, visited: frozenset) -> set[str]:
        if fid in visited:
            return set()
        visited = visited | {fid}
        plan = plans[fid]
        includes = plan["include"]
        excludes = plan["exclude"]
        nested = plan["nested_part"]
        bootstrap = plan.get("bootstrap_include", [])

        result: set[str] = set()
        # include + bootstrap_include patterns both contribute jobs/resources.
        for pat in includes + bootstrap:
            bp = pat.split("::")[-1]
            np = _normalize(bp)
            for jid in all_job_ids:
                bj = jid.split("::")[-1]
                if (
                    _matches(bp, bj)
                    or _matches(bp, jid)
                    or _normalize(bj) == np
                ):
                    result.add(jid)

        for ref in nested:
            child = _resolve(ref)
            if child:
                result |= _expand(child, visited)

        if excludes:
            result = {
                j
                for j in result
                if not any(_excl_matches(ep, j) for ep in excludes)
            }

        _counter[0] += 1
        if on_progress:
            on_progress(_counter[0], len(result))
        return result

    if full_id not in plans:
        raise ValueError(f"Plan {full_id!r} not found in cache.")
    return _expand(full_id, frozenset())


def dump_inventory_json(
    cache: dict,
    job_ids: "set[str] | list[str]",
    *,
    version: str,
    plan_full_ids: "tuple[str, ...] | list[str]",
    checkbox_repository: str,
    checkbox_commit: str,
) -> dict:
    """Build a JSON-serializable dict matching odm_program_documentation's
    ``Inventory`` schema (see ``inventory_to_dict``/``inventory_from_dict``
    in that project's ``src/odm_docs/inventory.py``) from this module's own
    ``cache`` dict, for the given expanded *job_ids*.

    Raises KeyError if any id in *job_ids* is not present in
    ``cache["jobs"]`` (fail fast on an inconsistent cache).
    """
    jobs_by_id = cache["jobs"]
    manifest_entries = cache["manifest_entries"]

    def _job_record(job_id: str) -> dict:
        job = jobs_by_id[job_id]
        return {
            "full_id": job["id"],
            "bare_id": job["bare_id"],
            "summary": job["summary"],
            "description": job["description"],
            "environ": list(job["environ"]),
            "command": job["command"],
            "requires": job["requires"],
            "source_file": job["source_file"],
        }

    sorted_job_ids = sorted(job_ids)
    manifest_jobs: "dict[str, set[str]]" = {}
    env_jobs: "dict[str, set[str]]" = {}
    for job_id in sorted_job_ids:
        if job_id not in jobs_by_id:
            raise KeyError(f"job {job_id!r} not found in cache")
        job = jobs_by_id[job_id]
        for key in {
            k
            for k in _MAN_RE.findall(job["requires"])
            if k != "ns" and not k.startswith("_")
        }:
            manifest_jobs.setdefault(key, set()).add(job_id)
        for key in job["environ"]:
            env_jobs.setdefault(key, set()).add(job_id)

    manifests = []
    for key in sorted(manifest_jobs):
        source = manifest_entries.get(key, {})
        manifests.append(
            {
                "key": key,
                "full_id": source.get("full_id", key),
                "name": source.get("name", ""),
                "prompt": source.get("prompt", ""),
                "value_type": source.get("value_type", "bool"),
                "related_jobs": [
                    _job_record(jid) for jid in sorted(manifest_jobs[key])
                ],
                "source_file": source.get("source_file", ""),
            }
        )

    environments = [
        {
            "key": key,
            "related_jobs": [
                _job_record(jid) for jid in sorted(env_jobs[key])
            ],
        }
        for key in sorted(env_jobs)
    ]

    return {
        "version": version,
        "plan_full_ids": list(plan_full_ids),
        "checkbox_repository": checkbox_repository,
        "checkbox_commit": checkbox_commit,
        "manifests": manifests,
        "environments": environments,
    }


def get_related_jobs(
    kind: str,
    key: str,
    job_ids: set[str],
    cache: dict,
) -> list[dict]:
    """Return [{id, summary, description, purpose}] for cached jobs using
    *key*.

    Searches the entire cache (not just *job_ids*) so that related jobs from
    other sub-plans are visible for context.  *kind* must be ``"manifest"``
    or ``"environ"``.  Results are sorted by job id.
    """
    jobs = cache["jobs"]
    field = "manifest" if kind == "manifest" else "environ"
    result = []
    for jid, job in jobs.items():
        if key in job[field]:
            result.append(
                {
                    "id": jid,
                    "summary": job["summary"],
                    "description": job["description"],
                    "purpose": job.get("purpose", ""),
                }
            )
    return sorted(result, key=lambda j: j["id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan CE-OEM checkbox providers and dump one inventory JSON "
            "file per discovered top-level-plan version."
        ),
    )
    parser.add_argument(
        "--providers-dir",
        required=True,
        metavar="DIR",
        help="Path to a checkbox providers root to scan",
    )
    parser.add_argument(
        "--plan-prefix",
        default="ce-oem-iot",
        metavar="PREFIX",
        help="Top-level test plan id prefix to match (default: ce-oem-iot)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        metavar="DIR",
        help="Directory to write one {version}.json file per discovered version",
    )
    parser.add_argument(
        "--checkbox-repository",
        default="",
        metavar="URL",
        help="Value to record as checkbox_repository in each dumped JSON",
    )
    parser.add_argument(
        "--checkbox-commit",
        default="",
        metavar="SHA",
        help="Value to record as checkbox_commit in each dumped JSON",
    )
    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force cache rebuild even if cache is fresh",
    )
    args = parser.parse_args(argv)

    providers_dir = Path(args.providers_dir).resolve()
    if not providers_dir.is_dir():
        print(
            f"ERROR: --providers-dir path not found: {providers_dir}",
            file=sys.stderr,
        )
        return 1
    repo_roots = [providers_dir]

    cache = load_or_build_cache(repo_roots, force=args.rebuild_cache)
    plans = discover_top_level_plans(cache, args.plan_prefix)
    if not plans:
        print(
            f"ERROR: no top-level test plans found matching prefix: "
            f"{args.plan_prefix}",
            file=sys.stderr,
        )
        return 1

    version_re = re.compile(
        rf"^{re.escape(args.plan_prefix)}-[a-z]+-(?P<version>\d+)(?:-04)?$"
    )
    by_version: "dict[str, list[tuple[str, str, str]]]" = {}
    for full_id, plan_id, name in plans:
        match = version_re.match(plan_id)
        if match:
            version = f"{match.group('version')}.04"
        else:
            version = plan_id
        by_version.setdefault(version, []).append((full_id, plan_id, name))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # NOTE: unlike gen_launcher.py's TUI (which wraps expand_plan with
    # load_expansion_cache/save_expansion_cache, see gen_launcher.py's
    # main()), this CLI re-runs expand_plan from scratch every invocation.
    # expand_plan is O(patterns x total_jobs) per plan node with no
    # memoization across nested sub-plans, so on a large provider corpus
    # (measured: ~0.5-3s per top-level plan on a ~1500-job corpus) a run
    # covering many versions/platforms can add up to tens of seconds.
    # Acceptable today because this CLI is only invoked once per CI
    # workflow trigger, not repeatedly. If invocation frequency increases,
    # wire in load_expansion_cache/save_expansion_cache here the same way
    # gen_launcher.py's main() does.
    for version, version_plans in sorted(by_version.items()):
        plan_full_ids = tuple(full_id for full_id, _, _ in version_plans)
        job_ids: set[str] = set()
        for full_id, _, _ in version_plans:
            job_ids |= expand_plan(full_id, cache)
        data = dump_inventory_json(
            cache,
            job_ids,
            version=version,
            plan_full_ids=plan_full_ids,
            checkbox_repository=args.checkbox_repository,
            checkbox_commit=args.checkbox_commit,
        )
        out_path = output_dir / f"{version}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Wrote {out_path} ({len(job_ids)} jobs)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
