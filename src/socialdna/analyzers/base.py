from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from socialdna.core.ids import stable_id
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.providers import ProviderIdentity
from socialdna.storage.schema import metadata


@dataclass
class TaskOutput:
    result: dict[str, Any] = field(default_factory=dict)
    records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    blobs: dict[str, tuple[Path, str, str]] = field(default_factory=dict)
    skipped: str | None = None
    provider: ProviderIdentity | None = None
    prompt_hash: str | None = None
    input_evidence_ids: list[str] = field(default_factory=list)
    creative_annotation: CreativeAnnotationSet | None = None


@dataclass
class TaskContext:
    task_id: str
    media_id: str
    provenance_id: str
    output: TaskOutput = field(default_factory=TaskOutput)

    def record(self, table: str, values: dict[str, Any]) -> str:
        row = dict(values)
        columns = metadata.tables[table].c
        for name, value in (
            ("task_id", self.task_id),
            ("media_asset_id", self.media_id),
            ("provenance_id", self.provenance_id),
        ):
            if name in columns:
                row[name] = value
        if "id" in columns and "id" not in row:
            row["id"] = stable_id(table, self.task_id, str(len(self.output.records.get(table, []))))
        self.output.records.setdefault(table, []).append(row)
        return str(row.get("id", ""))

    def evidence(
        self,
        subject_type: str,
        subject_id: str,
        start_ms: int,
        end_ms: int,
        *,
        artifact_id: str | None = None,
        excerpt: str | None = None,
    ) -> str:
        return self.record(
            "evidence_items",
            {
                "subject_type": subject_type,
                "subject_id": subject_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "artifact_id": artifact_id,
                "excerpt": excerpt,
            },
        )

    def observe(
        self,
        key: str,
        value: Any,
        start_ms: int,
        end_ms: int,
        *,
        modality: str,
        unit: str,
        description: str,
    ) -> None:
        from socialdna.core.hashing import canonical_json

        numeric = isinstance(value, (float, int))
        definitions = self.output.records.setdefault("feature_definitions", [])
        if not any(row["key"] == key for row in definitions):
            definitions.append(
                {
                    "key": key,
                    "modality": modality,
                    "value_kind": "numeric" if numeric else "json",
                    "unit": unit,
                    "description": description,
                    "schema_version": "1",
                }
            )
        observation = self.record(
            "observations",
            {
                "feature_key": key,
                "numeric_value": float(value) if numeric else None,
                "json_value": None if numeric else canonical_json(value),
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        self.evidence("observation", observation, start_ms, end_ms)
