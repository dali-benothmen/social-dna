"""Thin offline context adapters; no network or publishing side effects."""

from pathlib import Path
from typing import Any

import typer

from socialdna.application import context_service as service
from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.domain.context import PublicationReportSpec


def register(app: typer.Typer) -> None:
    context = typer.Typer(help="Versioned publication and growth-context evidence.")
    app.add_typer(context, name="context")

    @context.command("recipes")
    def recipes(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "context.recipes",
            lambda settings: {"recipes": service.PUBLICATION_RECIPES},
            data_dir,
            config,
            output_format,
        )

    @context.command("import")
    def import_command(
        ctx: typer.Context,
        path: Path,
        dry_run: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "context.import",
            lambda settings: service.import_document(settings, path, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @context.command("show")
    def show_command(
        ctx: typer.Context,
        identity: str,
        revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                return service.show(app, identity, revision=revision)

        execute(ctx, "context.show", operation, data_dir, config, output_format)

    @context.command("publication-report")
    def report_command(
        ctx: typer.Context,
        path: Path,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            spec = service.read_spec(path, PublicationReportSpec)
            with open_application(settings) as app:
                return service.publication_report(app, spec)

        execute(ctx, "context.publication-report", operation, data_dir, config, output_format)

    @context.command("cite")
    def cite_command(
        ctx: typer.Context,
        identity: str,
        field: str | None = None,
        start: int | None = None,
        end: int | None = None,
        artifact: str | None = None,
        revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                shown = service.show(app, identity, revision=revision)
                from socialdna.domain.evidence import EntityRef
                from socialdna.storage.context_repository import cite

                with app.database.transaction() as connection:
                    ref = cite(
                        connection,
                        EntityRef.model_validate(shown["ref"]),
                        field=field,
                        start=start,
                        end=end,
                        artifact_id=artifact,
                    )
                    return {"ref": ref.model_dump()}

        execute(ctx, "context.cite", operation, data_dir, config, output_format)
