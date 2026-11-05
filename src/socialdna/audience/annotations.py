import re
from typing import Literal

from pydantic import Field, model_validator

from socialdna.audience.clusters import ReactionCluster
from socialdna.audience.collections import AudienceModel
from socialdna.audience.linking import ContentLink
from socialdna.domain.creative import AnnotationProtocol
from socialdna.domain.evidence import EntityRef

ReactionLabel = Literal[
    "expressed_intention",
    "question",
    "objection",
    "positive_reaction",
    "negative_reaction",
    "ambiguous",
    "other",
]
RUBRIC_VERSION = "expressed-reactions-1"
RUBRIC = {
    "expressed_intention": {
        "include": "An explicitly stated prospective intention",
        "exclude": "Verified action/conversion, negated or ironic intention",
    },
    "question": {
        "include": "A stated question or request for information",
        "exclude": "Unexpressed confusion or a question inferred from punctuation alone",
    },
    "objection": {
        "include": "An explicitly stated concern, refusal or obstacle",
        "exclude": "Assumed disagreement or silent non-conversion",
    },
    "positive_reaction": {
        "include": "Expressed favorable appraisal",
        "exclude": "Hidden enjoyment or satisfaction",
    },
    "negative_reaction": {
        "include": "Expressed unfavorable appraisal",
        "exclude": "Hidden negative emotion",
    },
    "ambiguous": {
        "include": "Unresolved meaning, irony, attribution or language",
        "exclude": "Forced binary sentiment",
    },
    "other": {
        "include": "Reviewed text outside this small reaction rubric",
        "exclude": "An unreviewed missing annotation",
    },
}


class ReactionAnnotation(AudienceModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    comment: EntityRef
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, gt=0)
    quote: str = Field(min_length=1, max_length=100000)
    labels: tuple[ReactionLabel, ...] = Field(min_length=1, max_length=7)
    language: str | None = Field(default=None, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    negated: bool | None = None
    ironic: bool | None = None
    ambiguous: bool | None = None
    complete_rubric_review: bool = False
    state: Literal["proposed", "reviewed", "disputed"] = "proposed"
    reviewer: str | None = Field(default=None, min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def coherent(self) -> "ReactionAnnotation":
        if (
            self.comment.kind != "comment"
            or self.end_char <= self.start_char
            or len(self.quote) != self.end_char - self.start_char
        ):
            raise ValueError("Annotation requires an exact original Unicode comment span")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("Reaction labels must be unique")
        if self.state == "reviewed" and not self.reviewer:
            raise ValueError("Reviewed annotations require their reviewer")
        if self.complete_rubric_review and self.state != "reviewed":
            raise ValueError("Only human-reviewed full comments certify rubric coverage")
        return self


class AnnotationSet(AudienceModel):
    schema_version: Literal["1.0"] = "1.0"
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    collection: EntityRef
    permission_basis: str = Field(min_length=1, max_length=2000)
    protocol: AnnotationProtocol
    annotations: tuple[ReactionAnnotation, ...] = Field(default=(), max_length=2000)
    clusters: tuple[ReactionCluster, ...] = Field(default=(), max_length=50)
    links: tuple[ContentLink, ...] = Field(default=(), max_length=2000)

    @model_validator(mode="after")
    def qualified(self) -> "AnnotationSet":
        if self.collection.kind != "audience_collection":
            raise ValueError("Select an exact audience collection revision")
        keys = {a.key for a in self.annotations}
        if (
            len(keys) != len(self.annotations)
            or len({c.key for c in self.clusters}) != len(self.clusters)
            or len({link.key for link in self.links}) != len(self.links)
        ):
            raise ValueError("Annotation, cluster and link keys must each be unique")
        if any(m.reaction_key not in keys for c in self.clusters for m in c.members) or any(
            link.reaction_key not in keys for link in self.links
        ):
            raise ValueError("Clusters/links require reactions in this frozen annotation set")
        if self.protocol.origin != "human" and (
            any(a.state == "reviewed" for a in self.annotations)
            or any(c.state == "reviewed" for c in self.clusters)
            or any(
                link.state == "reviewed" or link.origin == "human_interpretation"
                for link in self.links
            )
        ):
            raise ValueError("Model/rule proposals cannot self-adjudicate")
        if (
            any(link.origin == "model_proposal" for link in self.links)
            and self.protocol.origin != "model"
        ):
            raise ValueError("Model links require a real provider identity in the import protocol")
        if self.protocol.origin == "model" and any(
            link.origin != "model_proposal" for link in self.links
        ):
            raise ValueError("Model links remain inferred proposals, not explicit references")
        return self


def literal_candidates(text: str, language: str | None) -> tuple[tuple[str, ...], bool | None]:
    """English literal candidates only. No sentiment/behavior/irony inference."""
    if not language or language.split("-")[0].lower() != "en":
        return ("ambiguous",), None
    negated = bool(
        re.search(r"\b(?:not|never|won['’]t|can['’]t|don['’]t|wouldn['’]t)\b", text, re.I)
    )
    labels = []
    if re.search(
        r"\b(?:i (?:need|want|plan) to (?:make|cook|try)|i['’]ll (?:make|cook|try)|"
        r"going to (?:make|cook|try))\b",
        text,
        re.I,
    ):
        labels.append("expressed_intention")
    if "?" in text:
        labels.append("question")
    return tuple(labels or ["other"]), negated
