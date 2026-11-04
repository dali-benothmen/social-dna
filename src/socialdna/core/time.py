from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Milliseconds = Annotated[int, Field(strict=True, ge=0)]


def utc_now() -> str:
    return format_utc(datetime.now(UTC))


def format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include an explicit timezone")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class MediaInterval(BaseModel):
    """Milliseconds on the source timeline, with an exclusive end."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    start_ms: Milliseconds
    end_ms: Milliseconds

    @model_validator(mode="after")
    def ordered(self) -> "MediaInterval":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self

    def overlaps(self, other: "MediaInterval") -> bool:
        return self.start_ms < other.end_ms and other.start_ms < self.end_ms
