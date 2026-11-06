"""One lossless record contract for JSON and flat, typed CSV exports.

CSV is intentionally read without dataframe type inference: external IDs such as
00012 must survive unchanged. Parsing and dry-run validation never touch storage.
"""

import csv
import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from socialdna.core.exceptions import ConfigurationError
from socialdna.core.time import format_utc

if TYPE_CHECKING:
    from socialdna.domain.behavioral import BehavioralExport

Key = Annotated[str, Field(min_length=1, max_length=256)]
Platform = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
Timestamp = Annotated[str, Field(min_length=1)]
State = Literal[
    "available", "not_supplied", "not_permitted", "not_applicable", "failed", "unavailable"
]


def timestamp(value: str) -> str:
    # Reject date-only, epoch numbers and naive local wall-clock times.
    if "T" not in value:
        raise ValueError("Timestamp must be ISO 8601 with T and an explicit UTC offset")
    return format_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def parse_behavioral(path: Path) -> "BehavioralExport":
    """Explicit v2 JSON contract; never relax or reinterpret the scalar v1 parser."""
    from socialdna.domain.behavioral import BehavioralExport

    try:
        with path.open("rb") as stream:
            raw = stream.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("Behavioral exports are limited to 4 MB")
        value = json.loads(
            raw,
            parse_constant=_bad_constant,
            parse_float=_finite_float,
            object_pairs_hook=_unique_keys,
        )
        return BehavioralExport.model_validate(value)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ConfigurationError(f"Invalid behavioral export: {exc}") from exc


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    platform: Platform
    record_type: str


class Account(Record):
    record_type: Literal["account"]
    external_id: Key
    handle: str | None = None
    creator_key: Key | None = None
    niche: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict)


class Post(Record):
    record_type: Literal["post"]
    external_id: Key
    account_external_id: Key
    content_type: Literal["video", "photo", "carousel", "text"] = "video"
    published_at: Timestamp
    title: str | None = None
    caption: str | None = None
    url: str | None = None

    _time = field_validator("published_at")(timestamp)


class Media(Record):
    record_type: Literal["media"]
    post_external_id: Key
    position: int = Field(default=0, ge=0, strict=True)
    # References are not fetched during import; local paths are explicitly analyzed later.
    uri: str = Field(min_length=1, max_length=8192)
    alt_text: str | None = Field(default=None, max_length=10000)


class Tag(Record):
    record_type: Literal["tag"]
    post_external_id: Key
    kind: Literal["hashtag", "topic"] = "hashtag"
    value: Key


class Comment(Record):
    record_type: Literal["comment"]
    post_external_id: Key
    external_id: Key
    body: str = Field(min_length=1, max_length=100_000)
    published_at: Timestamp
    parent_external_id: Key | None = None
    # Deliberately no author identifiers; import only minimized, permitted comments.
    _time = field_validator("published_at")(timestamp)


class MetricDefinition(Record):
    record_type: Literal["metric_definition"]
    key: Key
    subject_type: Literal["post", "account"] = "post"
    unit: Literal["count", "seconds", "ratio", "percent"] = "count"
    definition: str = Field(min_length=1, max_length=10_000)
    # Cumulative snapshots require post-age alignment; period metrics require exact windows.
    measurement: Literal["cumulative", "period"] = "cumulative"

    @model_validator(mode="after")
    def namespaced(self) -> "MetricDefinition":
        if not self.key.startswith(self.platform + "."):
            raise ValueError(
                "Metric keys must start with platform. and include a definition version"
            )
        if len(self.key.split(".")) < 3:
            raise ValueError("Use a versioned key such as instagram.views.v1")
        return self


class MetricSnapshot(Record):
    record_type: Literal["metric_snapshot"]
    subject_type: Literal["post", "account"] = "post"
    subject_external_id: Key
    metric_key: Key
    observed_at: Timestamp
    window_start: Timestamp | None = None
    window_end: Timestamp | None = None
    value: int | float | None = Field(default=None, ge=0)
    availability: State = "available"
    reason: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def numeric_value(cls, value: Any) -> Any:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("Metric values must be numbers, not booleans or numeric strings")
        return value

    _times = field_validator("observed_at", "window_start", "window_end")(
        lambda value: timestamp(value) if value is not None else None
    )

    @model_validator(mode="after")
    def valid_snapshot(self) -> "MetricSnapshot":
        if (self.availability == "available") != (self.value is not None):
            raise ValueError("Only available snapshots have a value; unknown values are null")
        if isinstance(self.value, bool):
            raise ValueError("Boolean metrics are not numeric observations")
        if self.availability != "available" and not self.reason:
            raise ValueError("Unavailable snapshots require a reason")
        if bool(self.window_start) != bool(self.window_end):
            raise ValueError("Supply both window_start and window_end, or neither")
        if self.window_start and self.window_end:
            if not self.window_start < self.window_end <= self.observed_at:
                raise ValueError("Require window_start < window_end <= observed_at")
        return self


ImportRecord = Annotated[
    Account | Post | Media | Tag | Comment | MetricDefinition | MetricSnapshot,
    Field(discriminator="record_type"),
]
RECORD_ADAPTER: TypeAdapter[ImportRecord] = TypeAdapter(ImportRecord)  # type: ignore[arg-type]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dataset_id: Key
    permission_basis: Literal["creator_owned_export", "authorized_export", "public_permitted"]
    source_uri: str = Field(min_length=1)
    comments_permitted: bool = False
    terms: dict[str, Any] = Field(default_factory=dict)


class ParsedImport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    schema_version: Literal["1.0"] = "1.0"
    source: Source | None = None
    records: list[ImportRecord] = Field(default_factory=list)
    # Row refers to record index (1-based) for JSON and physical line for CSV.
    rows: list[int] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    raw: bytes = Field(exclude=True, default=b"")


def parse_import(path: Path, format_name: Literal["csv", "json"]) -> ParsedImport:
    try:
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ConfigurationError("Tabular imports are limited to 32 MiB; split larger exports.")
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError(f"Cannot read UTF-8 import: {path}") from exc
    parsed = ParsedImport(raw=raw)
    rows: list[tuple[int, Any]] = []
    try:
        if format_name == "json":
            payload = json.loads(
                text,
                parse_constant=_bad_constant,
                parse_float=_finite_float,
                object_pairs_hook=_unique_keys,
            )
            if not isinstance(payload, dict) or set(payload) != {
                "schema_version",
                "source",
                "records",
            }:
                raise ValueError("JSON requires exactly schema_version, source and records")
            if payload["schema_version"] != "1.0" or not isinstance(payload["records"], list):
                raise ValueError("Expected schema_version 1.0 and a records array")
            parsed.source = Source.model_validate(payload["source"])
            if len(payload["records"]) > 100_000:
                raise ValueError("At most 100000 records are permitted per import")
            rows = list(enumerate(payload["records"], 1))
        else:
            reader = csv.DictReader(io.StringIO(text), strict=True)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)):
                raise ValueError("Duplicate CSV headers are not permitted")
            for record_count, row in enumerate(reader, 1):
                if record_count > 100_000:
                    raise ValueError("At most 100000 records are permitted per import")
                number = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    parsed.errors.append({"row": number, "message": "CSV row width differs"})
                    continue
                clean: dict[str, Any] = {key: value for key, value in row.items() if value != ""}
                version = clean.pop("_schema_version", None)
                source = {
                    key: clean.pop("_" + key, None)
                    for key in ("dataset_id", "permission_basis", "source_uri")
                }
                permitted = clean.pop("_comments_permitted", "false")
                source["comments_permitted"] = permitted
                try:
                    if version != "1.0":
                        raise ValueError("Each CSV row requires _schema_version=1.0")
                    current = Source.model_validate(source)
                    if parsed.source is not None and current != parsed.source:
                        raise ValueError("CSV source metadata must be identical across rows")
                    parsed.source = current
                    numeric_fields = ["position", "profile"]
                    if clean.get("record_type") == "metric_snapshot":
                        numeric_fields.append("value")
                    for key in numeric_fields:
                        if key in clean:
                            clean[key] = json.loads(
                                clean[key],
                                parse_constant=_bad_constant,
                                parse_float=_finite_float,
                                object_pairs_hook=_unique_keys,
                            )
                    rows.append((number, clean))
                except (ValueError, ValidationError) as exc:
                    parsed.errors.append({"row": number, "message": str(exc)})
        if not rows and not parsed.errors:
            raise ValueError("Dataset contains no records")
        if len(rows) > 100_000:
            raise ValueError("At most 100000 records are permitted per import")
    except (ValueError, csv.Error, ValidationError, RecursionError) as exc:
        parsed.errors.append({"row": 0, "message": str(exc)})
        return parsed
    for number, row in rows:
        try:
            record = RECORD_ADAPTER.validate_python(row)
            if isinstance(record, Comment) and not (
                parsed.source and parsed.source.comments_permitted
            ):
                raise ValueError("Comment bodies require explicit comments_permitted consent")
            parsed.records.append(record)
            parsed.rows.append(number)
        except (ValueError, ValidationError) as exc:
            parsed.errors.append({"row": number, "message": str(exc)})
    return parsed


def _bad_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("JSON number exceeds finite floating-point range")
    return result


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON object keys are not permitted")
    return result
