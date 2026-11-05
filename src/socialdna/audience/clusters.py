from typing import Literal

from pydantic import Field, model_validator

from socialdna.audience.collections import AudienceModel


class ClusterMember(AudienceModel):
    reaction_key: str
    role: Literal["member", "representative", "counterexample"] = "member"


class ReactionCluster(AudienceModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=2000)
    members: tuple[ClusterMember, ...] = Field(min_length=1, max_length=200)
    state: Literal["proposed", "reviewed"] = "proposed"
    reviewer: str | None = Field(default=None, min_length=1, max_length=200)
    method: Literal["supplied_membership_v1"] = "supplied_membership_v1"
    membership_score_semantics: Literal["not_supplied"] = "not_supplied"

    @model_validator(mode="after")
    def sourced(self) -> "ReactionCluster":
        if len({m.reaction_key for m in self.members}) != len(self.members):
            raise ValueError("Cluster membership is unique per reaction")
        if not any(m.role == "representative" for m in self.members):
            raise ValueError("A summary needs at least one resolvable representative")
        if self.state == "reviewed" and not self.reviewer:
            raise ValueError("Reviewed cluster summaries need their reviewer")
        return self
