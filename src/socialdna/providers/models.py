import hashlib
import importlib.metadata
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
from pydantic import Field, model_validator

from socialdna.config.settings import Settings
from socialdna.core.exceptions import (
    ConfigurationError,
    DependencyUnavailable,
    MediaProcessingError,
    ProviderFailure,
)
from socialdna.core.hashing import canonical_json, hash_config, hash_file
from socialdna.domain.providers import Capability, ProviderIdentity, StrictModel


class ModelFile(StrictModel):
    name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_bytes: int = Field(gt=0, le=10_000_000_000)
    url: str | None = None

    @model_validator(mode="after")
    def safe(self) -> "ModelFile":
        path = PurePosixPath(self.name)
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or "\\" in self.name
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", self.name)
        ):
            raise ValueError("Model file name must be a safe relative path.")
        if path.suffix not in {
            ".json",
            ".txt",
            ".bin",
            ".onnx",
            ".task",
            ".tflite",
            ".safetensors",
            ".tab",
        }:
            raise ValueError("Executable/unrecognized model file type is not permitted.")
        if self.url is not None:
            from urllib.parse import urlsplit

            url = urlsplit(self.url)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError("Model downloads require credential-free HTTPS URLs.")
        return self


class ModelManifest(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    capability: Capability
    identity: ProviderIdentity
    license: str = Field(min_length=1, max_length=300)
    languages: list[str] = Field(default_factory=list)
    expected_ram_mb: int = Field(default=512, gt=0)
    files: list[ModelFile] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique(self) -> "ModelManifest":
        if self.identity.execution != "local" or len({f.name for f in self.files}) != len(
            self.files
        ):
            raise ValueError("Model manifests require local execution and unique files.")
        if self.capability == "alignment" and any(f.name.endswith(".bin") for f in self.files):
            raise ValueError("Alignment requires safetensors, not pickle-compatible model.bin.")
        return self


def catalog() -> dict[str, ModelManifest]:
    asr_revision = "d90ca5fe260221311c53c58e660288d3deb8d356"
    asr_base = f"https://huggingface.co/Systran/faster-whisper-tiny/resolve/{asr_revision}/"
    asr = {
        "config.json": ("a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8", 10000),
        "tokenizer.json": (
            "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
            3_000_000,
        ),
        "vocabulary.txt": (
            "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
            1_000_000,
        ),
        "model.bin": (
            "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
            80_000_000,
        ),
    }
    ocr_base = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv4/"
    return {
        "asr-tiny": ModelManifest(
            name="asr-tiny",
            capability="transcription",
            identity=ProviderIdentity(
                provider="faster-whisper",
                model="Systran/faster-whisper-tiny",
                revision=asr_revision,
                execution="local",
            ),
            license="MIT (Whisper)",
            languages=["multilingual"],
            expected_ram_mb=512,
            files=[
                ModelFile(name=name, sha256=sha, max_bytes=size, url=asr_base + name)
                for name, (sha, size) in asr.items()
            ],
        ),
        "ocr-en": ModelManifest(
            name="ocr-en",
            capability="ocr",
            identity=ProviderIdentity(
                provider="rapidocr",
                model="PP-OCRv4-en",
                revision="v3.4.0-sha256",
                execution="local",
            ),
            license="Apache-2.0 (PaddleOCR)",
            languages=["en"],
            expected_ram_mb=512,
            files=[
                ModelFile(
                    name="det.onnx",
                    sha256="d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9",
                    max_bytes=10_000_000,
                    url=ocr_base + "det/ch_PP-OCRv4_det_infer.onnx",
                ),
                ModelFile(
                    name="rec.onnx",
                    sha256="e8770c967605983d1570cdf5352041dfb68fa0c21664f49f47b155abd3e0e318",
                    max_bytes=20_000_000,
                    url=ocr_base + "rec/en_PP-OCRv4_rec_infer.onnx",
                ),
            ],
        ),
        "pose-lite": ModelManifest(
            name="pose-lite",
            capability="pose",
            identity=ProviderIdentity(
                provider="mediapipe",
                model="pose_landmarker_lite",
                revision="float16/1-sha256",
                execution="local",
            ),
            license="MediaPipe runtime: Apache-2.0; review upstream pose-weight terms separately.",
            expected_ram_mb=512,
            files=[
                ModelFile(
                    name="model.task",
                    max_bytes=6_000_000,
                    sha256="59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
                    url="https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
                )
            ],
        ),
        "yamnet": ModelManifest(
            name="yamnet",
            capability="audio_classifier",
            identity=ProviderIdentity(
                provider="mediapipe", model="yamnet", revision="float32/1-sha256", execution="local"
            ),
            license="Apache-2.0 (YAMNet)",
            expected_ram_mb=256,
            files=[
                ModelFile(
                    name="model.tflite",
                    max_bytes=5_000_000,
                    sha256="4d8b4a53282dc83ef04e3e7dbc4fbc98082e34e44ed798e16c3a0cdd4c584faf",
                    url="https://storage.googleapis.com/mediapipe-models/audio_classifier/"
                    "yamnet/float32/1/yamnet.tflite",
                )
            ],
        ),
    }


PACKAGES = {
    "transcription": ["faster-whisper", "ctranslate2", "onnxruntime", "av", "tokenizers", "numpy"],
    "ocr": ["rapidocr", "onnxruntime", "numpy", "opencv-python-headless", "Pillow"],
    "alignment": ["whisperx", "torch", "transformers", "nltk", "numpy"],
    "pose": ["mediapipe", "numpy", "Pillow"],
    "audio_classifier": ["mediapipe", "numpy", "soundfile"],
}


def package_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in {name for packages in PACKAGES.values() for name in packages}:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


class ModelStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.data_dir / "models"

    def manifests(self) -> dict[str, ModelManifest]:
        models = catalog()
        for path in sorted((self.root / "catalog").glob("*.json")):
            model = self.read_manifest(path)
            models[model.name] = model
        return models

    @staticmethod
    def read_manifest(path: Path) -> ModelManifest:
        if path.stat().st_size > 1_000_000:
            raise ConfigurationError("Model manifest exceeds the 1 MB limit.")
        return ModelManifest.model_validate_json(path.read_bytes())

    def get(self, name: str) -> ModelManifest:
        models = self.manifests()
        if name not in models:
            raise DependencyUnavailable(
                f"Unknown model '{name}'; prepare or register a model manifest."
            )
        return models[name]

    def directory(self, model: ModelManifest) -> Path:
        return self.root / model.name / hash_config(model.model_dump())

    def verify(self, model: ModelManifest) -> Path:
        root = self.directory(model)
        for asset in model.files:
            path = (root / asset.name).resolve()
            if (
                not path.is_relative_to(root.resolve())
                or not path.is_file()
                or path.stat().st_size > asset.max_bytes
                or hash_file(path) != asset.sha256
            ):
                raise DependencyUnavailable(
                    f"Model {model.name} is missing or corrupt: {asset.name}.",
                    next_action=f"Run socialdna models prepare {model.name} --allow-download, "
                    "or import a verified local model directory.",
                )
        return root

    def status(self) -> list[dict[str, Any]]:
        from socialdna.providers.registry import runtime_versions

        runtime_cache: dict[Path | None, dict[str, str | None]] = {}
        result = []
        for model in self.manifests().values():
            python = self.settings.provider_pythons.get(
                model.capability, self.settings.provider_python
            )
            if python not in runtime_cache:
                try:
                    runtime_cache[python] = runtime_versions(self.settings, python)
                except (OSError, ProviderFailure, MediaProcessingError):
                    runtime_cache[python] = {
                        package: None for group in PACKAGES.values() for package in group
                    }
            versions = runtime_cache[python]
            try:
                self.verify(model)
                state = "ready"
            except DependencyUnavailable:
                state = "not_prepared"
            result.append(
                {
                    **model.model_dump(),
                    "state": state,
                    "download_upper_bound_bytes": sum(f.max_bytes for f in model.files),
                    "runtime_packages": {p: versions[p] for p in PACKAGES[model.capability]},
                    "runtime_ready": all(versions[p] for p in PACKAGES[model.capability]),
                    "worker_python": str(python) if python else "current interpreter",
                    "native_compatibility_verified": False,
                    "device_support": ["cpu", "cuda"]
                    if model.capability == "transcription"
                    else ["cpu"],
                    "path": str(self.directory(model)),
                }
            )
        return result

    def prepare(
        self, name: str, *, manifest_path: Path | None = None, source_dir: Path | None = None
    ) -> dict[str, Any]:
        model = self.read_manifest(manifest_path) if manifest_path else self.get(name)
        if model.name != name:
            raise ConfigurationError("Manifest name must match the requested model name.")
        if source_dir is None and (self.settings.offline or not self.settings.allow_download):
            # Already prepared weights remain usable even with the offline policy.
            self.verify(model)
            return {"model": name, "state": "ready", "downloaded": False}
        root = self.directory(model)
        root.mkdir(parents=True, exist_ok=True)
        for asset in model.files:
            target = root / asset.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file():
                if hash_file(target) == asset.sha256:
                    continue
                raise ProviderFailure(f"Existing model file is corrupt; not overwritten: {target}")
            with tempfile.NamedTemporaryFile(dir=root, prefix=".download-", delete=False) as output:
                temporary = Path(output.name)
                digest, length = hashlib.sha256(), 0
                try:

                    def write(
                        chunks: Any, size_limit: int = asset.max_bytes, hasher: Any = digest
                    ) -> None:
                        nonlocal length
                        for chunk in chunks:
                            length += len(chunk)
                            if length > size_limit:
                                raise ProviderFailure(
                                    "Model asset exceeded its declared size bound."
                                )
                            hasher.update(chunk)
                            output.write(chunk)

                    if source_dir is not None:
                        source = (source_dir / asset.name).resolve()
                        if not source.is_relative_to(source_dir.resolve()):
                            raise ConfigurationError("Model import source escaped its root.")
                        with source.open("rb") as stream:
                            write(iter(lambda: stream.read(1024 * 1024), b""))
                    elif asset.url:
                        with httpx.stream(
                            "GET", asset.url, follow_redirects=True, timeout=60, trust_env=False
                        ) as response:
                            response.raise_for_status()
                            write(response.iter_bytes())
                    else:
                        raise ConfigurationError("Model has no download URL; use --from-dir.")
                    output.flush()
                    os.fsync(output.fileno())
                    if digest.hexdigest() != asset.sha256:
                        raise ProviderFailure(f"Model checksum did not match: {asset.name}")
                except BaseException:
                    output.close()
                    temporary.unlink(missing_ok=True)
                    raise
            os.replace(temporary, target)
        self.verify(model)
        registered = self.root / "catalog" / f"{name}.json"
        registered.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=registered.parent, delete=False) as output:
            output.write(canonical_json(model.model_dump()).encode())
            temporary = Path(output.name)
        os.replace(temporary, registered)
        return {
            "model": name,
            "state": "ready",
            "path": str(root),
            "identity": model.identity.model_dump(),
            "downloaded": source_dir is None,
        }
