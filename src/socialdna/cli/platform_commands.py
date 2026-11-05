"""Platform-specific evidence inputs, not proprietary recommendation recovery."""

from pathlib import Path
from typing import Any

import typer

from socialdna.application import platform_service as service
from socialdna.application.bootstrap import open_application
from socialdna.application.context_service import read_spec
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.domain.platform_research import SURFACES, PlatformReportSpec


def register(app: typer.Typer) -> None:
    platform = typer.Typer(
        help="Reviewed platform guidance and source-qualified distribution observations."
    )
    app.add_typer(platform, name="platform")

    @platform.command("templates")
    def templates(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "platform.templates",
            lambda settings: {
                "surfaces": SURFACES,
                "question": "Within each exact platform/surface/context, do eligible early "
                "responses precede later observed distribution?",
                "boundary": "A shared validator is not a shared ranking model. "
                "Source permissions and actual available metrics must be supplied separately.",
            },
            data_dir,
            config,
            output_format,
        )

    @platform.command("import")
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
            "platform.import",
            lambda settings: service.import_document(settings, path, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @platform.command("report")
    def report_command(
        ctx: typer.Context,
        path: Path,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            spec = read_spec(path, PlatformReportSpec)
            with open_application(settings) as app:
                return service.report(app, spec)

        execute(ctx, "platform.report", operation, data_dir, config, output_format)
