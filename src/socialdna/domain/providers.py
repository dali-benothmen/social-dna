from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProviderIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str
    model: str
    revision: str
    execution: Literal["local", "remote"]
