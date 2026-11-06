"""Cheap preflight: no library initialization, inference, network or index creation."""

import os
import shutil
from typing import Any

from socialdna import __version__
from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable, SocialDNAError
from socialdna.domain.capabilities import CapabilityEntry, CapabilityManifest, CapabilityState
from socialdna.providers.models import PACKAGES, ModelStore
from socialdna.providers.registry import LocalProvider, ProviderRegistry


def preflight_error(exc: Exception) -> str:
    # Validation errors can embed the complete invalid manifest, including URL credentials.
    return (
        "Invalid local model manifest or runtime metadata; inspect the local configuration."
        if isinstance(exc, ValueError)
        else str(exc)
    )


def embedding_preflight(settings: Settings, no_ai: bool) -> CapabilityEntry:
    entry = CapabilityEntry(
        id="semantic_memory",
        status="unavailable",
        reason="No verified prepared embedding model/runtime was found.",
        commands=[["memory", "status"], ["memory", "register-space"]],
        prerequisites=["A prepared embedding model and a registered matching immutable space."],
        limitations=[
            "Space bindings, corpus coverage and index lag are not checked by this preflight."
        ],
    )
    if no_ai:
        entry.reason = "Disabled for this invocation by --no-ai."
        return entry
    try:
        store = ModelStore(settings)
        for model in store.manifests().values():
            if model.capability != "text_embedding":
                continue
            try:
                if model.identity.provider != "sentence-transformers":
                    raise DependencyUnavailable("Unsupported embedding backend.")
                provider = LocalProvider(settings, model, store.verify(model))
                if any(not provider.versions.get(name) for name in PACKAGES["text_embedding"]):
                    raise DependencyUnavailable("Embedding runtime packages are missing.")
                entry.status = "optional_prepared"
                entry.reason = (
                    "Prepared embedding assets/runtime metadata found; space pins not checked."
                )
                break
            except (SocialDNAError, OSError, ValueError) as exc:
                entry.reason = preflight_error(exc)
    except (SocialDNAError, OSError, ValueError) as exc:
        entry.reason = preflight_error(exc)
    return entry


def capabilities(settings: Settings, *, no_ai: bool = False) -> dict[str, Any]:
    entries: list[CapabilityEntry] = []

    def available(identity: str, reason: str, *commands: list[str], **kwargs: Any) -> None:
        entries.append(
            CapabilityEntry(
                id=identity, status="available", reason=reason, commands=list(commands), **kwargs
            )
        )

    video_tools = all(shutil.which(name) for name in ("ffmpeg", "ffprobe"))
    available(
        "library_url_comparisons",
        "Exact multi-URL library samples, registered R2 comparisons and qualified synthesis.",
        ["workflow", "plan"],
        ["workflow", "run"],
        ["workflow", "report"],
        limitations=[
            "No cold URL acquisition; compatible independently permitted observations "
            "and an explicit design are required for quantitative output."
        ],
    )
    available(
        "canonical_evidence_audits",
        "Exact SQL evidence lineage with optional bounded R6 graph and R8 history.",
        ["workflow", "plan"],
        ["workflow", "report"],
        limitations=[
            "No collection/refit; graph connectivity is not proof; "
            "withdrawn inputs withhold protected reports."
        ],
    )
    entries.append(
        CapabilityEntry(
            id="local_video",
            status="available" if video_tools else "unavailable",
            reason="FFmpeg and FFprobe found on PATH; codecs not exercised."
            if video_tools
            else "Install FFmpeg and FFprobe for local video processing.",
            commands=[["analyze", "video"], ["timeline", "show"]],
            limitations=["Signals and supplied subtitles are not semantic or causal findings."],
        )
    )
    available(
        "account_library_studies",
        "Bounded library studies, local-media dispatch and draft research questions.",
        ["workflow", "plan"],
        ["workflow", "run"],
        ["workflow", "report"],
        limitations=[
            "No native account pagination, certified mechanisms or automatic reevaluation."
        ],
    )
    available(
        "profile_audit_proposals",
        "Assisted dated profile observations and cited unreviewed field-check proposals.",
        ["workflow", "observe-profile"],
        ["workflow", "plan"],
        ["workflow", "report"],
        limitations=["No URL-only acquisition, semantic quality review or measured conversion."],
    )
    available(
        "video_reconstruction",
        "Saved actual video/text tracks or assisted URL-plus-original reconstruction.",
        ["workflow", "plan"],
        ["workflow", "run"],
        ["workflow", "report"],
        prerequisites=["Actual analyzed video; explicit permission for verbatim reproduction."],
        limitations=[
            "No original writing document, cold media access, speaker ID or translation; "
            "ASR/OCR are estimates and supplied subtitles are not verified speech."
        ],
    )
    available(
        "static_media",
        "Bounded offline raster and ordered static carousel analysis.",
        ["analyze", "image"],
        ["analyze", "carousel"],
        limitations=["Animated/multipage and mixed-video carousels are not supported."],
    )
    available(
        "account_analytics",
        "Authorized exports and frozen age-aligned comparisons.",
        ["import", "json"],
        ["import", "csv"],
        ["analyze", "account"],
        ["compare", "posts"],
        ["compare", "accounts"],
        ["compare", "reproduce"],
        prerequisites=["Source-defined outcomes and an explicit comparison design."],
    )
    available(
        "reports",
        "Persistent citation-backed JSON and escaped Markdown, not HTML.",
        ["report", "generate"],
        ["evidence", "resolve"],
    )
    available(
        "research_memory",
        "Canonical SQL/FTS and qualified SQLite-backed graph.",
        ["query"],
        ["graph", "neighbors"],
        prerequisites=["Canonical eligible inputs; query defaults do not require embeddings."],
    )
    available(
        "psychological_research",
        "Reviewed literature, rival hypotheses and bounded assessment.",
        ["research", "register"],
        ["research", "import-literature"],
        ["research", "prepare"],
        ["research", "evaluate"],
        ["research", "reevaluate"],
        ["research", "history"],
        prerequisites=["Exact reviewed source revisions, protocol and eligible comparisons."],
        limitations=["No automatic psychological mediator identification or validity guarantee."],
    )
    available(
        "audience_reactions",
        "Source-qualified collections and reviewed expressed reactions.",
        ["audience", "import-collection"],
        ["audience", "import-annotations"],
        ["analyze", "audience"],
        prerequisites=[
            "Permitted captured comments, collection coverage and reviewed annotations."
        ],
        limitations=["Collected commenters are not representative viewers or verified behavior."],
    )
    available(
        "behavioral_outcomes",
        "Source-defined series, denominators, attribution and account outcomes.",
        ["import", "behavioral"],
        ["analyze", "retention"],
        ["analyze", "outcomes"],
        prerequisites=["Authorized actual observations with compatible definitions and windows."],
        limitations=["No invented viewer-level data, denominators or causal attribution."],
    )
    for identity, reason, commands in (
        (
            "production",
            "Reviewed professional craft annotations and pinned numeric recipes.",
            [["creative", "import"], ["creative", "materialize"]],
        ),
        (
            "publishing_search",
            "Dated metadata, packaging, timezone and qualified cadence evidence.",
            [["context", "import"], ["context", "publication-report"]],
        ),
        (
            "platform_distribution",
            "Separate reviewed official guidance and surface-specific observations.",
            [["platform", "import"], ["platform", "report"]],
        ),
        (
            "profile_funnel",
            "Profile rubrics separate from source-defined measured conversion funnels.",
            [["profile", "import"], ["profile", "report"]],
        ),
        (
            "discovery_experiments",
            "Bounded discovery and registered outcomes; qualified proposals only.",
            [
                ["research", "discover"],
                ["experiment", "register"],
                ["experiment", "analyze"],
                ["recommendation", "create"],
            ],
        ),
    ):
        available(
            identity,
            reason,
            *commands,
            prerequisites=[
                "Authorized imported inputs and domain-specific reviewed specifications."
            ],
            limitations=[
                "Availability is interface support, not evidence sufficiency or effectiveness."
            ],
        )
    registry = ProviderRegistry(settings)
    for identity, name, capability in (
        ("transcription", settings.asr_model, "transcription"),
        ("ocr", settings.ocr_model, "ocr"),
        ("alignment", settings.alignment_model, "alignment"),
        ("pose", settings.pose_model, "pose"),
        ("audio_classifier", settings.audio_classifier_model, "audio_classifier"),
    ):
        state: CapabilityState = "unavailable"
        if no_ai:
            reason = "Disabled for this invocation by --no-ai."
        elif not name:
            reason = "No local model configured."
        else:
            try:
                registry.resolve(name, capability)
                state = "optional_prepared"
                reason = "Verified prepared assets and runtime metadata; inference not exercised."
            except (SocialDNAError, OSError, ValueError) as exc:
                reason = preflight_error(exc)
        entries.append(
            CapabilityEntry(
                id=identity,
                status=state,
                reason=reason,
                commands=[["models", "status"], ["models", "prepare"]],
                prerequisites=["Explicit optional runtime/model preparation and task request."],
                limitations=["Native compatibility and model accuracy require a real-model test."],
            )
        )
    entries.append(embedding_preflight(settings, no_ai))
    profile = settings.reasoning_profile
    ready = bool(profile and profile.enabled and "text" in profile.modalities and not no_ai)
    if profile and profile.execution == "remote":
        ready = (
            ready
            and not settings.offline
            and settings.remote_media_consent
            and "text" in profile.allowed_data
        )
    if profile and profile.api_key_env:
        ready = ready and bool(os.environ.get(profile.api_key_env))
    entries.append(
        CapabilityEntry(
            id="reasoning",
            status="optional_prepared" if ready else "unavailable",
            reason="Configured policy permits an explicit request; endpoint not contacted."
            if ready
            else "Requires an enabled text profile and configured credentials; "
            "remote execution also needs online consent and allowed text transfer.",
            commands=[["analyze", "video"]],
            limitations=["Host subscriptions do not configure or authorize engine model requests."],
        )
    )
    available(
        "source_workflows",
        "Bounded planning, durable attempts and source-only saved reports; no model required.",
        ["workflow", "plan"],
        ["workflow", "run"],
        ["workflow", "show"],
        ["workflow", "report"],
        ["workflow", "maintenance"],
        ["workflow", "maintain"],
        limitations=[
            "Native-source lane supports ingest/report; assisted media and "
            "reconstruction are separate capabilities."
        ],
    )
    available(
        "assisted_content_workflows",
        "Post URL plus authorized local originals reaches existing video/photo/carousel services.",
        ["workflow", "plan"],
        ["workflow", "run"],
        ["workflow", "report"],
        prerequisites=["Supplied originals and an explicit user permission declaration."],
        limitations=["No cold URL media acquisition, profile scope or remote model transfer."],
    )
    entries.append(
        CapabilityEntry(
            id="youtube_native_metadata",
            status="available"
            if not settings.offline and os.environ.get(settings.youtube_api_key_env)
            else "unavailable",
            reason="Official one-post native metadata adapter; no endpoint contacted.",
            commands=[["workflow", "run"]],
            prerequisites=[
                "Valid API key, online permission and verified matching retention timer."
            ],
            limitations=[
                "Credential validity and scheduler are not verified by this cheap preflight.",
                "No media, captions, comments, account enumeration or derived analytics.",
            ],
        )
    )
    unimplemented: tuple[tuple[str, CapabilityState, str], ...] = (
        (
            "live_platform_connectors",
            "planned",
            "Broad live acquisition is planned; only one YouTube post's native metadata ships. "
            "Instagram, TikTok, profiles and audiovisual acquisition are not implemented.",
        ),
        (
            "publishing_execution",
            "unavailable",
            "No posting, account editing, ad spend or recruitment tools.",
        ),
        (
            "proprietary_ranking_weights",
            "unavailable",
            "Observable associations cannot recover exact proprietary weights.",
        ),
        ("html_reports", "unavailable", "Use the tested JSON and Markdown report consumers."),
    )
    for identity, state, reason in unimplemented:
        entries.append(CapabilityEntry(id=identity, status=state, reason=reason))
    return CapabilityManifest(
        engine_version=__version__,
        capabilities=entries,
        policy={
            "offline": settings.offline,
            "no_ai": no_ai,
            "allow_download": settings.allow_download,
            "remote_media_consent": settings.remote_media_consent,
            "network_attempted": False,
            "inference_attempted": False,
            "library_opened": False,
        },
        resource_limits={
            key: getattr(settings, key)
            for key in (
                "max_media_bytes",
                "max_image_bytes",
                "max_image_pixels",
                "max_duration_seconds",
                "max_decode_frames",
                "media_timeout_seconds",
                "max_enrichment_frames",
                "inference_timeout_seconds",
                "inference_threads",
                "max_input_tokens",
                "max_output_tokens",
            )
        },
        limitations=[
            "Interface availability is not corpus coverage, permission or evidence sufficiency.",
            "Database, graph, index and endpoints were not checked; use doctor for library health.",
            "Resource limits are ceilings, not predicted runtime, RAM, disk use or monetary cost.",
        ],
    ).model_dump(mode="json")
