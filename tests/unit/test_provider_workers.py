import sys
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PIL import Image

from socialdna.domain.providers import OCRFrame, SpeechResult
from socialdna.providers.worker import infer, word_result


def test_speech_sdk_contract_uses_only_local_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class Model:
        def __init__(self, path: str, **kwargs: Any) -> None:
            calls.update(path=path, constructor=kwargs)

        def transcribe(self, path: str, **kwargs: Any) -> Any:
            calls.update(audio=path, parameters=kwargs)
            word = SimpleNamespace(word="Hello", start=0.1, end=0.2, probability=0.9)
            segment = SimpleNamespace(start=0.1, end=0.5, text="Hello", words=[word])
            return iter([segment]), SimpleNamespace(language="en", language_probability=0.9)

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    result = infer(
        {
            "capability": "transcription",
            "model_dir": "/reviewed/model",
            "audio_path": "/local/audio.wav",
            "options": {
                "device": "cpu",
                "compute_type": "int8",
                "threads": 2,
                "word_timestamps": True,
            },
        }
    )
    assert SpeechResult.model_validate(result).segments[0].words[0].text == "Hello"
    assert calls["constructor"]["local_files_only"] is True
    assert calls["parameters"]["vad_filter"] is True
    assert calls["parameters"]["word_timestamps"] is True


def test_whisperx_contract_never_downloads_models(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}
    nltk = SimpleNamespace(data=SimpleNamespace(path=[]), download=None)
    monkeypatch.setitem(sys.modules, "nltk", nltk)

    def load(**kwargs: Any) -> Any:
        calls.update(kwargs)
        return "model", {"language": "en"}

    def align(*args: Any, **kwargs: Any) -> Any:
        return {
            "segments": [
                {
                    "start": 0,
                    "end": 1,
                    "text": "Hello",
                    "words": [
                        {"word": "Hello", "start": 0.1},
                    ],
                }
            ]
        }

    monkeypatch.setitem(
        sys.modules, "whisperx", SimpleNamespace(load_align_model=load, align=align)
    )
    result = SpeechResult.model_validate(
        infer(
            {
                "capability": "alignment",
                "model_dir": "/reviewed/model",
                "language": "en",
                "speech": [{"start": 0, "end": 1, "text": "Hello"}],
                "audio_path": "/local/audio.wav",
                "options": {"device": "cpu"},
            }
        )
    )
    assert calls["model_cache_only"] is True and calls["model_name"] == "/reviewed/model"
    assert result.segments[0].words[0].start is None
    assert result.segments[0].words[0].end is None
    with pytest.raises(RuntimeError, match="Network"):
        nltk.download("punkt_tab")


def test_ocr_sdk_enum_paths_and_normalized_quads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    image_path = tmp_path / "own.png"
    Image.new("RGB", (100, 50), "white").save(image_path)
    calls = {}

    class Version(Enum):
        PPOCRV4 = "PP-OCRv4"

    class Language(Enum):
        EN = "en"

    class Model:
        def __init__(self, params: dict[str, Any]) -> None:
            calls.update(params)

        def __call__(self, image: Any) -> Any:
            return SimpleNamespace(
                txts=["Text"],
                scores=[0.9],
                boxes=np.asarray([[[10, 10], [90, 10], [90, 40], [10, 40]]]),
            )

    monkeypatch.setitem(
        sys.modules,
        "rapidocr",
        SimpleNamespace(RapidOCR=Model, OCRVersion=Version, LangRec=Language),
    )
    result = infer(
        {
            "capability": "ocr",
            "model_dir": "/reviewed/model",
            "frames": [{"id": "frame", "path": str(image_path)}],
            "options": {"threads": 2},
        }
    )
    frame = OCRFrame.model_validate(result["frames"][0])
    assert frame.boxes[0].points[0] == (0.1, 0.2)
    assert calls["Global.use_cls"] is False
    assert calls["Rec.ocr_version"] == Version.PPOCRV4
    assert calls["Rec.model_path"] == "/reviewed/model/rec.onnx"


def test_zero_length_word_is_retained_without_fabricated_timing() -> None:
    word = word_result("token", 0.2, 0.2, 0.5)
    assert word["text"] == "token" and word["start"] is None and word["end"] is None
