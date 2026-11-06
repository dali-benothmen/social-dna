"""Small host-neutral interfaces; no host SDK or shell interpolation."""

from pathlib import Path

import typer

from socialdna.application.capability_service import capabilities
from socialdna.application.skill_service import export_skill, schema
from socialdna.cli.common import ConfigFile, DataDir, Format, execute


def register(app: typer.Typer) -> None:
    skill = typer.Typer(help="Export the portable skill and inspect engine JSON schemas.")
    app.add_typer(skill, name="skill")

    @app.command("capabilities")
    def manifest(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Preflight interfaces and local models without initializing storage or downloading."""
        execute(
            ctx,
            "capabilities",
            lambda settings: capabilities(
                settings, no_ai=bool((ctx.find_root().obj or {}).get("no_ai"))
            ),
            data_dir,
            config,
            output_format,
        )

    @skill.command("export")
    def export(ctx: typer.Context, destination: Path, output_format: Format = None) -> None:
        """Copy the bundled skill to a new explicit socialdna directory; never overwrite."""
        execute(ctx, "skill.export", lambda _: export_skill(destination), None, None, output_format)

    @skill.command("schema")
    def inspect_schema(ctx: typer.Context, name: str, output_format: Format = None) -> None:
        """Return a named engine contract as JSON Schema (see invalid-name list)."""
        execute(ctx, "skill.schema", lambda _: schema(name), None, None, output_format)
