"""Distribute one instruction bundle; never configure a host or replace existing skills."""

import shutil
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from socialdna.core.exceptions import ConfigurationError, StoragePermissionError
from socialdna.domain.acquisition import CaptureManifest
from socialdna.domain.capabilities import CapabilityManifest
from socialdna.domain.content import ContentReport
from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus, ResearchProtocol
from socialdna.domain.reconstruction import VideoReconstruction
from socialdna.domain.research import CorrectedPerformanceSpec, ResearchRegistration
from socialdna.domain.results import ResultEnvelope
from socialdna.domain.workflows import WorkflowPlan, WorkflowReport, WorkflowRequest
from socialdna.research.experiments import ExperimentSpec

SCHEMAS: dict[str, type[BaseModel]] = {
    "result": ResultEnvelope,
    "capabilities": CapabilityManifest,
    "comparison": CorrectedPerformanceSpec,
    "registration": ResearchRegistration,
    "literature": LiteratureCorpus,
    "protocol": ResearchProtocol,
    "evaluation": EvaluationSpec,
    "experiment": ExperimentSpec,
    "workflow_request": WorkflowRequest,
    "workflow_plan": WorkflowPlan,
    "capture": CaptureManifest,
    "workflow_report": WorkflowReport,
    "content_report": ContentReport,
    "video_reconstruction": VideoReconstruction,
}

BUNDLES = (
    "socialdna",
    "social-dna-ingest",
    "social-dna-report",
    "social-dna-analyze",
    "social-dna-reconstruct",
)


def schema(name: str) -> dict[str, Any]:
    if name not in SCHEMAS:
        raise ConfigurationError("Unknown schema; choose " + ", ".join(SCHEMAS))
    return {"name": name, "schema": SCHEMAS[name].model_json_schema()}


def bundle_path(name: str = "socialdna") -> Path:
    if name not in BUNDLES:
        raise ConfigurationError("Choose an implemented skill: " + ", ".join(BUNDLES))
    resource = "skill_bundle" if name == "socialdna" else "task_skill_bundles/" + name
    packaged = Path(str(files("socialdna").joinpath(resource)))
    if packaged.is_dir():
        return packaged
    # Editable checkout only. Installed wheels/sdists must contain their own bundle.
    checkout = Path(__file__).resolve().parents[3] / "skills" / name
    if Path(__file__).resolve().parents[2].name == "src" and checkout.is_dir():
        return checkout
    raise ConfigurationError("Packaged SocialDNA skill is missing; reinstall the distribution.")


def export_skill(destination: Path, name: str = "socialdna") -> dict[str, Any]:
    source = bundle_path(name)
    destination = destination.expanduser().absolute()
    if destination.name != name:
        raise ConfigurationError("Destination must be a new directory named " + name + ".")
    if destination.exists() or destination.is_symlink():
        raise ConfigurationError("Destination already exists; no skill files were overwritten.")
    if not destination.parent.is_dir():
        raise ConfigurationError("Create the intended host's skills parent directory first.")
    try:
        shutil.copytree(source, destination)
        if name != "socialdna":
            shared = Path(str(files("socialdna").joinpath("task_skill_shared")))
            if not shared.is_dir():
                shared = source.parent / "shared"
            shutil.copytree(shared, destination / "references")
    except OSError as exc:
        raise StoragePermissionError(
            "Cannot export skill; inspect the destination for a partial copy before retrying."
        ) from exc
    return {
        "path": str(destination),
        "files": sorted(
            path.relative_to(destination).as_posix()
            for path in destination.rglob("*")
            if path.is_file()
        ),
        "host_configuration_changed": False,
    }
