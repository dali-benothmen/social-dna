import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from socialdna.application import audience_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.query_service import graph_query, query
from socialdna.application.report_service import generate_report
from socialdna.application.research_service import generate_research_report, register_research
from socialdna.audience.annotations import AnnotationSet
from socialdna.audience.collections import CollectionSpec
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.memory import QuerySpec
from socialdna.media.timeline import timeline
from socialdna.storage.backup import create_backup, restore_library, verify_backup
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import artifact_checks, database_checks, evidence_checks
from socialdna.storage.schema import metadata

BODIES = [
    "🍳 I need to make this tonight! 0:02",
    "I can't afford these ingredients.",
    "🍳 I need to make this tonight! 0:02",
    "Sure, I'll make it... said no one.",
    "¿Se puede hacer sin leche?",
    "<script>bad</script> Not making this.",
    "Thanks! This is my recipe.",
    "No ingredient quantities?",
]


def import_comments(settings: Settings, path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    data["source"]["comments_permitted"] = True
    data["records"].extend(
        {
            "record_type": "comment",
            "platform": "demo",
            "post_external_id": "p0",
            "external_id": f"c{index}",
            "body": body,
            "published_at": "2026-01-07T00:00:00Z",
        }
        for index, body in enumerate(BODIES)
    )
    path.write_text(json.dumps(data))
    result = import_dataset(settings, path, "json")
    assert result["valid"]
    return result


def collection_spec(app: Application, **changes: Any) -> CollectionSpec:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        post = repo.latest("post", stable_id("post", "demo", "p0"))
        assert post
        members = []
        for index in range(len(BODIES)):
            comment = repo.latest("comment", stable_id("comment", post.id, f"c{index}"))
            assert comment
            members.append(
                {
                    "comment": comment.model_dump(),
                    "language": "es" if index == 4 else "en",
                    "creator_authored": True if index == 6 else (None if index == 7 else False),
                }
            )
    return CollectionSpec.model_validate(
        {
            "key": "ranked-comments",
            "permission_basis": "Creator-owned comment export",
            "source_uri": "urn:owned:ranked-comments",
            "posts": [post.model_dump()],
            "members": members,
            "collected_at": utc_now(),
            "ordering": "ranked",
            "sampling_method": "ranked",
            "completeness": "partial",
            "declared_frame": "Top-ranked permitted comments",
            "pagination_complete": False,
            "truncated": True,
            "limit": 8,
            "supplied_count": 10,
            "known_total": 1000,
            "deleted_moderated_coverage": "Unknown deleted/moderated comments",
            **changes,
        }
    )


def annotation_spec(
    collection: dict[str, Any], spec: CollectionSpec, **changes: Any
) -> AnnotationSet:
    annotations = []
    labels = [
        "expressed_intention",
        "objection",
        "expressed_intention",
        "expressed_intention",
        "question",
        "expressed_intention",
        "positive_reaction",
        "question",
    ]
    for index, member in enumerate(spec.members):
        annotations.append(
            {
                "key": f"a{index}",
                "comment": member.comment.model_dump(),
                "start_char": 0,
                "end_char": len(BODIES[index]),
                "quote": BODIES[index],
                "labels": [labels[index]],
                "language": member.language,
                "negated": index == 5,
                "ironic": index == 3,
                "ambiguous": False,
                "state": "reviewed",
                "reviewer": "fixture human",
                "complete_rubric_review": True,
                "rationale": "Controlled test adjudication of expressed wording, "
                "not verified behavior",
            }
        )
    return AnnotationSet.model_validate(
        {
            "key": "reviewed",
            "collection": collection["ref"],
            "permission_basis": "Authorized reviewer annotations",
            "protocol": {
                "origin": "human",
                "author": "fixture human",
                "procedure": "expressed-reactions-1 reviewed original text",
                "outcome_access": "blinded",
            },
            "annotations": annotations,
            "clusters": [
                {
                    "key": "intention",
                    "title": "Intention with counterexamples",
                    "summary": "Some collected comments express intention; "
                    "irony and negation remain counterexamples.",
                    "state": "reviewed",
                    "reviewer": "fixture human",
                    "members": [
                        {"reaction_key": "a0", "role": "representative"},
                        {"reaction_key": "a3", "role": "counterexample"},
                        {"reaction_key": "a5", "role": "counterexample"},
                    ],
                }
            ],
            "links": [
                {
                    "key": "opening",
                    "reaction_key": "a0",
                    "target": spec.posts[0].model_dump(),
                    "origin": "human_interpretation",
                    "description": "Reviewer interprets the reaction as related to this post, "
                    "not proof of causation",
                    "uncertainty": "high",
                    "state": "reviewed",
                    "reviewer": "fixture human",
                }
            ],
            **changes,
        }
    )


def setup(app: Application) -> tuple[dict[str, Any], CollectionSpec, dict[str, Any]]:
    spec = collection_spec(app)
    collection = service.import_into_application(app, spec)
    annotations = service.import_into_application(app, annotation_spec(collection, spec))
    return collection, spec, annotations


def test_reviewed_reactions_counts_links_reports_and_restart(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, _, annotations = setup(app)
        report = service.analyze(app, collection["ref"]["id"], key="reviewed")
        assert report["counts"]["eligible_text_groups"] == 6
        assert report["counts"]["known_creator_replies"] == 1
        assert report["counts"]["duplicate_comment_ids"] == 1
        assert report["rates"]["expressed_intention"]["confirmed_reviewed_annotation_count"] == 1
        assert report["rates"]["expressed_intention"]["uncertain_or_proposed_count"] == 2
        assert report["rates"]["question"]["confirmed_reviewed_annotation_count"] == 2
        assert all(row["population_prevalence"] is None for row in report["rates"].values())
        assert report["links"][0]["link"]["origin"] == "human_interpretation"
        assert report["links"][0]["playback_reference_ms"] is None
        assert (
            service.analyze(app, collection["ref"]["id"], key="reviewed")["run_id"]
            == report["run_id"]
        )
        markdown = generate_report(app, report["run_id"], "markdown")
        assert "counterexample" in markdown["content"] and "<script>" not in markdown["content"]
        assert "viewer" in markdown["content"] and "not reaction time" in markdown["content"]
        assert generate_report(app, report["run_id"])["content"]["report_type"] == "audience"
        with app.database.transaction() as connection:
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(annotations["reactions"][0]["evidence"]),
                purpose="new_claim",
            )
            assert resolved.locator_kind == "audience_record"
    with open_application(settings) as app:
        assert service.load_analysis(app, report["run_id"])["rates"] == report["rates"]
        remembered = query(app, QuerySpec(text="ingredients", owner_kind="reaction_annotation"))
        assert remembered["hits"][0]["citations"][0]["locator_kind"] == "audience_record"
        view = graph_query(app, remembered["hits"][0]["owner"]["revision_id"])
        assert any(node["ref"]["kind"] == "comment" for node in view["nodes"])


def test_unknowns_literal_proposals_and_annotation_revisions(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        spec = collection_spec(app)
        collection = service.import_into_application(app, spec)
        empty = service.analyze(app, collection["ref"]["id"])
        assert all(v["observed_annotation_fraction"] is None for v in empty["rates"].values())
        proposed = service.analyze(app, collection["ref"]["id"], literal=True)
        assert all(
            v["confirmed_reviewed_annotation_count"] == 0 for v in proposed["rates"].values()
        )
        assert proposed["reactions"][4]["annotation"]["labels"] == ["ambiguous"]
        assert all(a["annotation"]["state"] == "proposed" for a in proposed["reactions"])
        reviewed_spec = annotation_spec(collection, spec)
        first = service.import_into_application(app, reviewed_spec)
        frozen = utc_now()
        report = service.analyze(app, collection["ref"]["id"], key="reviewed", as_of=frozen)
        changed = reviewed_spec.model_dump(mode="json")
        changed["annotations"][1]["rationale"] = "New objection review"
        second = service.import_into_application(app, AnnotationSet.model_validate(changed))
        assert second["reactions"][0]["ref"] == first["reactions"][0]["ref"]
        assert second["reactions"][1]["ref"] != first["reactions"][1]["ref"]
        assert (
            service.analyze(app, collection["ref"]["id"], key="reviewed", as_of=frozen)["run_id"]
            == report["run_id"]
        )


def test_exact_unicode_and_wrong_members_are_rejected(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        spec = collection_spec(app)
        collection = service.import_into_application(app, spec)
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        raw["annotations"][0]["quote"] = "x" + raw["annotations"][0]["quote"][1:]
        with pytest.raises(ConfigurationError, match="Unicode"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        raw["annotations"][0]["comment"] = spec.members[1].comment.model_dump()
        with pytest.raises(ConfigurationError, match="Unicode"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))


def test_withdrawal_is_transitive_and_does_not_overwrite_archived_bytes(
    settings: Settings, account_export: Path
) -> None:
    imported = import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, _, _ = setup(app)
        analysis = service.analyze(app, collection["ref"]["id"], key="reviewed")
        archived = generate_report(app, analysis["run_id"])
        original = Path(archived["path"]).read_bytes()
        with app.database.transaction() as connection:
            withdraw(connection, source_id=imported["source_id"], reason="Comment source revoked")
            result = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(analysis["evidence"])
            )
            assert not result.eligible and result.locator is None
        assert not service.show(app, collection["ref"]["id"], key="reviewed")["eligible"]
        with pytest.raises(ConfigurationError, match="[Ii]neligible|[Ww]ithdrawn"):
            generate_report(app, analysis["run_id"])
        assert Path(archived["path"]).read_bytes() == original


def test_redaction_removes_registered_text_and_blocks_reimport(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, spec, _ = setup(app)
        analysis = service.analyze(app, collection["ref"]["id"], key="reviewed")
        report = generate_report(app, analysis["run_id"], "markdown")
        target = spec.members[0].comment.id
        assert query(app, QuerySpec(text="tonight", owner_kind="reaction_annotation"))["hits"]
        plan = service.redact(app, comment_id=target)
        assert not plan["written"] and Path(report["path"]).is_file()
        assert plan["counts"]["artifact"] >= 3
        result = service.redact(
            app,
            comment_id=target,
            confirmation=plan["confirmation"],
            reason="Owner requested erasure",
        )
        assert result["active_library_redacted"] and not Path(report["path"]).exists()
        assert not query(app, QuerySpec(text="tonight", owner_kind="reaction_annotation"))["hits"]
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(metadata.tables["comments"].c.body).where(
                        metadata.tables["comments"].c.id == target
                    )
                )
                == "[redacted]"
            )
            assert (
                not EvidenceResolver(connection)
                .resolve(EvidenceRef.model_validate(analysis["evidence"]))
                .eligible
            )
            for row in connection.execute(
                select(metadata.tables["entity_revisions"].c.payload_json)
            ).scalars():
                # Duplicate c2 is independently supplied and may retain its body;
                # all source-linked annotation copies and c0 history are erased.
                if target in row:
                    assert BODIES[0] not in row
        checks = database_checks(app) + artifact_checks(app) + evidence_checks(app)
        assert all(c.status != "error" for c in checks), checks
    with pytest.raises(ConfigurationError, match="erased"):
        import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        assert not service.show(app, collection["ref"]["id"])["eligible"]


def test_literal_playback_reference_requires_actual_event_and_is_not_reaction_time(
    settings: Settings, account_export: Path, video: Path
) -> None:
    from socialdna.application.creative_service import import_into_application as creative_import
    from socialdna.application.import_service import import_local
    from socialdna.application.performance_service import analyze_account
    from socialdna.domain.media import AnalysisOptions
    from socialdna.domain.research import PerformanceSpec

    document = json.loads(account_export.read_text())
    document["records"].append(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": "p0",
            "uri": video.as_uri(),
        }
    )
    account_export.write_text(json.dumps(document))
    import_comments(settings, account_export)
    with open_application(settings) as app:
        media = import_local(app, video)
        analyze_account(
            app,
            stable_id("account", "demo", "0001"),
            PerformanceSpec(metric_key="demo.views.v1", features=("caption_length",)),
            analyze_media=True,
            media_options=AnalysisOptions(no_ai=True),
            max_posts=1,
        )
        with app.database.transaction() as connection:
            sha = EvidenceRepository(connection).get("media_assets", media["media_id"])["sha256"]
        events = creative_import(
            app,
            CreativeAnnotationSet.model_validate(
                {
                    "key": "actual-event",
                    "media_sha256": sha,
                    "permission_basis": "Owned fixture; semantic assertions test software only",
                    "protocol": {
                        "origin": "human",
                        "author": "reviewer",
                        "procedure": "review",
                        "outcome_access": "blinded",
                    },
                    "events": [
                        {
                            "key": "step",
                            "technique": "preparation_instruction",
                            "description": "Controlled instruction assertion",
                            "modalities": ["visual"],
                            "anchors": [
                                {
                                    "start_min_ms": 1900,
                                    "start_max_ms": 1900,
                                    "end_min_ms": 2500,
                                    "end_max_ms": 2500,
                                }
                            ],
                            "state": "reviewed",
                            "reviewer": "reviewer",
                        },
                        {
                            "key": "opening",
                            "technique": "finished_dish",
                            "description": "Controlled opening assertion",
                            "modalities": ["visual"],
                            "anchors": [
                                {
                                    "start_min_ms": 0,
                                    "start_max_ms": 0,
                                    "end_min_ms": 700,
                                    "end_max_ms": 700,
                                }
                            ],
                            "state": "reviewed",
                            "reviewer": "reviewer",
                        },
                    ],
                }
            ),
        )["events"]
        spec = collection_spec(app)
        collection = service.import_into_application(app, spec)
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        raw["links"][0].update(
            target=events[0]["ref"],
            target_evidence=events[0]["evidence"],
            origin="explicit_reference",
            reference_kind="timestamp",
            reference_text="0:02",
        )
        raw["links"].append(
            {
                "key": "inferred-opening",
                "reaction_key": "a1",
                "target": events[1]["ref"],
                "target_evidence": events[1]["evidence"],
                "origin": "human_interpretation",
                "description": "Uncertain reviewer interpretation, not an observed response time",
                "uncertainty": "high",
                "state": "reviewed",
                "reviewer": "reviewer",
            }
        )
        service.import_into_application(app, AnnotationSet.model_validate(raw))
        report = service.analyze(app, collection["ref"]["id"])
        assert report["links"][0]["playback_reference_ms"] == 2000
        assert report["links"][1]["playback_reference_ms"] is None
        assert report["links"][0]["target_context"]["technique"] == "preparation_instruction"
        assert (
            "Controlled instruction assertion"
            in generate_report(app, report["run_id"], "markdown")["content"]
        )
        assert "audience" not in timeline(app, media["media_id"])
        overlay = timeline(app, media["media_id"], include_audience=True)["audience"]
        assert len(overlay["links"]) == 2
        assert overlay["links"][0]["reaction"]["annotation"]["quote"] == BODIES[0]
        raw["links"][0].update(target=events[1]["ref"], target_evidence=events[1]["evidence"])
        with pytest.raises(ConfigurationError, match="outside the target"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))
        from socialdna.storage.creative_repository import cite_post_text

        with app.database.transaction() as connection:
            caption = cite_post_text(connection, spec.posts[0], "caption")
        raw["links"][0].update(
            target=events[0]["ref"],
            target_evidence=events[0]["evidence"],
            reference_kind="quote",
            reference_text="I need",
            target_quote_evidence=caption.model_dump(),
        )
        with pytest.raises(ConfigurationError, match="event's literal input"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))


def test_model_proposals_preserve_provider_and_need_new_human_adjudication(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, spec, reviewed = setup(app)
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        raw["protocol"].update(
            origin="model",
            author="imported local classifier",
            provider={
                "provider": "fixture",
                "model": "not-a-quality-benchmark",
                "revision": "pinned-fixture",
                "execution": "local",
            },
        )
        with pytest.raises(ValidationError, match="self-adjudicate"):
            AnnotationSet.model_validate(raw)
        for annotation in raw["annotations"]:
            annotation.update(state="proposed", reviewer=None, complete_rubric_review=False)
        raw["clusters"][0].update(state="proposed", reviewer=None)
        raw["links"][0].update(origin="model_proposal", state="proposed", reviewer=None)
        proposed = service.import_into_application(app, AnnotationSet.model_validate(raw))
        assert proposed["ref"] != reviewed["ref"]
        result = service.analyze(app, collection["ref"]["id"])
        assert result["reactions"][0]["protocol"]["provider"]["revision"] == "pinned-fixture"
        assert all(v["confirmed_reviewed_annotation_count"] == 0 for v in result["rates"].values())
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        raw["clusters"][0]["members"].append({"reaction_key": "a1", "role": "counterexample"})
        adjudicated = service.import_into_application(app, AnnotationSet.model_validate(raw))
        assert adjudicated["clusters"][0]["ref"] != reviewed["clusters"][0]["ref"]
        assert adjudicated["reactions"][0]["ref"]["id"] == reviewed["reactions"][0]["ref"]["id"]
        assert adjudicated["reactions"][0]["ref"] != proposed["reactions"][0]["ref"]
        assert service.analyze(app, collection["ref"]["id"])["counts"]["fully_reviewed_groups"] == 6


def test_collection_revisions_conflicting_reviews_and_retention_expiry(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, spec, _ = setup(app)
        frozen = utc_now()
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        conflicting = dict(raw["annotations"][0], key="alternative-review", labels=["other"])
        raw["annotations"].append(conflicting)
        service.import_into_application(app, AnnotationSet.model_validate(raw))
        rates = service.analyze(app, collection["ref"]["id"])["rates"]["expressed_intention"]
        assert rates["confirmed_reviewed_annotation_count"] == 0
        assert rates["disagreement_count"] == 1
        old = service.analyze(app, collection["ref"]["id"], as_of=frozen)
        assert old["rates"]["expressed_intention"]["confirmed_reviewed_annotation_count"] == 1
        new_spec = spec.model_copy(update={"declared_frame": "Corrected frame description"})
        corrected = service.import_into_application(app, new_spec)
        assert corrected["ref"]["revision_id"] != collection["ref"]["revision_id"]
        assert service.analyze(app, collection["ref"]["id"])["annotation_set_ref"] is None
        # An expired permission withholds even historical reads, without pretending
        # that expiry itself performs authorized byte erasure.
        expiry = CollectionSpec.model_validate(
            {
                **spec.model_dump(mode="json"),
                "key": "expired",
                "collected_at": "2026-01-10T00:00:00Z",
                "expires_at": "2026-02-01T00:00:00Z",
            }
        )
        expired = service.import_into_application(app, expiry)
        assert not service.show(app, expired["ref"]["id"])["eligible"]
        with pytest.raises(ConfigurationError, match="[Ii]neligible|expir"):
            service.analyze(app, expired["ref"]["id"])


def test_erasure_removes_unique_text_and_reconciles_restored_checkpoint(
    settings: Settings, account_export: Path, tmp_path: Path
) -> None:
    import_comments(settings, account_export)
    backup = tmp_path / "before-erasure"
    with open_application(settings) as app:
        collection, spec, _ = setup(app)
        raw = spec.model_dump(mode="json")
        raw["members"][1].update(eligible=False, exclusion_reason=BODIES[1])
        collection = service.import_into_application(app, CollectionSpec.model_validate(raw))
        analysis = service.analyze(app, collection["ref"]["id"])
        generate_report(app, analysis["run_id"], "markdown")
        create_backup(app.paths, backup)
        target = spec.members[1].comment.id
        plan = service.redact(app, comment_id=target)
        service.redact(app, comment_id=target, confirmation=plan["confirmation"], reason="Erasure")
        for file in [
            app.paths.database,
            *app.paths.root.glob("socialdna.db-*"),
            *app.paths.artifacts.rglob("*"),
        ]:
            if file.is_file():
                assert BODIES[1].encode() not in file.read_bytes(), file
        sanitized = tmp_path / "after-erasure"
        create_backup(app.paths, sanitized)
        assert verify_backup(sanitized)["database_revision"] == "0019_content"
    # The old backup remains an external retention obligation; restore gates
    # normal access until terminal erasure authority has been replayed.
    restored = tmp_path / "restored-audience"
    restore_library(backup, restored, withdrawals_from=settings.data_dir)
    with open_application(Settings(data_dir=restored)) as app:
        assert not service.show(app, collection["ref"]["id"])["eligible"]
        for file in [app.paths.database, *app.paths.artifacts.rglob("*")]:
            if file.is_file():
                assert BODIES[1].encode() not in file.read_bytes(), file
        assert all(c.status != "error" for c in evidence_checks(app) + artifact_checks(app))
    with pytest.raises(ConfigurationError, match="erased"):
        import_dataset(Settings(data_dir=restored), account_export, "json")


def test_interrupted_erasure_denies_first_and_resumes_on_restart(
    settings: Settings, account_export: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, spec, _ = setup(app)
        analysis = service.analyze(app, collection["ref"]["id"])
        report = generate_report(app, analysis["run_id"])
        target = spec.members[1].comment.id
        plan = service.redact(app, comment_id=target)
        original_unlink = Path.unlink

        def fail_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
            if path == Path(report["path"]):
                raise OSError("injected cleanup interruption")
            original_unlink(path, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "unlink", fail_unlink)
            with pytest.raises(OSError, match="injected cleanup"):
                service.redact(
                    app, comment_id=target, confirmation=plan["confirmation"], reason="Erase"
                )
        assert not service.show(app, collection["ref"]["id"])["eligible"]
        with app.database.transaction() as connection:
            assert (
                connection.scalar(select(metadata.tables["audience_redactions"].c.status))
                == "pending"
            )
        with pytest.raises(ConfigurationError, match="cleanup is pending"):
            create_backup(app.paths, settings.data_dir.parent / "pending-must-not-back-up")
        with pytest.raises(IntegrityError, match="immutable"):
            with app.database.transaction() as connection:
                connection.exec_driver_sql("UPDATE entity_revisions SET payload_json='{}'")
    with open_application(settings) as app:
        assert not Path(report["path"]).exists()
        with app.database.transaction() as connection:
            assert (
                connection.scalar(select(metadata.tables["audience_redactions"].c.status))
                == "complete"
            )
        assert all(c.status != "error" for c in database_checks(app) + evidence_checks(app))


def test_source_erasure_blocks_all_comments_and_invalid_reimport_leaves_no_blob(
    settings: Settings, account_export: Path
) -> None:
    imported = import_comments(settings, account_export)
    with open_application(settings) as app:
        _, _, _ = setup(app)
        plan = service.redact(app, source_id=imported["source_id"])
        assert plan["counts"]["comment"] == len(BODIES)
        with pytest.raises(ConfigurationError, match="confirmation"):
            service.redact(
                app, source_id=imported["source_id"], confirmation="stale", reason="Erase"
            )
        service.redact(
            app, source_id=imported["source_id"], confirmation=plan["confirmation"], reason="Erase"
        )
        before = sorted(p for p in app.paths.artifacts.rglob("*") if p.is_file())
    changed = json.loads(account_export.read_text())
    changed["source"]["dataset_id"] = "another-import-with-erased-identity"
    account_export.write_text(json.dumps(changed))
    with pytest.raises(ConfigurationError, match="erased"):
        import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        assert before == sorted(p for p in app.paths.artifacts.rglob("*") if p.is_file())
        with app.database.transaction() as connection:
            assert set(connection.scalars(select(metadata.tables["comments"].c.body))) == {
                "[redacted]"
            }


def test_audience_citations_appear_in_research_reports_and_erasure_removes_copies(
    settings: Settings, account_export: Path, tmp_path: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        collection, spec, annotations = setup(app)
    path = tmp_path / "research-audience.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "key": "audience-context",
                "question": "What expressed reactions appear in this collected sample?",
                "population": "Permitted collected comments, not viewers",
                "evidence": [annotations["reactions"][1]["evidence"]],
                "hypotheses": [],
            }
        )
    )
    registered = register_research(settings, path)
    with open_application(settings) as app:
        report = generate_research_report(
            app, registered["question"]["id"], report_format="markdown"
        )
        assert "audience" in report["content"] and "objection" in report["content"]
        target = spec.members[1].comment.id
        plan = service.redact(app, comment_id=target)
        service.redact(app, comment_id=target, confirmation=plan["confirmation"], reason="Erasure")
        assert not Path(report["artifact"]["path"]).exists()
        with pytest.raises(ConfigurationError, match="erased"):
            generate_research_report(app, registered["question"]["id"], report_format="markdown")


def test_cli_collection_import_analysis_and_dry_run_do_not_require_models(
    settings: Settings, account_export: Path, tmp_path: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        spec = collection_spec(app)
    path = tmp_path / "collection.json"
    path.write_text(spec.model_dump_json())

    def cli(*args: str, data: Path = settings.data_dir) -> dict[str, Any]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "socialdna",
                "--offline",
                "--format",
                "json",
                "--data-dir",
                str(data),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)["data"]

    empty = tmp_path / "dry-run-only"
    assert not cli("audience", "import-collection", str(path), "--dry-run", data=empty)["written"]
    assert not empty.exists()
    collection = cli("audience", "import-collection", str(path))
    comments = cli("audience", "comments", "--post", spec.posts[0].id, "--limit", "2")
    assert len(comments["comments"]) == 2 and comments["next_after"]
    annotation_path = tmp_path / "annotations.json"
    annotation_path.write_text(annotation_spec(collection, spec).model_dump_json())
    cli("audience", "import-annotations", str(annotation_path))
    result = cli("analyze", "audience", "--collection", collection["ref"]["id"])
    assert result["rates"]["question"]["confirmed_reviewed_annotation_count"] == 2
    citation = cli("evidence", "resolve", result["evidence"]["id"])
    assert citation["eligible"] and citation["locator_kind"] == "audience_record"
    assert cli("audience", "show", collection["ref"]["id"])["eligible"]


def test_explicit_quote_links_require_literal_target_and_reject_unrelated_alternatives(
    settings: Settings, account_export: Path
) -> None:
    from socialdna.storage.creative_repository import cite_post_text

    document = json.loads(account_export.read_text())
    next(r for r in document["records"] if r.get("external_id") == "p0")["caption"] = "ingredients"
    account_export.write_text(json.dumps(document))
    import_comments(settings, account_export)
    with open_application(settings) as app:
        spec = collection_spec(app)
        collection = service.import_into_application(app, spec)
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        with app.database.transaction() as connection:
            literal = cite_post_text(connection, spec.posts[0], "caption")
            unrelated = EvidenceRepository(connection).latest(
                "post", stable_id("post", "demo", "p1")
            )
        raw["links"][0].update(
            reaction_key="a1",
            origin="explicit_reference",
            reference_kind="quote",
            reference_text="ingredients",
            target_quote_evidence=literal.model_dump(),
        )
        service.import_into_application(app, AnnotationSet.model_validate(raw))
        assert (
            service.analyze(app, collection["ref"]["id"])["links"][0]["playback_reference_ms"]
            is None
        )
        raw["links"][0]["reference_text"] = "afford"
        with pytest.raises(ConfigurationError, match="literal target"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))
        raw["links"][0]["reference_text"] = "ingredients"
        raw["links"][0]["alternatives"] = [
            {"target": unrelated.model_dump(), "reason": "Not this post"}
        ]
        with pytest.raises(ConfigurationError, match="outside the comment"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))


def test_comment_erasure_covers_corrected_history_and_refuses_stale_confirmation(
    settings: Settings, account_export: Path
) -> None:
    import_comments(settings, account_export)
    with open_application(settings) as app:
        _, spec, _ = setup(app)
        target = spec.members[1].comment.id
        stale = service.redact(app, comment_id=target)
    document = json.loads(account_export.read_text())
    corrected_text = "Corrected unique objection still requires erasure"
    next(r for r in document["records"] if r.get("external_id") == "c1")["body"] = corrected_text
    account_export.write_text(json.dumps(document))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        with pytest.raises(ConfigurationError, match="confirmation"):
            service.redact(
                app, comment_id=target, confirmation=stale["confirmation"], reason="Erase"
            )
        plan = service.redact(app, comment_id=target)
        assert plan["confirmation"] != stale["confirmation"]
        service.redact(app, comment_id=target, confirmation=plan["confirmation"], reason="Erase")
        with app.database.transaction() as connection:
            comments = metadata.tables["comments"]
            assert (
                connection.scalar(select(comments.c.body).where(comments.c.id == target))
                == "[redacted]"
            )
            assert (
                connection.scalar(
                    select(comments.c.body).where(comments.c.id == spec.members[0].comment.id)
                )
                == BODIES[0]
            )
        for file in [app.paths.database, *app.paths.artifacts.rglob("*")]:
            if file.is_file():
                data = file.read_bytes()
                assert BODIES[1].encode() not in data
                assert corrected_text.encode() not in data


def test_explicit_post_quote_cannot_borrow_text_from_a_different_post_revision(
    settings: Settings, account_export: Path
) -> None:
    from socialdna.storage.creative_repository import cite_post_text

    document = json.loads(account_export.read_text())
    next(r for r in document["records"] if r.get("external_id") == "p0")["caption"] = "ingredients"
    account_export.write_text(json.dumps(document))
    import_comments(settings, account_export)
    with open_application(settings) as app:
        spec = collection_spec(app)
        collection = service.import_into_application(app, spec)
    document = json.loads(account_export.read_text())
    next(r for r in document["records"] if r.get("external_id") == "p0")["caption"] = (
        "ingredients revised"
    )
    account_export.write_text(json.dumps(document))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            current = EvidenceRepository(connection).latest("post", spec.posts[0].id)
            assert current and current != spec.posts[0]
            literal = cite_post_text(connection, current, "caption")
        raw = annotation_spec(collection, spec).model_dump(mode="json")
        raw["links"][0].update(
            reaction_key="a1",
            origin="explicit_reference",
            reference_kind="quote",
            reference_text="ingredients",
            target_quote_evidence=literal.model_dump(),
        )
        with pytest.raises(ConfigurationError, match="exact target post revision"):
            service.import_into_application(app, AnnotationSet.model_validate(raw))
