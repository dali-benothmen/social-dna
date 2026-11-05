"""Profile quality and actual measured conversion remain independent lanes."""

from pathlib import Path
from typing import Any

import typer

from socialdna.application import profile_service as service
from socialdna.application.bootstrap import open_application
from socialdna.application.context_service import read_spec
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.domain.profile import RUBRIC, ProfileReportSpec


def register(app: typer.Typer) -> None:
    profile = typer.Typer(
        help="Dated public profiles, human rubrics and authorized aggregate funnels."
    )
    app.add_typer(profile, name="profile")

    @profile.command("rubric")
    def rubric(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "profile.rubric",
            lambda settings: {"rubric": RUBRIC},
            data_dir,
            config,
            output_format,
        )

    @profile.command("import")
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
            "profile.import",
            lambda settings: service.import_document(settings, path, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @profile.command("report")
    def report_command(
        ctx: typer.Context,
        path: Path,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            spec = read_spec(path, ProfileReportSpec)
            with open_application(settings) as app:
                return service.report(app, spec)

        execute(ctx, "profile.report", operation, data_dir, config, output_format)
