import tempfile
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select

from socialdna.analyzers.audio import measure_audio
from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.analyzers.visual import measure_motion, measure_visual
from socialdna.application.bootstrap import Application
from socialdna.application.import_service import resolve_media
from socialdna.application.report_service import generate_report
from socialdna.application.task_runner import TaskRunner
from socialdna.core.exceptions import InvalidMedia
from socialdna.core.hashing import canonical_json, hash_config, hash_file
from socialdna.core.ids import new_id
from socialdna.core.time import utc_now
from socialdna.domain.media import AnalysisOptions
from socialdna.media.audio import extract_audio
from socialdna.media.ffmpeg import require_tool, tool_version
from socialdna.media.frames import decode_proxy, extract_frames, frame_candidates
from socialdna.media.scenes import detect_scenes
from socialdna.media.subtitles import import_subtitles
from socialdna.storage.schema import metadata


def analyze_video(
    application: Application,
    target: str,
    *,
    options: AnalysisOptions | None = None,
    subtitles: Path | None = None,
    copy_media: bool = False,
    resume: str | None = None,
    on_run: Callable[[str], None] | None = None,
    after_task: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    require_tool("ffmpeg")
    require_tool("ffprobe")
    options = options or AnalysisOptions()
    if subtitles is not None:
        subtitles = subtitles.expanduser().resolve()
        if not subtitles.is_file() or subtitles.suffix.lower() not in (".srt", ".vtt"):
            raise InvalidMedia("Supply an existing SRT or VTT file.")
        if subtitles.stat().st_size > 5_000_000:
            raise InvalidMedia("Subtitle file exceeds the 5 MB limit.")
    media_id, source, info, checksum = resolve_media(application, target, copy_media=copy_media)
    versions = {name: tool_version(name) for name in ("ffmpeg", "ffprobe")}
    libraries = {
        name: version(name)
        for name in (
            "numpy",
            "opencv-python-headless",
            "scenedetect-headless",
            "Pillow",
            "librosa",
            "soundfile",
            "pysubs2",
            "scipy",
        )
    }
    config = {
        **options.model_dump(),
        "subtitles_hash": hash_file(subtitles) if subtitles else None,
        "tools": versions,
        "libraries": libraries,
        "max_decode_frames": application.settings.max_decode_frames,
        "pipeline_version": "deterministic-1",
    }
    runs = metadata.tables["analysis_runs"]
    with application.database.transaction() as connection:
        if resume:
            prior = connection.execute(select(runs).where(runs.c.id == resume)).mappings().first()
            if (
                prior is None
                or prior["target_id"] != media_id
                or prior["config_hash"] != hash_config(config)
            ):
                raise InvalidMedia(
                    "Resume requires the original media, options, subtitle bytes, "
                    "decode limit and tool/library versions; otherwise start a new run."
                )
            run_id = resume
            connection.execute(
                runs.update().where(runs.c.id == run_id).values(status="running", finished_at=None)
            )
        else:
            run_id = new_id()
            connection.execute(
                runs.insert().values(
                    id=run_id,
                    target_type="media",
                    target_id=media_id,
                    depth=options.depth,
                    profile_version="deterministic-1",
                    config_json=canonical_json(config),
                    config_hash=hash_config(config),
                    status="running",
                    created_at=utc_now(),
                    started_at=utc_now(),
                )
            )
    if on_run:
        on_run(run_id)
    runner = TaskRunner(application, run_id, media_id)

    def path_for(artifact_id: str) -> Path:
        with application.database.transaction() as connection:
            row = application.artifacts.get(connection, artifact_id)
        return application.artifacts.path_for(row["relative_path"])

    def run(
        key: str,
        configuration: dict[str, Any],
        dependencies: list[str],
        callback: Callable[[TaskContext], TaskOutput],
        *,
        allow_partial: bool = False,
    ) -> None:
        runner.run(key, configuration, dependencies, callback, allow_partial=allow_partial)
        if after_task:
            after_task(key)

    with tempfile.TemporaryDirectory(
        prefix="video-", dir=application.paths.root / "cache"
    ) as directory:
        work = Path(directory)
        run(
            "prepare",
            {
                "sha256": checksum,
                "tools": versions,
                "max_decode_frames": application.settings.max_decode_frames,
            },
            [],
            lambda ctx: decode_proxy(source, work / "proxy.mkv", info, application.settings, ctx),
        )
        prepared = runner.results["prepare"]
        duration = prepared.get("video_end_ms", info.duration_ms)
        with application.database.transaction() as connection:
            connection.execute(
                metadata.tables["media_assets"]
                .update()
                .where(metadata.tables["media_assets"].c.id == media_id)
                .values(duration_ms=duration)
            )
        effective_info = info.model_copy(update={"duration_ms": duration})

        def proxy() -> Path:
            return path_for(prepared["proxy_artifact_id"])

        run(
            "scenes",
            {
                "threshold": options.scene_threshold,
                "min_scene_frames": 3,
                "window_width": 2,
                "min_content_val": 15.0,
                "libraries": {
                    name: libraries[name]
                    for name in ("scenedetect-headless", "opencv-python-headless")
                },
            },
            ["prepare"],
            lambda ctx: detect_scenes(
                proxy(),
                prepared["timestamps_ms"],
                duration,
                options.scene_threshold,
                ctx,
                info.frame_rate,
            ),
        )
        run(
            "motion",
            {"stride": 3, "opencv": libraries["opencv-python-headless"]},
            ["prepare"],
            lambda ctx: measure_motion(proxy(), prepared["timestamps_ms"], duration, ctx),
        )
        run(
            "frames",
            {
                "sample_ms": options.sample_ms,
                "max_frames": options.max_frames,
                "pillow": libraries["Pillow"],
            },
            ["prepare", "scenes", "motion"],
            lambda ctx: extract_frames(
                proxy(),
                prepared["timestamps_ms"],
                frame_candidates(
                    prepared["timestamps_ms"],
                    runner.results["scenes"]["scenes"],
                    options.sample_ms,
                    runner.results["motion"]["samples"],
                    options.max_frames,
                ),
                duration,
                work,
                ctx,
            ),
        )
        run(
            "visual",
            {
                "palette_bins": options.palette_bins,
                "numpy": libraries["numpy"],
                "opencv": libraries["opencv-python-headless"],
            },
            ["frames"],
            lambda ctx: measure_visual(
                runner.results["frames"]["frames"], path_for, options.palette_bins, ctx
            ),
        )
        run(
            "audio.extract",
            {"tools": versions, "sample_rate": 16000},
            ["prepare"],
            lambda ctx: extract_audio(
                source, work / "audio.wav", effective_info, application.settings, ctx
            ),
        )
        audio = runner.results["audio.extract"]
        run(
            "audio.features",
            {
                "silence_db": options.silence_db,
                "libraries": {
                    name: libraries[name] for name in ("numpy", "librosa", "soundfile", "scipy")
                },
            },
            ["audio.extract"],
            lambda ctx: measure_audio(
                path_for(audio["artifact_id"]) if audio.get("available") else None,
                audio.get("start_ms", 0),
                duration,
                options.silence_db,
                ctx,
            ),
        )
        run(
            "subtitles",
            {"content_hash": config["subtitles_hash"], "pysubs2": libraries["pysubs2"]},
            ["prepare"],
            lambda ctx: import_subtitles(subtitles, duration, ctx),
        )

        def unavailable(ctx: TaskContext) -> TaskOutput:
            return TaskOutput(skipped="This capability requires Milestone 3 model adapters.")

        for key in ("transcription", "ocr", "multimodal"):
            run(
                key,
                {},
                [],
                unavailable,
            )
        dependencies = list(runner.tasks)
        run(
            "timeline",
            {},
            dependencies,
            lambda ctx: TaskOutput(
                result={
                    "media_id": media_id,
                    "start_ms": 0,
                    "end_ms": duration,
                }
            ),
            allow_partial=True,
        )
    failed = [task for task in runner.tasks.values() if task["status"] == "failed"]
    with application.database.transaction() as connection:
        connection.execute(
            runs.update()
            .where(runs.c.id == run_id)
            .values(status="failed" if failed else "succeeded", finished_at=utc_now())
        )
    report_formats: tuple[Literal["json", "markdown"], ...] = ("json", "markdown")
    reports = [generate_report(application, run_id, format_) for format_ in report_formats]
    return {
        "run_id": run_id,
        "media_id": media_id,
        "status": "partial" if failed else "success",
        "tasks": runner.tasks,
        "reports": [
            {key: value for key, value in report.items() if key != "content"} for report in reports
        ],
        "limitations": reports[0]["content"]["limitations"],
    }
