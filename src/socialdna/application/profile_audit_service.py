"""Assisted observation intake and bounded, snapshot-cited deterministic profile checks."""

import json
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select

from socialdna import __version__
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.profile_service import import_into_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config, hash_file
from socialdna.core.time import utc_now
from socialdna.domain.context import ContextClock, TextField
from socialdna.domain.evidence import EntityRef
from socialdna.domain.profile import ProfileExport, ProfileLink, ProfilePhoto, ProfileSnapshot
from socialdna.domain.profile_audit import ProfileAuditProposal, ProfileFinding
from socialdna.domain.workflows import WorkflowPlan
from socialdna.ingestion.tabular import Account, ParsedImport, Source
from socialdna.ingestion.urls import parse_url
from socialdna.media.images import decode
from socialdna.reporting.markdown import escape
from socialdna.storage import content_repository as content
from socialdna.storage import context_repository as context
from socialdna.storage import workflow_repository as workflows
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def observe(
    settings: Settings,
    url: str,
    *,
    external_id: str,
    captured_at: str,
    permission_basis: Literal["creator_owned_export", "authorized_export", "public_permitted"],
    source_description: str,
    username: str | None = None,
    display_name: str | None = None,
    bio: str | None = None,
    category: str | None = None,
    links: tuple[str, ...] = (),
    links_empty: bool = False,
    pins: tuple[str, ...] = (),
    pins_empty: bool = False,
    photo: Path | None = None,
    photo_absent: bool = False,
) -> dict[str, Any]:
    """Host/user supplies actual independently permitted observations, not engine acquisition.

    Flags avoid requiring user-authored engine JSON. Omission means not_collected;
    an explicitly supplied empty string means observed empty. Stable identity is
    supplied, never invented from a mutable handle. No external link is fetched.
    """
    from socialdna.application.account_import_service import persist_records

    target = parse_url(url)
    clock = ContextClock(captured_at=captured_at)
    if target.kind != "account" or clock.captured_at > utc_now():
        raise ConfigurationError("Observe a profile URL with an actual nonfuture capture time")
    if target.platform == "youtube" and target.external_id.startswith("channel/"):
        if external_id != target.external_id.removeprefix("channel/"):
            raise ConfigurationError("Stable channel identity differs from its URL")
    if not source_description.strip() or len(source_description) > 2000:
        raise ConfigurationError("Describe the independently permitted observation source")
    if (links and links_empty) or (pins and pins_empty) or (photo and photo_absent):
        raise ConfigurationError("Observed assets cannot also be declared empty/absent")
    account_record = Account(
        record_type="account", platform=target.platform, external_id=external_id, handle=username
    )
    photo_spec = None
    if photo:
        photo = photo.expanduser().resolve()
        decode(photo, settings)  # U1 byte/pixel/animation/orientation gates, before any write.
        photo_spec = ProfilePhoto(
            path=str(photo),
            sha256=hash_file(photo, byte_limit=min(settings.max_image_bytes, 10_000_000)),
        )

    def text(value: str | None) -> TextField:
        return TextField(
            state="not_collected" if value is None else "present" if value else "empty", value=value
        )

    # Validate typed fields/links before opening the persistent library.
    fields = {
        name: text(value)
        for name, value in (
            ("username", username),
            ("display_name", display_name),
            ("bio", bio),
            ("category", category),
        )
    }
    link_specs = tuple(
        ProfileLink(key=f"link-{i}", label="Observed destination", destination=v)
        for i, v in enumerate(links)
    )
    raw = {
        "url": target.canonical_url,
        "external_id": external_id,
        "clock": clock.model_dump(),
        "fields": {k: v.model_dump() for k, v in fields.items()},
        "links": list(links),
        "links_empty": links_empty,
        "pins": list(pins),
        "pins_empty": pins_empty,
        "photo": photo_spec.model_dump() if photo_spec else None,
        "photo_absent": photo_absent,
        "source_description": source_description,
        "permission_basis": permission_basis,
    }
    digest = hash_config(raw)
    source = Source(
        dataset_id="profile-" + digest[:32],
        permission_basis=permission_basis,
        source_uri=target.canonical_url,
        terms={"source_description": source_description, "independently_supplied": True},
    )
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            imported = persist_records(
                app,
                connection,
                ParsedImport(
                    source=source,
                    records=[account_record],
                    rows=[1],
                    raw=canonical_json(
                        {"source": source.model_dump(), "records": [account_record.model_dump()]}
                    ).encode(),
                ),
            )
            repo = EvidenceRepository(connection)
            account = repo.latest("account", imported["account_ids"][0])
            assert account is not None
            pin_refs = tuple(repo.ref(repo.get("entity_revisions", revision)) for revision in pins)
        spec = ProfileSnapshot(
            key="public",
            account=account,
            clock=clock,
            username=fields["username"],
            display_name=fields["display_name"],
            bio=fields["bio"],
            category=fields["category"],
            positioning=TextField(state="not_collected"),
            declaration_basis="source_record",
            photo_state="present" if photo else "absent" if photo_absent else "not_collected",
            photo=photo_spec,
            links_state="collected" if links else "empty" if links_empty else "not_collected",
            links=link_specs,
            pins_state="collected" if pins else "empty" if pins_empty else "not_collected",
            pins=pin_refs,
        )
        result = import_into_application(
            app,
            ProfileExport(
                dataset_id="profile-" + digest[:32],
                source_uri=target.canonical_url,
                permission_basis=permission_basis + ": " + source_description,
                records=(spec,),
            ),
        )
    return {
        **result,
        "snapshot": result["records"][0]["ref"],
        "network_attempted": False,
        "limitations": [
            "Independent source/identity/permission declarations, "
            "not platform verification or URL acquisition."
        ],
    }


def snapshot(
    app: Application, revision: str, plan: WorkflowPlan
) -> tuple[EntityRef, dict[str, Any]]:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        ref = repo.ref(repo.get("entity_revisions", revision))
        if ref.kind != "profile_snapshot":
            raise ConfigurationError("Profile scope requires an actual profile snapshot revision")
        data = context.read(connection, ref)
        account = json.loads(repo.entity(EntityRef.model_validate(data["account"]))["payload_json"])
        # The independent snapshot's exact source URL and platform are checked; aliases
        # are not guessed and arbitrary same-platform snapshots cannot be substituted.
        source = repo.get("source_records", repo.entity(ref)["source_id"])
        if (
            parse_url(source["source_uri"]).canonical_url != plan.canonical_url
            or account["platform"] != plan.platform
        ):
            raise ConfigurationError("Profile snapshot belongs to another URL/platform")
    return ref, data


def run(app: Application, identity: str, plan: WorkflowPlan) -> dict[str, Any]:
    assert plan.request.profile_revision is not None
    ref, data = snapshot(app, plan.request.profile_revision, plan)
    with app.database.transaction() as connection:
        existing = content.records(connection, identity, "profile_audit")
    if existing:
        return content.load(app, existing[0], "json")
    spec = data["spec"]
    findings = []
    with app.database.transaction() as connection:
        for name in ("username", "display_name", "bio", "category", "positioning"):
            value = spec[name]
            state = value["state"]
            citation = (
                context.cite(
                    connection, ref, field=name + "/value", start=0, end=len(value["value"])
                )
                if state == "present"
                else context.cite(connection, ref)
            )
            present = state == "present"
            empty = state in ("empty", "absent", "removed")
            findings.append(
                ProfileFinding(
                    field=name,
                    direction="strength" if present else "weakness" if empty else "unknown",
                    observation=f"Observed {name}: {value['value']}"
                    if present
                    else f"{name}: {state}.",
                    proposal=(
                        "Preserve available information; review audience fit separately."
                        if present
                        else "Consider adding an audience-relevant description."
                        if empty
                        else "Collect this field before judging it."
                    ),
                    priority="consider" if present else "check" if empty else "review",
                    evidence=(citation,),
                )
            )
        whole = context.cite(connection, ref)
        for name, state in (
            ("photo", spec["photo_state"]),
            ("links", spec["links_state"]),
            ("pins", spec["pins_state"]),
        ):
            known = state in ("present", "collected")
            findings.append(
                ProfileFinding(
                    field=name,
                    direction="strength" if known else "unknown",
                    observation=f"{name}: {state}; presence does not establish quality.",
                    proposal="Review actual content and audience fit; "
                    "no aesthetic/CTA/pin-alignment judgment is established.",
                    priority="review",
                    evidence=(whole,),
                )
            )
        measurements: dict[str, int | str] | None = None
        if spec.get("photo"):
            asset = app.artifacts.get(connection, spec["photo"]["artifact_id"])
            if not app.artifacts.verify(asset):
                raise ConfigurationError("Profile photo failed integrity verification")
            info, _ = decode(app.artifacts.path_for(asset["relative_path"]), app.settings)
            measurements = {"width": info.width, "height": info.height, "format": info.format}
        report = ProfileAuditProposal(
            workflow_id=identity,
            canonical_url=plan.canonical_url,
            account=EntityRef.model_validate(data["account"]),
            snapshot=ref,
            captured_at=spec["clock"]["captured_at"],
            goal=plan.request.goal,
            focus=plan.request.audit_focus,
            producer="socialdna/" + __version__,
            findings=tuple(findings),
            photo_measurements=measurements,
            limitations=(
                "Assisted observations; no profile fetch, account crawl or linked-site access.",
                "Field checks only, not clarity, branding, inferred pillars or human review.",
                "Focus changes presentation, not judgments. Popularity sets no direction.",
                "No measured conversion effect. C1-D/R5 measured funnels remain separate.",
            ),
            required_actions=(
                {
                    "code": "interpretation_review_required",
                    "message": "Review the exact snapshot and unreviewed proposals "
                    "for substantive positioning/visual judgments.",
                },
            ),
        )
        payload = {
            "workflow_id": identity,
            "entity_inputs": [ref.model_dump()],
            "evidence_inputs": [r.model_dump() for f in findings for r in f.evidence],
            "result": report.model_dump(mode="json"),
        }
        saved = content.save(
            connection,
            "profile_audit",
            identity,
            "audit",
            payload,
            EvidenceRepository(connection).entity(ref)["provenance_id"],
        )
        content.cite(connection, saved)
        lines = [
            "# Profile audit proposal",
            "",
            "Unreviewed field checks; substantive interpretation remains partial.",
            "",
            "URL: " + escape(plan.canonical_url),
            "",
            "Focus: " + report.focus,
            "",
        ]
        order = (
            {"strength": 0, "weakness": 1, "unknown": 2}
            if report.focus == "strengths"
            else {"weakness": 0, "strength": 1, "unknown": 2}
        )
        for finding in sorted(findings, key=lambda f: order[f.direction]):
            lines += [
                f"- {finding.direction}: {escape(finding.observation)} "
                f"{escape(finding.proposal)} (evidence `{finding.evidence[0].revision_id}`)"
            ]
        lines += ["", "## Limitations", "", *("- " + escape(v) for v in report.limitations)]
        content.freeze(
            app, connection, saved, report.model_dump(mode="json"), "\n".join(lines) + "\n"
        )
        workflows.bind(connection, identity, "capture", ref, None)
        workflows.bind(connection, identity, "report", saved, None)
        workflows.state(connection, identity, "partial", "interpretation_review_required")
    return content.load(app, saved, "json")


def freshness(app: Application, ref: EntityRef) -> dict[str, Any]:
    """A read-only freshness hint outside the immutable report; never refresh/refit."""
    with app.database.transaction() as connection:
        payload = content.active(connection, ref)
        result = payload["result"]
        entities, rows = metadata.tables["entity_revisions"], metadata.tables["context_records"]
        candidates = (
            connection.execute(
                select(entities)
                .join(rows, rows.c.revision_id == entities.c.id)
                .where(
                    entities.c.kind == "profile_snapshot",
                    rows.c.account_revision_id.in_(
                        select(entities.c.id).where(
                            entities.c.kind == "account",
                            entities.c.entity_id == result["account"]["id"],
                        )
                    ),
                    rows.c.captured_at > result["captured_at"],
                )
            )
            .mappings()
            .all()
        )
        # Only eligible newer snapshots justify a staleness indication.
        newer = []
        for row in candidates:
            candidate = EvidenceRepository(connection).ref(dict(row))
            try:
                context.read(connection, candidate)
            except ConfigurationError:
                continue
            newer.append(candidate.revision_id)
    return {"stale": bool(newer), "newer_snapshot_revisions": sorted(newer), "refreshed": False}
