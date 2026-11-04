from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataPaths:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / "socialdna.db"

    @property
    def vectors(self) -> Path:
        return self.root / "vectors"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def lock(self) -> Path:
        return self.root / ".socialdna.lock"

    def create(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for relative in (
            "vectors",
            "cache",
            "artifacts/objects",
            "artifacts/frames",
            "artifacts/audio",
            "artifacts/transcripts",
            "artifacts/thumbnails",
            "models",
            "reports",
            "logs",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
