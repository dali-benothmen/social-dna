"""Account CLI adapters; business logic belongs to application services."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from pydantic import ValidationError

from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.research import PerformanceSpec, parse_performance_spec


def _spec(
    path: Path | None,
    metric: str | None,
    age_days: float | None,
    model: str | None,
    unmatched: bool = False,
) -> PerformanceSpec:
    try:
        values = json.loads(path.read_text(encoding="utf-8")) if path else {}
        if not isinstance(values, dict):
            raise ValueError("Specification must be a JSON object")
        if metric:
            values["metric_key"] = metric
        if age_days is not None:
            values["age_days"] = age_days
        if model:
            values["model"] = model
        if unmatched:
            values["matched"] = False
        return parse_performance_spec(values)
    except (OSError, ValueError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid performance specification: {exc}") from exc


def register(ingestion: typer.Typer, analysis: typer.Typer, comparison: typer.Typer) -> None:
    def import_command(format_name: Literal["csv", "json"]) -> Callable[..., None]:
        def command(
            ctx: typer.Context,
            path: Path,
            dry_run: bool = False,
            data_dir: DataDir = None,
            config: ConfigFile = None,
            output_format: Format = None,
        ) -> None:
            """Validate/import authorized exports. Dry runs never initialize or write storage."""
            from socialdna.application.account_import_service import import_dataset

            execute(
                ctx,
                "import." + format_name,
                lambda settings: import_dataset(settings, path, format_name, dry_run=dry_run),
                data_dir,
                config,
                output_format,
            )

        return command

    ingestion.command("json")(import_command("json"))
    ingestion.command("csv")(import_command("csv"))

    @analysis.command("account")
    def account(
        ctx: typer.Context,
        account_id: str,
        metric: str | None = None,
        spec: Path | None = None,
        age_days: float | None = None,
        model: str | None = None,
        analyze_media: bool = False,
        max_posts: int = 100,
        max_items: int = 20,
        depth: str = "standard",
        with_local_models: bool = False,
        reproduce_run: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Persist age-aligned analytics; optionally process local media references first."""

        def operation(settings: Settings) -> dict[str, Any]:
            from socialdna.application.performance_service import analyze_account

            specification = _spec(spec, metric, age_days, model) if not reproduce_run else None
            try:
                options = AnalysisOptions.model_validate(
                    {
                        "depth": depth,
                        "no_ai": not with_local_models
                        or bool((ctx.find_root().obj or {}).get("no_ai")),
                    }
                )
            except ValidationError as exc:
                raise ConfigurationError(str(exc)) from exc
            if reproduce_run and any((spec, metric, age_days is not None, model, analyze_media)):
                raise ConfigurationError("Reproduction uses only saved inputs/specification")
            with open_application(settings) as application:
                return analyze_account(
                    application,
                    account_id,
                    specification,
                    analyze_media=analyze_media,
                    media_options=options,
                    max_posts=max_posts,
                    max_items=max_items,
                    reproduce_run=reproduce_run,
                )

        execute(ctx, "analyze.account", operation, data_dir, config, output_format)

    def compare_command(kind: Literal["posts", "accounts"]) -> Callable[..., None]:
        def command(
            ctx: typer.Context,
            left: Annotated[list[str], typer.Option(help="Repeat --left for each ID.")],
            right: Annotated[list[str], typer.Option(help="Repeat --right for each ID.")],
            metric: str | None = None,
            spec: Path | None = None,
            age_days: float | None = None,
            model: str | None = None,
            unmatched: bool = False,
            data_dir: DataDir = None,
            config: ConfigFile = None,
            output_format: Format = None,
        ) -> None:
            """Compare disjoint groups using age-aligned outcomes and matched context."""

            def operation(settings: Settings) -> dict[str, Any]:
                from socialdna.application.performance_service import compare

                specification = _spec(spec, metric, age_days, model, unmatched)
                with open_application(settings) as application:
                    return compare(application, kind, left, right, specification)

            execute(ctx, "compare." + kind, operation, data_dir, config, output_format)

        return command

    comparison.command("posts")(compare_command("posts"))
    comparison.command("accounts")(compare_command("accounts"))

    @comparison.command("reproduce")
    def reproduce_command(
        ctx: typer.Context,
        run_id: str,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Rerun a saved comparison/account spec using its frozen inputs and versions."""
        from socialdna.application.performance_service import reproduce

        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return reproduce(application, run_id)

        execute(ctx, "compare.reproduce", operation, data_dir, config, output_format)
