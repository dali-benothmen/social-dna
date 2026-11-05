"""Thin command adapters for authorized creative annotation and pinned recipes."""

from pathlib import Path
from typing import Annotated, Any

import typer

from socialdna.application.bootstrap import open_application
from socialdna.application.creative_service import (
    creative_timeline,
    definitions,
    import_annotations,
    materialize,
)
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.evidence import EntityRef
from socialdna.storage.creative_repository import cite_post_text
from socialdna.storage.evidence_repository import EvidenceRepository


def register(app: typer.Typer) -> None:
    creative = typer.Typer(help="Review observable creative events and materialize pinned recipes.")
    app.add_typer(creative, name="creative")

    @creative.command("import")
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
            "creative.import",
            lambda settings: import_annotations(settings, path, dry_run=dry_run),
            data_dir,
            config,
            output_format,
        )

    @creative.command("definitions")
    def definitions_command(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return definitions(application)

        execute(ctx, "creative.definitions", operation, data_dir, config, output_format)

    @creative.command("show")
    def show_command(
        ctx: typer.Context,
        media_id: str,
        key: str | None = None,
        as_of: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return creative_timeline(application, media_id, key=key, cutoff=as_of)

        execute(ctx, "creative.show", operation, data_dir, config, output_format)

    @creative.command("materialize")
    def materialize_command(
        ctx: typer.Context,
        media_id: str,
        recipe: Annotated[list[str], typer.Option("--recipe")],
        key: str | None = None,
        as_of: str | None = None,
        post: str | None = None,
        post_revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            if bool(post) != bool(post_revision):
                raise ConfigurationError("Supply both --post and --post-revision")
            with open_application(settings) as application:
                subject = (
                    EntityRef(kind="post", id=post, revision_id=post_revision)
                    if post and post_revision
                    else None
                )
                return materialize(
                    application, media_id, recipe, key=key, cutoff=as_of, post=subject
                )

        execute(ctx, "creative.materialize", operation, data_dir, config, output_format)

    @creative.command("cite-text")
    def cite_text_command(
        ctx: typer.Context,
        post_id: str,
        field: str = "caption",
        revision: str | None = None,
        start: int = 0,
        end: int | None = None,
        tag_index: int | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            if field not in ("caption", "hashtag"):
                raise ConfigurationError("Field must be caption or hashtag")
            with open_application(settings) as application:
                with application.database.transaction() as connection:
                    repository = EvidenceRepository(connection)
                    post = (
                        EntityRef(kind="post", id=post_id, revision_id=revision)
                        if revision
                        else repository.latest("post", post_id)
                    )
                    if not post:
                        raise ConfigurationError("Unknown captured post")
                    ref = cite_post_text(
                        connection,
                        post,
                        "caption" if field == "caption" else "hashtag",
                        start,
                        end,
                        tag_index,
                    )
                    return EvidenceResolver(connection).resolve(ref).model_dump(mode="json")

        execute(ctx, "creative.cite-text", operation, data_dir, config, output_format)
