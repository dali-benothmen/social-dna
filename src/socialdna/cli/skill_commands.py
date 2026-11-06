"""Small host-neutral interfaces; no host SDK or shell interpolation."""

from pathlib import Path

import typer

from socialdna.application.capability_service import capabilities
from socialdna.application.setup_service import guidance
from socialdna.application.skill_service import catalog, export_skill, inspect_bundle, schema
from socialdna.cli.common import ConfigFile, DataDir, Format, execute


def register(app: typer.Typer) -> None:
    skill = typer.Typer(help="Export the portable skill and inspect engine JSON schemas.")
    app.add_typer(skill, name="skill")

    @app.command("setup")
    def setup(
        ctx: typer.Context,
        task: str = "report",
        host: str = "codex",
        project_dir: Path = Path("."),
        url: str | None = None,
        scope: str = "content",
        input_kind: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Explain first-use prerequisites and next steps; no installs, storage or network."""
        execute(
            ctx,
            "setup",
            lambda settings: guidance(
                settings,
                task=task,
                host=host,
                project_dir=project_dir,
                url=url,
                scope=scope,
                input_kind=input_kind,
            ),
            data_dir,
            config,
            output_format,
        )

    @skill.command("list")
    def list_skills(ctx: typer.Context, output_format: Format = None) -> None:
        """List delivered bundles separately from planned specialist skills."""
        execute(ctx, "skill.list", lambda _: catalog(), None, None, output_format)

    @skill.command("inspect")
    def inspect_skill(
        ctx: typer.Context, name: str = "socialdna", output_format: Format = None
    ) -> None:
        """Validate selected public resources and return their hashes without exporting."""
        execute(ctx, "skill.inspect", lambda _: inspect_bundle(name), None, None, output_format)

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
    def export(
        ctx: typer.Context, destination: Path, name: str = "socialdna", output_format: Format = None
    ) -> None:
        """Export an implemented skill to a new matching directory; never overwrite."""
        execute(
            ctx,
            "skill.export",
            lambda _: export_skill(destination, name),
            None,
            None,
            output_format,
        )

    @skill.command("schema")
    def inspect_schema(ctx: typer.Context, name: str, output_format: Format = None) -> None:
        """Return a named engine contract as JSON Schema (see invalid-name list)."""
        execute(ctx, "skill.schema", lambda _: schema(name), None, None, output_format)
