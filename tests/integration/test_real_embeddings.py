"""Opt-in real adapter/Qdrant integration. No download and no relevance-quality claim."""

import json
import os
import shutil
from pathlib import Path

import pytest

from socialdna.application import query_service
from socialdna.application.bootstrap import open_application
from socialdna.application.research_service import register_research
from socialdna.config.settings import Settings
from socialdna.domain.memory import EmbeddingSpace, QuerySpec
from socialdna.memory.vector_sync import drain
from socialdna.providers.embeddings import LocalEmbedder

pytestmark = pytest.mark.local_models


def test_verified_real_embedding_runtime(settings: Settings, tmp_path: Path) -> None:
    library = os.environ.get("SOCIALDNA_TEST_MODEL_LIBRARY")
    specification = os.environ.get("SOCIALDNA_TEST_EMBEDDING_SPACE")
    if not library or not specification:
        pytest.skip("Set an explicitly prepared local model library and embedding-space JSON")
    shutil.copytree(Path(library) / "models", settings.data_dir / "models")
    settings.offline = True
    python = os.environ.get("SOCIALDNA_TEST_EMBEDDING_PYTHON")
    if python:
        settings.provider_pythons["text_embedding"] = Path(python)
    space = EmbeddingSpace.model_validate_json(Path(specification).read_bytes())
    question = tmp_path / "question.json"
    question.write_text(
        json.dumps(
            {
                "key": "cooking-opening",
                "question": "Why begin a cooking video with the finished dish?",
                "population": "Adapter acceptance fixture; no empirical finding",
            }
        )
    )
    register_research(settings, question)
    with open_application(settings) as app:
        provider = LocalEmbedder(settings, space)
        vectors = provider.encode(
            ["A finished meal appears in the opening.", "La receta empieza con el plato terminado."]
        )
        query = provider.encode(["cooking video opening"], query=True)
        assert len(vectors) == 2 and len(query[0]) == space.dimensions
        assert vectors[0] != vectors[1]
        query_service.register_embedding_space(app, space)
        result = drain(app, space.id, provider=provider)
        assert result["pending"] == 0 and result["completed"]
    with open_application(settings) as app:
        result = query_service.query(
            app, QuerySpec(text="cooking video opening", mode="semantic", space_id=space.id)
        )
        assert result["semantic"] == "available" and result["hits"]
