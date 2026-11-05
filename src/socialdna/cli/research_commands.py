"""Thin R1 command adapters over the shared Python services."""

from pathlib import Path
from typing import Annotated, Any

import typer

from socialdna.application import investigation_service, literature_service
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.research_service import (
    generate_research_report,
    register_research,
    show_research,
)
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus, ResearchProtocol
from socialdna.storage.backup import backup_library, restore_library
from socialdna.storage.evidence_repository import EvidenceRepository


def register(app: typer.Typer, storage: typer.Typer) -> None:
    evidence = typer.Typer(help="Create, resolve and withdraw exact versioned citations.")
    research = typer.Typer(
        help="Register questions, import reviewed research and evaluate bounded rival protocols."
    )
    app.add_typer(evidence, name="evidence")
    app.add_typer(research, name="research")

    @research.command("import-literature")
    def literature_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            corpus = literature_service.read_spec(spec, LiteratureCorpus)
            with open_application(settings) as application:
                return literature_service.import_corpus(application, corpus)

        execute(ctx, "research.import-literature", operation, data_dir, config, output_format)

    @research.command("prepare")
    def prepare_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            protocol = literature_service.read_spec(spec, ResearchProtocol)
            with open_application(settings) as application:
                return investigation_service.prepare(application, protocol)

        execute(ctx, "research.prepare", operation, data_dir, config, output_format)

    @research.command("evaluate")
    def evaluate_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            evaluation = literature_service.read_spec(spec, EvaluationSpec)
            with open_application(settings) as application:
                return investigation_service.evaluate(application, evaluation)

        execute(ctx, "research.evaluate", operation, data_dir, config, output_format)

    @evidence.command("resolve")
    def resolve_command(
        ctx: typer.Context,
        identity: str,
        revision: str | None = None,
        purpose: str = "inspect",
        as_of: str | None = None,
        media: str | None = None,
        post: str | None = None,
        run: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            if purpose not in ("inspect", "new_claim"):
                raise ConfigurationError("Purpose must be inspect or new_claim")
            with open_application(settings) as application:
                with application.database.transaction() as connection:
                    return (
                        EvidenceResolver(connection)
                        .resolve(
                            identity,
                            revision_id=revision,
                            purpose="new_claim" if purpose == "new_claim" else "inspect",
                            as_of=as_of,
                            media_id=media,
                            post_id=post,
                            run_id=run,
                        )
                        .model_dump(mode="json")
                    )

        execute(ctx, "evidence.resolve", operation, data_dir, config, output_format)

    @evidence.command("cite-comment")
    def comment_command(
        ctx: typer.Context,
        comment_id: str,
        start: Annotated[int, typer.Option("--start")],
        end: Annotated[int, typer.Option("--end")],
        comment_revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                with application.database.transaction() as connection:
                    ref = EvidenceRepository(connection).comment_evidence(
                        comment_id, start, end, revision_id=comment_revision
                    )
                    return EvidenceResolver(connection).resolve(ref).model_dump(mode="json")

        execute(ctx, "evidence.cite-comment", operation, data_dir, config, output_format)

    @evidence.command("cite-metric")
    def metric_command(
        ctx: typer.Context,
        snapshot_id: str,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                with application.database.transaction() as connection:
                    ref = EvidenceRepository(connection).metric_evidence(snapshot_id)
                    return EvidenceResolver(connection).resolve(ref).model_dump(mode="json")

        execute(ctx, "evidence.cite-metric", operation, data_dir, config, output_format)

    @evidence.command("withdraw")
    def withdraw_command(
        ctx: typer.Context,
        reason: Annotated[str, typer.Option("--reason")],
        source: str | None = None,
        evidence_id: str | None = None,
        actor: str = "local-user",
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                with application.database.transaction() as connection:
                    return withdraw(
                        connection,
                        source_id=source,
                        evidence_id=evidence_id,
                        reason=reason,
                        actor=actor,
                    )

        execute(ctx, "evidence.withdraw", operation, data_dir, config, output_format)

    @research.command("register")
    def register_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        dry_run: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "research.register",
            lambda settings: register_research(settings, spec, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @research.command("show")
    def show_command(
        ctx: typer.Context,
        identity: str,
        revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return show_research(application, identity, revision_id=revision)

        execute(ctx, "research.show", operation, data_dir, config, output_format)

    @research.command("report")
    def report_command(
        ctx: typer.Context,
        question_id: str,
        report_format: str = "json",
        revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return generate_research_report(
                    application, question_id, report_format=report_format, revision_id=revision
                )

        execute(ctx, "research.report", operation, data_dir, config, output_format)

    @storage.command("backup")
    def backup_command(
        ctx: typer.Context,
        destination: Path,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "storage.backup",
            lambda settings: backup_library(settings, destination),
            data_dir,
            config,
            output_format,
        )

    @storage.command("restore")
    def restore_command(
        ctx: typer.Context,
        backup: Path,
        destination: Path,
        withdrawals_from: Path | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "storage.restore",
            lambda settings: restore_library(
                backup, destination, withdrawals_from=withdrawals_from
            ),
            data_dir,
            config,
            output_format,
        )
