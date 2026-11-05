"""Verified prepared Sentence Transformers, isolated/offline like other local providers."""

import json
from typing import Any

from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable
from socialdna.core.hashing import hash_config
from socialdna.domain.memory import EmbeddingSpace
from socialdna.memory.vector_sync import vectors_checked
from socialdna.providers.models import ModelStore
from socialdna.providers.registry import LocalProvider


class LocalEmbedder:
    def __init__(self, settings: Settings, space: EmbeddingSpace) -> None:
        self.space = space
        store = ModelStore(settings)
        model = store.get(space.model_name)
        if (
            model.capability != "text_embedding"
            or model.identity.provider != "sentence-transformers"
            or model.identity.revision != space.model_revision
            or model.license != space.license
            or hash_config(model.model_dump(mode="json")) != space.manifest_hash
            or tuple(model.languages) != space.languages
        ):
            raise DependencyUnavailable(
                "Prepared model identity does not match the immutable embedding space"
            )
        required = {
            "modules.json",
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "1_Pooling/config.json",
        }
        if not required <= {file.name for file in model.files} or any(
            file.name.endswith(".bin") for file in model.files
        ):
            raise DependencyUnavailable(
                "Text embeddings require a complete safetensors Transformer/mean-pooling manifest"
            )
        root = store.verify(model)
        # Validate the executable module recipe before importing any optional code.
        modules = json.loads((root / "modules.json").read_text())
        if [(item.get("type"), item.get("path")) for item in modules] != [
            ("sentence_transformers.models.Transformer", ""),
            ("sentence_transformers.models.Pooling", "1_Pooling"),
        ]:
            raise DependencyUnavailable(
                "Only the audited Transformer + mean-pooling module recipe is supported"
            )
        pooling = json.loads((root / "1_Pooling/config.json").read_text())
        if not pooling.get("pooling_mode_mean_tokens") or any(
            value
            for key, value in pooling.items()
            if key.startswith("pooling_mode_") and key != "pooling_mode_mean_tokens"
        ):
            raise DependencyUnavailable("Prepared model pooling differs from the space")
        # Refuse undeclared auxiliary files: a local loader must not discover an
        # unhashed module/config/weight outside the registered artifact manifest.
        declared = {file.name for file in model.files}
        actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
        if actual != declared:
            raise DependencyUnavailable("Prepared embedding directory contains unverified files")
        self.provider = LocalProvider(settings, model, root)
        if self.provider.versions.get("sentence-transformers") != space.runtime_version:
            raise DependencyUnavailable(
                "Embedding runtime version does not match the immutable space"
            )
        if any(
            not self.provider.versions.get(name)
            or space.runtime_dependencies.get(name) != self.provider.versions[name]
            for name in ("torch", "transformers", "tokenizers", "numpy")
        ):
            raise DependencyUnavailable(
                "Embedding dependency versions do not match the immutable space"
            )

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        if not texts or len(texts) > 32 or any(len(text) > 1000 for text in texts):
            raise DependencyUnavailable(
                "Embedding batches are bounded to 32 texts of 1000 characters"
            )
        response: dict[str, Any] = self.provider.invoke(
            {
                "texts": texts,
                "options": {"space": self.space.model_dump(mode="json"), "query": query},
            }
        )
        values: list[list[float]] = response["vectors"]
        return vectors_checked(values, self.space, len(texts))
