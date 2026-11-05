"""Explicit versioned import and analysis adapters over the shared engine."""

from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from socialdna.application import behavioral_service as service
from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.behavioral import AccountOutcomeSpec


def register(app: typer.Typer, ingestion: typer.Typer, analysis: typer.Typer) -> None:
    behavioral = typer.Typer(help="Source-defined metrics, exact bins and behavioral evidence.")
    app.add_typer(behavioral, name="behavioral")

    @behavioral.command("subject")
    def subject(
        ctx: typer.Context,
        identity: str,
        kind: str = "account",
        as_of: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                return service.subject(app, kind, identity, as_of=as_of)

        execute(ctx, "behavioral.subject", operation, data_dir, config, output_format)

    @ingestion.command("behavioral")
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
            "import.behavioral",
            lambda settings: service.import_document(settings, path, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @behavioral.command("show")
    def show(
        ctx: typer.Context,
        identity: str,
        revision: str | None = None,
        as_of: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                return service.show(app, identity, revision=revision, as_of=as_of)

        execute(ctx, "behavioral.show", operation, data_dir, config, output_format)

    @analysis.command("retention")
    def retention(
        ctx: typer.Context,
        series: str | None = None,
        post: str | None = None,
        compare_series: str | None = None,
        revision: str | None = None,
        as_of: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                return service.analyze_retention(
                    app,
                    series_id=series,
                    post_id=post,
                    compare_id=compare_series,
                    revision=revision,
                    as_of=as_of,
                )

        execute(ctx, "analyze.retention", operation, data_dir, config, output_format)

    @analysis.command("outcomes")
    def outcomes(
        ctx: typer.Context,
        account_id: str,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        try:
            with spec.open("rb") as stream:
                raw = stream.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Outcome specification exceeds 1 MB")
            parsed = AccountOutcomeSpec.model_validate_json(raw)
        except (OSError, ValueError, ValidationError) as exc:
            raise ConfigurationError(f"Invalid account-outcome specification: {exc}") from exc

        def operation(settings: Settings) -> dict[str, Any]:
            from socialdna.application.performance_service import analyze_account_outcomes

            with open_application(settings) as app:
                return analyze_account_outcomes(app, account_id, parsed)

        execute(ctx, "analyze.outcomes", operation, data_dir, config, output_format)
