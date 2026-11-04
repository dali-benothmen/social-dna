import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable, MediaProcessingError, ProviderFailure
from socialdna.domain.providers import OCRFrame, ProviderIdentity, SpeechResult
from socialdna.media.ffmpeg import run_process
from socialdna.providers.models import PACKAGES, ModelManifest, ModelStore, package_versions


def runtime_versions(settings: Settings, python: Path | None = None) -> dict[str, str | None]:
    python = python or settings.provider_python
    if python is None:
        return package_versions()
    # Only query installed metadata; do not import heavy libraries in doctor/analysis preflight.
    names = sorted({name for group in PACKAGES.values() for name in group})
    script = (
        "import importlib.metadata as m, json; result={}; "
        f"names={names!r}\n"
        "for n in names:\n"
        " try: result[n]=m.version(n)\n"
        " except m.PackageNotFoundError: result[n]=None\n"
        "print(json.dumps(result))"
    )
    output = run_process([str(python), "-c", script], timeout=15)
    value: dict[str, str | None] = json.loads(output.stdout)
    return value


class LocalProvider:
    def __init__(self, settings: Settings, manifest: ModelManifest, root: Path) -> None:
        self.settings, self.manifest, self.root = settings, manifest, root
        self.identity: ProviderIdentity = manifest.identity
        self.python = settings.provider_pythons.get(manifest.capability, settings.provider_python)
        self.versions = runtime_versions(settings, self.python)

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        request = {**request, "capability": self.manifest.capability, "model_dir": str(self.root)}
        with tempfile.TemporaryDirectory(
            prefix="inference-", dir=self.settings.data_dir / "cache"
        ) as work:
            source, destination = Path(work) / "request.json", Path(work) / "response.json"
            source.write_text(json.dumps(request, allow_nan=False), encoding="utf-8")
            try:
                run_process(
                    [
                        str(self.python or sys.executable),
                        str(Path(__file__).with_name("worker.py")),
                        str(source),
                        str(destination),
                    ],
                    timeout=self.settings.inference_timeout_seconds,
                )
            except Exception as exc:
                raise ProviderFailure(
                    f"Local {self.manifest.capability} worker failed. Check the optional "
                    "runtime, model compatibility, device configuration and inference timeout."
                ) from exc
            if not destination.is_file() or destination.stat().st_size > 8_000_000:
                raise ProviderFailure("Local worker produced no bounded response.")
            result: dict[str, Any] = json.loads(destination.read_bytes())
            return result

    def transcribe(self, request: dict[str, Any]) -> SpeechResult:
        return SpeechResult.model_validate(self.invoke(request))

    def read_text(self, request: dict[str, Any]) -> list[OCRFrame]:
        return TypeAdapter(list[OCRFrame]).validate_python(self.invoke(request)["frames"])

    def classify_audio(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self.invoke(request)["windows"]
        return result


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.models = ModelStore(settings)
        self.versions = package_versions()

    def resolve(self, name: str, capability: str) -> LocalProvider:
        model = self.models.get(name)
        if model.capability != capability:
            raise DependencyUnavailable(f"Model {name} does not implement {capability}.")
        backend = {
            "transcription": "faster-whisper",
            "ocr": "rapidocr",
            "alignment": "whisperx",
            "pose": "mediapipe",
            "audio_classifier": "mediapipe",
        }[capability]
        if model.identity.provider != backend:
            raise DependencyUnavailable(
                f"Model {name} must declare the {backend} backend identity."
            )
        required = {
            "transcription": {"config.json", "model.bin", "tokenizer.json"},
            "ocr": {"det.onnx", "rec.onnx"},
            "pose": {"model.task"},
            "audio_classifier": {"model.tflite"},
            "alignment": {"config.json", "model.safetensors"},
        }[capability]
        if not required <= {asset.name for asset in model.files}:
            raise DependencyUnavailable(f"Manifest for {name} omits required {capability} assets.")
        root = self.models.verify(model)
        try:
            provider = LocalProvider(self.settings, model, root)
        except (MediaProcessingError, OSError) as exc:
            raise DependencyUnavailable(
                "Optional worker interpreter is unavailable or invalid."
            ) from exc
        missing = [name for name in PACKAGES[capability] if not provider.versions.get(name)]
        if missing:
            raise DependencyUnavailable(
                "Optional inference dependencies are missing: " + ", ".join(missing)
            )
        if capability == "transcription" and not (
            {"vocabulary.txt", "vocabulary.json"} & {f.name for f in model.files}
        ):
            raise DependencyUnavailable("ASR manifest requires vocabulary.txt or vocabulary.json.")
        return provider
