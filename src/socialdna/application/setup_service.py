"""Read-only first-use guidance, not an installer, connection probe or evidence audit."""

import os
import shutil
from pathlib import Path
from typing import Any

from socialdna import __version__
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.workflows import IMPLEMENTED_TASKS, TASK_NAMES
from socialdna.ingestion.urls import parse_url

HOST_PATHS = {"codex": ".agents", "claude-code": ".claude", "opencode": ".opencode"}


def guidance(
    settings: Settings,
    *,
    task: str = "report",
    host: str = "codex",
    project_dir: Path = Path("."),
    url: str | None = None,
    scope: str = "content",
    input_kind: str | None = None,
) -> dict[str, Any]:
    """Inspect declared inputs and executable availability only; never open a library."""
    task = task.removeprefix("social-dna-")
    if task not in TASK_NAMES or host not in HOST_PATHS:
        raise ConfigurationError("Choose a known task and host (codex, claude-code, opencode).")
    if scope not in ("content", "profile") or (scope == "profile" and task != "analyze"):
        raise ConfigurationError("Only analyze supports --scope profile.")
    if input_kind not in (None, "image", "video"):
        raise ConfigurationError("Choose --input-kind image or video for a local original.")
    if input_kind and (task not in ("analyze", "reconstruct") or scope == "profile"):
        raise ConfigurationError("Local input-kind applies to content analysis/reconstruction.")
    if task == "reconstruct" and input_kind == "image":
        raise ConfigurationError("Finished-video reconstruction requires a video, not a photo.")
    target = parse_url(url) if url else None
    if target and (
        (task in ("ingest", "reconstruct") and target.kind != "post")
        or (task == "analyze" and target.kind != ("account" if scope == "profile" else "post"))
        or (task in ("account", "research") and target.kind != "account")
    ):
        raise ConfigurationError("The URL kind does not match this task/scope.")
    name = "social-dna-" + task
    destination = project_dir.expanduser().absolute() / HOST_PATHS[host] / "skills" / name
    prefix = ["socialdna", "--data-dir", str(settings.data_dir), "--no-ai", "--format", "json"]
    if settings.offline:
        prefix.append("--offline")
    diagnostics: list[dict[str, str]] = []
    steps: list[dict[str, Any]] = []

    def diagnostic(code: str, state: str, message: str) -> None:
        diagnostics.append({"code": code, "state": state, "message": message})

    def step(key: str, arguments: list[str], **extra: Any) -> None:
        steps.append({"id": key, "argv": [*prefix, *arguments], **extra})

    diagnostic("engine", "available", f"SocialDNA {__version__}; this command performs no setup.")
    if task not in IMPLEMENTED_TASKS:
        diagnostic(
            "task", "blocked", "Specialist skill is planned; no bundle can be installed yet."
        )
    else:
        diagnostic(
            "task", "available", "Delivered interface; data and evidence sufficiency unverified."
        )
        if destination.exists() or destination.is_symlink():
            diagnostic(
                "installation", "unverified", "Destination exists; export will not overwrite it."
            )
        elif not destination.parent.is_dir():
            diagnostic(
                "installation",
                "action_required",
                "Create the intended skills parent with permission.",
            )
        step(
            "export",
            ["skill", "export", str(destination), "--name", name],
            requires="Explicit permission to install this skill; parent directory must exist.",
        )

    if input_kind == "video" or task == "reconstruct":
        missing = [binary for binary in ("ffmpeg", "ffprobe") if not shutil.which(binary)]
        diagnostic(
            "video_tools",
            "blocked" if missing else "available",
            "Missing: " + ", ".join(missing)
            if missing
            else "FFmpeg/ffprobe found on PATH; not executed.",
        )
    if input_kind:
        diagnostic(
            "models",
            "not_required",
            "Deterministic local analysis needs no API key/model. "
            "ASR/OCR are optional explicit lanes.",
        )
    if target:
        if target.platform == "youtube" and target.kind == "post" and task in ("ingest", "report"):
            key_present = bool(os.environ.get(settings.youtube_api_key_env, "").strip())
            diagnostic(
                "native_access",
                "blocked" if settings.offline or not key_present else "unverified",
                "Offline mode prohibits acquisition."
                if settings.offline
                else "Credential present; validity, quota, permission and retention scheduler "
                "are NOT verified."
                if key_present
                else "Configure the YouTube API key locally, never in chat or CLI arguments; "
                "see references/setup.md.",
            )
            step(
                "maintenance",
                ["workflow", "maintenance"],
                requires="Inspect retention requirements; installing/enabling a timer "
                "needs separate permission.",
            )
            step(
                "plan",
                ["workflow", "plan", "--url", target.canonical_url],
                requires="Permission to persist a plan; this does not fetch anything.",
            )
            step(
                "run",
                ["workflow", "run", "{workflow_id}"],
                bindings={"workflow_id": "plan.data.workflow_id"},
                requires="Explicit network permission, valid credential "
                "and verified retention scheduler.",
            )
            step(
                "report",
                ["workflow", "report", "{workflow_id}", "--format", "markdown"],
                bindings={"workflow_id": "plan.data.workflow_id"},
                requires="Inspect run result, including partial/denied outcomes; "
                "metadata is not content analysis.",
            )
        else:
            diagnostic(
                "source",
                "action_required",
                "URL identity is recognized, not fetched. Use existing eligible library records "
                "or independently authorized observations/originals; "
                "no native account/Instagram/TikTok collector is delivered.",
            )
    if task == "analyze" and scope == "profile":
        diagnostic(
            "profile",
            "action_required",
            "Use workflow observe-profile for actual permitted fields/photo, then pin its "
            "returned revision in an analyze/profile plan. Missing fields remain unknown; "
            "a quality audit is not measured conversion.",
        )
    elif task in ("analyze", "reconstruct"):
        diagnostic(
            "media",
            "action_required",
            "Supply an authorized local original and declare its actual permission basis. "
            "The URL alone grants no download permission.",
        )
        if not target and task == "analyze" and input_kind:
            step(
                "analyze",
                ["analyze", input_kind, "{original_path}"],
                bindings={"original_path": "user-supplied authorized local path"},
            )
            step(
                "report",
                ["report", "generate", "--run", "{run_id}", "--format", "json"],
                bindings={"run_id": "analyze.data.run_id"},
            )
        else:
            step("request_contract", ["skill", "schema", "workflow_request"])
        if task == "reconstruct":
            diagnostic(
                "transcript",
                "action_required",
                "Use actual subtitle/ASR/OCR tracks. Verbatim reproduction requires an explicit "
                "rights declaration; reconstruction is not the original production script.",
            )
    elif task in ("account", "research"):
        diagnostic(
            "study",
            "action_required",
            "Use bounded eligible library posts and an explicit question/max-posts. "
            "Follow-up is explicit, not background monitoring; draft synthesis is not "
            "certified causal research.",
        )
        step("request_contract", ["skill", "schema", "workflow_request"])
    elif task == "compare":
        diagnostic(
            "comparison",
            "action_required",
            "Provide at least two URLs. Narrative comparison can be partial; numeric inference "
            "requires an eligible registered comparison design and comparable outcomes.",
        )
        step("request_contract", ["skill", "schema", "workflow_request"])
    elif task in ("report", "evidence") and not target:
        diagnostic(
            "selection",
            "action_required",
            "Select a saved workflow or exact evidence/entity revision returned by the engine. "
            "The agent binds IDs; do not invent them. Rendering/auditing does not acquire "
            "new sources.",
        )
        step("request_contract", ["skill", "schema", "workflow_request"])
    elif task == "ingest" and not target:
        diagnostic(
            "source",
            "action_required",
            "Provide a supported post URL or permitted local export. "
            "No connection is inferred from installed software.",
        )

    return {
        "status": "partial"
        if any(d["state"] in ("blocked", "action_required") for d in diagnostics)
        else "success",
        "engine_version": __version__,
        "task": name,
        "host": host,
        "destination": str(destination),
        "canonical_url": target.canonical_url if target else None,
        "diagnostics": diagnostics,
        "next_steps": steps,
        "invocation": ("$" if host == "codex" else "/" if host == "claude-code" else "Load skill ")
        + name,
        "policy": {
            "library_opened": False,
            "network_requested": False,
            "host_configuration_changed": False,
            "models_executed": False,
        },
        "guidance": "Review diagnostics, obtain needed permissions, then execute only applicable "
        "next steps. argv arrays are templates, not shell strings. Resolve bindings from actual "
        "prior results; stop on errors/partial results. Setup success never certifies connection, "
        "evidence sufficiency or a live host conversation.",
    }
