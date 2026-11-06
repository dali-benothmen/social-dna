"""Host-neutral source-only tasks, with explicit maintenance setup and no hidden fetches."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.workflows import WorkflowRequest
from socialdna.reporting.export import export_report


def register(app: typer.Typer) -> None:
    commands = typer.Typer(help="Plan, run and inspect bounded URL-to-source-report workflows.")
    app.add_typer(commands, name="workflow")

    @commands.command("plan")
    def plan(
        ctx: typer.Context,
        url: Annotated[str | None, typer.Option()] = None,
        mode: str = "ingest",
        from_workflow: Annotated[str | None, typer.Option("--from")] = None,
        goal: str = "Capture the source's native public metadata.",
        question_scope: str = "unassessed",
        max_attempts: int = 3,
        scope: str = "content",
        profile_revision: str | None = None,
        audit_focus: str = "balanced",
        account_external_id: str | None = None,
        max_posts: int = 10,
        analyze_media: bool = False,
        refresh_from: str | None = None,
        context_revision: Annotated[list[str] | None, typer.Option("--context-revision")] = None,
        left_url: Annotated[list[str] | None, typer.Option("--left-url")] = None,
        against: Annotated[list[str] | None, typer.Option("--against")] = None,
        comparison_spec: Path | None = None,
        support_revision: Annotated[list[str] | None, typer.Option("--support-revision")] = None,
        contrary_revision: Annotated[list[str] | None, typer.Option("--contrary-revision")] = None,
        recommendation_spec: Path | None = None,
        entity_revision: str | None = None,
        evidence_id: str | None = None,
        evidence_revision: str | None = None,
        audit_depth: int = 2,
        audit_max_nodes: int = 50,
        audit_max_edges: int = 100,
        include_graph: bool = False,
        include_history: bool = True,
        media: Annotated[list[Path] | None, typer.Option("--media")] = None,
        permission_basis: str | None = None,
        copy_media: bool = False,
        replace_media: bool = False,
        subtitles: Path | None = None,
        depth: str = "standard",
        max_frames: int = 120,
        transcribe: bool = False,
        ocr: bool = False,
        align: bool = False,
        reconstruction_output: str = "combined",
        track: Annotated[list[str] | None, typer.Option("--track")] = None,
        start_ms: int = 0,
        end_ms: int | None = None,
        allow_verbatim: bool = False,
        creative_revision: str | None = None,
        dry_run: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Persist a bounded plan without network access; --dry-run also avoids library writes."""
        try:

            def specification(path: Path | None) -> Any:
                if path is None:
                    return None
                try:
                    with path.open("rb") as stream:
                        raw = stream.read(1_000_001)
                    if len(raw) > 1_000_000:
                        raise ConfigurationError("Workflow specification exceeds 1 MB")
                    return json.loads(raw)
                except (OSError, ValueError):
                    raise ConfigurationError(
                        "Cannot read a bounded JSON workflow specification"
                    ) from None

            if bool(evidence_id) != bool(evidence_revision):
                raise ConfigurationError(
                    "Evidence selection needs both --evidence-id and --evidence-revision"
                )
            request = WorkflowRequest.model_validate(
                {
                    "mode": mode,
                    "url": url,
                    "from_workflow": from_workflow,
                    "goal": goal,
                    "question_scope": question_scope,
                    "max_attempts": max_attempts,
                    "scope": scope,
                    "profile_revision": profile_revision,
                    "audit_focus": audit_focus,
                    "account_external_id": account_external_id,
                    "max_posts": max_posts,
                    "analyze_media": analyze_media,
                    "refresh_from": refresh_from,
                    "context_revisions": tuple(context_revision or []),
                    "left_urls": tuple(left_url or []),
                    "against": tuple(against or []),
                    "comparison": {
                        "design": specification(comparison_spec),
                        "support_revisions": tuple(support_revision or []),
                        "contrary_revisions": tuple(contrary_revision or []),
                        "recommendation": specification(recommendation_spec),
                    },
                    "entity_revision": entity_revision,
                    "evidence_reference": {"id": evidence_id, "revision_id": evidence_revision}
                    if evidence_id
                    else None,
                    "audit": {
                        "depth": audit_depth,
                        "max_nodes": audit_max_nodes,
                        "max_edges": audit_max_edges,
                        "include_graph": include_graph,
                        "include_history": include_history,
                    },
                    "media": tuple(str(path) for path in (media or [])),
                    "permission_basis": permission_basis,
                    "copy_media": copy_media,
                    "replace_media": replace_media,
                    "subtitles": str(subtitles) if subtitles else None,
                    "reconstruction": {
                        "output": reconstruction_output,
                        "track_ids": tuple(track or []),
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "allow_verbatim": allow_verbatim,
                        "creative_revision": creative_revision,
                    },
                    "analysis_options": AnalysisOptions.model_validate(
                        {
                            "no_ai": bool((ctx.find_root().obj or {}).get("no_ai"))
                            or not (transcribe or ocr or align),
                            "depth": depth,
                            "max_frames": max_frames,
                            "transcribe": transcribe,
                            "ocr": ocr,
                            "align": align,
                        }
                    ),
                }
            )
        except ValidationError:
            raise ConfigurationError(
                "Invalid workflow request: ingest needs --url; report needs --from. "
                "Analyze needs a post URL and declared permission for supplied originals. "
                "Reconstruct accepts --from or --url plus an authorized video. "
                "Compare requires --url and --against; evidence selects --from, "
                "--entity-revision or an exact evidence pair. "
                "See skill schema workflow_request."
            ) from None
        execute(
            ctx,
            "workflow.plan",
            lambda settings: workflow_service.plan(settings, request, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @commands.command("observe-profile")
    def observe_profile(
        ctx: typer.Context,
        url: str,
        external_id: Annotated[str, typer.Option()],
        captured_at: Annotated[str, typer.Option()],
        permission_basis: Annotated[str, typer.Option()],
        source_description: Annotated[str, typer.Option()],
        username: str | None = None,
        display_name: str | None = None,
        bio: str | None = None,
        category: str | None = None,
        link: Annotated[list[str] | None, typer.Option("--link")] = None,
        links_empty: bool = False,
        pin_revision: Annotated[list[str] | None, typer.Option("--pin-revision")] = None,
        pins_empty: bool = False,
        photo: Path | None = None,
        photo_absent: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Import actual permitted profile observations; no fetch or user-authored JSON needed."""
        from socialdna.application.profile_audit_service import observe

        if permission_basis not in (
            "creator_owned_export",
            "authorized_export",
            "public_permitted",
        ):
            raise ConfigurationError("Declare a supported independent observation permission basis")
        from typing import Literal, cast

        permission = cast(
            Literal["creator_owned_export", "authorized_export", "public_permitted"],
            permission_basis,
        )
        execute(
            ctx,
            "workflow.observe-profile",
            lambda settings: observe(
                settings,
                url,
                external_id=external_id,
                captured_at=captured_at,
                permission_basis=permission,
                source_description=source_description,
                username=username,
                display_name=display_name,
                bio=bio,
                category=category,
                links=tuple(link or []),
                links_empty=links_empty,
                pins=tuple(pin_revision or []),
                pins_empty=pins_empty,
                photo=photo,
                photo_absent=photo_absent,
            ),
            data_dir,
            config,
            output_format,
        )

    @commands.command("run")
    def run(
        ctx: typer.Context,
        workflow_id: str,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Execute/resume the declared plan; no duplicate capture on a successful retry."""
        execute(
            ctx,
            "workflow.run",
            lambda settings: workflow_service.run(settings, workflow_id),
            data_dir,
            config,
            output_format,
        )

    @commands.command("show")
    def show(
        ctx: typer.Context,
        workflow_id: str,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Return exact plan, attempts, state and canonical output bindings."""
        execute(
            ctx,
            "workflow.show",
            lambda settings: workflow_service.show(settings, workflow_id),
            data_dir,
            config,
            output_format,
        )

    @commands.command("report")
    def report(
        ctx: typer.Context,
        workflow_id: str,
        report_format: Annotated[str, typer.Option("--format")] = "json",
        output: Path | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
    ) -> None:
        """Return a JSON envelope and optionally export the frozen JSON/Markdown document."""
        from socialdna.application.workflow_report_service import generate

        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                result = generate(application, workflow_id, report_format)
                if output is not None:
                    result["export_path"] = export_report(result, output)
                return result

        execute(ctx, "workflow.report", operation, data_dir, config, "json")

    @commands.command("maintenance")
    def maintenance(
        ctx: typer.Context,
        output_dir: Path | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Inspect/export matching systemd units; never install, enable or alter host settings."""
        from socialdna.application.workflow_maintenance import configuration

        execute(
            ctx,
            "workflow.maintenance",
            lambda settings: configuration(settings, output_dir),
            data_dir,
            config,
            output_format,
        )

    @commands.command("maintain")
    def maintain(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Apply source expiry and resume confirmed cleanup; no acquisition or inference."""
        from socialdna.storage.workflow_retention import expire

        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                count = expire(application.database, application.paths)
                return {
                    "expired_sources_reconciled": count,
                    "network_attempted": False,
                    "limitations": [
                        "Only managed active-library copies are maintained; "
                        "external exports/backups are not erased."
                    ],
                }

        execute(ctx, "workflow.maintain", operation, data_dir, config, output_format)
