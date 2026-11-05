"""Install both built distributions and smoke-test their packaged migrations.

Run `uv build` first. Use --offline when the dependency resolver's complete
registry metadata and compatible wheels are cached. Use --uv and --cache-dir
when build tooling is isolated outside PATH.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path


def run(arguments: list[str], *, cwd: Path) -> str:
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {arguments}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--cache-dir")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    cache = ["--cache-dir", args.cache_dir] if args.cache_dir else []
    for pattern in (f"socialdna-{version}-*.whl", f"socialdna-{version}.tar.gz"):
        distributions = sorted((root / "dist").glob(pattern))
        if len(distributions) != 1:
            raise RuntimeError(f"Expected exactly one {pattern} in dist/, found {distributions}")
        distribution = distributions[0]
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
            base = [
                str(executable),
                "--data-dir",
                str(isolated / "data"),
                "--offline",
                "--format",
                "json",
            ]
            imported = json.loads(run([*base, "import", "json", str(export)], cwd=isolated))
            account_id = imported["data"]["account_ids"][0]
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
            print(f"PASS: {distribution.name} isolated install, initialization and verification")


if __name__ == "__main__":
    main()
