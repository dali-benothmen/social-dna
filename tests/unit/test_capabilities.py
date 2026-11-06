from pathlib import Path

import pytest

from socialdna.application.capability_service import capabilities, embedding_preflight
from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable
from socialdna.domain.capabilities import CapabilityManifest
from socialdna.domain.providers import ReasoningProfile
from socialdna.providers.models import PACKAGES, ModelStore
from socialdna.providers.registry import LocalProvider, ProviderRegistry


def index(settings: Settings, **kwargs: bool) -> dict:
    result = CapabilityManifest.model_validate(capabilities(settings, **kwargs))
    assert len({entry.id for entry in result.capabilities}) == len(result.capabilities)
    assert not settings.data_dir.exists()
    assert not result.policy["network_attempted"]
    assert not result.policy["inference_attempted"]
    assert not result.policy["library_opened"]
    return {entry.id: entry.model_dump() for entry in result.capabilities}


def test_core_only_no_ai_and_missing_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("socialdna.application.capability_service.shutil.which", lambda _: None)

    def forbidden(*args: object) -> None:
        raise AssertionError("No-AI preflight must not resolve providers")

    monkeypatch.setattr(ProviderRegistry, "resolve", forbidden)
    entries = index(Settings(data_dir=tmp_path / "absent", offline=True), no_ai=True)
    assert entries["local_video"]["status"] == "unavailable"
    assert (
        entries["static_media"]["status"] == entries["account_analytics"]["status"] == "available"
    )
    assert entries["psychological_research"]["status"] == "available"
    assert entries["ocr"]["status"] == "unavailable"
    assert entries["live_platform_connectors"]["status"] == "planned"
    assert entries["publishing_execution"]["status"] == "unavailable"
    assert {
        "production",
        "platform_distribution",
        "publishing_search",
        "profile_funnel",
    } <= entries.keys()


@pytest.mark.parametrize("ready", [True, False])
def test_provider_preparation_is_not_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ready: bool
) -> None:
    calls = []

    def resolve(self: object, name: str, capability: str) -> None:
        calls.append(capability)
        if not ready:
            raise DependencyUnavailable("Controlled missing weights or runtime")

    monkeypatch.setattr(ProviderRegistry, "resolve", resolve)
    entries = index(Settings(data_dir=tmp_path / "absent", offline=True))
    assert len(calls) == 4
    assert entries["ocr"]["status"] == ("optional_prepared" if ready else "unavailable")
    assert entries["alignment"]["status"] == "unavailable"
    assert entries["semantic_memory"]["prerequisites"]


@pytest.mark.parametrize(
    ("offline", "consent", "enabled", "no_ai", "expected"),
    [
        (True, True, True, False, False),
        (False, False, True, False, False),
        (False, True, False, False, False),
        (False, True, True, True, False),
        (False, True, True, False, True),
    ],
)
def test_remote_reasoning_policy_never_contacts_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offline: bool,
    consent: bool,
    enabled: bool,
    no_ai: bool,
    expected: bool,
) -> None:
    monkeypatch.setenv("SECRET_TEST_KEY", "must-never-appear")
    settings = Settings(
        data_dir=tmp_path / "absent",
        offline=offline,
        remote_media_consent=consent,
        reasoning_profile=ReasoningProfile(
            enabled=enabled,
            endpoint="https://example.invalid/v1",
            provider="test",
            model="test",
            revision="test",
            execution="remote",
            api_key_env="SECRET_TEST_KEY",
            allowed_data=["text"],
        ),
    )
    entries = index(settings, no_ai=no_ai)
    assert (entries["reasoning"]["status"] == "optional_prepared") == expected
    assert "SECRET_TEST_KEY" not in str(entries)
    assert "must-never-appear" not in str(entries)


def test_corrupt_model_catalog_is_local_unavailable_not_core_failure(tmp_path: Path) -> None:
    root = tmp_path / "data"
    catalog = root / "models" / "catalog"
    catalog.mkdir(parents=True)
    (catalog / "broken.json").write_text('"password-do-not-echo"')
    result = capabilities(Settings(data_dir=root))
    entries = {entry["id"]: entry for entry in result["capabilities"]}
    assert entries["ocr"]["status"] == "unavailable"
    assert entries["static_media"]["status"] == "available"
    assert "password-do-not-echo" not in str(result)
    assert not (root / "socialdna.db").exists()


@pytest.mark.parametrize("denial", ["credential", "data"])
def test_remote_preflight_requires_allowed_data_and_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denial: str
) -> None:
    monkeypatch.delenv("SECRET_TEST_KEY", raising=False)
    if denial == "data":
        monkeypatch.setenv("SECRET_TEST_KEY", "controlled")
    settings = Settings(
        data_dir=tmp_path / "absent",
        remote_media_consent=True,
        reasoning_profile=ReasoningProfile(
            enabled=True,
            endpoint="https://example.invalid/v1",
            provider="test",
            model="test",
            revision="test",
            execution="remote",
            api_key_env="SECRET_TEST_KEY",
            allowed_data=["text"] if denial == "credential" else [],
        ),
    )
    assert index(settings)["reasoning"]["status"] == "unavailable"


@pytest.mark.parametrize("runtime_ready", [False, True])
def test_embedding_preflight_checks_metadata_but_not_space_or_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime_ready: bool
) -> None:
    from types import SimpleNamespace

    model = SimpleNamespace(
        capability="text_embedding", identity=SimpleNamespace(provider="sentence-transformers")
    )
    monkeypatch.setattr(ModelStore, "manifests", lambda _: {"fixture": model})
    monkeypatch.setattr(ModelStore, "verify", lambda *_: tmp_path)
    versions = {
        package: "controlled" if runtime_ready else None for package in PACKAGES["text_embedding"]
    }
    monkeypatch.setattr(
        LocalProvider, "__init__", lambda self, *_: setattr(self, "versions", versions)
    )
    settings = Settings(data_dir=tmp_path / "absent", offline=True)
    result = embedding_preflight(settings, False)
    assert result.status == ("optional_prepared" if runtime_ready else "unavailable")
    assert result.prerequisites and result.limitations
    assert not settings.data_dir.exists()
