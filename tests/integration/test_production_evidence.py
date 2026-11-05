"""Multi-video craft → actual import/analytics/evidence/report integration.

Generated clips and source-labelled synthetic counters test software, not empirical
craft effectiveness. A fast-edited failure is intentionally retained in the cohort.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from test_psychological_research import CORPUS, design, protocol, registration
from typer.testing import CliRunner

from socialdna.application import (
    investigation_service,
    literature_service,
    reevaluation_service,
)
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.creative_service import (
    creative_timeline,
    import_into_application,
    materialize,
)
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.performance_service import analyze_account, compare
from socialdna.cli.app import app as cli
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.memory import QuerySpec
from socialdna.domain.production import ProductionAnnotationSet
from socialdna.domain.research import PerformanceSpec
from socialdna.memory import documents, hybrid, lexical
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import database_checks
from socialdna.storage.schema import metadata


def annotation(sha: str, shots: int) -> ProductionAnnotationSet:
    def event(
        technique: str, key: str, start: int, end: int | None = None, value: str | None = None
    ) -> dict[str, Any]:
        return {
            "key": key,
            "technique": technique,
            "value": value,
            "description": "Controlled source-authored fixture cue; not detector validation",
            "modalities": ["audio" if technique == "music_beat" else "visual"],
            "state": "reviewed",
            "reviewer": "fixture reviewer",
            "reliability": "high",
            "anchors": [
                {
                    "kind": "point" if end is None else "interval",
                    "start_min_ms": start,
                    "start_max_ms": start,
                    **({"end_min_ms": end, "end_max_ms": end} if end is not None else {}),
                }
            ],
        }

    events = [
        event("shot", f"shot-{i}", i * (3000 // shots), (i + 1) * (3000 // shots))
        for i in range(shots)
    ]
    events += [event("cut", f"cut-{i}", i * (3000 // shots)) for i in range(1, shots)]
    events += [event("music_beat", f"beat-{i}", i * 500) for i in range(6)]
    events += [event("subtitle_design", "subtitle", 500, 2500, "readable")]
    return ProductionAnnotationSet.model_validate(
        {
            "schema_version": "2.0",
            "key": "professional-review",
            "media_sha256": sha,
            "permission_basis": "Owned generated clips and controlled human-review fixtures",
            "protocol": {
                "origin": "human",
                "author": "fixture reviewer",
                "procedure": "full clip review v2",
                "outcome_access": "blinded",
                "label_frozen_before_outcomes": True,
            },
            "coverage": [
                {
                    "modality": modality,
                    "techniques": techniques,
                    "mode": "exhaustive_review",
                    "intervals": [{"start_ms": 0, "end_ms": 3000}],
                    "limitation": "Controlled software fixture",
                }
                for modality, techniques in (
                    ("visual", ["shot", "cut", "subtitle_design"]),
                    ("audio", ["music_beat"]),
                )
            ],
            "events": events,
        }
    )


def create_clip(path: Path, shots: int, index: int) -> None:
    colors = ("red", "blue", "green", "yellow", "magenta", "cyan")
    arguments = ["ffmpeg", "-nostdin", "-v", "error"]
    for shot in range(shots):
        arguments += [
            "-f",
            "lavfi",
            "-i",
            f"color=c={colors[(shot + index) % 6]}:s=96x64:r=12:d={3 / shots}",
        ]
    # Synthetic metronome ticks; the fixture explicitly declares these beats.
    arguments += [
        "-f",
        "lavfi",
        "-i",
        f"aevalsrc=sin(2*PI*{600 + index * 50}*t)*lt(mod(t\\,0.5)\\,0.05):s=16000:d=3",
    ]
    arguments += [
        "-filter_complex",
        "".join(f"[{i}:v]" for i in range(shots)) + f"concat=n={shots}:v=1:a=0[v]",
        "-map",
        "[v]",
        "-map",
        f"{shots}:a",
        "-c:v",
        "ffv1",
        "-threads",
        "1",
        "-c:a",
        "pcm_s16le",
        "-y",
        str(path),
    ]
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_multi_video_performance_history_reload_and_withdrawal(
    settings: Settings,
    tmp_path: Path,
    video: Path,
) -> None:
    del video  # Reuse the shared FFmpeg-availability gate, not its bytes/labels.
    counts = [2, 4, 3, 6, 2, 6]
    outcomes = [100, 400, 150, 600, 120, 80]
    records: list[dict[str, Any]] = [
        {
            "record_type": "metric_definition",
            "platform": "demo",
            "key": "demo.views.v1",
            "definition": "Controlled seven-day fixture views, not real platform results",
        }
    ]
    for creator in range(3):
        records.append(
            {
                "record_type": "account",
                "platform": "demo",
                "external_id": f"craft-{creator}",
                "creator_key": f"craft-{creator}",
                "niche": "craft-fixture",
            }
        )
    for index, count in enumerate(counts):
        path = tmp_path / f"clip-{index}.mkv"
        create_clip(path, count, index)
        records.extend(
            [
                {
                    "record_type": "post",
                    "platform": "demo",
                    "external_id": f"craft-{index}",
                    "account_external_id": f"craft-{index // 2}",
                    "caption": "clip",
                    "published_at": "2026-01-01T00:00:00Z",
                },
                {
                    "record_type": "media",
                    "platform": "demo",
                    "post_external_id": f"craft-{index}",
                    "uri": str(path),
                    "position": 0,
                },
                {
                    "record_type": "metric_snapshot",
                    "platform": "demo",
                    "subject_external_id": f"craft-{index}",
                    "metric_key": "demo.views.v1",
                    "value": outcomes[index],
                    "observed_at": "2026-01-08T00:00:00Z",
                    "window_start": "2026-01-01T00:00:00Z",
                    "window_end": "2026-01-08T00:00:00Z",
                },
            ]
        )
    dataset = tmp_path / "performance.json"
    dataset.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "owned-craft-fixture",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:fixture:craft-performance",
                },
                "records": records,
            }
        )
    )
    assert import_dataset(settings, dataset, "json")["valid"]
    registered = registration(settings, tmp_path)
    with open_application(settings) as app:
        for creator in range(3):
            analyze_account(
                app,
                stable_id("account", "demo", f"craft-{creator}"),
                PerformanceSpec(metric_key="demo.views.v1"),
                analyze_media=True,
                media_options=AnalysisOptions(no_ai=True),
            )
        specs, media_ids, imported = [], [], []
        with app.database.transaction() as connection:
            links = metadata.tables["post_media"]
            for index, count in enumerate(counts):
                media_id = connection.scalar(
                    select(links.c.media_asset_id).where(
                        links.c.post_id == stable_id("post", "demo", f"craft-{index}")
                    )
                )
                assert media_id is not None
                asset = EvidenceRepository(connection).get("media_assets", media_id)
                specs.append(annotation(asset["sha256"], count))
                media_ids.append(media_id)
        for spec in specs:
            first = import_into_application(app, spec)
            assert import_into_application(app, spec)["ref"] == first["ref"]
            imported.append(first)
        recipes = [
            "creative.shot_duration_mean.v2",
            "creative.subtitle_occupancy.v2",
            "creative.cut_to_beat_rate.v2",
        ]
        values = materialize(app, media_ids[0], recipes, key="professional-review")["values"]
        assert values[recipes[0]]["value"] == 1.5
        assert values[recipes[1]]["value"] == pytest.approx(2 / 3)
        assert values[recipes[2]]["value"] == 1
        posts = [stable_id("post", "demo", f"craft-{index}") for index in range(6)]
        analysis = compare(
            app,
            "posts",
            posts[::2],
            posts[1::2],
            design(
                family_id="craft-performance",
                model="none",
                features=["creative.shot_duration_mean", "caption_length"],
                creative_annotation_key="professional-review",
                creative_recipes={"creative.shot_duration_mean": recipes[0]},
                family_terms=["creative.shot_duration_mean", "caption_length"],
            ),
        )
        assert len(analysis["posts"]) == 6
        assert len({r["creator_id"] for r in analysis["posts"]}) == 3
        assert sorted(r["outcome"] for r in analysis["posts"]) == sorted(outcomes)
        assert len(analysis["results"]["comparison"]["pairs"]) == 3
        assert all(
            r["feature_values"]["creative.shot_duration_mean"]["lineage"]["evidence_refs"]
            for r in analysis["posts"]
        )
        corpus = literature_service.import_corpus(
            app, literature_service.read_spec(CORPUS, LiteratureCorpus)
        )
        prepared = investigation_service.prepare(
            app, protocol(registered, corpus, feature="creative.shot_duration_mean")
        )
        result = investigation_service.evaluate(
            app,
            EvaluationSpec.model_validate(
                {"protocol": prepared["protocol"], "analysis_run_ids": [analysis["run_id"]]}
            ),
        )
        ref = EntityRef.model_validate(result["assessment"])
        report = investigation_service.assessment_report(app, ref)
        frozen = Path(report["artifact"]["path"]).read_bytes()
        changed = specs[0].model_dump(mode="json")
        changed["events"][0]["verdict"] = "ambiguous"
        import_into_application(app, ProductionAnnotationSet.model_validate(changed))
        assert investigation_service.show_record(app, ref)["freshness"] == "stale"
        assert (
            materialize(app, media_ids[0], [recipes[0]], key="professional-review")["values"][
                recipes[0]
            ]["value"]
            is None
        )
        revised = reevaluation_service.reevaluate(app, ref.id)
        assert revised["analyses_run"] == 1
        assert (
            Path(investigation_service.assessment_report(app, ref)["artifact"]["path"]).read_bytes()
            == frozen
        )
        assert all(check.status != "error" for check in database_checks(app))
        with app.database.transaction() as connection:
            for value in values.values():
                for citation in value["lineage"]["evidence_refs"]:
                    assert (
                        EvidenceResolver(connection)
                        .resolve(EvidenceRef.model_validate(citation))
                        .eligible
                    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--offline",
            "--format",
            "json",
            "research",
            "history",
            ref.id,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert len(json.loads(completed.stdout)["data"]["transitions"]) == 1
    path = tmp_path / "annotations.json"
    path.write_text(specs[1].model_dump_json())
    invoked = CliRunner().invoke(
        cli,
        [
            "--data-dir",
            str(settings.data_dir),
            "--offline",
            "--format",
            "json",
            "creative",
            "import",
            str(path),
        ],
    )
    assert invoked.exit_code == 0, invoked.output
    with open_application(settings) as app:
        timeline = creative_timeline(app, media_ids[1], key="professional-review")
        assert timeline["schema_version"] == "2.0" and timeline["relations"] == []
        assert any("all-pairs" in item for item in timeline["limitations"])
        with app.database.transaction() as connection:
            citation = EvidenceRef.model_validate(imported[1]["events"][0]["evidence"])
            assert EvidenceResolver(connection).resolve(citation).eligible
            document = documents.build(connection, "evidence", citation.revision_id)
            assert document is not None
            lexical.project(connection, document)
        assert hybrid.search(app, QuerySpec(text="shot", mode="fts"))["hits"]
        with app.database.transaction() as connection:
            withdraw(
                connection,
                source_id=imported[1]["source_id"],
                reason="Annotation permission revoked",
                actor="owner",
            )
        with pytest.raises(ConfigurationError):
            materialize(app, media_ids[1], [recipes[0]], key="professional-review")
        assert not hybrid.search(app, QuerySpec(text="shot", mode="fts"))["hits"]
