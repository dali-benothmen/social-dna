"""Atomic, offline human-reviewed corpus import; never an autonomous paper verifier."""

from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import insert

from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef
from socialdna.domain.investigation import LiteratureCorpus
from socialdna.storage import research_repository as research
from socialdna.storage.schema import metadata

T = TypeVar("T", bound=BaseModel)


def read_spec(path: Path, model: type[T]) -> T:
    try:
        with path.open("rb") as stream:
            raw = stream.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ConfigurationError("Research input exceeds the 1 MB limit")
        return model.model_validate_json(raw)
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid research input: {exc}") from exc


def import_corpus(application: Application, corpus: LiteratureCorpus) -> dict[str, Any]:
    result: dict[str, Any] = {
        name: {}
        for name in ("sources", "findings", "citations", "constructs", "operationalizations")
    }
    with application.database.transaction() as connection:
        common = research.provenance(connection, corpus.key, corpus.model_dump(mode="json"))
        findings = {}
        constructs: dict[str, EntityRef] = {}
        for study in corpus.studies:
            spec = study.model_dump(mode="json")
            provenance = research.provenance(
                connection,
                study.doi,
                spec,
                uri=study.url,
                permission=study.permission_basis,
            )
            source = research.save(
                connection, "literature_source", study.doi, {"spec": spec}, provenance
            )
            connection.execute(
                insert(metadata.tables["memory_changes"]).values(
                    kind="eligibility", target_id=source.id
                )
            )
            result["sources"][study.key] = source.model_dump()
            for finding in study.findings:
                key = study.key + "." + finding.key
                ref = research.save(
                    connection,
                    "study_finding",
                    stable_id("study-finding-key", study.doi, finding.key),
                    {
                        "spec": finding.model_dump(mode="json"),
                        "source_document": source.model_dump(),
                    },
                    provenance,
                    entities=(source,),
                )
                findings[key] = research.cite(connection, ref)
                result["findings"][key] = ref.model_dump()
                result["citations"][key] = findings[key].model_dump()
        for construct in corpus.constructs:
            refs = tuple(findings[key] for key in construct.finding_keys)
            ref = research.save(
                connection,
                "psychological_construct",
                stable_id("construct-key", corpus.key, construct.key),
                {"spec": construct.model_dump(mode="json")},
                common,
                evidence=refs,
            )
            constructs[construct.key] = ref
            result["constructs"][construct.key] = ref.model_dump()
        for measure in corpus.operationalizations:
            construct_ref = constructs[measure.construct_key]
            ref = research.save(
                connection,
                "operationalization",
                stable_id("operationalization-key", corpus.key, measure.key),
                {"spec": measure.model_dump(mode="json"), "construct": construct_ref.model_dump()},
                common,
                entities=(construct_ref,),
            )
            result["operationalizations"][measure.key] = ref.model_dump()
    return {"written": True, **result, "verification": "user_attested_not_automatically_verified"}
