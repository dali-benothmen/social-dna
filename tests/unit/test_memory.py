import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable, ProviderFailure
from socialdna.core.hashing import hash_config, hash_file
from socialdna.domain.memory import EmbeddingSpace, QuerySpec
from socialdna.memory.documents import text_fields
from socialdna.memory.vector_sync import vectors_checked
from socialdna.providers.embeddings import LocalEmbedder
from socialdna.providers.models import ModelManifest, ModelStore
from socialdna.providers.worker import infer


def space(**changes: Any) -> EmbeddingSpace:
    return EmbeddingSpace.model_validate(
        {
            "model_name": "local-fixture",
            "model_revision": "pinned-revision",
            "manifest_hash": "a" * 64,
            "license": "fixture",
            "dimensions": 2,
            "max_tokens": 512,
            "languages": ["en"],
            "runtime_version": "5.7.0",
            "runtime_dependencies": {
                "torch": "test",
                "transformers": "test",
                "tokenizers": "test",
                "numpy": "test",
            },
            **changes,
        }
    )


@pytest.mark.parametrize(
    "change",
    [
        {"model_revision": "next"},
        {"manifest_hash": "b" * 64},
        {"dimensions": 3},
        {"query_prefix": "different: "},
        {"document_prefix": "different: "},
        {"languages": ["de"]},
        {"max_tokens": 128},
        {"runtime_version": "5.8.0"},
    ],
)
def test_space_identity_pins_compatibility(change: dict[str, Any]) -> None:
    assert space().id == space().id
    assert space(**change).id != space().id


@pytest.mark.parametrize(
    "values",
    [[], [[1.0]], [[float("nan"), 0]], [[float("inf"), 1]], [[True, 0]], [[0, 0]], [[2, 0]]],
)
def test_invalid_vectors_refused(values: list[list[float]]) -> None:
    with pytest.raises(ProviderFailure):
        vectors_checked(values, space(), 1)


def test_query_validation_and_no_raw_author_representation() -> None:
    with pytest.raises(ValidationError):
        QuerySpec(text=" ")
    with pytest.raises(ValidationError):
        QuerySpec(text="x", as_of="2026-01-01")
    with pytest.raises(ValidationError):
        QuerySpec(text="x", limit=True)
    assert (
        QuerySpec(text="x", as_of="2026-01-01T02:00:00+02:00").as_of
        == "2026-01-01T00:00:00.000000Z"
    )
    text = text_fields(
        {
            "annotation": {"quote": "literal comment", "reviewer": "private reviewer"},
            "protocol": {"author": "private author"},
            "source_uri": "secret url",
        }
    )
    assert "literal comment" in text
    assert "private" not in text and "secret" not in text


def manifest_fixture(tmp_path: Path) -> tuple[Path, Path, ModelManifest]:
    root = tmp_path / "provided"
    root.mkdir()
    documents = {
        "modules.json": [
            {"type": "sentence_transformers.models.Transformer", "path": ""},
            {"type": "sentence_transformers.models.Pooling", "path": "1_Pooling"},
        ],
        "1_Pooling/config.json": {
            "pooling_mode_mean_tokens": True,
            "pooling_mode_cls_token": False,
        },
        "config.json": {},
        "tokenizer_config.json": {},
        "tokenizer.json": {},
        "model.safetensors": "not real weights: manifest-only test fixture",
    }
    files = []
    for name, value in documents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        files.append({"name": name, "sha256": hash_file(path), "max_bytes": 10000})
    model = ModelManifest.model_validate(
        {
            "name": "local-fixture",
            "capability": "text_embedding",
            "license": "fixture",
            "languages": ["en"],
            "identity": {
                "provider": "sentence-transformers",
                "model": "fixture",
                "revision": "pinned-revision",
                "execution": "local",
            },
            "files": files,
        }
    )
    path = tmp_path / "manifest.json"
    path.write_text(model.model_dump_json())
    return root, path, model


def test_explicit_preparation_hashes_runtime_and_no_implicit_download(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.offline = True
    root, path, manifest = manifest_fixture(tmp_path)
    pinned = space(manifest_hash=hash_config(manifest.model_dump(mode="json")))
    store = ModelStore(settings)
    with pytest.raises(DependencyUnavailable):
        LocalEmbedder(settings, pinned)
    store.prepare("local-fixture", manifest_path=path, source_dir=root)
    monkeypatch.setattr(
        "socialdna.providers.registry.runtime_versions",
        lambda *args: {
            "sentence-transformers": "5.7.0",
            "torch": "test",
            "transformers": "test",
            "tokenizers": "test",
            "numpy": "test",
        },
    )
    provider = LocalEmbedder(settings, pinned)
    monkeypatch.setattr(provider.provider, "invoke", lambda request: {"vectors": [[1.0, 0.0]]})
    assert provider.encode(["literal text"]) == [[1.0, 0.0]]
    with pytest.raises(DependencyUnavailable):
        LocalEmbedder(settings, pinned.model_copy(update={"runtime_version": "other"}))
    (store.directory(manifest) / "unverified.json").write_text("{}")
    with pytest.raises(DependencyUnavailable, match="unverified"):
        LocalEmbedder(settings, pinned)


def test_worker_prefixes_and_token_budget_are_real_not_silent_truncation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = []

    class Model:
        max_seq_length = 512

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            assert kwargs["local_files_only"] is True and kwargs["trust_remote_code"] is False

        def tokenizer(self, texts: list[str], **kwargs: Any) -> dict[str, Any]:
            assert not kwargs["truncation"]
            return {"input_ids": [[0] * len(text) for text in texts]}

        def encode(self, texts: list[str], **kwargs: Any) -> Any:
            recorded.extend(texts)
            assert kwargs["normalize_embeddings"] and kwargs["prompt"] == ""
            return SimpleNamespace(tolist=lambda: [[1.0, 0.0]])

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(set_num_threads=lambda _: None))
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model)
    )
    request = {
        "capability": "text_embedding",
        "model_dir": str(tmp_path),
        "texts": ["saffron"],
        "options": {"space": space().model_dump(), "query": True},
    }
    assert infer(request)["vectors"] == [[1.0, 0.0]]
    assert recorded == ["query: saffron"]
    request["texts"] = ["x" * 600]
    with pytest.raises(ValueError, match="budget"):
        infer(request)
