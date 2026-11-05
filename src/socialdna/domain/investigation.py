"""Bounded, versioned research inputs; no model-authored findings or causal claims."""

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from socialdna.domain.evidence import EntityRef, EvidenceRef


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def no_blank_fields(self) -> "ResearchModel":
        if any(isinstance(v, str) and not v.strip() for v in self.__dict__.values()):
            raise ValueError("Research text fields cannot be blank")
        return self


class FindingSpec(ResearchModel):
    key: str = Field(min_length=1, max_length=100)
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, gt=0)
    quote: str = Field(min_length=1, max_length=2000)
    location: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=2000)
    design: Literal["experiment", "observational", "review", "meta_analysis"]
    population: str = Field(min_length=1, max_length=2000)
    exposure: str = Field(min_length=1, max_length=2000)
    outcome: str = Field(min_length=1, max_length=1000)
    direction: Literal["positive", "negative", "null", "mixed", "not_estimated"]
    limitations: tuple[str, ...] = Field(min_length=1, max_length=20)


class StudySpec(ResearchModel):
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(max_length=2000)
    doi: str = Field(pattern=r"^10\.\d{4,9}/\S+$")
    authors: tuple[str, ...] = Field(min_length=1, max_length=100)
    year: int = Field(strict=True, ge=1800, le=2100)
    publication_status: Literal["current", "corrected", "retracted"] = "current"
    review_status: Literal["reviewed", "unverified"]
    reviewer: str = Field(min_length=1, max_length=200)
    verification_note: str = Field(min_length=1, max_length=2000)
    permission_basis: str = Field(min_length=1, max_length=1000)
    source_text: str = Field(min_length=1, max_length=20000)
    findings: tuple[FindingSpec, ...] = Field(min_length=1, max_length=30)

    @field_validator("doi")
    @classmethod
    def canonical_doi(cls, value: str) -> str:
        # DOI equivalence folds Basic Latin only, not arbitrary Unicode.
        return value.translate(
            str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
        )

    @field_validator("url")
    @classmethod
    def primary_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Literature needs an HTTPS primary-source URL without credentials")
        return value

    @model_validator(mode="after")
    def exact_excerpts(self) -> "StudySpec":
        if len({f.key for f in self.findings}) != len(self.findings):
            raise ValueError("Study finding keys must be unique")
        for finding in self.findings:
            if (
                not 0 <= finding.start_char < finding.end_char <= len(self.source_text)
                or self.source_text[finding.start_char : finding.end_char] != finding.quote
            ):
                raise ValueError("Finding quote must exactly match the captured Unicode span")
        return self


class ConstructSpec(ResearchModel):
    key: str = Field(min_length=1, max_length=100)
    definition: str = Field(min_length=1, max_length=2000)
    exclusions: tuple[str, ...] = Field(min_length=1, max_length=20)
    finding_keys: tuple[str, ...] = Field(min_length=1, max_length=30)


class OperationalizationSpec(ResearchModel):
    key: str = Field(min_length=1, max_length=100)
    construct_key: str = Field(min_length=1, max_length=100)
    procedure: str = Field(min_length=1, max_length=3000)
    population: str = Field(min_length=1, max_length=2000)
    indicator: str = Field(min_length=1, max_length=1000)
    validity: Literal["unvalidated_project_measure", "reviewed_external_measure"]
    limitations: tuple[str, ...] = Field(min_length=1, max_length=20)


class LiteratureCorpus(ResearchModel):
    schema_version: Literal["1.0"] = "1.0"
    key: str = Field(min_length=1, max_length=100)
    studies: tuple[StudySpec, ...] = Field(min_length=1, max_length=30)
    constructs: tuple[ConstructSpec, ...] = Field(default=(), max_length=30)
    operationalizations: tuple[OperationalizationSpec, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def unique_bindings(self) -> "LiteratureCorpus":
        if len({s.doi for s in self.studies}) != len(self.studies):
            raise ValueError("Import only one edition per DOI in a corpus")
        for items in (self.studies, self.constructs, self.operationalizations):
            if len({item.key for item in items}) != len(items):
                raise ValueError("Corpus keys must be unique within each kind")
        finding_keys = [f"{s.key}.{f.key}" for s in self.studies for f in s.findings]
        if len(set(finding_keys)) != len(finding_keys):
            raise ValueError("Qualified study/finding keys must be unambiguous")
        if any(set(c.finding_keys) - set(finding_keys) for c in self.constructs):
            raise ValueError("Construct references an unknown study finding")
        if any(
            o.construct_key not in {c.key for c in self.constructs}
            for o in self.operationalizations
        ):
            raise ValueError("Operationalization references an unknown construct")
        return self


class ApplicabilityReview(ResearchModel):
    finding: EvidenceRef
    applicability: Literal["direct", "indirect", "not_applicable"]
    rationale: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=200)


class Prediction(ResearchModel):
    feature: str = Field(min_length=1, max_length=100)
    metric_key: str = Field(min_length=1, max_length=200)
    direction: Literal["positive", "negative"]
    contrast: str = Field(min_length=1, max_length=2000)
    falsifier: str = Field(min_length=1, max_length=2000)
    discriminating_measurement: str = Field(min_length=1, max_length=2000)


class HypothesisPlan(ResearchModel):
    hypothesis: EntityRef
    explanation: Literal["psychological", "contextual"]
    prediction: Prediction
    construct_ref: EntityRef | None = None
    operationalization: EntityRef | None = None
    literature: tuple[ApplicabilityReview, ...] = Field(default=(), max_length=30)
    confounders: tuple[str, ...] = Field(min_length=1, max_length=30)
    scope_conditions: tuple[str, ...] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def consistent_kind(self) -> "HypothesisPlan":
        if self.hypothesis.kind != "hypothesis":
            raise ValueError("A hypothesis plan must bind an exact registered hypothesis")
        if (self.construct_ref is None) != (self.operationalization is None):
            raise ValueError("A construct requires its actual operationalization and vice versa")
        if self.explanation == "contextual" and (self.construct_ref or self.literature):
            raise ValueError("Contextual explanations do not require psychological constructs")
        return self


class ResearchProtocol(ResearchModel):
    schema_version: Literal["1.0"] = "1.0"
    key: str = Field(min_length=1, max_length=100)
    question: EntityRef
    hypotheses: tuple[HypothesisPlan, ...] = Field(min_length=2, max_length=10)
    population: str = Field(min_length=1, max_length=3000)
    selection_policy: Literal["canonical_sql_manifest"] = "canonical_sql_manifest"
    production_context: str = Field(min_length=1, max_length=2000)
    distribution_context: str = Field(min_length=1, max_length=2000)
    publishing_context: str = Field(min_length=1, max_length=2000)
    profile_context: str = Field(min_length=1, max_length=2000)
    experiment_design: str = Field(min_length=1, max_length=3000)
    treatment_variants: tuple[str, ...] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def question_and_rivals(self) -> "ResearchProtocol":
        if self.question.kind != "research_question":
            raise ValueError("A protocol requires a registered question revision")
        if len({p.hypothesis.id for p in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("Rival hypotheses must have distinct identities")
        return self


class EvaluationSpec(ResearchModel):
    schema_version: Literal["1.0"] = "1.0"
    protocol: EntityRef
    analysis_run_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    evidence: tuple[EvidenceRef, ...] = Field(default=(), max_length=100)
    expected_claim_level: Literal["hypothesis", "association"] = "hypothesis"

    @model_validator(mode="after")
    def bounded_unique_inputs(self) -> "EvaluationSpec":
        if self.protocol.kind != "research_protocol":
            raise ValueError("Evaluation requires an exact prepared protocol")
        if len(set(self.analysis_run_ids)) != len(self.analysis_run_ids):
            raise ValueError("Analysis run identities must be unique")
        if len({r.revision_id for r in self.evidence}) != len(self.evidence):
            raise ValueError("Evidence revisions must be unique")
        return self
