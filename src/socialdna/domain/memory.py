"""Versioned representation and bounded retrieval contracts, not research conclusions."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from socialdna.core.hashing import hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import format_utc

Family = Literal[
    "content_segments",
    "psychological_patterns",
    "statistical_findings",
    "audience_reactions",
    "research_knowledge",
    "behavioral_observations",
]


class EmbeddingSpace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    model_name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    model_revision: str = Field(min_length=1, max_length=200)
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str = Field(min_length=1, max_length=300)
    dimensions: int = Field(strict=True, ge=1, le=4096)
    distance: Literal["cosine"] = "cosine"
    pooling: Literal["mean"] = "mean"
    normalize: Literal[True] = True
    query_prefix: str = Field(default="query: ", max_length=100)
    document_prefix: str = Field(default="passage: ", max_length=100)
    chunk_policy: Literal["unicode-800-no-overlap-v1"] = "unicode-800-no-overlap-v1"
    representation_version: Literal["citation-text-v1"] = "citation-text-v1"
    max_tokens: int = Field(strict=True, ge=32, le=512)
    languages: tuple[str, ...] = Field(min_length=1, max_length=100)
    runtime_version: str = Field(min_length=1, max_length=100)
    runtime_dependencies: dict[str, str] = Field(default_factory=dict, max_length=10)

    @property
    def id(self) -> str:
        return stable_id("embedding-space", hash_config(self.model_dump(mode="json")))


class QuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str = Field(min_length=1, max_length=1000)
    mode: Literal["fts", "sql", "semantic", "hybrid"] = "fts"
    family: Family | None = None
    owner_kind: str | None = None
    owner_id: str | None = None
    source_id: str | None = None
    revision_id: str | None = None
    as_of: str | None = None
    space_id: str | None = None
    limit: int = Field(default=10, strict=True, ge=1, le=100)
    candidate_limit: int = Field(default=300, strict=True, ge=10, le=5000)
    graph_depth: int = Field(default=0, strict=True, ge=0, le=2)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query cannot be blank")
        return value.strip()

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: str | None) -> str | None:
        return format_utc(datetime.fromisoformat(value.replace("Z", "+00:00"))) if value else None
