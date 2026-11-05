"""Thin command adapters over shared memory services."""

from pathlib import Path
from typing import Any

import typer

from socialdna.application import query_service
from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.memory import EmbeddingSpace, QuerySpec


def _query_spec(**values: Any) -> QuerySpec:
    try:
        return QuerySpec.model_validate(values)
    except ValueError as exc:
        raise ConfigurationError("Invalid memory query: " + str(exc)) from exc


def register(app: typer.Typer, storage: typer.Typer) -> None:
    graph = typer.Typer(help="Bounded qualified canonical-reference graph, not a causal graph.")
    memory = typer.Typer(
        help="Persistent research-memory capabilities and immutable embedding spaces."
    )
    app.add_typer(graph, name="graph")
    app.add_typer(memory, name="memory")

    @app.command("query")
    def query_command(
        ctx: typer.Context,
        text: str,
        mode: str = "fts",
        family: str | None = None,
        owner_kind: str | None = None,
        owner_id: str | None = None,
        source: str | None = None,
        revision: str | None = None,
        as_of: str | None = None,
        space: str | None = None,
        limit: int = 10,
        candidate_limit: int = 300,
        graph_depth: int = 0,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            spec = _query_spec(
                **{
                    "text": text,
                    "mode": mode,
                    "family": family,
                    "owner_kind": owner_kind,
                    "owner_id": owner_id,
                    "source_id": source,
                    "revision_id": revision,
                    "as_of": as_of,
                    "space_id": space,
                    "limit": limit,
                    "candidate_limit": candidate_limit,
                    "graph_depth": graph_depth,
                }
            )
            with open_application(settings) as application:
                return query_service.query(application, spec)

        execute(ctx, "query", operation, data_dir, config, output_format)

    @memory.command("status")
    def status_command(
        ctx: typer.Context,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return query_service.status(application)

        execute(ctx, "memory.status", operation, data_dir, config, output_format)

    @memory.command("register-space")
    def space_command(
        ctx: typer.Context,
        spec: Path,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            try:
                if spec.stat().st_size > settings.max_input_bytes:
                    raise ConfigurationError(
                        "Embedding-space specification exceeds the input budget"
                    )
                value = EmbeddingSpace.model_validate_json(spec.read_bytes())
            except (OSError, ValueError) as exc:
                raise ConfigurationError(
                    "Invalid embedding-space specification: " + str(exc)
                ) from exc
            with open_application(settings) as application:
                return query_service.register_embedding_space(application, value)

        execute(ctx, "memory.register-space", operation, data_dir, config, output_format)

    def maintain(rebuild: bool) -> Any:
        def command(
            ctx: typer.Context,
            limit: int = 1000,
            space: str | None = None,
            vectors: bool = False,
            repair: bool = False,
            data_dir: DataDir = None,
            config: ConfigFile = None,
            output_format: Format = None,
        ) -> None:
            def operation(settings: Settings) -> dict[str, Any]:
                with open_application(settings) as application:
                    return query_service.reconcile(
                        application,
                        limit=limit,
                        rebuild=rebuild,
                        space_id=space,
                        vectors=vectors,
                        repair=repair,
                    )

            execute(
                ctx,
                "storage.reindex" if rebuild else "storage.reconcile",
                operation,
                data_dir,
                config,
                output_format,
            )

        return command

    storage.command("reconcile")(maintain(False))
    storage.command("reindex")(maintain(True))

    @graph.command("neighbors")
    def neighbors_command(
        ctx: typer.Context,
        revision: str,
        depth: int = 2,
        max_nodes: int = 2000,
        max_edges: int = 4000,
        as_of: str | None = None,
        historical: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            cutoff = _query_spec(text="graph", as_of=as_of).as_of
            with open_application(settings) as application:
                return query_service.graph_query(
                    application,
                    revision,
                    depth=depth,
                    max_nodes=max_nodes,
                    max_edges=max_edges,
                    as_of=cutoff,
                    historical=historical,
                )

        execute(ctx, "graph.neighbors", operation, data_dir, config, output_format)

    @graph.command("path")
    def path_command(
        ctx: typer.Context,
        source: str,
        target: str,
        depth: int = 2,
        max_nodes: int = 2000,
        max_edges: int = 4000,
        as_of: str | None = None,
        historical: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            cutoff = _query_spec(text="graph", as_of=as_of).as_of
            with open_application(settings) as application:
                return query_service.graph_query(
                    application,
                    source,
                    target=target,
                    depth=depth,
                    max_nodes=max_nodes,
                    max_edges=max_edges,
                    as_of=cutoff,
                    historical=historical,
                )

        execute(ctx, "graph.path", operation, data_dir, config, output_format)
