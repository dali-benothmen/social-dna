from pathlib import Path
from typing import Any

import typer

from socialdna.application import audience_service
from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings


def register(app: typer.Typer, analysis: typer.Typer) -> None:
    audience = typer.Typer(
        help="Source-qualified collections, reactions, content links and redaction."
    )
    app.add_typer(audience, name="audience")

    @audience.command("comments")
    def comments(
        ctx: typer.Context,
        post: str = typer.Option(..., "--post"),
        limit: int = 1000,
        after: str = "",
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return audience_service.comments(application, post, limit=limit, after=after)

        execute(ctx, "audience.comments", operation, data_dir, config, output_format)

    @audience.command("import-collection")
    def import_collection(
        ctx: typer.Context,
        path: Path,
        dry_run: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "audience.import-collection",
            lambda settings: audience_service.import_document(
                settings, path, "collection", dry_run=dry_run
            ),
            data_dir,
            config,
            output_format,
        )

    @audience.command("import-annotations")
    def import_annotations(
        ctx: typer.Context,
        path: Path,
        dry_run: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        execute(
            ctx,
            "audience.import-annotations",
            lambda settings: audience_service.import_document(
                settings, path, "annotations", dry_run=dry_run
            ),
            data_dir,
            config,
            output_format,
        )

    @audience.command("show")
    def show(
        ctx: typer.Context,
        collection: str,
        revision: str | None = None,
        as_of: str | None = None,
        annotation_key: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return audience_service.show(
                    application, collection, revision=revision, as_of=as_of, key=annotation_key
                )

        execute(ctx, "audience.show", operation, data_dir, config, output_format)

    @analysis.command("audience")
    def analyze(
        ctx: typer.Context,
        collection: str = typer.Option(..., "--collection"),
        revision: str | None = None,
        as_of: str | None = None,
        annotation_key: str | None = None,
        propose_literal: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return audience_service.analyze(
                    application,
                    collection,
                    revision=revision,
                    as_of=as_of,
                    key=annotation_key,
                    literal=propose_literal,
                )

        execute(ctx, "analyze.audience", operation, data_dir, config, output_format)

    @audience.command("redact")
    def redact(
        ctx: typer.Context,
        comment: str | None = None,
        source: str | None = None,
        confirm: str | None = None,
        reason: str = "",
        actor: str = "local-user",
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Preview exact impact; --confirm TOKEN executes irreversible active-library erasure."""

        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return audience_service.redact(
                    application,
                    comment_id=comment,
                    source_id=source,
                    confirmation=confirm,
                    reason=reason,
                    actor=actor,
                )

        execute(ctx, "audience.redact", operation, data_dir, config, output_format)
