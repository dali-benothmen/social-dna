"""Installed real R2 comparison/audit smoke, synthetic consented inputs, no network."""

import json
import sys
from pathlib import Path

from socialdna.application import performance_service, workflow_service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.workflow_report_service import generate
from socialdna.config.settings import Settings
from socialdna.core.time import utc_now
from socialdna.domain.workflows import WorkflowRequest


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True)
    settings = Settings(data_dir=root / "library", offline=True)
    records = [
        {
            "record_type": "account",
            "platform": "instagram",
            "external_id": "001",
            "handle": "fixture",
            "creator_key": "fixture",
        },
        {
            "record_type": "metric_definition",
            "platform": "instagram",
            "key": "instagram.views.v1",
            "definition": "Synthetic consented export count, not live platform evidence",
        },
    ]
    for index in range(2):
        records.extend(
            [
                {
                    "record_type": "post",
                    "platform": "instagram",
                    "external_id": f"fixture{index}",
                    "account_external_id": "001",
                    "content_type": "video",
                    "caption": "x" * (index + 1),
                    "published_at": "2026-01-01T00:00:00Z",
                    "title": "Ordinary synthetic post",
                },
                {
                    "record_type": "metric_snapshot",
                    "platform": "instagram",
                    "subject_external_id": f"fixture{index}",
                    "metric_key": "instagram.views.v1",
                    "value": 100 + index,
                    "observed_at": "2026-01-08T00:00:00Z",
                    "window_start": "2026-01-01T00:00:00Z",
                    "window_end": "2026-01-08T00:00:00Z",
                },
            ]
        )
    path = root / "synthetic.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "installed-comparison",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:synthetic:installed-comparison",
                },
                "records": records,
            }
        )
    )
    if not import_dataset(settings, path, "json")["valid"]:
        raise RuntimeError("Installed comparison import failed")
    identity = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="compare",
            url="https://www.instagram.com/p/fixture0/",
            against=("https://www.instagram.com/p/fixture1/",),
            question_scope="comparison_descriptive",
            goal="Describe the two synthetic observations",
            comparison={
                "design": {
                    "metric_key": "instagram.views.v1",
                    "design": "descriptive",
                    "estimand": "descriptive",
                    "knowledge_cutoff": utc_now(),
                    "publication_cutoff": "2026-11-01T00:00:00Z",
                    "features": ["caption_length"],
                    "covariates": ["caption_length"],
                    "model": "none",
                    "bootstrap_resamples": 200,
                    "feature_policy": "retrospective_content",
                    "family_id": "installed-comparison",
                    "family_terms": ["caption_length"],
                    "sampling_frame": "Two synthetic imported posts",
                }
            },
        ),
    )["workflow_id"]
    result = workflow_service.run(settings, identity)
    if result["status"] != "success" or result["content"]["quantitative"]["available_n"] != 2:
        raise RuntimeError("Installed real comparison pipeline failed")
    with open_application(settings) as app:
        reproduced = performance_service.reproduce(app, result["content"]["comparison_run_id"])
        if reproduced["results"] != result["content"]["quantitative"]:
            raise RuntimeError("Installed statistical reproduction diverged")
        if generate(app, identity)["content"] != result["content"]:
            raise RuntimeError("Installed comparison did not survive reopening")
    audit = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="evidence",
            from_workflow=identity,
            audit={"depth": 1, "max_nodes": 20, "max_edges": 50, "include_graph": True},
        ),
    )["workflow_id"]
    audited = workflow_service.run(settings, audit)
    if audited["content"]["root"] != result["report"] or not audited["content"]["citations"]:
        raise RuntimeError("Installed canonical evidence audit failed")
    with open_application(settings) as app:
        if "Exact evidence audit" not in generate(app, audit, "markdown")["content"]:
            raise RuntimeError("Installed frozen audit Markdown is unavailable")
    print("PASS: installed actual R2 comparison, reproduction, canonical audit and frozen reports")


if __name__ == "__main__":
    main()
