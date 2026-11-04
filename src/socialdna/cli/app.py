import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from socialdna import __version__
from socialdna.application.bootstrap import initialize
from socialdna.cli.errors import error_result
from socialdna.cli.output import OutputFormat, emit
from socialdna.config.settings import Settings
from socialdna.core.enums import ExitCode
from socialdna.core.exceptions import ConfigurationError, SocialDNAError
from socialdna.domain.results import CheckResult, Issue, ResultEnvelope
from socialdna.storage.health import doctor, storage_status, storage_verify

app = typer.Typer(
    help="Local-first, evidence-grounded social media research.",
    no_args_is_help=True,
    invoke_without_command=True,
    pretty_exceptions_enable=False,
)
storage = typer.Typer(help="Inspect and verify automatically managed local storage.")
app.add_typer(storage, name="storage")

DataDir = Annotated[Path | None, typer.Option(help="Override the platform data directory.")]
ConfigFile = Annotated[Path | None, typer.Option("--config", help="Read [socialdna] from TOML.")]
Format = Annotated[str | None, typer.Option("--format", help="Output format: text or json.")]


@app.callback()
def root(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
    version: Annotated[bool, typer.Option("--version", is_eager=True)] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    ctx.ensure_object(dict)
    ctx.obj.update(data_dir=data_dir, config=config, output_format=output_format)


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
        data = operation(settings)
        checks = [CheckResult.model_validate(item) for item in data.get("checks", [])]
        errors = [
            Issue(code=check.name, message=check.message)
            for check in checks
            if check.status == "error"
        ]
        warnings = [
            Issue(code=check.name, message=check.message)
            for check in checks
            if check.status == "warning"
        ]
        result = ResultEnvelope(
            command=command,
            status="error" if errors else "success",
            data=data,
            warnings=warnings,
            errors=errors,
        )
        emit(result, selected_format)
        if errors:
            raise typer.Exit(ExitCode.STORAGE_INTEGRITY)
    except SocialDNAError as exc:
        emit(error_result(command, exc), selected_format)
        raise typer.Exit(exc.exit_code) from exc


@app.command("init")
def init_command(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Initialize storage; also happens automatically on first use."""
    execute(ctx, "init", initialize, data_dir, config, output_format)


@app.command("doctor")
def doctor_command(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Inspect installed dependencies, storage integrity and model availability."""
    execute(
        ctx,
        "doctor",
        lambda settings: {
            "checks": [check.model_dump() for check in doctor(settings)],
        },
        data_dir,
        config,
        output_format,
    )


@storage.command("status")
def status_command(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Report canonical, vector, and graph storage capabilities."""
    execute(ctx, "storage.status", storage_status, data_dir, config, output_format)


@storage.command("verify")
def verify_command(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Check database integrity, foreign keys, metadata and artifact checksums."""
    execute(
        ctx,
        "storage.verify",
        lambda settings: {
            "checks": [check.model_dump() for check in storage_verify(settings)],
        },
        data_dir,
        config,
        output_format,
    )


def main() -> None:
    """Normalize parser and runtime failures as well as successful command output."""
    args = sys.argv[1:]
    json_requested = "--format=json" in args or any(
        value == "--format" and index + 1 < len(args) and args[index + 1] == "json"
        for index, value in enumerate(args)
    )
    try:
        exit_code = app(standalone_mode=False)
        if isinstance(exit_code, int):
            raise SystemExit(exit_code)
    except typer.TyperException as exc:
        if json_requested:
            result = ResultEnvelope(
                command="cli",
                status="error",
                errors=[Issue(code="invalid_input", message=exc.format_message())],
            )
            emit(result, "json")
        else:
            typer.echo(f"Error: {exc.format_message()}", err=True)
        raise SystemExit(ExitCode.INVALID_INPUT) from exc
    except SocialDNAError as exc:
        emit(error_result("cli", exc), "json" if json_requested else "text")
        raise SystemExit(exc.exit_code) from exc
    except Exception as exc:
        result = ResultEnvelope(
            command="cli",
            status="error",
            errors=[
                Issue(
                    code="internal_error",
                    message="Unexpected failure; no success is claimed. "
                    f"Error type: {type(exc).__name__}.",
                )
            ],
        )
        emit(result, "json" if json_requested else "text")
        raise SystemExit(ExitCode.INTERNAL) from exc
