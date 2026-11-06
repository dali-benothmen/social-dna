"""Minimized API observations: retrieval time is not a historical metric timestamp."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialdna.ingestion.tabular import timestamp

POLICY_VERSION: Literal["youtube-native-metadata-2026-11-06-v1"] = (
    "youtube-native-metadata-2026-11-06-v1"
)
NATIVE_OPERATIONS: tuple[Literal["inspect", "native_report"], ...] = ("inspect", "native_report")
YOUTUBE_FIELDS = (
    "id",
    "snippet/channelId",
    "snippet/channelTitle",
    "snippet/title",
    "snippet/description",
    "snippet/publishedAt",
    "snippet/categoryId",
    "snippet/defaultLanguage",
    "snippet/defaultAudioLanguage",
    "contentDetails/duration",
    "statistics/viewCount",
    "statistics/likeCount",
    "statistics/commentCount",
)


class CaptureManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    provider: Literal["youtube_data_api_v3"] = "youtube_data_api_v3"
    policy_version: Literal["youtube-native-metadata-2026-11-06-v1"] = POLICY_VERSION
    source_url: str
    external_id: str
    captured_at: str
    expires_at: str
    fields: dict[str, str | None]
    pages: Literal[1] = 1
    returned_posts: Literal[1] = 1
    media_acquired: Literal[False] = False
    metric_observed_at: None = None
    allowed_operations: tuple[Literal["inspect", "native_report"], ...] = NATIVE_OPERATIONS
    response_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_capture(self) -> "CaptureManifest":
        if set(self.fields) != set(YOUTUBE_FIELDS):
            raise ValueError("Capture must represent each declared native field")
        if self.fields["id"] != self.external_id:
            raise ValueError("Capture identity differs from the requested video")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", self.external_id) or not re.fullmatch(
            r"UC[A-Za-z0-9_-]{22}", self.fields["snippet/channelId"] or ""
        ):
            raise ValueError("Invalid video/channel identity")
        if not self.fields["snippet/channelId"] or not self.fields["snippet/publishedAt"]:
            raise ValueError("A source capture needs actual ownership and publication metadata")
        if not timestamp(self.captured_at) < timestamp(self.expires_at):
            raise ValueError("Capture expiry must follow retrieval")
        timestamp(self.fields["snippet/publishedAt"])
        return self


class CaptureFailure(Exception):
    """Safe, controlled provider diagnostics; never retain a provider response/error string."""

    def __init__(
        self, code: str, message: str, *, retry_after: int | None = None, permission: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.permission = permission
