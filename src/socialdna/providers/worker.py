"""Bounded subprocess entry point; optional native runtimes never enter the engine process."""

import contextlib
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any


def deny_network(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("Network access is disabled in local inference workers.")


def word_result(
    text: str, start: float | None, end: float | None, confidence: float | None
) -> dict[str, Any]:
    if start is None or end is None or end <= start:
        start = end = None
    return {"text": text, "start": start, "end": end, "confidence": confidence}


def infer(request: dict[str, Any]) -> dict[str, Any]:
    capability = request["capability"]
    root = Path(request["model_dir"])
    options = request["options"]
    if capability == "transcription":
        from faster_whisper import WhisperModel

        model = WhisperModel(
            str(root),
            device=options["device"],
            compute_type=options["compute_type"],
            cpu_threads=options["threads"],
            local_files_only=True,
        )
        segments, info = model.transcribe(
            request["audio_path"],
            language=options.get("language"),
            vad_filter=True,
            word_timestamps=options["word_timestamps"],
            beam_size=5,
            condition_on_previous_text=False,
        )
        return {
            "language": info.language,
            "language_probability": info.language_probability,
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text.strip(),
                    "words": [
                        word_result(w.word, w.start, w.end, w.probability)
                        for w in (s.words or [])
                        if w.word.strip()
                    ],
                }
                for s in segments
                if s.text.strip() and s.end > s.start
            ],
        }
    if capability == "ocr":
        import numpy as np
        from PIL import Image
        from rapidocr import LangRec, OCRVersion, RapidOCR

        engine = RapidOCR(
            params={
                "Global.use_cls": False,
                "Global.log_level": "error",
                "Det.model_path": str(root / "det.onnx"),
                "Rec.model_path": str(root / "rec.onnx"),
                "Rec.lang_type": LangRec.EN,
                "Det.ocr_version": OCRVersion.PPOCRV4,
                "Rec.ocr_version": OCRVersion.PPOCRV4,
                "EngineConfig.onnxruntime.intra_op_num_threads": options["threads"],
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
        frames = []
        for frame in request["frames"]:
            with Image.open(frame["path"]) as source:
                rgb = np.asarray(source.convert("RGB"))
            result: Any = engine(rgb[:, :, ::-1])  # ndarray inputs use BGR
            boxes = []
            if result.txts is not None:
                for points, text, score in zip(
                    result.boxes, result.txts, result.scores, strict=True
                ):
                    if text.strip():
                        boxes.append(
                            {
                                "text": text,
                                "confidence": float(score),
                                "points": [
                                    [
                                        min(1, max(0, float(x) / rgb.shape[1])),
                                        min(1, max(0, float(y) / rgb.shape[0])),
                                    ]
                                    for x, y in points
                                ],
                            }
                        )
            frames.append({"frame_id": frame["id"], "boxes": boxes})
        return {"frames": frames}
    if capability == "alignment":
        import nltk
        import whisperx

        nltk.data.path.insert(0, str(root / "nltk_data"))
        nltk.download = deny_network
        model, metadata = whisperx.load_align_model(
            language_code=request["language"],
            device=options["device"],
            model_name=str(root),
            model_dir=str(root),
            model_cache_only=True,
        )
        result = whisperx.align(
            request["speech"],
            model,
            metadata,
            request["audio_path"],
            options["device"],
            return_char_alignments=False,
        )
        return {
            "language": request["language"],
            "segments": [
                {
                    "start": s["start"],
                    "end": s["end"],
                    "text": s["text"],
                    "words": [
                        word_result(w["word"], w.get("start"), w.get("end"), w.get("score"))
                        for w in s.get("words", [])
                        if w.get("word", "").strip()
                    ],
                }
                for s in result["segments"]
                if s["text"].strip()
            ],
        }
    if capability == "pose":
        import mediapipe as mp
        import numpy as np
        from PIL import Image

        config = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(root / "model.task")),
            num_poses=2,
        )
        frames = []
        with mp.tasks.vision.PoseLandmarker.create_from_options(config) as model:
            for frame in request["frames"]:
                with Image.open(frame["path"]) as image:
                    rgb = np.asarray(image.convert("RGB"))
                result = model.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
                frames.append(
                    {
                        "frame_id": frame["id"],
                        "poses": [
                            [
                                {
                                    "x": p.x,
                                    "y": p.y,
                                    "z": p.z,
                                    "visibility": p.visibility,
                                    "presence": p.presence,
                                }
                                for p in pose
                            ]
                            for pose in result.pose_landmarks
                        ],
                    }
                )
        return {"frames": frames}
    if capability == "audio_classifier":
        import mediapipe as mp
        import soundfile as sf

        config = mp.tasks.audio.AudioClassifierOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(root / "model.tflite")),
            max_results=5,
        )
        windows = []
        with mp.tasks.audio.AudioClassifier.create_from_options(config) as model:
            with sf.SoundFile(request["audio_path"]) as audio:
                for index, samples in enumerate(
                    audio.blocks(blocksize=audio.samplerate, dtype="float32")
                ):
                    data = mp.tasks.components.containers.AudioData.create_from_array(
                        samples, sample_rate=audio.samplerate
                    )
                    results = model.classify(data)
                    windows.append(
                        {
                            "start_ms": index * 1000,
                            "end_ms": index * 1000 + round(len(samples) * 1000 / audio.samplerate),
                            "categories": [
                                {"label": c.category_name or str(c.index), "score": c.score}
                                for r in results
                                for head in r.classifications
                                for c in head.categories
                            ],
                        }
                    )
        return {"windows": windows}
    raise ValueError("Unknown worker capability.")


def main() -> None:
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[key] = "1"
    socket.create_connection = deny_network
    for attribute in ("connect", "connect_ex"):
        setattr(socket.socket, attribute, deny_network)
    request_path, response_path = map(Path, sys.argv[1:])
    os.environ["MPLCONFIGDIR"] = str(request_path.parent / "matplotlib-cache")
    os.environ["NUMBA_CACHE_DIR"] = str(request_path.parent / "numba-cache")
    if request_path.stat().st_size > 8_000_000:
        raise ValueError("Inference request exceeds the size limit.")
    request = json.loads(request_path.read_bytes())
    with contextlib.redirect_stdout(sys.stderr):
        result = infer(request)
    data = json.dumps(result, allow_nan=False).encode()
    if len(data) > 8_000_000:
        raise ValueError("Inference response exceeds the size limit.")
    response_path.write_bytes(data)


if __name__ == "__main__":
    main()
