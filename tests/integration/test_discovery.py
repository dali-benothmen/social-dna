"""Real imports → canonical population → bounded search → frozen evidence/reload."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.discovery_confirmation import confirm
from socialdna.application.discovery_service import discover, reproduce, show
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.research.candidates import ConfirmationSpec, DiscoverySpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def dataset(path: Path, *, first: int = 0, count: int = 16) -> None:
    records: list[dict[str, Any]] = [
        {
            "record_type": "metric_definition",
            "platform": "demo",
            "key": "demo.views.v1",
            "definition": "Controlled software-fixture seven-day views",
        }
    ]
    for creator in range(first, first + count):
        records.append(
            {
                "record_type": "account",
                "platform": "demo",
                "external_id": f"c{creator}",
                "creator_key": f"c{creator}",
                "niche": "education",
            }
        )
        for i in range(6):
            start = f"2026-01-{i + 1:02}T00:00:00Z"
            end = f"2026-01-{i + 8:02}T00:00:00Z"
            records.extend(
                [
                    {
                        "record_type": "post",
                        "platform": "demo",
                        "external_id": f"p{creator}-{i}",
                        "account_external_id": f"c{creator}",
                        "published_at": start,
                        "content_type": "video",
                        "caption": "a" * (i + 1),
                    },
                    {
                        "record_type": "metric_snapshot",
                        "platform": "demo",
                        "subject_external_id": f"p{creator}-{i}",
                        "metric_key": "demo.views.v1",
                        "window_start": start,
                        "window_end": end,
                        "observed_at": end,
                        "value": 100 + 30 * (i - 2) ** 2 + ((creator + i) % 3),
                    },
                ]
            )
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": f"controlled-{first}",
                    "source_uri": f"urn:owned:discovery:{first}",
                    "permission_basis": "creator_owned_export",
                },
                "records": records,
            }
        )
    )


def request(**changes: Any) -> DiscoverySpec:
    cutoff = utc_now()
    return DiscoverySpec.model_validate(
        {
            "key": "nonlinear-cooking",
            "family_id": "nonlinear-cooking",
            "holdout_id": "creator-reservation",
            "as_of": cutoff,
            "input": {
                "kind": "posts",
                "analysis": {
                    "metric_key": "demo.views.v1",
                    "design": "descriptive",
                    "estimand": "descriptive",
                    "feature_policy": "retrospective_content",
                    "knowledge_cutoff": cutoff,
                    "publication_cutoff": "2026-10-01T00:00:00Z",
                    "sampling_frame": "All authorized fixture posts in declared creator population",
                    "features": ["caption_length"],
                    "covariates": ["caption_length"],
                    "family_id": "source-only",
                    "family_terms": ["caption_length"],
                },
            },
            "scope": {
                "platform": "demo",
                "surface": "aggregate",
                "native_format": "video",
                "language": "en",
                "market": "US",
                "audience": "controlled",
                "niches": ["education"],
                "objective": "aggregate_attention",
                "traffic": "unknown",
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-10-01T00:00:00Z",
                "basis": "Controlled source inventory, not empirical social-media evidence",
            },
            "candidates": [
                {
                    "key": k,
                    "kind": k,
                    "features": ["caption_length"],
                    "proposal_source": "prespecified",
                    "prediction": "Controlled caption-length association",
                }
                for k in ("main", "quadratic")
            ],
            **changes,
        }
    )


def test_imported_population_search_evidence_restart_reproduction_and_holdouts(
    settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "owned.json"
    dataset(path)
    imported = import_dataset(settings, path, "json")
    assert imported["valid"], imported
    with open_application(settings) as app:
        spec = request()
        report = discover(app, spec)
        assert report["result"]["selected"] == "quadratic"
        outer = report["result"]["outer"]["evaluations"]["in_scope"]
        assert outer["mae"] < 2 and outer["baseline_mae"] > 40
        ref, citation = (
            EntityRef.model_validate(report["ref"]),
            EvidenceRef.model_validate(report["evidence"]),
        )
        assert reproduce(app, ref)["result"] == report["result"]
        with app.database.transaction() as connection:
            assert EvidenceResolver(connection).resolve(citation, purpose="new_claim").eligible
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["discovery_attempts"])
                )
                == 9
            )
        with pytest.raises(ConfigurationError, match="already registered"):
            discover(app, spec)
        changed = spec.model_copy(
            update={"key": "another-round", "holdout_id": "renamed", "parent_search": ref}
        )
        with pytest.raises(ConfigurationError, match="Consumed"):
            discover(app, changed)
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(metadata.tables["discovery_rounds"].c.status).where(
                        metadata.tables["discovery_rounds"].c.id == "another-round"
                    )
                )
                == "refused"
            )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--offline",
            "--format",
            "json",
            "--data-dir",
            str(settings.data_dir),
            "research",
            "show-discovery",
            spec.key,
            "--reproduce",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout)["data"]["reproduced"] is True
    with open_application(settings) as app:
        assert show(app, ref)["result"] == report["result"]
        assert reproduce(app, ref)["holdout_consumed_again"] is False
        with app.database.transaction() as connection:
            resolver = EvidenceResolver(connection)
            assert resolver.resolve(citation).eligible
            withdraw(
                connection,
                source_id=imported["source_id"],
                reason="Controlled permission withdrawal",
            )
            assert not resolver.resolve(citation).eligible
        with pytest.raises(ConfigurationError, match="Ineligible"):
            show(app, ref)


def test_independent_confirmation_estimates_actual_quadratic_contrast(
    settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "owned.json"
    dataset(path)
    import_dataset(settings, path, "json")
    with open_application(settings) as app:
        original = discover(app, request())
    # Truly new creators and outcomes, imported after the discovery was completed.
    dataset(path, first=100, count=22)
    import_dataset(settings, path, "json")
    with open_application(settings) as app:
        options = request()
        source = options.input.model_dump(mode="json")
        source["analysis"]["population"] = {
            "creator_ids": [stable_id("creator", f"c{i}") for i in range(100, 122)]
        }
        confirmation = ConfirmationSpec.model_validate(
            {
                "key": "independent",
                "family_id": "independent",
                "discovery": original["ref"],
                "input": source,
                "scope": options.scope.model_dump(mode="json"),
                "as_of": options.as_of,
                "holdout_id": "new-creators",
                "direction": "positive",
                "minimum_absolute_effect": 10,
                "interpretation": "A quadratic raw-basis coefficient above ten on new creators",
            }
        )
        report = confirm(app, confirmation)
        result = report["result"]
        assert result["disposition"] == "supports_prespecified_contrast"
        effect = result["contrast"]["coefficients"][0]
        assert 29 < effect["raw_basis_estimate"] < 31
        assert result["causal_or_mechanism_proof"] is False
        assert reproduce(app, EntityRef.model_validate(report["ref"]))["result"] == result
        with pytest.raises(ConfigurationError, match="Consumed"):
            confirm(
                app,
                confirmation.model_copy(
                    update={"key": "repeat-confirmation", "holdout_id": "renamed-again"}
                ),
            )


def test_missing_features_small_populations_and_failed_fits_are_auditable(
    settings: Settings, account_export: Path
) -> None:
    raw = json.loads(account_export.read_text())
    from test_versioned_analytics import explicit_windows

    account_export.write_text(json.dumps(raw))
    explicit_windows(account_export)
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        report = discover(app, request())
        assert report["result"]["selected"] is None
        with app.database.transaction() as connection:
            table = metadata.tables["discovery_attempts"]
            assert set(connection.scalars(select(table.c.status))) == {"refused"}
            repo = EvidenceRepository(connection)
            assert repo.entity(EntityRef.model_validate(report["ref"]))["content_hash"]
