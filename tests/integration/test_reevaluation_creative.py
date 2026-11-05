"""Reviewed creative edits invalidate actual recipe inputs, not psychological truth."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_creative_analysis import RESULT, setup_review
from test_psychological_research import ACCOUNT, design, protocol
from test_psychological_research import library as library

from socialdna.application import investigation_service
from socialdna.application import reevaluation_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.creative_service import import_into_application
from socialdna.application.performance_service import analyze_account, load_performance_report
from socialdna.config.settings import Settings
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.evidence import EntityRef
from socialdna.domain.investigation import EvaluationSpec
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.research import PerformanceSpec


def test_reviewed_annotation_revision_refits_pinned_recipe_and_preserves_prior_features(
    settings: Settings,
    library: dict[str, Any],
    account_export: Path,
    video: Path,
) -> None:
    with open_application(settings) as app:
        _, annotation, _ = setup_review(app, video)
    data = json.loads(account_export.read_text())
    data["records"].append(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": "p0",
            "position": 0,
            "uri": str(video),
        }
    )
    account_export.write_text(json.dumps(data))
    assert import_dataset(settings, account_export, "json")["valid"]
    spec = design(
        features=["creative.result_first", "caption_length"],
        family_terms=["creative.result_first", "caption_length"],
        family_id="creative-revisions",
        creative_annotation_key="reviewed-opening",
        creative_recipes={"creative.result_first": RESULT},
    )
    with open_application(settings) as app:
        analyze_account(
            app,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.views.v1"),
            analyze_media=True,
            media_options=AnalysisOptions(no_ai=True),
        )
        spec = spec.model_copy(update={"knowledge_cutoff": utc_now()})
        prepared = investigation_service.prepare(
            app, protocol(library["registered"], library["corpus"], feature="creative.result_first")
        )
        initial = analyze_account(app, ACCOUNT, spec)
        ref = EntityRef.model_validate(
            investigation_service.evaluate(
                app,
                EvaluationSpec.model_validate(
                    {"protocol": prepared["protocol"], "analysis_run_ids": [initial["run_id"]]}
                ),
            )["assessment"]
        )
        post_id = stable_id("post", "demo", "p0")
        assert (
            next(r for r in initial["posts"] if r["post_id"] == post_id)["features"][
                "creative.result_first"
            ]
            == 1
        )
        modified = annotation.model_dump(mode="json")
        modified["events"] = [event for event in modified["events"] if event["key"] != "dish"]
        import_into_application(app, CreativeAnnotationSet.model_validate(modified))
        assert investigation_service.show_record(app, ref)["freshness"] == "stale"
        revised = service.reevaluate(app, ref.id)
        content = investigation_service.show_record(
            app, EntityRef.model_validate(revised["assessment"])
        )["content"]
        assert any(
            c["kind"] == "annotation_or_recipe_changed" for c in content["reevaluation"]["changes"]
        )
        report = load_performance_report(app, run_id=content["population_manifests"][0]["run_id"])
        assert (
            next(r for r in report["posts"] if r["post_id"] == post_id)["features"][
                "creative.result_first"
            ]
            == 0
        )
        assert load_performance_report(app, run_id=initial["run_id"])["posts"] == initial["posts"]
        with pytest.raises(ValidationError, match="exact versioned recipe"):
            design(
                **{
                    **spec.model_dump(),
                    "creative_recipes": {"creative.result_first": "unavailable.v2"},
                }
            )
