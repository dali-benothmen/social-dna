import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialdna.analyzers.base import TaskContext
from socialdna.analyzers.language import compare_text_tracks
from socialdna.analyzers.ocr import box_iou, persist_ocr
from socialdna.analyzers.speech import persist_speech
from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable, ProviderFailure
from socialdna.domain.providers import OCRBox, OCRFrame, ReasoningProfile, SpeechResult, Word
from socialdna.providers.models import ModelFile, ModelManifest, ModelStore
from socialdna.providers.worker import deny_network


def test_nullable_words_and_audio_offsets() -> None:
    result = SpeechResult.model_validate(
        {
            "language": "en",
            "segments": [
                {
                    "start": 0.1,
                    "end": 0.8,
                    "text": "Hello world",
                    "words": [
                        {"text": "Hello", "start": 0.1, "end": 0.4, "confidence": 0.9},
                        {"text": "world"},
                    ],
                }
            ],
        }
    )
    output = persist_speech(result, 500, 2000, TaskContext("task", "media", "provenance"))
    assert output.records["text_tracks"][0]["track_type"] == "asr"
    assert output.records["text_segments"][0]["start_ms"] == 600
    assert output.records["text_words"][0]["end_ms"] == 900
    assert output.records["text_words"][1]["start_ms"] is None
    assert output.records["text_words"][1]["end_ms"] is None
    with pytest.raises(ValidationError):
        Word(text="invented", start=0.2)
    with pytest.raises(ValidationError):
        SpeechResult.model_validate(
            {"language": "en", "segments": [{"start": 1, "end": 0.5, "text": "bad"}]}
        )


def test_ocr_normalized_boxes_and_temporal_persistence() -> None:
    box = OCRBox(
        text="Hello", confidence=0.9, points=[(0.1, 0.2), (0.9, 0.2), (0.9, 0.5), (0.1, 0.5)]
    )
    assert box_iou(box, box) == pytest.approx(1)
    frames = [
        {"id": "first", "timestamp_ms": 200, "end_ms": 250, "artifact_id": "image1"},
        {"id": "second", "timestamp_ms": 600, "end_ms": 650, "artifact_id": "image2"},
    ]
    result = persist_ocr(
        [OCRFrame(frame_id=frame["id"], boxes=[box]) for frame in frames],
        frames,
        TaskContext("task", "media", "provenance"),
    )
    assert len(result.records["text_segments"]) == 1
    assert len(result.records["ocr_boxes"]) == 2
    assert result.records["text_segments"][0]["end_ms"] == 650
    assert len(result.records["evidence_items"]) == 3
    with pytest.raises(ValidationError):
        OCRBox(text="bad", confidence=2, points=box.points)
    with pytest.raises(ValidationError):
        OCRBox(text="bad", confidence=0.5, points=[(2, 1)] * 4)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/v1/chat/completions",
        "http://localhost:8000",
        "http://127.0.0.1:8000?key=secret",
    ],
)
def test_local_profiles_cannot_disguise_remote_endpoints(url: str) -> None:
    with pytest.raises(ValidationError):
        ReasoningProfile(
            endpoint=url, provider="test", model="model", revision="1", execution="local"
        )


def test_model_manifest_import_offline_and_corruption(settings: Settings, tmp_path: Path) -> None:
    content = b'{"fake-test-weights":true}'
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.json").write_bytes(content)
    manifest = ModelManifest.model_validate(
        {
            "name": "test-model",
            "capability": "transcription",
            "license": "test-only",
            "identity": {
                "provider": "test",
                "model": "test-model",
                "revision": "1",
                "execution": "local",
            },
            "files": [
                {
                    "name": "config.json",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "max_bytes": 1000,
                }
            ],
        }
    )
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(manifest.model_dump_json())
    settings.offline = True
    store = ModelStore(settings)
    with pytest.raises(DependencyUnavailable):
        store.prepare("asr-tiny")
    result = store.prepare("test-model", manifest_path=manifest_file, source_dir=source)
    assert result["state"] == "ready"
    assert store.prepare("test-model")["downloaded"] is False
    (store.verify(manifest) / "config.json").write_bytes(b"corrupt")
    with pytest.raises(DependencyUnavailable, match="corrupt"):
        store.verify(manifest)
    with pytest.raises(ProviderFailure, match="not overwritten"):
        store.prepare("test-model", source_dir=source)
    assert not list(store.directory(manifest).glob(".download-*"))


@pytest.mark.parametrize(
    "name",
    ["../model.bin", "/tmp/model.bin", "model.py", "dir/../../model.onnx", "dir\\model.onnx"],
)
def test_unsafe_model_files_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        ModelFile(name=name, sha256="a" * 64, max_bytes=100)


def test_text_comparison_is_not_an_accuracy_claim() -> None:
    assert compare_text_tracks("Hello world", "hello WORLD!") == 1
    assert 0 < compare_text_tracks("Hello world", "Hello everyone") < 1
    assert compare_text_tracks("Hello world", "nothing matches") == 0
    with pytest.raises(RuntimeError, match="Network"):
        deny_network()


def test_model_size_and_checksum_failures_leave_no_staged_files(
    settings: Settings, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.json").write_bytes(b"too many bytes")
    manifest = {
        "name": "bounded-model",
        "capability": "ocr",
        "license": "test-only",
        "identity": {"provider": "test", "model": "test", "revision": "1", "execution": "local"},
        "files": [{"name": "config.json", "sha256": "a" * 64, "max_bytes": 2}],
    }
    path = tmp_path / "manifest.json"
    from socialdna.core.hashing import canonical_json

    path.write_text(canonical_json(manifest))
    store = ModelStore(settings)
    with pytest.raises(ProviderFailure, match="size bound"):
        store.prepare("bounded-model", manifest_path=path, source_dir=source)
    assert not list((settings.data_dir / "models").rglob(".download-*"))
    assert not (settings.data_dir / "models/catalog/bounded-model.json").exists()


def test_external_worker_missing_runtime_is_dependency_unavailable(
    settings: Settings, tmp_path: Path
) -> None:
    from socialdna.core.exceptions import MediaProcessingError
    from socialdna.providers.registry import runtime_versions

    settings.provider_python = tmp_path / "does-not-exist"
    with pytest.raises(MediaProcessingError):
        runtime_versions(settings)
    assert all(not model["runtime_ready"] for model in ModelStore(settings).status())
