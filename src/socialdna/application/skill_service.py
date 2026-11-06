"""Distribute one instruction bundle; never configure a host or replace existing skills."""

import hashlib
import shutil
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from socialdna import __version__
from socialdna.core.exceptions import ConfigurationError, StoragePermissionError
from socialdna.domain.account_study import AccountStudy
from socialdna.domain.acquisition import CaptureManifest
from socialdna.domain.capabilities import CapabilityManifest
from socialdna.domain.comparison_workflow import URLComparison
from socialdna.domain.content import ContentReport
from socialdna.domain.evidence_audit import EvidenceAudit
from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus, ResearchProtocol
from socialdna.domain.profile_audit import ProfileAuditProposal
from socialdna.domain.reconstruction import VideoReconstruction
from socialdna.domain.research import CorrectedPerformanceSpec, ResearchRegistration
from socialdna.domain.results import ResultEnvelope
from socialdna.domain.workflows import (
    IMPLEMENTED_TASKS,
    TASK_NAMES,
    WorkflowPlan,
    WorkflowReport,
    WorkflowRequest,
)
from socialdna.research.experiments import ExperimentSpec
from socialdna.research.recommendations import RecommendationSpec

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
    "profile_audit": ProfileAuditProposal,
    "account_study": AccountStudy,
    "url_comparison": URLComparison,
    "evidence_audit": EvidenceAudit,
    "recommendation": RecommendationSpec,
}

BUNDLES = ("socialdna", *("social-dna-" + task for task in IMPLEMENTED_TASKS))
UMBRELLA_FILES = (
    "LICENSE",
    "SKILL.md",
    "assets/account.json",
    "references/core.md",
    "references/interface.md",
    "references/research.md",
    "references/setup.md",
    "references/commands.json",
)


def catalog() -> dict[str, Any]:
    return {
        "engine_version": __version__,
        "bundles": list(BUNDLES),
        "planned": ["social-dna-" + task for task in TASK_NAMES if task not in IMPLEMENTED_TASKS],
        "limitations": [
            "Delivered interfaces are not permission, connectivity or sufficient evidence.",
            "Analyze supports content and profile scopes; specialist tasks remain planned.",
        ],
    }


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


def _bundle_contents(name: str) -> dict[str, bytes]:
    """Only reviewed public resources may be exported, never arbitrary folder contents."""
    source = bundle_path(name)
    resources = (
        {item: (source, item) for item in UMBRELLA_FILES}
        if name == "socialdna"
        else {
            "SKILL.md": (source, "SKILL.md"),
            "references/setup.md": (bundle_path(), "references/setup.md"),
        }
    )
    if name != "socialdna":
        shared = Path(str(files("socialdna").joinpath("task_skill_shared")))
        if not shared.is_dir():
            shared = source.parent / "shared"
        resources["references/workflow.md"] = (shared, "workflow.md")
    contents = {}
    try:
        for relative, (root, item) in resources.items():
            path = root
            components = [root]
            for part in Path(item).parts:
                path = path / part
                components.append(path)
            if any(component.is_symlink() for component in components):
                raise ConfigurationError(
                    "Skill resources must not be symlinks; reinstall the distribution."
                )
            with path.open("rb") as stream:
                content = stream.read(1_000_001)
            if len(content) > 1_000_000:
                raise ConfigurationError("Skill resource exceeds the 1 MB public resource limit.")
            contents[relative] = content
    except OSError as exc:
        raise ConfigurationError(
            "Cannot read complete public skill resources; reinstall the distribution."
        ) from exc
    header = contents["SKILL.md"].replace(b"\r\n", b"\n")
    if not header.startswith(("---\nname: " + name + "\n").encode()):
        raise ConfigurationError("Skill metadata does not match the selected bundle.")
    return contents


def inspect_bundle(name: str = "socialdna") -> dict[str, Any]:
    return _manifest(name, _bundle_contents(name))


def _manifest(name: str, contents: dict[str, bytes]) -> dict[str, Any]:
    return {
        "name": name,
        "engine_version": __version__,
        "files": sorted(contents),
        "sha256": {
            key: hashlib.sha256(value).hexdigest() for key, value in sorted(contents.items())
        },
    }


def _write_resource(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(".SKILL.md.pending") if path.name == "SKILL.md" else path
    with staged.open("xb") as stream:
        stream.write(content)
    if staged != path:
        # Atomic exclusive publication of complete bytes. Never rename over another file.
        path.hardlink_to(staged)
        staged.unlink()


def export_skill(destination: Path, name: str = "socialdna") -> dict[str, Any]:
    destination = destination.expanduser().absolute()
    if destination.name != name:
        raise ConfigurationError("Destination must be a new directory named " + name + ".")
    if destination.exists() or destination.is_symlink():
        raise ConfigurationError("Destination already exists; no skill files were overwritten.")
    if not destination.parent.is_dir():
        raise ConfigurationError("Create the intended host's skills parent directory first.")
    contents = _bundle_contents(name)  # Validate every resource before any destination write.
    owned = None
    try:
        destination.mkdir()  # Exclusive, including concurrent installs into an empty directory.
        owned = destination.stat()
        for relative in sorted(contents, key=lambda value: (value == "SKILL.md", value)):
            _write_resource(destination / relative, contents[relative])
    except FileExistsError as exc:
        if owned is None:
            raise ConfigurationError(
                "Destination already exists; no skill files were overwritten."
            ) from exc
        _cleanup_export(destination, owned)
        raise StoragePermissionError(
            "Cannot publish skill; inspect destination before retrying."
        ) from exc
    except OSError as exc:
        if owned is not None:
            _cleanup_export(destination, owned)
        raise StoragePermissionError(
            "Cannot export skill; an owned incomplete copy was cleaned where possible. "
            "Inspect destination before retrying; no existing skill was overwritten."
        ) from exc
    return {
        **_manifest(name, contents),
        "path": str(destination),
        "host_configuration_changed": False,
    }


def _cleanup_export(destination: Path, owned: Any) -> None:
    """Only roll back the exact leaf created here, never a pre-existing/swapped target."""
    try:
        current = destination.lstat()
        if not destination.is_symlink() and (current.st_dev, current.st_ino) == (
            owned.st_dev,
            owned.st_ino,
        ):
            shutil.rmtree(destination)
    except OSError:
        pass  # An interrupted/permission-denied export needs explicit operator recovery.
