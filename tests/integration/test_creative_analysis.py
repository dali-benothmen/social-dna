"""Real media/storage workflows; semantic labels are controlled test assertions.

The generated red/blue clip is not a cooking detector benchmark. These tests verify
review provenance, timing, feature lineage and downstream integration only.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from socialdna.application.account_import_service import import_dataset
from socialdna.application.analysis_service import analyze_video
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.creative_service import (
    creative_timeline,
    import_into_application,
    materialize,
)
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.import_service import import_local
from socialdna.application.performance_service import (
    analyze_account,
    build_population,
    compare,
    reproduce,
)
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.research import CorrectedPerformanceSpec, PerformanceSpec
from socialdna.media.timeline import timeline
from socialdna.storage.creative_repository import cite_media, cite_post_text
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import database_checks
from socialdna.storage.schema import metadata

RESULT = "creative.result_first.v1"
PROMISE = "creative.spoken_promise.v1"


def annotations(sha: str, **changes: Any) -> CreativeAnnotationSet:
    document = {
        "key": "reviewed-opening",
        "media_sha256": sha,
        "permission_basis": "Owned generated fixture; controlled semantic assertions "
        "for software testing",
        "protocol": {
            "origin": "human",
            "author": "fixture reviewer",
            "procedure": "continuous opening review v1",
            "outcome_access": "blinded",
            "label_frozen_before_outcomes": True,
        },
        "coverage": [
            {
                "modality": "visual",
                "techniques": ["finished_dish", "preparation_instruction", "ingredient_display"],
                "mode": "exhaustive_review",
                "intervals": [{"start_ms": 0, "end_ms": 3000}],
                "limitation": "Fixture assertions, not empirical annotation-quality validation",
            }
        ],
        "events": [
            {
                "key": "dish",
                "technique": "finished_dish",
                "description": "Controlled result-first fixture assertion",
                "modalities": ["visual"],
                "anchors": [
                    {"start_min_ms": 0, "start_max_ms": 0, "end_min_ms": 700, "end_max_ms": 800}
                ],
                "state": "reviewed",
                "reviewer": "fixture reviewer",
                "reliability": "high",
            },
            {
                "key": "prep",
                "technique": "preparation_instruction",
                "description": "Controlled preparation assertion",
                "modalities": ["visual"],
                "anchors": [
                    {
                        "start_min_ms": 1000,
                        "start_max_ms": 1100,
                        "end_min_ms": 2000,
                        "end_max_ms": 2100,
                    }
                ],
                "state": "reviewed",
                "reviewer": "fixture reviewer",
            },
        ],
        **changes,
    }
    return CreativeAnnotationSet.model_validate(document)


def setup_review(
    app: Application, video: Path
) -> tuple[str, CreativeAnnotationSet, dict[str, Any]]:
    media = import_local(app, video)
    with app.database.transaction() as connection:
        sha = EvidenceRepository(connection).get("media_assets", media["media_id"])["sha256"]
    spec = annotations(sha)
    return media["media_id"], spec, import_into_application(app, spec)


def scalar(app: Application, media_id: str, recipe: str = RESULT, **kwargs: Any) -> dict[str, Any]:
    return materialize(app, media_id, [recipe], key="reviewed-opening", **kwargs)["values"][recipe]


def test_reviewed_events_relations_features_persist_with_selective_invalidation(
    settings: Settings,
    video: Path,
) -> None:
    with open_application(settings) as app:
        media_id, spec, imported = setup_review(app, video)
        shown = creative_timeline(app, media_id)
        assert shown["eligible"] and len(shown["events"]) == 2
        assert any(
            r["relation"] == "precedes" and r["status"] == "verified" for r in shown["relations"]
        )
        result = scalar(app, media_id)
        assert result["value"] == 1 and result["eligible"]
        assert result["lineage"]["outcome_blind"]
        assert len(result["lineage"]["evidence_refs"]) == 3
        frozen_at = utc_now()
        second = import_into_application(app, spec)
        assert imported["ref"] == second["ref"]
        assert scalar(app, media_id)["id"] == result["id"]
        modified = spec.model_dump(mode="json")
        modified["events"].append(
            {
                "key": "color",
                "technique": "warm_color",
                "description": "Reviewed color cast assertion",
                "modalities": ["color"],
                "anchors": [{"kind": "point", "start_min_ms": 300, "start_max_ms": 300}],
                "state": "reviewed",
                "reviewer": "reviewer",
            }
        )
        updated = import_into_application(app, CreativeAnnotationSet.model_validate(modified))
        assert updated["ref"] != imported["ref"]
        assert updated["events"][0]["ref"] == imported["events"][0]["ref"]
        assert scalar(app, media_id)["id"] == result["id"]
        assert scalar(app, media_id, "creative.warm_color.v1")["value"] == 1
        modified["events"][0]["anchors"] = [
            {"start_min_ms": 2500, "start_max_ms": 2500, "end_min_ms": 2900, "end_max_ms": 2900}
        ]
        import_into_application(app, CreativeAnnotationSet.model_validate(modified))
        changed = scalar(app, media_id)
        assert changed["id"] != result["id"] and changed["value"] == 0
        historical = scalar(app, media_id, cutoff=frozen_at)
        assert historical["id"] == result["id"]
        with app.database.transaction() as connection:
            assert not connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        assert all(c.status != "error" for c in database_checks(app))
    with open_application(settings) as app:
        assert scalar(app, media_id, cutoff=frozen_at)["value"] == 1
        with app.database.transaction() as connection:
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(imported["events"][0]["evidence"]), purpose="new_claim"
            )
            assert resolved.locator.kind == "creative_event"


def test_sparse_or_ambiguous_sets_never_become_absence(settings: Settings, video: Path) -> None:
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, video)
        raw = spec.model_dump(mode="json")
        raw["events"] = []
        raw["coverage"][0]["mode"] = "sampled"
        raw["coverage"][0]["sample_times_ms"] = [0, 1500]
        import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        assert scalar(app, media_id)["value"] is None
        assert scalar(app, media_id)["coverage"] == "unknown"
        raw["key"] = "independent-review"
        import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        ambiguous = materialize(app, media_id, [RESULT])["values"][RESULT]
        assert (
            ambiguous["value"] is None
            and "ambiguous_annotation_sets" in ambiguous["lineage"]["reason"]
        )


def test_discontinuous_anchors_are_preserved_as_separate_occurrences(
    settings: Settings, video: Path
) -> None:
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, video)
        document = spec.model_dump(mode="json")
        document["events"][0]["anchors"] = [
            {"start_min_ms": 0, "start_max_ms": 0, "end_min_ms": 300, "end_max_ms": 300},
            {"start_min_ms": 700, "start_max_ms": 750, "end_min_ms": 800, "end_max_ms": 900},
        ]
        import_into_application(app, CreativeAnnotationSet.model_validate(document))
        shown = creative_timeline(app, media_id)
        assert len(shown["events"][0]["annotation"]["anchors"]) == 2
        assert scalar(app, media_id)["value"] == 1
        assert any(
            r["relation"] == "precedes" and r["status"] == "verified" for r in shown["relations"]
        )


def test_actual_availability_and_outcome_awareness_are_not_backdated(
    settings: Settings, video: Path
) -> None:
    before = utc_now()
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, video)
        assert scalar(app, media_id)["available_at"] >= before
        assert scalar(app, media_id, cutoff=before)["value"] is None
        raw = spec.model_dump(mode="json")
        raw["protocol"].update(outcome_access="outcome_aware", label_frozen_before_outcomes=False)
        import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        result = scalar(app, media_id)
        assert result["value"] == 1 and not result["lineage"]["outcome_blind"]
        assert result["lineage"]["annotation_protocols"][0]["outcome_access"] == "outcome_aware"


@pytest.mark.parametrize("withdraw_input", [False, True])
def test_withdrawal_propagates_without_falling_back_to_old_labels(
    settings: Settings, video: Path, withdraw_input: bool
) -> None:
    with open_application(settings) as app:
        media_id, spec, imported = setup_review(app, video)
        scalar(app, media_id)
        with app.database.transaction() as connection:
            if withdraw_input:
                dependency = imported["events"][0]["inputs"][0]["ref"]
                withdraw(
                    connection,
                    evidence_id=dependency["id"],
                    reason="review input revoked",
                    actor="test",
                )
            else:
                raw = spec.model_dump(mode="json")
                raw["events"][0]["description"] = "Revised reviewed assertion"
        if not withdraw_input:
            revised = import_into_application(app, CreativeAnnotationSet.model_validate(raw))
            with app.database.transaction() as connection:
                withdraw(
                    connection,
                    source_id=revised["source_id"],
                    reason="new review revoked",
                    actor="test",
                )
        view = creative_timeline(app, media_id)
        assert not view["eligible"] and view["events"] == []
        with pytest.raises(ConfigurationError, match="(?i)withdrawn|ineligible"):
            scalar(app, media_id)


def test_wrong_media_timing_and_modality_inputs_are_rejected(
    settings: Settings, video: Path
) -> None:
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, video)
        with app.database.transaction() as connection:
            late = cite_media(connection, media_id, 2000, 3000)
        raw = spec.model_dump(mode="json")
        raw["events"][0]["inputs"] = [{"ref": late.model_dump(), "modality": "visual"}]
        with pytest.raises(ConfigurationError, match="timing bounds"):
            import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        raw["events"][0]["inputs"][0]["role"] = "context"
        with pytest.raises(ConfigurationError, match="observed"):
            import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        raw["events"][0]["inputs"] = []
        raw["events"][0]["anchors"][0]["end_max_ms"] = 3001
        with pytest.raises(ConfigurationError, match="duration"):
            import_into_application(app, CreativeAnnotationSet.model_validate(raw))


def test_missing_audio_is_unknown_and_cannot_receive_audio_assertions(
    settings: Settings,
    video: Path,
    tmp_path: Path,
) -> None:
    silent = tmp_path / "no-audio.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            str(silent),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, silent)
        assert scalar(app, media_id)["value"] == 1
        assert scalar(app, media_id, "creative.result_with_promise.v1")["value"] is None
        raw = spec.model_dump(mode="json")
        raw["events"][0].update(technique="utility_promise", modalities=["speech"])
        with pytest.raises(ConfigurationError, match="audio stream"):
            import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        with app.database.transaction() as connection:
            other = import_local(app, video)
            wrong = cite_media(connection, other["media_id"], 0, 1000)
        raw = spec.model_dump(mode="json")
        raw["events"][0]["inputs"] = [{"ref": wrong.model_dump(), "modality": "visual"}]
        with pytest.raises(ConfigurationError, match="different media"):
            import_into_application(app, CreativeAnnotationSet.model_validate(raw))


def test_imported_model_proposals_preserve_provider_and_need_separate_review(
    settings: Settings,
    video: Path,
) -> None:
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, video)
        raw = spec.model_dump(mode="json")
        raw["protocol"] = {
            "origin": "model",
            "author": "prepared external model",
            "procedure": "frame interpretation prompt v1",
            "outcome_access": "unknown",
            "provider": {
                "provider": "external-local",
                "model": "fixture-model",
                "revision": "weights-sha-123",
                "execution": "local",
            },
        }
        raw["coverage"][0]["mode"] = "sampled"
        for item in raw["events"]:
            item.update(state="proposed", reviewer=None)
        proposal = import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        assert scalar(app, media_id)["value"] is None
        with app.database.transaction() as connection:
            row = EvidenceRepository(connection).get(
                "entity_revisions", proposal["events"][0]["ref"]["revision_id"]
            )
            provenance = EvidenceRepository(connection).get(
                "provenance_records", row["provenance_id"]
            )
            assert provenance["model_revision"] == "weights-sha-123"
        review_document = spec.model_dump(mode="json")
        review_document["protocol"]["procedure"] = "Human adjudication of imported proposals, v2"
        reviewed = import_into_application(
            app, CreativeAnnotationSet.model_validate(review_document)
        )
        assert reviewed["events"][0]["ref"] != proposal["events"][0]["ref"]
        assert scalar(app, media_id)["value"] == 1


def test_opt_in_profile_preserves_primitive_cache_and_reports_pinned_lanes(
    settings: Settings, video: Path, tmp_path: Path
) -> None:
    with open_application(settings) as app:
        basic = analyze_video(app, str(video), options=AnalysisOptions(depth="quick", no_ai=True))
        media_id, spec, _ = setup_review(app, video)
        path = tmp_path / "review.json"
        path.write_text(spec.model_dump_json())
        options = AnalysisOptions(
            depth="quick",
            no_ai=True,
            creative_profile="cooking-opening-v1",
            creative_frame_budget=4,
        )
        first = analyze_video(app, media_id, options=options, creative_annotations=path)
        assert first["status"] == "success"
        primitive = {
            key
            for key, task in basic["tasks"].items()
            if task["status"] == "succeeded" and key != "timeline"
        }
        assert all(first["tasks"][key]["status"] == "cached" for key in primitive)
        data = timeline(app, media_id, run_id=first["run_id"], include_creative=True)
        assert len(data["creative"]["events"]) == 2
        assert len([f for f in data["frames"] if f["selection_reason"] == "creative-targeted"]) <= 4
        saved = generate_report(app, first["run_id"])
        assert saved["content"]["schema_version"] == "2.0"
        old_bytes = Path(saved["path"]).read_bytes()
        md = generate_report(app, first["run_id"], "markdown")["content"]
        assert (
            "Creative event lanes" in md
            and "uncertainty" not in data["creative"]["events"][0]["annotation"]
        )
        assert scalar(app, media_id)["value"] == 1
        changed = spec.model_dump(mode="json")
        changed["events"][0]["description"] = "<script>unsafe</script> [click](https://bad)"
        path.write_text(json.dumps(changed))
        second = analyze_video(app, media_id, options=options, creative_annotations=path)
        assert second["tasks"]["frames.creative"]["status"] == "cached"
        assert all(second["tasks"][key]["status"] == "cached" for key in primitive)
        third = analyze_video(app, media_id, options=options, creative_annotations=path)
        assert third["tasks"]["creative.events"]["status"] == "cached"
        assert third["tasks"]["frames.creative"]["status"] == "cached"
        rendered = generate_report(app, second["run_id"], "markdown")["content"]
        assert "<script>" not in rendered and "\\[click\\]" in rendered
        assert Path(saved["path"]).read_bytes() == old_bytes
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(metadata.tables["reports"].c.schema_version).where(
                        metadata.tables["reports"].c.run_id == first["run_id"]
                    )
                )
                == "2.0"
            )
        assert generate_report(app, basic["run_id"])["content"]["schema_version"] == "1.0"


def test_literal_profile_keeps_supplied_subtitle_separate_from_speech(
    settings: Settings, video: Path, tmp_path: Path
) -> None:
    subtitles = tmp_path / "promise.srt"
    subtitles.write_text("1\n00:00:00,200 --> 00:00:00,900\nYou'll learn how to save time\n")
    with open_application(settings) as app:
        result = analyze_video(
            app,
            str(video),
            options=AnalysisOptions(
                depth="quick",
                no_ai=True,
                creative_profile="cooking-opening-v1",
                creative_frame_budget=2,
            ),
            subtitles=subtitles,
        )
        assert result["status"] == "success"
        shown = timeline(app, result["media_id"], run_id=result["run_id"], include_creative=True)[
            "creative"
        ]
        assert shown["events"][0]["annotation"]["modalities"] == ["subtitle"]
        assert shown["events"][0]["annotation"]["state"] == "proposed"
        values = materialize(
            app, result["media_id"], [RESULT, PROMISE, "creative.subtitle_promise.v1"]
        )["values"]
        assert all(row["value"] is None for row in values.values())
        assert all(
            "not psychological" not in r.get("interpretation", "") for r in shown["relations"]
        )
        spoof = {
            "key": "invalid-speech-review",
            "media_sha256": shown["events"][0]["media"]["id"],
            "permission_basis": "Owned test",
            "protocol": {
                "origin": "human",
                "author": "test",
                "procedure": "attempted modality spoof",
                "outcome_access": "unknown",
            },
            "events": [shown["events"][0]["annotation"]],
        }
        with app.database.transaction() as connection:
            spoof["media_sha256"] = EvidenceRepository(connection).get(
                "media_assets", result["media_id"]
            )["sha256"]
        spoof["events"][0] = {
            **spoof["events"][0],
            "modalities": ["speech"],
            "state": "reviewed",
            "reviewer": "test",
            "inputs": [{"ref": shown["events"][0]["inputs"][0]["ref"], "modality": "speech"}],
        }
        with pytest.raises(ConfigurationError, match="Text-track"):
            import_into_application(app, CreativeAnnotationSet.model_validate(spoof))


def test_same_version_definition_and_recipe_changes_are_rejected(
    settings: Settings,
    video: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from socialdna.analyzers.creative import RECIPES, TECHNIQUES
    from socialdna.storage.creative_repository import register_definitions

    with open_application(settings) as app:
        setup_review(app, video)
        original = TECHNIQUES["finished_dish"]
        monkeypatch.setitem(
            TECHNIQUES,
            "finished_dish",
            original.model_copy(update={"definition": "Changed under the same version"}),
        )
        with pytest.raises(StorageIntegrityError, match="definition version"):
            with app.database.transaction() as connection:
                register_definitions(connection)
        monkeypatch.setitem(TECHNIQUES, "finished_dish", original)
        monkeypatch.setitem(
            RECIPES, RESULT, RECIPES[RESULT].model_copy(update={"opening_ms": 4000})
        )
        with pytest.raises(StorageIntegrityError, match="pinned version"):
            with app.database.transaction() as connection:
                register_definitions(connection)


def test_post_text_citations_and_pinned_recipe_join_existing_comparison(
    settings: Settings, video: Path, account_export: Path
) -> None:
    document = json.loads(account_export.read_text())
    reversed_video = video.parent / "ingredient-first-fixture.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(video),
            "-vf",
            "reverse",
            "-an",
            "-c:v",
            "ffv1",
            "-threads",
            "1",
            str(reversed_video),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    for record in document["records"]:
        if record["record_type"] == "post" and record["external_id"] == "p0":
            record["caption"] = "🍳 You'll learn how to cook"
    document["records"].append(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": "p0",
            "uri": video.as_uri(),
        }
    )
    document["records"].extend(
        [
            {
                "record_type": "tag",
                "platform": "demo",
                "post_external_id": "p0",
                "kind": "hashtag",
                "value": tag,
            }
            for tag in ("#Dinner", "#CAFÉ")
        ]
    )
    document["records"].append(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": "p1",
            "uri": reversed_video.as_uri(),
        }
    )
    account_export.write_text(json.dumps(document))
    import_dataset(settings, account_export, "json")
    account = stable_id("account", "demo", "0001")
    with open_application(settings) as app:
        analyze_account(
            app,
            account,
            PerformanceSpec(metric_key="demo.views.v1", features=("caption_length",)),
            analyze_media=True,
            media_options=AnalysisOptions(depth="quick", no_ai=True),
        )
        media_id, spec, _ = setup_review(app, video)
        other_id, other_spec, _ = setup_review(app, reversed_video)
        other_document = other_spec.model_dump(mode="json")
        other_document["events"][0]["anchors"] = [
            {"start_min_ms": 2500, "start_max_ms": 2500, "end_min_ms": 2900, "end_max_ms": 2900}
        ]
        import_into_application(app, CreativeAnnotationSet.model_validate(other_document))
        assert scalar(app, other_id)["value"] == 0
        post_id = stable_id("post", "demo", "p0")
        with app.database.transaction() as connection:
            post = EvidenceRepository(connection).latest("post", post_id)
            assert post is not None
            text = cite_post_text(connection, post, "caption", 2)
            assert EvidenceResolver(connection).resolve(text).locator.quote.startswith("You'll")
            tag = cite_post_text(connection, post, "hashtag", tag_index=0)
            locator = EvidenceResolver(connection).resolve(tag).locator
            assert locator.normalization == "hashtag_casefold_strip"
            assert locator.quote in ("dinner", "café")
        assert scalar(app, media_id, "creative.hashtag_count.v1", post=post)["value"] == 2
        raw = spec.model_dump(mode="json")
        raw["events"].append(
            {
                "key": "caption",
                "technique": "utility_promise",
                "description": "Literal caption promise",
                "modalities": ["caption"],
                "post": post.model_dump(),
                "anchors": [
                    {"kind": "untimed", "unknown_reason": "Post caption has no presentation clock"}
                ],
                "inputs": [{"ref": text.model_dump(), "modality": "caption"}],
                "state": "reviewed",
                "reviewer": "reviewer",
            }
        )
        annotated = import_into_application(app, CreativeAnnotationSet.model_validate(raw))
        assert scalar(app, media_id, "creative.caption_promise.v1", post=post)["value"] == 1
        spec2 = CorrectedPerformanceSpec.model_validate(
            {
                "metric_key": "demo.views.v1",
                "estimand": "within_creator_association",
                "design": "within_creator",
                "feature_policy": "retrospective_content",
                "knowledge_cutoff": utc_now(),
                "publication_cutoff": "2026-11-01T00:00:00Z",
                "baseline_cutoff": "evaluation",
                "maturity_policy": "collection_proxy",
                "sampling_frame": "all imported fixture posts",
                "features": ["creative.result_first"],
                "covariates": ["caption_length"],
                "family_id": "creative-fixture",
                "family_terms": ["creative.result_first"],
                "creative_recipes": {"creative.result_first": RESULT},
                "creative_annotation_key": "reviewed-opening",
                "bootstrap_resamples": 200,
            }
        )
        count_before = None
        with app.database.transaction() as connection:
            count_before = connection.scalar(
                select(func.count()).select_from(metadata.tables["analysis_tasks"])
            )
        rows, _ = build_population(app, spec2, account_ids=[account])
        first = next(row for row in rows if row["post_id"] == post_id)
        assert first["features"]["creative.result_first"] == 1
        assert first["feature_values"]["creative.result_first"]["eligible"]
        assert first["creative_annotation_ref"] and first["feature_evidence_ids"]
        report = analyze_account(app, account, spec2)
        assert report["schema_version"] == "2.0"
        assert report["results"]["available_n"] == 6  # outcome availability, not feature coverage
        assert (
            sum(
                row["feature_values"]["creative.result_first"]["eligible"]
                for row in report["posts"]
            )
            == 2
        )
        assert reproduce(app, report["run_id"])["results"] == report["results"]
        contrast = compare(app, "posts", [post_id], [stable_id("post", "demo", "p1")], spec2)
        assert contrast["results"]["available_n"] == 2
        assert reproduce(app, contrast["run_id"])["results"] == contrast["results"]
        historical = spec2.model_copy(update={"feature_policy": "historical_prediction"})
        historical_rows, _ = build_population(app, historical, account_ids=[account])
        assert not next(row for row in historical_rows if row["post_id"] == post_id)[
            "feature_values"
        ]["creative.result_first"]["eligible"]
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["analysis_tasks"])
                )
                == count_before
            )
        archived = generate_report(app, report["run_id"])
        original_bytes = Path(archived["path"]).read_bytes()
        with app.database.transaction() as connection:
            withdraw(
                connection,
                source_id=annotated["source_id"],
                reason="Reviewed labels withdrawn",
                actor="test",
            )
            citation = EvidenceRef.model_validate(report["statistical_evidence"][0]["ref"])
            assert not EvidenceResolver(connection).resolve(citation).eligible
        with pytest.raises(ConfigurationError, match="(?i)withdrawn|ineligible"):
            reproduce(app, report["run_id"])
        assert Path(archived["path"]).read_bytes() == original_bytes


def test_cli_dry_run_has_no_storage_writes_and_commands_survive_restart(
    settings: Settings, video: Path, tmp_path: Path
) -> None:
    source = tmp_path / "review.json"
    with open_application(settings) as app:
        media_id, spec, _ = setup_review(app, video)
    source.write_text(spec.model_dump_json())
    untouched = tmp_path / "dry-run-library"

    def cli(*args: str, data: Path = settings.data_dir) -> dict[str, Any]:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "socialdna",
                "--data-dir",
                str(data),
                "--format",
                "json",
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(completed.stdout)["data"]

    assert cli("creative", "import", str(source), "--dry-run", data=untouched)["written"] is False
    assert not untouched.exists()
    imported = cli("creative", "import", str(source))
    assert imported["valid"]
    assert len(cli("creative", "definitions")["recipes"]) >= 10
    assert cli("creative", "show", media_id)["events"]
    assert (
        cli("creative", "materialize", media_id, "--recipe", RESULT)["values"][RESULT]["value"] == 1
    )
    assert (
        cli("evidence", "resolve", imported["events"][0]["evidence"]["id"])["locator"]["kind"]
        == "creative_event"
    )
    assert all(c["status"] != "error" for c in cli("storage", "verify")["checks"])
