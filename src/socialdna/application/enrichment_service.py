import base64
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.analyzers.language import compare_text_tracks, persist_interpretations
from socialdna.analyzers.ocr import persist_ocr
from socialdna.analyzers.speech import persist_speech, speech_request
from socialdna.application.bootstrap import Application
from socialdna.application.task_runner import TaskRunner
from socialdna.core.exceptions import ConfigurationError, DependencyUnavailable, ProviderFailure
from socialdna.core.hashing import hash_config
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.providers import AudioWindow, PoseFrame
from socialdna.providers.models import PACKAGES
from socialdna.providers.reasoning import PROMPT_HASH, CompatibleReasoningProvider, authorize
from socialdna.providers.registry import LocalProvider, ProviderRegistry
from socialdna.storage.schema import metadata


@dataclass
class Selection:
    provider: LocalProvider | None
    configuration: dict[str, Any]
    reason: str | None
    required: bool


def select_providers(application: Application, options: AnalysisOptions) -> dict[str, Selection]:
    settings = application.settings
    if options.align and options.transcribe is False and not options.no_ai:
        raise ConfigurationError(
            "Alignment requires ASR; remove --no-transcribe or disable alignment."
        )
    registry = ProviderRegistry(settings) if not options.no_ai else None
    selections = {}
    for key, capability, name, requested in (
        (
            "transcription",
            "transcription",
            settings.asr_model,
            True if options.align and options.transcribe is None else options.transcribe,
        ),
        ("ocr", "ocr", settings.ocr_model, options.ocr),
        ("alignment", "alignment", settings.alignment_model, options.align),
        ("pose", "pose", settings.pose_model, options.pose),
        (
            "audio.classify",
            "audio_classifier",
            settings.audio_classifier_model,
            options.classify_audio,
        ),
    ):
        enabled = not options.no_ai and (
            requested is True or (requested is None and options.depth != "quick")
        )
        configuration: dict[str, Any] = {"enabled": enabled, "model": name}
        provider, reason = None, None
        if enabled and registry is not None:
            try:
                if name is None:
                    raise DependencyUnavailable("No model was configured for this capability.")
                provider = registry.resolve(name, capability)
                configuration["manifest_hash"] = hash_config(provider.manifest.model_dump())
                configuration["identity"] = provider.identity.model_dump()
                configuration["runtime"] = {p: provider.versions[p] for p in PACKAGES[capability]}
            except DependencyUnavailable as exc:
                reason = str(exc)
        else:
            reason = "Disabled by --no-ai or the selected analysis profile."
        if reason:
            configuration["unavailable"] = reason
        selections[key] = Selection(provider, configuration, reason, requested is True and enabled)
    return selections


def input_evidence(application: Application, subject_ids: list[str]) -> list[dict[str, Any]]:
    table = metadata.tables["evidence_items"]
    with application.database.transaction() as connection:
        return [
            dict(row)
            for row in connection.execute(
                select(table).where(table.c.subject_id.in_(subject_ids)).order_by(table.c.id)
            ).mappings()
        ]


def choose_frames(frames: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(frames) <= limit:
        return frames
    indices = (
        [round(index * (len(frames) - 1) / (limit - 1)) for index in range(limit)]
        if limit > 1
        else [0]
    )
    return [frames[index] for index in indices]


def run_enrichment(
    application: Application,
    runner: TaskRunner,
    options: AnalysisOptions,
    selections: dict[str, Selection],
    duration: int,
    *,
    after_task: Callable[[str], None] | None = None,
) -> None:
    settings = application.settings

    def artifact_path(identifier: str) -> Path:
        with application.database.transaction() as connection:
            row = application.artifacts.get(connection, identifier)
        return application.artifacts.path_for(row["relative_path"])

    frames = choose_frames(
        runner.results.get("frames", {}).get("frames", []),
        min(
            settings.max_enrichment_frames, {"quick": 4, "standard": 12, "deep": 24}[options.depth]
        ),
    )
    frame_evidence = input_evidence(application, [frame["id"] for frame in frames])
    audio = runner.results.get("audio.extract", {})
    with application.database.transaction() as connection:
        segments = metadata.tables["audio_segments"]
        audio_ids: list[str] = list(
            connection.scalars(
                select(segments.c.id).where(
                    segments.c.task_id == runner.tasks["audio.extract"]["producer_id"],
                    segments.c.segment_type == "audio_track",
                )
            )
        )
    audio_evidence = input_evidence(application, audio_ids)
    frame_request = [
        {"id": frame["id"], "path": str(artifact_path(frame["artifact_id"]))} for frame in frames
    ]

    def execute(
        key: str,
        dependencies: list[str],
        callback: Callable[[TaskContext, LocalProvider], TaskOutput],
        extra: dict[str, Any],
    ) -> None:
        selection = selections[key]

        def compute(context: TaskContext) -> TaskOutput:
            if key in {"transcription", "alignment", "audio.classify"} and not audio.get(
                "available"
            ):
                return TaskOutput(skipped="No audio stream is available for this capability.")
            if selection.provider is None:
                return TaskOutput(
                    skipped=selection.reason or "Model unavailable.",
                    result={"unavailable": selection.required},
                )
            context.output.provider = selection.provider.identity
            return callback(context, selection.provider)

        runner.run(key, {**selection.configuration, **extra}, dependencies, compute)
        if after_task:
            after_task(key)

    def transcribe(context: TaskContext, provider: LocalProvider) -> TaskOutput:
        if not audio.get("available"):
            return TaskOutput(skipped="No audio stream is available for transcription.")
        request = speech_request(str(artifact_path(audio["artifact_id"])), settings, options.depth)
        context.output.input_evidence_ids = [item["id"] for item in audio_evidence]
        result = provider.transcribe(request)
        return persist_speech(result, audio["start_ms"], audio["end_ms"], context)

    execute(
        "transcription",
        ["audio.extract"],
        transcribe,
        {
            "language": settings.asr_language,
            "device": settings.asr_device,
            "compute_type": settings.asr_compute_type,
            "word_timestamps": options.depth == "deep",
            "threads": settings.inference_threads,
            "vad": True,
        },
    )

    def align(context: TaskContext, provider: LocalProvider) -> TaskOutput:
        speech = runner.results["transcription"]
        if not audio.get("available") or not speech.get("segments"):
            return TaskOutput(skipped="No ASR speech segments are available for alignment.")
        if provider.manifest.languages and speech["language"] not in provider.manifest.languages:
            raise DependencyUnavailable(
                "Alignment model does not declare the detected speech language."
            )
        request = speech_request(str(artifact_path(audio["artifact_id"])), settings, options.depth)
        request.update(
            language=speech["language"],
            speech=[
                {
                    "start": (s["start_ms"] - audio["start_ms"]) / 1000,
                    "end": (s["end_ms"] - audio["start_ms"]) / 1000,
                    "text": s["text"],
                }
                for s in speech["segments"]
            ],
        )
        context.output.input_evidence_ids = [item["id"] for item in audio_evidence] + [
            s["evidence_id"] for s in speech["segments"]
        ]
        return persist_speech(
            provider.transcribe(request), audio["start_ms"], audio["end_ms"], context, aligned=True
        )

    execute("alignment", ["audio.extract", "transcription"], align, {"device": settings.asr_device})

    def ocr(context: TaskContext, provider: LocalProvider) -> TaskOutput:
        context.output.input_evidence_ids = [item["id"] for item in frame_evidence]
        # Infer identical bytes once, then map the result to each observed timestamp.
        unique = {
            frame["artifact_id"]: request
            for frame, request in zip(frames, frame_request, strict=True)
        }
        results = provider.read_text(
            {"frames": list(unique.values()), "options": {"threads": settings.inference_threads}}
        )
        by_frame = {row.frame_id: row for row in results}
        if len(results) != len(unique) or set(by_frame) != {item["id"] for item in unique.values()}:
            raise ProviderFailure("OCR output must contain exactly the requested unique frames.")
        by_artifact = {artifact: by_frame[request["id"]] for artifact, request in unique.items()}
        return persist_ocr(
            [
                by_artifact[frame["artifact_id"]].model_copy(update={"frame_id": frame["id"]})
                for frame in frames
            ],
            frames,
            context,
        )

    execute(
        "ocr", ["frames"], ocr, {"max_frames": len(frames), "threads": settings.inference_threads}
    )

    def pose(context: TaskContext, provider: LocalProvider) -> TaskOutput:
        context.output.input_evidence_ids = [item["id"] for item in frame_evidence]
        results = TypeAdapter(list[PoseFrame]).validate_python(
            provider.invoke(
                {"frames": frame_request, "options": {"threads": settings.inference_threads}}
            )["frames"]
        )
        by_id = {frame["id"]: frame for frame in frames}
        if len(results) != len(frames) or {r.frame_id for r in results} != set(by_id):
            raise ProviderFailure("Pose response references duplicate or unknown frames.")
        for result in results:
            frame = by_id[result.frame_id]
            context.observe(
                "visual.pose_landmarks",
                result.model_dump(),
                frame["timestamp_ms"],
                frame["end_ms"],
                modality="visual",
                unit="normalized-image-geometry",
                description="33 model-estimated body landmarks per pose; "
                "no identity or emotion classification.",
            )
        context.output.result = {"measured_frames": len(results)}
        return context.output

    execute("pose", ["frames"], pose, {"max_frames": len(frames)})

    def classify(context: TaskContext, provider: LocalProvider) -> TaskOutput:
        if not audio.get("available"):
            return TaskOutput(skipped="No audio is available for classification.")
        context.output.input_evidence_ids = [item["id"] for item in audio_evidence]
        results = TypeAdapter(list[AudioWindow]).validate_python(
            provider.classify_audio(
                {"audio_path": str(artifact_path(audio["artifact_id"])), "options": {}}
            )
        )
        for result in results:
            begin, end = (
                audio["start_ms"] + result.start_ms,
                min(audio["end_ms"], audio["start_ms"] + result.end_ms),
            )
            if begin < audio["start_ms"] or end <= begin:
                raise ProviderFailure("Audio classifier window is outside its input audio.")
            context.observe(
                "audio.event_candidates",
                {
                    "categories": [c.model_dump() for c in result.categories],
                    "claim_level": "hypothesis",
                    "confidence_method": "uncalibrated model scores",
                },
                begin,
                end,
                modality="audio",
                unit="model-candidates",
                description="Uncertain audio event candidates, not verified sound/music labels.",
            )
        context.output.result = {"classified_windows": len(results)}
        return context.output

    execute("audio.classify", ["audio.extract"], classify, {})

    def compare(context: TaskContext) -> TaskOutput:
        speech = runner.results["transcription"].get("segments", [])
        if not speech or not runner.results["subtitles"].get("track_id"):
            return TaskOutput(
                skipped="ASR and supplied subtitles are both required for text comparison."
            )
        text = metadata.tables["text_segments"]
        with application.database.transaction() as connection:
            supplied = list(
                connection.execute(
                    select(text)
                    .where(text.c.track_id == runner.results["subtitles"]["track_id"])
                    .order_by(text.c.start_ms)
                ).mappings()
            )
        context.output.input_evidence_ids = [
            item["id"]
            for item in input_evidence(
                application, [s["id"] for s in speech] + [s["id"] for s in supplied]
            )
        ]
        context.observe(
            "text.track_token_agreement",
            compare_text_tracks(
                " ".join(s["text"] for s in speech), " ".join(s["text"] for s in supplied)
            ),
            0,
            duration,
            modality="linguistic",
            unit="ratio",
            description="Symmetric token agreement, not WER or transcription accuracy.",
        )
        return context.output

    runner.run("language.compare", {}, ["transcription", "subtitles"], compare)
    if after_task:
        after_task("language.compare")

    profile = settings.reasoning_profile

    def reason(context: TaskContext) -> TaskOutput:
        if options.no_ai or not options.reason or profile is None:
            return TaskOutput(
                skipped="Reasoning requires --reason and an explicit enabled provider profile.",
                result={"unavailable": options.reason and not options.no_ai},
            )
        # Only bounded derived evidence, never original video/audio, reaches this adapter.
        types = {"text"} | ({"image"} if "image" in profile.modalities and frames else set())
        authorize(application, profile, types)
        segments = metadata.tables["text_segments"]
        selected_text_ids = [s["id"] for s in runner.results["transcription"].get("segments", [])]
        for key in ("ocr", "subtitles"):
            task_id = runner.tasks[key]["producer_id"]
            tracks = metadata.tables["text_tracks"]
            with application.database.transaction() as connection:
                selected_text_ids.extend(
                    connection.scalars(
                        select(segments.c.id)
                        .join(tracks)
                        .where(tracks.c.task_id == task_id)
                        .order_by(segments.c.start_ms)
                        .limit(50)
                    )
                )
        source = input_evidence(application, selected_text_ids)
        if "image" in types:
            source = frame_evidence + source
        if not source:
            return TaskOutput(skipped="No eligible evidence exists for reasoning.")
        bundle = [
            {
                "id": row["id"],
                "start_ms": row["start_ms"],
                "end_ms": row["end_ms"],
                "text": (row["excerpt"] or "")[:2000],
                "subject_type": row["subject_type"],
            }
            for row in source[:60]
        ]
        image_indices = {frame["id"]: index for index, frame in enumerate(frames)}
        for item, row in zip(bundle, source[:60], strict=True):
            if row["subject_type"] == "frame":
                item["image_index"] = image_indices[row["subject_id"]]
        images = []
        if "image" in types:
            for frame in frames:
                content = artifact_path(frame["artifact_id"]).read_bytes()
                images.append("data:image/jpeg;base64," + base64.b64encode(content).decode())
        context.output.input_evidence_ids = [row["id"] for row in bundle]
        provider = CompatibleReasoningProvider(application, context.task_id, profile)
        context.output.provider, context.output.prompt_hash = (
            provider.identity,
            provider.prompt_hash,
        )
        result = persist_interpretations(
            provider.reason({"evidence": bundle, "images": images}), bundle, context
        )
        result.result["provider_call_ids"] = provider.call_ids
        return result

    runner.run(
        "multimodal",
        {
            "requested": options.reason,
            "prompt_hash": PROMPT_HASH,
            "no_ai": options.no_ai,
            "profile": profile.model_dump() if profile else None,
            "max_input_bytes": settings.max_input_bytes,
            "max_input_tokens": settings.max_input_tokens,
            "max_output_tokens": settings.max_output_tokens,
            "remote_consent": settings.remote_media_consent,
            "offline": settings.offline,
        },
        ["frames", "transcription", "ocr", "subtitles"],
        reason,
    )
    if after_task:
        after_task("multimodal")
