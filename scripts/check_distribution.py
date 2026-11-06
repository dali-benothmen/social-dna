"""Install both built distributions and smoke-test their packaged migrations.

Run `uv build` first. Use --offline when the dependency resolver's complete
registry metadata and compatible wheels are cached. Use --uv and --cache-dir
when build tooling is isolated outside PATH.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from tarfile import open as open_tar


def audit_archive(distribution: Path) -> dict[str, int]:
    """Reject unsafe/private runtime paths without extracting or reading credential stores."""
    if distribution.suffix == ".whl":
        with zipfile.ZipFile(distribution) as archive:
            entries = [
                (item.filename, (item.external_attr >> 16) & 0o170000 == 0o120000)
                for item in archive.infolist()
            ]
    else:
        with open_tar(distribution, "r:gz") as archive:
            entries = [(item.name, not (item.isfile() or item.isdir())) for item in archive]
    forbidden = {".git", ".agents", ".codex", ".claude", ".opencode", ".venv", "__pycache__"}
    for name, link in entries:
        path = PurePosixPath(name)
        if (
            link
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or any(":" in part for part in path.parts)
            or any(part in forbidden for part in path.parts)
            or path.name in {".env", "auth.json", "credentials.json"}
            or path.name.startswith(".env.")
            or path.suffix in {".db", ".sqlite", ".sqlite3", ".pem", ".key"}
            or any(marker in path.name for marker in (".db-", ".sqlite-", ".sqlite3-"))
        ):
            raise RuntimeError(f"Unsafe or private distribution member: {name}")
    return {"members_checked": len(entries)}


def run(arguments: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {arguments}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def portable_smoke(base: list[str], python: Path, isolated: Path, bundle_source: Path) -> None:
    """Export actual installed bundle to all host layouts and retain usable reports."""
    preflight = json.loads(
        run(
            [
                base[0],
                "--data-dir",
                str(isolated / "unused"),
                "--offline",
                "--no-ai",
                "--format",
                "json",
                "capabilities",
            ],
            cwd=isolated,
        )
    )["data"]
    if (isolated / "unused").exists() or preflight["policy"]["library_opened"]:
        raise RuntimeError("Installed capability preflight initialized a library")
    catalog = json.loads(run([*base, "skill", "list"], cwd=isolated))["data"]
    if len(catalog["bundles"]) != 9 or len(catalog["planned"]) != 6:
        raise RuntimeError("Installed skill catalog confuses delivered and planned skills")
    setup = subprocess.run(
        [
            base[0],
            "--data-dir",
            str(isolated / "setup-unused"),
            "--offline",
            "--no-ai",
            "--format",
            "json",
            "setup",
            "--task",
            "analyze",
            "--input-kind",
            "image",
        ],
        cwd=isolated,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if setup.returncode != 5 or json.loads(setup.stdout)["data"]["policy"]["library_opened"]:
        raise RuntimeError("Installed setup did not preserve its action-required/no-write contract")
    if (isolated / "setup-unused").exists():
        raise RuntimeError("Installed setup initialized storage")
    if "site-packages" not in run(
        [
            str(python),
            "-c",
            "from socialdna.application.skill_service import bundle_path; print(bundle_path())",
        ],
        cwd=isolated,
    ):
        raise RuntimeError("Installed skill bundle fell back to checkout files")
    for host in (".agents", ".claude", ".opencode"):
        parent = isolated / "project with spaces" / host / "skills"
        parent.mkdir(parents=True)
        destination = parent / "socialdna"
        exported = json.loads(run([*base, "skill", "export", str(destination)], cwd=isolated))[
            "data"
        ]
        if not {"SKILL.md", "references/core.md", "references/interface.md"} <= set(
            exported["files"]
        ):
            raise RuntimeError("Installed exported skill is missing supporting resources")
        expected = {
            path.relative_to(bundle_source).as_posix(): path.read_bytes()
            for path in bundle_source.rglob("*")
            if path.is_file()
        }
        if set(exported["files"]) != set(expected) or any(
            (destination / name).read_bytes() != content for name, content in expected.items()
        ):
            raise RuntimeError("Installed skill differs from the complete source bundle")
        for task in (
            "social-dna-ingest",
            "social-dna-report",
            "social-dna-analyze",
            "social-dna-reconstruct",
            "social-dna-account",
            "social-dna-research",
            "social-dna-compare",
            "social-dna-evidence",
        ):
            target = parent / task
            manifest = json.loads(
                run([*base, "skill", "export", str(target), "--name", task], cwd=isolated)
            )["data"]
            if set(manifest["files"]) != {
                "SKILL.md",
                "references/workflow.md",
                "references/setup.md",
            }:
                raise RuntimeError("Installed task skill is not independently self-contained")
            task_source = bundle_source.parent / task / "SKILL.md"
            shared_source = bundle_source.parent / "shared" / "workflow.md"
            if (target / "SKILL.md").read_bytes() != task_source.read_bytes() or (
                target / "references/workflow.md"
            ).read_bytes() != shared_source.read_bytes():
                raise RuntimeError("Installed task skill differs from its maintained source")
            if (target / "references/setup.md").read_bytes() != (
                bundle_source / "references/setup.md"
            ).read_bytes():
                raise RuntimeError("Installed task skill lost its canonical setup guide")
            inspected = json.loads(run([*base, "skill", "inspect", "--name", task], cwd=isolated))[
                "data"
            ]
            if inspected["sha256"] != manifest["sha256"] or any(
                hashlib.sha256((target / name).read_bytes()).hexdigest() != checksum
                for name, checksum in inspected["sha256"].items()
            ):
                raise RuntimeError("Installed task manifest does not describe exported bytes")
    dry = json.loads(
        run(
            [*base, "workflow", "plan", "--url", "https://youtu.be/EaYRjrQuxEk", "--dry-run"],
            cwd=isolated,
        )
    )["data"]
    if not dry["dry_run"] or dry["written"]:
        raise RuntimeError("Installed URL planning failed its no-write contract")
    planned = json.loads(
        run([*base, "workflow", "plan", "--url", "https://youtu.be/EaYRjrQuxEk"], cwd=isolated)
    )["data"]
    shown = json.loads(run([*base, "workflow", "show", planned["workflow_id"]], cwd=isolated))[
        "data"
    ]
    if shown["attempts"] or shown["plan"]["external_id"] != "EaYRjrQuxEk":
        raise RuntimeError("Installed workflow plan did not survive process restart")
    contract = json.loads(run([*base, "skill", "schema", "result"], cwd=isolated))["data"]
    if contract["schema"]["properties"]["schema_version"]["const"] != "1.0":
        raise RuntimeError("Installed result schema diverged")
    photo = isolated / "a photo.png"
    run(
        [
            str(python),
            "-c",
            "from PIL import Image; import sys; "
            "Image.new('RGB', (80, 60), 'orange').save(sys.argv[1])",
            str(photo),
        ],
        cwd=isolated,
    )
    analysis = json.loads(run([*base, "--no-ai", "analyze", "image", str(photo)], cwd=isolated))[
        "data"
    ]
    saved = isolated / "a report.json"
    report = json.loads(
        run(
            [*base, "report", "generate", "--run", analysis["run_id"], "--output", str(saved)],
            cwd=isolated,
        )
    )["data"]
    if json.loads(saved.read_text(encoding="utf-8")) != report["content"]:
        raise RuntimeError("Installed JSON export differs from the canonical report")
    saved_md = isolated / "a report.md"
    markdown = run(
        [
            *base,
            "report",
            "generate",
            "--run",
            analysis["run_id"],
            "--format",
            "markdown",
            "--output",
            str(saved_md),
        ],
        cwd=isolated,
    )
    if markdown != saved_md.read_text(encoding="utf-8") or not markdown.startswith("# Image"):
        raise RuntimeError("Installed Markdown export lost its readable document")
    evidence = report["content"]["evidence"]
    resolved = json.loads(
        run([*base, "evidence", "resolve", evidence["id"], "--purpose", "new_claim"], cwd=isolated)
    )["data"]
    if not resolved["eligible"] or resolved["locator_kind"] != "image_record":
        raise RuntimeError("Installed static report lost its exact citation")


def audience_smoke(base: list[str], isolated: Path, post_ids: list[str]) -> None:
    """Exercise the public installed commands, not checkout-only Python imports."""

    def cli(*args: str) -> dict:
        return json.loads(run([*base, *args], cwd=isolated))["data"]

    comments = []
    for post in post_ids:
        comments.extend(cli("audience", "comments", "--post", post)["comments"])
    if len(comments) != 2 or not all(c["eligible"] for c in comments):
        raise RuntimeError("Installed comment listing lost its permitted captured records")
    post = comments[0]["post_ref"]
    collection_path = isolated / "audience-collection.json"
    collection_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "key": "installed-audience",
                "permission_basis": "Owned synthetic acceptance fixture",
                "source_uri": "urn:owned:installed-audience",
                "posts": [post],
                "members": [
                    {"comment": c["ref"], "language": "en", "creator_authored": False}
                    for c in comments
                ],
                "collected_at": datetime.now(UTC).isoformat(),
                "ordering": "ranked",
                "sampling_method": "ranked",
                "completeness": "partial",
                "declared_frame": "Two controlled collected comments, not viewers",
                "supplied_count": 2,
                "known_total": None,
                "pagination_complete": False,
                "truncated": True,
                "deleted_moderated_coverage": "Unknown",
            }
        )
    )
    collection = cli("audience", "import-collection", str(collection_path))
    annotations = []
    for index, comment in enumerate(comments):
        annotations.append(
            {
                "key": f"reaction-{index}",
                "comment": comment["ref"],
                "start_char": 0,
                "end_char": len(comment["body"]),
                "quote": comment["body"],
                "labels": ["expressed_intention" if "need to" in comment["body"] else "objection"],
                "language": "en",
                "negated": False,
                "ironic": False,
                "ambiguous": False,
                "state": "reviewed",
                "reviewer": "acceptance fixture",
                "complete_rubric_review": True,
                "rationale": "Controlled review of expressed wording, not verified behavior",
            }
        )
    annotation_path = isolated / "audience-annotations.json"
    annotation_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "key": "reviewed",
                "collection": collection["ref"],
                "permission_basis": "Owned synthetic acceptance annotations",
                "protocol": {
                    "origin": "human",
                    "author": "acceptance fixture",
                    "procedure": "expressed-reactions-1 controlled assertions",
                    "outcome_access": "blinded",
                },
                "annotations": annotations,
                "clusters": [
                    {
                        "key": "fixture",
                        "title": "Supplied reactions",
                        "summary": "Controlled expressions and a counterexample, not behavior",
                        "state": "reviewed",
                        "reviewer": "acceptance fixture",
                        "members": [
                            {"reaction_key": annotations[0]["key"], "role": "representative"},
                            {"reaction_key": annotations[1]["key"], "role": "counterexample"},
                        ],
                    }
                ],
                "links": [
                    {
                        "key": "post-context",
                        "reaction_key": annotations[0]["key"],
                        "target": post,
                        "origin": "human_interpretation",
                        "description": "Proposed interpretation, not a causal explanation",
                        "state": "reviewed",
                        "reviewer": "acceptance fixture",
                        "uncertainty": "high",
                    }
                ],
            }
        )
    )
    cli("audience", "import-annotations", str(annotation_path))
    result = cli("analyze", "audience", "--collection", collection["ref"]["id"])
    if result["rates"]["expressed_intention"]["confirmed_reviewed_annotation_count"] != 1:
        raise RuntimeError("Installed reviewed audience counts are incorrect")
    if result["links"][0]["playback_reference_ms"] is not None:
        raise RuntimeError("Installed inferred link acquired a fabricated timestamp")
    citation = cli("evidence", "resolve", result["evidence"]["id"])
    if not citation["eligible"] or citation["locator_kind"] != "audience_record":
        raise RuntimeError("Installed audience citation lost its exact binding")
    report = cli("report", "generate", "--run", result["run_id"])
    if report["content"]["report_type"] != "audience":
        raise RuntimeError("Installed audience report did not survive restart")
    cli("storage", "reconcile", "--limit", "5000")
    remembered = cli("query", "tonight", "--owner-kind", "reaction_annotation")
    if not remembered["hits"] or not remembered["hits"][0]["citations"][0]["eligible"]:
        raise RuntimeError("Installed persistent FTS memory lost its qualified audience citation")
    root = remembered["hits"][0]["owner"]["revision_id"]
    view = cli("graph", "neighbors", root)
    if not any(node["ref"]["kind"] == "comment" for node in view["nodes"]):
        raise RuntimeError("Installed SQLite-backed graph lost its captured comment context")
    cli("storage", "reindex", "--limit", "5000")
    if not cli("query", "tonight", "--mode", "sql", "--owner-kind", "reaction_annotation")["hits"]:
        raise RuntimeError("Installed memory rebuild did not preserve canonical retrieval")
    target = comments[0]["ref"]["id"]
    preview = cli("audience", "redact", "--comment", target)
    cli(
        "audience",
        "redact",
        "--comment",
        target,
        "--confirm",
        preview["confirmation"],
        "--reason",
        "Synthetic acceptance cleanup",
        "--actor",
        "installed smoke test",
    )
    if (
        Path(report["path"]).exists()
        or cli("evidence", "resolve", result["evidence"]["id"])["eligible"]
    ):
        raise RuntimeError("Installed erasure did not remove reports and withhold citations")
    if cli("query", "tonight", "--owner-kind", "reaction_annotation")["hits"]:
        raise RuntimeError("Installed memory resurrected erased audience content")
    cli("storage", "verify")


def behavioral_smoke(base: list[str], isolated: Path, account_id: str, post_ids: list[str]) -> None:
    def cli(*args: str) -> dict:
        return json.loads(run([*base, *args], cwd=isolated))["data"]

    account = cli("behavioral", "subject", account_id, "--kind", "account")["ref"]
    posts = [cli("behavioral", "subject", p, "--kind", "post") for p in post_ids]
    path = isolated / "behavioral.json"
    source = {
        "dataset_id": "installed-owned-behavior",
        "source_uri": "urn:owned:behavioral-fixture",
        "permission_basis": "creator_owned_export",
        "analytics_permitted": True,
    }

    def import_records(records: list[dict]) -> dict:
        path.write_text(json.dumps({"schema_version": "2.0", "source": source, "records": records}))
        return cli("import", "behavioral", str(path))

    base_definition = {
        "record_type": "behavioral_definition",
        "platform": "demo",
        "subject_type": "account",
        "meaning": "followers",
        "semantics": "count",
        "unit": "accounts",
        "domain": "nonnegative",
        "measurement": "cumulative",
        "numerator_definition": "account followers",
        "population_basis": "accounts",
        "replay_policy": "not_applicable",
        "source_definition_uri": "urn:owned:fixture-definition",
        "description": "Controlled installed-package source definition, not an API claim",
    }
    definitions = import_records(
        [
            {**base_definition, "key": "demo.followers.owned.v1"},
            {
                **base_definition,
                "key": "demo.retention.owned.v1",
                "subject_type": "post",
                "meaning": "retention",
                "semantics": "ratio",
                "unit": "watch ratio",
                "measurement": "series",
                "numerator_definition": "repeat-inclusive watch events",
                "denominator_definition": "eligible plays",
                "population_basis": "plays",
                "replay_policy": "includes_replays",
            },
            {
                "record_type": "audience_cohort",
                "key": "installed-owned-cohort",
                "account": account,
                "known": True,
                "eligibility": "All source-defined eligible observations",
                "aggregation_limitations": "Aggregate fixture only",
            },
        ]
    )["records"]
    refs = {r["key"]: r["ref"] for r in definitions}
    cohort = refs["installed-owned-cohort"]
    records = []
    for index, post in enumerate(posts):
        published = datetime.fromisoformat(post["record"]["published_at"].replace("Z", "+00:00"))
        records.append(
            {
                "record_type": "metric_series",
                "key": f"installed-retention-{index}",
                "subject": post["ref"],
                "definition": refs["demo.retention.owned.v1"],
                "cohort": cohort,
                "clock": {
                    "window_start": published.isoformat(),
                    "window_end": (published + timedelta(days=7)).isoformat(),
                    "data_cutoff": (published + timedelta(days=7)).isoformat(),
                    "collected_at": datetime.now(UTC).isoformat(),
                },
                "coordinate_kind": "normalized_progress",
                "resolution": "Two source half-video bins",
                "convention": "half_open_intervals",
                "completeness": "complete_for_declared_grid",
                "expected_bins": 2,
                "bins": [
                    {"ordinal": 0, "start": 0, "end": 0.5, "measurement": {"value": 1.2}},
                    {"ordinal": 1, "start": 0.5, "end": 1, "measurement": {"value": 0.8}},
                ],
            }
        )
    for key, when, value in [
        ("first", "2026-01-01T00:00:00Z", 100),
        ("last", "2026-01-09T00:00:00Z", 95),
    ]:
        records.append(
            {
                "record_type": "metric_measurement",
                "key": "installed-followers-" + key,
                "subject": account,
                "definition": refs["demo.followers.owned.v1"],
                "cohort": cohort,
                "clock": {
                    "window_start": when,
                    "window_end": when,
                    "data_cutoff": when,
                    "collected_at": datetime.now(UTC).isoformat(),
                },
                "measurement": {"value": value},
            }
        )
    imported = import_records(records)["records"]
    curves = [r for r in imported if r["ref"]["kind"] == "metric_series"]
    result = cli(
        "analyze",
        "retention",
        "--series",
        curves[0]["ref"]["id"],
        "--compare-series",
        curves[1]["ref"]["id"],
    )
    if (
        result["comparison"]["status"] != "available"
        or result["series"]["bins"][0]["result"]["value"] != 1.2
    ):
        raise RuntimeError("Installed repeat-inclusive retention comparison failed")
    if not cli("evidence", "resolve", result["series"]["bins"][0]["evidence"]["id"])["eligible"]:
        raise RuntimeError("Installed exact behavioral bin citation failed")
    if (
        cli("report", "generate", "--run", result["run_id"])["content"]["comparison"]
        != result["comparison"]
    ):
        raise RuntimeError("Installed behavioral report did not survive restart")
    specification = isolated / "account-outcomes.json"
    specification.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "definition": refs["demo.followers.owned.v1"],
                "cohort": cohort,
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-09T00:00:00Z",
            }
        )
    )
    outcomes = cli("analyze", "outcomes", account_id, "--spec", str(specification))
    if (
        outcomes["net_change"]["value"] != -5
        or outcomes["attribution"]["causal_effect"] is not None
    ):
        raise RuntimeError("Installed signed account outcome/attribution semantics failed")
    cli("report", "generate", "--run", outcomes["run_id"])
    cli("storage", "verify")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--cache-dir")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--source-workflows-only",
        action="store_true",
        help="Run health, skill and source-workflow acceptance; skip legacy deep research smokes.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    cache = ["--cache-dir", args.cache_dir] if args.cache_dir else []
    for pattern in (f"socialdna-{version}-*.whl", f"socialdna-{version}.tar.gz"):
        distributions = sorted((root / "dist").glob(pattern))
        if len(distributions) != 1:
            raise RuntimeError(f"Expected exactly one {pattern} in dist/, found {distributions}")
        distribution = distributions[0]
        print(f"Archive safety: {distribution.name}: {audit_archive(distribution)}", flush=True)
        with tempfile.TemporaryDirectory(prefix="socialdna-distribution-") as directory:
            isolated = Path(directory)
            environment = isolated / "venv"
            run(
                [args.uv, "venv", str(environment), "--python", sys.executable, *cache],
                cwd=isolated,
            )
            python = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            run(
                [
                    args.uv,
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    *(["--offline"] if args.offline else []),
                    str(distribution),
                    *cache,
                ],
                cwd=isolated,
            )
            module = run(
                [str(python), "-c", "import socialdna; print(socialdna.__file__)"], cwd=isolated
            )
            if "site-packages" not in module:
                raise RuntimeError(f"Distribution imported from the checkout: {module}")
            executable = environment / (
                "Scripts/socialdna.exe" if sys.platform == "win32" else "bin/socialdna"
            )
            for command in (["doctor"], ["storage", "verify"]):
                result = json.loads(
                    run(
                        [
                            str(executable),
                            *command,
                            "--data-dir",
                            str(isolated / "data"),
                            "--format",
                            "json",
                        ],
                        cwd=isolated,
                    )
                )
                if result["status"] != "success" or result["errors"]:
                    raise RuntimeError(f"Installed distribution failed health checks: {result}")
            export = isolated / "account.json"
            shutil.copyfile(root / "examples/imports/account.json", export)
            dataset = json.loads(export.read_text())
            dataset["source"]["comments_permitted"] = True
            dataset["records"].extend(
                [
                    {
                        "record_type": "comment",
                        "platform": "demo",
                        "post_external_id": "post-a",
                        "external_id": str(index),
                        "body": text,
                        "published_at": "2026-01-03T00:00:00Z",
                    }
                    for index, text in enumerate(["I need to make this tonight!", "Too expensive."])
                ]
            )
            export.write_text(json.dumps(dataset))
            base = [
                str(executable),
                "--data-dir",
                str(isolated / "data"),
                "--offline",
                "--format",
                "json",
            ]
            portable_smoke(base, python, isolated, root / "skills" / "socialdna")
            print(
                run(
                    [
                        str(python),
                        str(root / "scripts/source_workflow_smoke.py"),
                        str(isolated / "synthetic-source-data"),
                    ],
                    cwd=isolated,
                ).strip()
            )
            print(
                run(
                    [
                        str(python),
                        str(root / "scripts/media_workflow_smoke.py"),
                        str(isolated / "supplied-media-data"),
                    ],
                    cwd=isolated,
                ).strip()
            )
            print(
                run(
                    [
                        str(python),
                        str(root / "scripts/account_workflow_smoke.py"),
                        str(isolated / "assisted-account-data"),
                    ],
                    cwd=isolated,
                ).strip()
            )
            print(
                run(
                    [
                        str(python),
                        str(root / "scripts/comparison_workflow_smoke.py"),
                        str(isolated / "comparison-data"),
                    ],
                    cwd=isolated,
                ).strip()
            )
            print(
                f"PASS: {distribution.name} portable skill exports, schemas, "
                "static reports and citations"
            )
            if args.source_workflows_only:
                continue
            imported = json.loads(run([*base, "import", "json", str(export)], cwd=isolated))
            account_id = imported["data"]["account_ids"][0]
            audience_posts = imported["data"]["post_ids"]
            analyzed = json.loads(
                run(
                    [*base, "analyze", "account", account_id, "--metric", "demo.views.v1"],
                    cwd=isolated,
                )
            )
            account_report = json.loads(
                run([*base, "report", "generate", "--account", account_id], cwd=isolated)
            )
            if account_report["data"]["content"]["results"]["available_n"] != 2:
                raise RuntimeError("Installed account report lost imported observations")
            if analyzed["run_id"] != account_report["data"]["content"]["run_id"]:
                raise RuntimeError("Installed account report did not reopen the saved analysis")
            corrected_spec = isolated / "corrected.json"
            corrected_spec.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "metric_key": "demo.views.v1",
                        "features": ["caption_length"],
                        "covariates": ["caption_length"],
                        "design": "within_creator",
                        "estimand": "within_creator_association",
                        "feature_policy": "retrospective_content",
                        "maturity_policy": "collection_proxy",
                        "knowledge_cutoff": datetime.now(UTC).isoformat(),
                        "publication_cutoff": datetime.now(UTC).isoformat(),
                        "sampling_frame": "authorized installed-package acceptance fixture",
                        "family_id": "installed-corrected",
                        "family_terms": ["caption_length"],
                    }
                ),
                encoding="utf-8",
            )
            corrected = json.loads(
                run(
                    [*base, "analyze", "account", account_id, "--spec", str(corrected_spec)],
                    cwd=isolated,
                )
            )["data"]
            if corrected["schema_version"] != "2.0" or corrected["results"]["available_n"] != 2:
                raise RuntimeError("Installed versioned population did not preserve observations")
            statistical_ref = corrected["statistical_evidence"][0]["ref"]
            statistical_citation = json.loads(
                run([*base, "evidence", "resolve", statistical_ref["id"]], cwd=isolated)
            )["data"]
            reproduced = json.loads(
                run([*base, "compare", "reproduce", corrected["run_id"]], cwd=isolated)
            )["data"]
            if (
                not statistical_citation["eligible"]
                or reproduced["results"] != corrected["results"]
            ):
                raise RuntimeError(
                    "Installed statistical citation/reproduction did not survive restart"
                )
            print(
                f"PASS: {distribution.name} installed versioned analysis, "
                "statistical citation and reproduction"
            )
            snapshot_id = account_report["data"]["content"]["posts"][0]["snapshot_ids"][0]
            citation = json.loads(
                run([*base, "evidence", "cite-metric", snapshot_id], cwd=isolated)
            )
            specification = isolated / "research.json"
            specification.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "key": "installed-smoke",
                        "question": "Can this installed package preserve an exact metric citation?",
                        "population": "Software acceptance fixtures, not empirical research",
                        "evidence": [citation["data"]["ref"]],
                    }
                ),
                encoding="utf-8",
            )
            registered = json.loads(
                run([*base, "research", "register", "--spec", str(specification)], cwd=isolated)
            )
            question_id = registered["data"]["question"]["id"]
            research_report = json.loads(
                run([*base, "research", "report", question_id], cwd=isolated)
            )
            report_id = research_report["data"]["ref"]["id"]
            reopened = json.loads(run([*base, "research", "show", report_id], cwd=isolated))
            if not reopened["data"]["content"]["citations"][0]["eligible"]:
                raise RuntimeError("Installed research report lost its eligible citation")
            print(
                f"PASS: {distribution.name} installed R1 citation, registration and report restart"
            )
            print(
                f"PASS: {distribution.name} installed account import, analytics and report restart"
            )
            if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                source = isolated / "generated.mkv"
                run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=c=red:s=64x48:r=10:d=0.5",
                        "-an",
                        "-c:v",
                        "ffv1",
                        "-threads",
                        "1",
                        str(source),
                    ],
                    cwd=isolated,
                )
                analysis = json.loads(
                    run(
                        [
                            str(executable),
                            "analyze",
                            "video",
                            str(source),
                            "--format",
                            "json",
                            "--data-dir",
                            str(isolated / "data"),
                        ],
                        cwd=isolated,
                    )
                )
                if analysis["status"] != "success" or not analysis["data"]["reports"]:
                    raise RuntimeError(f"Installed media analysis failed: {analysis}")
                report = json.loads(
                    run(
                        [
                            str(executable),
                            "report",
                            "generate",
                            "--run",
                            analysis["run_id"],
                            "--format",
                            "json",
                            "--data-dir",
                            str(isolated / "data"),
                        ],
                        cwd=isolated,
                    )
                )
                if not report["data"]["content"]["timeline"]["observations"]:
                    raise RuntimeError("Installed media report has no measurements.")
                print(f"PASS: {distribution.name} installed video analysis and report restart")
                annotation = isolated / "creative.json"
                annotation.write_text(
                    json.dumps(
                        {
                            "key": "installed-review",
                            "media_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                            "permission_basis": "Owned generated acceptance fixture, "
                            "not a semantic-quality benchmark",
                            "protocol": {
                                "origin": "human",
                                "author": "acceptance fixture",
                                "procedure": "controlled synthetic assertion",
                                "outcome_access": "blinded",
                            },
                            "coverage": [
                                {
                                    "modality": "visual",
                                    "techniques": ["finished_dish", "preparation_instruction"],
                                    "mode": "exhaustive_review",
                                    "intervals": [{"start_ms": 0, "end_ms": 500}],
                                    "limitation": "Controlled labels only",
                                }
                            ],
                            "events": [
                                {
                                    "key": "result",
                                    "technique": "finished_dish",
                                    "description": "Synthetic test label; clip is a color card",
                                    "modalities": ["visual"],
                                    "anchors": [
                                        {"kind": "point", "start_min_ms": 0, "start_max_ms": 0}
                                    ],
                                    "state": "reviewed",
                                    "reviewer": "fixture",
                                }
                            ],
                        }
                    )
                )
                imported = json.loads(
                    run([*base, "creative", "import", str(annotation)], cwd=isolated)
                )["data"]
                values = json.loads(
                    run(
                        [
                            *base,
                            "creative",
                            "materialize",
                            analysis["data"]["media_id"],
                            "--recipe",
                            "creative.result_first.v1",
                        ],
                        cwd=isolated,
                    )
                )["data"]
                if values["values"]["creative.result_first.v1"]["value"] != 1:
                    raise RuntimeError("Installed short-video creative recipe failed")
                cited = json.loads(
                    run(
                        [*base, "evidence", "resolve", imported["events"][0]["evidence"]["id"]],
                        cwd=isolated,
                    )
                )["data"]
                if not cited["eligible"] or cited["locator"]["kind"] != "creative_event":
                    raise RuntimeError("Installed creative citation lost its exact binding")
                enriched = json.loads(
                    run(
                        [
                            *base,
                            "analyze",
                            "video",
                            analysis["data"]["media_id"],
                            "--no-ai",
                            "--creative-profile",
                            "cooking-opening-v1",
                            "--creative-annotations",
                            str(annotation),
                            "--creative-frame-budget",
                            "2",
                        ],
                        cwd=isolated,
                    )
                )["data"]
                pinned = json.loads(
                    run([*base, "report", "generate", "--run", enriched["run_id"]], cwd=isolated)
                )["data"]["content"]
                if (
                    pinned["schema_version"] != "2.0"
                    or not pinned["timeline"]["creative"]["events"]
                ):
                    raise RuntimeError("Installed creative report lost pinned annotation lanes")
                run([*base, "storage", "verify"], cwd=isolated)
                print(
                    f"PASS: {distribution.name} installed creative import, recipe, "
                    "citation and report restart"
                )
            behavioral_smoke(base, isolated, account_id, audience_posts)
            print(
                f"PASS: {distribution.name} installed retention comparison, "
                "exact bins and signed account outcomes"
            )
            audience_smoke(base, isolated, audience_posts)
            print(
                f"PASS: {distribution.name} installed audience review, citation, report, "
                "persistent SQL/FTS/graph memory and erasure"
            )
            print(f"PASS: {distribution.name} isolated install, initialization and verification")


if __name__ == "__main__":
    main()
