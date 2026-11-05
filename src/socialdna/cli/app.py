import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from socialdna import __version__
from socialdna.application.bootstrap import initialize
from socialdna.cli.account_commands import register as register_accounts
from socialdna.cli.audience_commands import register as register_audience_commands
from socialdna.cli.behavioral_commands import register as register_behavioral_commands
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.cli.creative_commands import register as register_creative_commands
from socialdna.cli.errors import error_result
from socialdna.cli.memory_commands import register as register_memory_commands
from socialdna.cli.output import emit
from socialdna.cli.research_commands import register as register_research_commands
from socialdna.config.settings import Settings
from socialdna.core.enums import ExitCode
from socialdna.core.exceptions import ConfigurationError, SocialDNAError
from socialdna.domain.results import Issue, ResultEnvelope
from socialdna.storage.health import doctor, storage_status, storage_verify

app = typer.Typer(
    help="Local-first, evidence-grounded social media research.",
    no_args_is_help=True,
    invoke_without_command=True,
    pretty_exceptions_enable=False,
)
storage = typer.Typer(help="Inspect and verify automatically managed local storage.")
app.add_typer(storage, name="storage")
ingestion = typer.Typer(help="Import authorized local data.")
analysis = typer.Typer(help="Analyze registered or local media.")
timeline_app = typer.Typer(help="Query the synchronized media timeline.")
report_app = typer.Typer(help="Generate grounded reports from persistent evidence.")
app.add_typer(ingestion, name="import")
app.add_typer(analysis, name="analyze")
app.add_typer(timeline_app, name="timeline")
app.add_typer(report_app, name="report")
models_app = typer.Typer(help="Inspect and explicitly prepare verified optional model assets.")
app.add_typer(models_app, name="models")
compare_app = typer.Typer(help="Compare age-aligned post or account populations.")
app.add_typer(compare_app, name="compare")


@app.callback()
def root(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
    offline: bool | None = None,
    no_ai: Annotated[bool, typer.Option("--no-ai")] = False,
    remote_media_consent: bool | None = None,
    version: Annotated[bool, typer.Option("--version", is_eager=True)] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    ctx.ensure_object(dict)
    ctx.obj.update(
        data_dir=data_dir,
        config=config,
        output_format=output_format,
        offline=offline,
        no_ai=no_ai,
        remote_media_consent=remote_media_consent,
    )


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


@ingestion.command("local")
def import_local_command(
    ctx: typer.Context,
    path: Path,
    copy_media: bool = False,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Register local video; --copy-media also retains managed original bytes."""
    from socialdna.application.bootstrap import open_application
    from socialdna.application.import_service import import_local

    def operation(settings: Settings) -> dict[str, Any]:
        with open_application(settings) as application:
            return import_local(application, path, copy_media=copy_media)

    execute(ctx, "import.local", operation, data_dir, config, output_format)


@analysis.command("video")
def analyze_video_command(
    ctx: typer.Context,
    target: str,
    depth: str = "standard",
    subtitles: Path | None = None,
    copy_media: bool = False,
    resume: str | None = None,
    palette_bins: int = 8,
    max_frames: int = 120,
    scene_threshold: float = 3.0,
    silence_db: float = -45,
    no_ai: Annotated[bool, typer.Option("--no-ai")] = False,
    transcribe: bool | None = None,
    ocr: bool | None = None,
    align: bool = False,
    pose: bool = False,
    classify_audio: bool = False,
    reason: bool = False,
    creative_profile: str | None = None,
    creative_annotations: Path | None = None,
    creative_frame_budget: int = 12,
    offline: bool | None = None,
    remote_media_consent: bool | None = None,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Analyze video with optional prepared local models. Use --no-ai for signals only."""
    from pydantic import ValidationError

    from socialdna.application.analysis_service import analyze_video
    from socialdna.application.bootstrap import open_application
    from socialdna.domain.media import AnalysisOptions

    def operation(settings: Settings) -> dict[str, Any]:
        try:
            options = AnalysisOptions.model_validate(
                {
                    "depth": depth,
                    "palette_bins": palette_bins,
                    "max_frames": max_frames,
                    "scene_threshold": scene_threshold,
                    "silence_db": silence_db,
                    "no_ai": no_ai or bool((ctx.find_root().obj or {}).get("no_ai")),
                    "transcribe": transcribe,
                    "ocr": ocr,
                    "align": align,
                    "pose": pose,
                    "classify_audio": classify_audio,
                    "reason": reason,
                    "creative_profile": creative_profile,
                    "creative_frame_budget": creative_frame_budget,
                }
            )
        except ValidationError as exc:
            raise ConfigurationError(str(exc)) from exc
        if offline is not None:
            settings.offline = offline
        if remote_media_consent is not None:
            settings.remote_media_consent = remote_media_consent
        with open_application(settings) as application:
            return analyze_video(
                application,
                target,
                options=options,
                subtitles=subtitles,
                copy_media=copy_media,
                resume=resume,
                creative_annotations=creative_annotations,
                on_run=lambda run_id: typer.echo(f"Analysis run: {run_id}", err=True),
                on_estimate=(
                    lambda estimate: typer.echo(
                        "Resource estimate: " + json.dumps(estimate), err=True
                    )
                )
                if depth == "deep"
                else None,
            )

    execute(ctx, "analyze.video", operation, data_dir, config, output_format)


@models_app.command("status")
def models_status_command(
    ctx: typer.Context,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Inspect local checksums, expected downloads, dependencies, devices and licenses."""
    from socialdna.application.bootstrap import open_application
    from socialdna.providers.models import ModelStore

    def operation(settings: Settings) -> dict[str, Any]:
        with open_application(settings):
            return {"models": ModelStore(settings).status(), "downloads_attempted": False}

    execute(ctx, "models.status", operation, data_dir, config, output_format)


@models_app.command("prepare")
def models_prepare_command(
    ctx: typer.Context,
    name: str,
    allow_download: bool | None = None,
    offline: bool | None = None,
    manifest: Path | None = None,
    from_dir: Path | None = None,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Download with explicit consent, or import files named in a verified manifest."""
    import httpx
    from pydantic import ValidationError

    from socialdna.application.bootstrap import open_application
    from socialdna.core.exceptions import DependencyUnavailable
    from socialdna.providers.models import ModelStore

    def operation(settings: Settings) -> dict[str, Any]:
        if allow_download is not None:
            settings.allow_download = allow_download
        if offline is not None:
            settings.offline = offline
        with open_application(settings):
            try:
                return ModelStore(settings).prepare(
                    name, manifest_path=manifest, source_dir=from_dir
                )
            except (ValidationError, OSError) as exc:
                raise ConfigurationError(
                    "Invalid model manifest or local source directory."
                ) from exc
            except httpx.HTTPError as exc:
                raise DependencyUnavailable(
                    "Model download failed; retry or use a verified local import."
                ) from exc

    execute(ctx, "models.prepare", operation, data_dir, config, output_format)


def parse_offset(value: str) -> int:
    from decimal import Decimal, InvalidOperation

    try:
        text = value.strip()
        milliseconds = (
            Decimal(text[:-2])
            if text.endswith("ms")
            else Decimal(text[:-1] if text.endswith("s") else text) * 1000
        )
        if not milliseconds.is_finite() or milliseconds < 0:
            raise ValueError()
        return round(milliseconds)
    except (ValueError, InvalidOperation) as exc:
        raise ConfigurationError(
            "Time must be non-negative seconds (5s) or milliseconds (5000ms)."
        ) from exc


@timeline_app.command("show")
def timeline_command(
    ctx: typer.Context,
    media_id: str,
    creative: bool = False,
    audience: bool = False,
    behavioral: bool = False,
    start: str = "0s",
    end: str | None = None,
    run: str | None = None,
    data_dir: DataDir = None,
    config: ConfigFile = None,
    output_format: Format = None,
) -> None:
    """Query intersecting evidence lanes in a half-open media interval."""
    from socialdna.application.bootstrap import open_application
    from socialdna.media.timeline import timeline

    def operation(settings: Settings) -> dict[str, Any]:
        with open_application(settings) as application:
            return timeline(
                application,
                media_id,
                parse_offset(start),
                parse_offset(end) if end is not None else None,
                run_id=run,
                include_creative=creative,
                include_audience=audience,
                include_behavioral=behavioral,
            )

    execute(ctx, "timeline.show", operation, data_dir, config, output_format)


@report_app.command("generate")
def report_command(
    ctx: typer.Context,
    run: Annotated[str | None, typer.Option()] = None,
    account: Annotated[str | None, typer.Option()] = None,
    report_format: Annotated[str, typer.Option("--format")] = "json",
    data_dir: DataDir = None,
    config: ConfigFile = None,
) -> None:
    """Emit a JSON report envelope or raw Markdown; persist the generated report artifact."""
    from socialdna.application.bootstrap import open_application
    from socialdna.application.report_service import generate_report

    if bool(run) == bool(account):
        raise ConfigurationError("Supply exactly one of --run or --account.")
    if report_format not in ("json", "markdown"):
        raise ConfigurationError("Report format must be json or markdown.")
    if report_format == "json":

        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as application:
                return generate_report(application, run, "json", account_id=account)

        execute(ctx, "report.generate", operation, data_dir, config, "json")
    else:
        root_options = ctx.find_root().obj or {}
        settings = Settings.load(
            config_file=config or root_options.get("config"),
            data_dir=data_dir or root_options.get("data_dir"),
        )
        with open_application(settings) as application:
            result = generate_report(application, run, "markdown", account_id=account)
        typer.echo(result["content"], nl=False)
        if result["status"] == "partial":
            raise typer.Exit(ExitCode.PARTIAL)


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


register_creative_commands(app)
register_audience_commands(app, analysis)
register_behavioral_commands(app, ingestion, analysis)
register_accounts(ingestion, analysis, compare_app)
register_research_commands(app, storage)
register_memory_commands(app, storage)
