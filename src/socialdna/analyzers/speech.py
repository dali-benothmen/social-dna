from typing import Any

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.core.exceptions import ProviderFailure
from socialdna.domain.providers import SpeechResult


def persist_speech(
    result: SpeechResult,
    start_ms: int,
    end_ms: int,
    context: TaskContext,
    *,
    aligned: bool = False,
) -> TaskOutput:
    track_id = context.record(
        "text_tracks",
        {
            "track_type": "asr_aligned" if aligned else "asr",
            "language": result.language,
            "source": "WhisperX" if aligned else "faster-whisper",
            "is_primary": False,
        },
    )
    segments = []
    previous_start = -1
    for source in result.segments:
        begin, end = start_ms + round(source.start * 1000), start_ms + round(source.end * 1000)
        if begin < previous_start or begin >= end_ms + 50 or end > end_ms + 1000:
            raise ProviderFailure("Speech provider timestamps do not fit the audio evidence.")
        previous_start = begin
        begin, end = max(start_ms, begin), min(end_ms, end)
        if end <= begin:
            continue
        segment_id = context.record(
            "text_segments",
            {
                "track_id": track_id,
                "start_ms": begin,
                "end_ms": end,
                "text": source.text,
                "confidence": None,
            },
        )
        evidence_id = context.evidence("text_segment", segment_id, begin, end, excerpt=source.text)
        segments.append(
            {
                "id": segment_id,
                "start_ms": begin,
                "end_ms": end,
                "text": source.text,
                "evidence_id": evidence_id,
            }
        )
        for ordinal, word in enumerate(source.words):
            word_start = start_ms + round(word.start * 1000) if word.start is not None else None
            word_end = start_ms + round(word.end * 1000) if word.end is not None else None
            if word_start is not None and word_end is not None:
                word_start, word_end = max(begin, word_start), min(end, word_end)
                if word_end <= word_start:
                    # Keep text but do not invent a duration for an untimed/zero-length token.
                    word_start = word_end = None
            context.record(
                "text_words",
                {
                    "segment_id": segment_id,
                    "ordinal": ordinal,
                    "start_ms": word_start,
                    "end_ms": word_end,
                    "text": word.text,
                    "confidence": word.confidence,
                },
            )
    context.output.result = {
        "track_id": track_id,
        "language": result.language,
        "language_probability": result.language_probability,
        "segments": segments,
        "limitations": ["ASR/word timestamps are model estimates, not ground truth."],
    }
    return context.output


def speech_request(audio_path: str, settings: Any, depth: str) -> dict[str, Any]:
    return {
        "audio_path": audio_path,
        "options": {
            "language": settings.asr_language,
            "device": settings.asr_device,
            "compute_type": settings.asr_compute_type,
            "threads": settings.inference_threads,
            "word_timestamps": depth == "deep",
        },
    }
