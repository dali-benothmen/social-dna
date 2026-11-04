import ipaddress
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

Capability = Literal["transcription", "ocr", "alignment", "pose", "audio_classifier"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ProviderIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=300)
    revision: str = Field(min_length=1, max_length=200)
    execution: Literal["local", "remote"]


class Word(StrictModel):
    text: str = Field(min_length=1, max_length=1000)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self) -> "Word":
        if (self.start is None) != (self.end is None):
            raise ValueError("Word timestamps must both be present or both absent.")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("Word end must be after its start.")
        return self


class SpeechSegment(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=10000)
    words: list[Word] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def ordered(self) -> "SpeechSegment":
        if self.end <= self.start:
            raise ValueError("Speech segment end must follow start.")
        for word in self.words:
            if word.start is not None and word.end is not None:
                if word.start < self.start - 0.05 or word.end > self.end + 0.05:
                    raise ValueError("Word timestamp is outside its speech segment.")
        return self


class SpeechResult(StrictModel):
    language: str = Field(min_length=1, max_length=30)
    language_probability: float | None = Field(default=None, ge=0, le=1)
    segments: list[SpeechSegment] = Field(default_factory=list, max_length=10000)


class OCRBox(StrictModel):
    text: str = Field(min_length=1, max_length=5000)
    confidence: float = Field(ge=0, le=1)
    # Normalized quad, in evidence-frame coordinates, not original rotated source pixels.
    points: list[tuple[float, float]] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def normalized(self) -> "OCRBox":
        if any(not 0 <= component <= 1 for point in self.points for component in point):
            raise ValueError("OCR box coordinates must be normalized into [0, 1].")
        return self


class OCRFrame(StrictModel):
    frame_id: str
    boxes: list[OCRBox] = Field(default_factory=list, max_length=1000)


class Landmark(StrictModel):
    x: float
    y: float
    z: float
    visibility: float | None = Field(default=None, ge=0, le=1)
    presence: float | None = Field(default=None, ge=0, le=1)


class PoseFrame(StrictModel):
    frame_id: str
    poses: list[list[Landmark]] = Field(max_length=2)

    @model_validator(mode="after")
    def shape(self) -> "PoseFrame":
        if any(len(pose) != 33 for pose in self.poses):
            raise ValueError("MediaPipe poses require exactly 33 landmarks.")
        return self


class AudioCategory(StrictModel):
    label: str = Field(min_length=1, max_length=200)
    score: float = Field(ge=0, le=1)


class AudioWindow(StrictModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    categories: list[AudioCategory] = Field(max_length=20)

    @model_validator(mode="after")
    def ordered(self) -> "AudioWindow":
        if self.end_ms <= self.start_ms:
            raise ValueError("Audio category window must have a positive duration.")
        return self


class ReasoningProfile(StrictModel):
    enabled: bool = False
    endpoint: str
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=200)
    execution: Literal["local", "remote"] = "local"
    modalities: list[Literal["text", "image"]] = Field(default=["text"])
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    allowed_data: list[Literal["text", "image"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def safe_endpoint(self) -> "ReasoningProfile":
        url = urlsplit(self.endpoint)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ValueError("Provider endpoint must not contain credentials, query or fragment.")
        if self.execution == "local":
            try:
                loopback = ipaddress.ip_address(url.hostname).is_loopback
            except ValueError:
                loopback = False
            if not loopback or url.scheme != "http":
                raise ValueError("Local HTTP providers require a literal loopback IP address.")
        elif url.scheme != "https":
            raise ValueError("Remote providers require HTTPS.")
        return self


class Interpretation(StrictModel):
    modality: Literal["visual", "linguistic"]
    description: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    confidence: Literal["low", "medium"] = "low"
    alternatives: list[str] = Field(min_length=1, max_length=10)


class ReasoningResult(StrictModel):
    interpretations: list[Interpretation] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class TranscriptionProvider(Protocol):
    identity: ProviderIdentity

    def transcribe(self, request: dict[str, Any]) -> SpeechResult: ...


class VisionProvider(Protocol):
    identity: ProviderIdentity

    def read_text(self, request: dict[str, Any]) -> list[OCRFrame]: ...


class AudioProvider(Protocol):
    identity: ProviderIdentity

    def classify_audio(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class ReasoningProvider(Protocol):
    identity: ProviderIdentity

    def reason(self, request: dict[str, Any]) -> ReasoningResult: ...
