"""Source-qualified per-platform distributions; fixtures are not empirical ranking evidence."""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_behavioral_analysis import export

from socialdna.application import behavioral_service
from socialdna.application import platform_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.platform_research import PlatformExport, PlatformReportSpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import database_checks


def distribution_library(app: Any, platform: str) -> dict[str, Any]:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        account = repo.latest("account", stable_id("account", platform, "0001"))
        posts = [repo.latest("post", stable_id("post", platform, f"p{i}")) for i in range(2)]
    assert account and all(posts)
    base = {
        "record_type": "behavioral_definition",
        "platform": platform,
        "subject_type": "post",
        "meaning": "other",
        "semantics": "count",
        "unit": "events",
        "domain": "nonnegative",
        "measurement": "period",
        "numerator_definition": "Source-defined controlled period counter",
        "population_basis": "plays",
        "replay_policy": "includes_replays",
        "source_definition_uri": "urn:controlled:source-definition",
        "description": "Controlled software fixture, not actual platform performance",
    }
    definitions = behavioral_service.import_into_application(
        app,
        export(
            [
                {**base, "key": f"{platform}.early.v1", "unit": "share_events"},
                {**base, "key": f"{platform}.later.v1", "unit": "impressions"},
                {
                    "record_type": "audience_cohort",
                    "key": "surface-plays",
                    "account": account.model_dump(),
                    "known": True,
                    "eligibility": "Controlled source-defined eligible plays",
                    "dimensions": {"traffic": "SOURCE_NATIVE"},
                    "aggregation_limitations": "Aggregate controlled fixtures, "
                    "not independent viewers",
                },
            ]
        ),
    )
    refs = [r["ref"] for r in definitions["records"]]
    measurements = []
    for i, post in enumerate(posts):
        assert post is not None
        start = datetime(2026, 1, i + 1, tzinfo=UTC)
        middle, end = start + timedelta(hours=1), start + timedelta(days=1)
        for name, left, right, definition, value in (
            ("early", start, middle, refs[0], (10, 20)[i]),
            ("later", middle, end, refs[1], (100, 30)[i]),
        ):
            measurements.append(
                {
                    "record_type": "metric_measurement",
                    "key": f"{platform}-{name}-{i}",
                    "subject": post.model_dump(),
                    "definition": definition,
                    "cohort": refs[2],
                    "clock": {
                        "window_start": left.isoformat(),
                        "window_end": right.isoformat(),
                        "data_cutoff": right.isoformat(),
                        "collected_at": (end + timedelta(days=1)).isoformat(),
                    },
                    "measurement": {"value": value},
                }
            )
    observed = behavioral_service.import_into_application(app, export(measurements))
    return {
        "account": account.model_dump(),
        "posts": [p.model_dump() for p in posts if p],
        "definitions": refs[:2],
        "measurements": [r["ref"] for r in observed["records"]],
    }


def platform_export(records: list[dict[str, Any]]) -> PlatformExport:
    return PlatformExport.model_validate(
        {
            "dataset_id": "platform-controlled",
            "source_uri": "urn:owned:platform-inputs",
            "permission_basis": "Owned controlled software fixtures and permitted official excerpt",
            "records": records,
        }
    )


@pytest.mark.parametrize(
    ("platform", "surface"), [("instagram", "reels"), ("tiktok", "for_you"), ("youtube", "shorts")]
)
def test_distinct_platform_sources_lagged_observations_reload_and_correction(
    settings: Settings, account_export: Path, platform: str, surface: str
) -> None:
    raw = json.loads(account_export.read_text())
    for record in raw["records"]:
        record["platform"] = platform
        for key, value in list(record.items()):
            if isinstance(value, str) and value.startswith("demo."):
                record[key] = platform + value[4:]
    account_export.write_text(json.dumps(raw))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        library = distribution_library(app, platform)
        scope = {
            "platform": platform,
            "surface": surface,
            "native_format": "video",
            "language": "en",
            "market": "US",
            "niche": "education",
            "audience": "controlled source cohort",
        }
        capabilities = {
            "record_type": "platform_capabilities",
            "key": "source-capabilities",
            "account": library["account"],
            "scope": scope,
            "clock": {"captured_at": "2026-02-01T00:00:00Z"},
            "analytics_permitted": True,
            "access_scope": "Owned controlled period analytics export",
            "collection_method": "authorized_export",
            "source_report": "controlled-period-report-v1",
            "reviewer": "fixture reviewer",
            "mapping_basis": "Explicit controlled source code, not guessed from aggregate views",
            "source_lag_seconds": 0,
            "metrics": [
                {
                    "definition": definition,
                    "role": role,
                    "availability": "available",
                    "reason": "Supplied controlled counter",
                }
                for definition, role in zip(
                    library["definitions"], ("shares", "impressions"), strict=True
                )
            ],
            "mappings": [{"raw_code": "SOURCE_NATIVE", "surface": surface, "traffic": "organic"}],
        }
        cap = service.import_into_application(app, platform_export([capabilities]))["records"][0][
            "ref"
        ]
        observations = []
        for i, post in enumerate(library["posts"]):
            observations.append(
                {
                    "record_type": "distribution_observation",
                    "key": f"lagged-{i}",
                    "account": library["account"],
                    "post": post,
                    "capabilities": cap,
                    "early": library["measurements"][2 * i],
                    "later": library["measurements"][2 * i + 1],
                    "raw_surface_code": "SOURCE_NATIVE",
                    "clock": {"captured_at": "2026-02-01T00:00:00Z"},
                }
            )
        imported = service.import_into_application(app, platform_export(observations))
        assert service.import_into_application(app, platform_export(observations)) == imported
        refs = tuple(EntityRef.model_validate(r["ref"]) for r in imported["records"])
        request = PlatformReportSpec(
            account=EntityRef.model_validate(library["account"]),
            scope=scope,
            observations=refs,
            traffic="organic",
            as_of=utc_now(),
        )
        report = service.report(app, request)
        assert report["result"]["observed_pair_count"] == 2
        assert [r["later"]["value"] for r in report["result"]["local_observations"]] == [100, 30]
        assert report["result"]["official_guidance"] == []
        assert not any(
            r["early_known_before_later"] for r in report["result"]["local_observations"]
        )
        with app.database.transaction() as connection:
            from socialdna.storage import behavioral_repository as behavior

            early = behavior.read(connection, EntityRef.model_validate(library["measurements"][0]))[
                "spec"
            ]
            overlap = json.loads(
                json.dumps(
                    behavior.read(connection, EntityRef.model_validate(library["measurements"][1]))[
                        "spec"
                    ]
                )
            )
        overlap["key"] = "overlap-fixture"
        for key in ("window_start", "window_end", "data_cutoff"):
            overlap["clock"][key] = early["clock"][key]
        overlap_ref = behavioral_service.import_into_application(app, export([overlap]))["records"][
            0
        ]["ref"]
        with pytest.raises(ConfigurationError, match="Overlapping"):
            service.import_into_application(
                app, platform_export([dict(observations[0], later=overlap_ref)])
            )
        unknown = json.loads(json.dumps(capabilities))
        unknown["key"] = "unknown-surface-capabilities"
        unknown["mappings"][0].update(surface=None, traffic="unknown")
        unknown_ref = service.import_into_application(app, platform_export([unknown]))["records"][
            0
        ]["ref"]
        unknown_observation = service.import_into_application(
            app,
            platform_export(
                [dict(observations[0], key="unknown-observation", capabilities=unknown_ref)]
            ),
        )["records"][0]["ref"]
        unknown_report = service.report(
            app,
            request.model_copy(
                update={
                    "observations": (EntityRef.model_validate(unknown_observation),),
                    "as_of": utc_now(),
                }
            ),
        )
        assert unknown_report["result"]["status"] == "insufficient_distribution_access"
        assert unknown_report["result"]["refusals"]
        assert (
            service.report(app, request.model_copy(update={"traffic": "paid"}))["result"]["status"]
            == "insufficient_distribution_access"
        )
        with pytest.raises(ConfigurationError, match="independent repeated"):
            service.report(app, request.model_copy(update={"observations": (refs[0], refs[0])}))
        bad = dict(observations[0], early=library["measurements"][1])
        with pytest.raises(ConfigurationError, match="early response"):
            service.import_into_application(app, platform_export([bad]))
        assert all(c.status != "error" for c in database_checks(app))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "context",
            "show",
            report["ref"]["id"],
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert (
        json.loads(completed.stdout)["data"]["content"]["result"]["claim_level"]
        == "descriptive_observational"
    )
    if platform == "youtube":
        with open_application(settings) as app:
            # Exact 16-word permitted excerpt from the official help source.
            text = "The Shorts Feed is personalized to reflect what we think you want to see next."
            official = {
                "record_type": "platform_document",
                "key": "official-shorts",
                "account": library["account"],
                "platform": "youtube",
                "surfaces": ["shorts"],
                "publisher": "YouTube",
                "url": "https://support.google.com/youtube/answer/16089387?hl=en",
                "title": "How YouTube recommendations work",
                "source_text": text,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "capture_scope": "permitted_excerpt",
                "clock": {"captured_at": "2026-11-05T00:00:00Z"},
                "review_status": "reviewed",
                "reviewer": "source excerpt checked during delivery",
                "review_basis": "Official page exact supplied excerpt; "
                "no ranking weights or empirical effect claim",
            }
            doc = service.import_into_application(app, platform_export([official]))["records"][0][
                "ref"
            ]
            statement = {
                "record_type": "platform_statement",
                "key": "shorts-scope",
                "account": library["account"],
                "document": doc,
                "surface": "shorts",
                "start_char": 0,
                "end_char": len(text),
                "quote": text,
                "interpretation": "Official statement about the Shorts surface, "
                "not a measured effect",
                "limitation": "Does not reveal proprietary weights "
                "or establish creator-level causality",
            }
            imported_statement = service.import_into_application(app, platform_export([statement]))
            statement_ref = EntityRef.model_validate(imported_statement["records"][0]["ref"])
            request = request.model_copy(
                update={"statements": (statement_ref,), "as_of": utc_now()}
            )
            combined = service.report(app, request)
            assert combined["result"]["official_guidance"][0]["claim_level"] == "official_guidance"
            from socialdna.application import audience_service
            from socialdna.domain.memory import QuerySpec
            from socialdna.memory import documents, hybrid, lexical

            with app.database.transaction() as connection:
                document = documents.build(
                    connection,
                    "evidence",
                    imported_statement["records"][0]["evidence"]["revision_id"],
                )
                assert document and document["claim_level"] == "official_guidance"
                lexical.project(connection, document)
                artifact = EvidenceRepository(connection).get(
                    "artifact_objects", combined["artifact_id"]
                )
                frozen_path = app.artifacts.path_for(artifact["relative_path"])
                frozen = frozen_path.read_bytes()
            assert hybrid.search(app, QuerySpec(text="personalized"))["hits"]
            service.import_into_application(
                app,
                platform_export(
                    [
                        dict(
                            official,
                            title="Controlled new-version metadata of the same permitted excerpt",
                        )
                    ]
                ),
            )
            with app.database.transaction() as connection:
                assert (
                    EvidenceResolver(connection)
                    .resolve(EvidenceRef.model_validate(combined["evidence"]))
                    .eligible
                )
            assert not hybrid.search(app, QuerySpec(text="personalized"))["hits"]
            assert frozen_path.read_bytes() == frozen
            corrected = dict(official, review_status="unreviewed", revision_reason="correction")
            service.import_into_application(app, platform_export([corrected]))
            with app.database.transaction() as connection:
                assert (
                    not EvidenceResolver(connection)
                    .resolve(EvidenceRef.model_validate(combined["evidence"]))
                    .eligible
                )
                withdraw(
                    connection, source_id=imported["source_id"], reason="Owner permission withdrawn"
                )
                assert (
                    not EvidenceResolver(connection)
                    .resolve(EvidenceRef.model_validate(report["evidence"]))
                    .eligible
                )
            plan = audience_service.redact(app, source_id=imported["source_id"])
            audience_service.redact(
                app,
                source_id=imported["source_id"],
                confirmation=plan["confirmation"],
                reason="Erase controlled distribution context",
            )
            assert not frozen_path.exists()
