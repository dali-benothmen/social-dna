"""Shared CLI options and consistent, stdout-safe command envelopes."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from socialdna.cli.errors import error_result
from socialdna.cli.output import OutputFormat, emit
from socialdna.config.settings import Settings
from socialdna.core.enums import ExitCode
from socialdna.core.exceptions import ConfigurationError, SocialDNAError
from socialdna.domain.results import CheckResult, Issue, ResultEnvelope

DataDir = Annotated[Path | None, typer.Option(help="Override the platform data directory.")]
ConfigFile = Annotated[Path | None, typer.Option("--config", help="Read [socialdna] from TOML.")]
Format = Annotated[str | None, typer.Option("--format", help="Output format: text or json.")]


def execute(
    ctx: typer.Context,
    command: str,
    operation: Callable[[Settings], dict[str, Any]],
    data_dir: Path | None,
    config: Path | None,
    output_format: str | None,
) -> None:
    options = ctx.find_root().obj or {}
    format_value = output_format or options.get("output_format") or "text"
    if format_value not in ("text", "json"):
        raise ConfigurationError("--format must be text or json")
    selected_format = cast(OutputFormat, format_value)
    try:
        settings = Settings.load(
            config_file=config or options.get("config"),
            data_dir=data_dir or options.get("data_dir"),
        )
        if options.get("offline") is not None:
            settings.offline = options["offline"]
        if options.get("remote_media_consent") is not None:
            settings.remote_media_consent = options["remote_media_consent"]
        data = operation(settings)
        checks = [CheckResult.model_validate(item) for item in data.get("checks", [])]
        errors = [
            Issue(code=check.name, message=check.message)
            for check in checks
            if check.status == "error"
        ]
        if data.get("valid") is False:
            errors.extend(
                Issue(code="invalid_import", message=f"Row {item['row']}: {item['message']}")
                for item in data.get("errors", [])
            )
        warnings = [
            Issue(code=check.name, message=check.message)
            for check in checks
            if check.status == "warning"
        ]
        result = ResultEnvelope(
            command=command,
            status="error"
            if errors
            else "partial"
            if data.get("status") == "partial"
            else "success",
            run_id=data.get("run_id"),
            data=data,
            limitations=data.get("limitations", []),
            warnings=warnings,
            errors=errors,
        )
        emit(result, selected_format)
        if errors:
            raise typer.Exit(
                ExitCode.INVALID_INPUT if data.get("valid") is False else ExitCode.STORAGE_INTEGRITY
            )
        if result.status == "partial":
            raise typer.Exit(ExitCode.PARTIAL)
    except SocialDNAError as exc:
        emit(error_result(command, exc), selected_format)
        raise typer.Exit(exc.exit_code) from exc
