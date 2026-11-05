"""Bind proposed explanations to reviewed definitions and actual measurement plans."""

import json

from sqlalchemy import Connection

from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.investigation import HypothesisPlan
from socialdna.storage.evidence_repository import EvidenceRepository


def validate(connection: Connection, plan: HypothesisPlan) -> None:
    if plan.construct_ref is None or plan.operationalization is None:
        return  # An unsupported explanation may be registered, not disguised as established.
    if (
        plan.construct_ref.kind != "psychological_construct"
        or plan.operationalization.kind != "operationalization"
    ):
        raise ConfigurationError("Psychological plans require typed construct/measurement refs")
    repo = EvidenceRepository(connection)
    repo.entity(plan.construct_ref)
    measure = json.loads(repo.entity(plan.operationalization)["payload_json"])
    if measure["construct"] != plan.construct_ref.model_dump():
        raise ConfigurationError("Operationalization belongs to a different construct revision")
