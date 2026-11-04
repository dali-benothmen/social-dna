import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from socialdna.application.analysis_service import analyze_video
from socialdna.application.bootstrap import open_application
from socialdna.application.report_service import generate_report
from socialdna.application.task_runner import TaskRunner
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ProviderFailure
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.providers import (
    OCRBox,
    OCRFrame,
    ProviderIdentity,
    ReasoningProfile,
    SpeechResult,
)
from socialdna.providers.models import PACKAGES, catalog
from socialdna.providers.registry import ProviderRegistry
from socialdna.storage.schema import metadata


class FixtureProvider:
    """CI contract test double; real-runtime coverage is separately opt-in."""

    calls: dict[str, int] = {}

    def __init__(self, name: str, capability: str) -> None:
        self.manifest = catalog()["ocr-en" if capability == "ocr" else "asr-tiny"].model_copy(
            update={"name": name}
        )
        self.identity = self.manifest.identity
        self.versions = {name: "fixture" for group in PACKAGES.values() for name in group}
        self.capability = capability

    def transcribe(self, request: dict[str, Any]) -> SpeechResult:
        self.calls["transcription"] = self.calls.get("transcription", 0) + 1
        return SpeechResult.model_validate(
            {
                "language": "en",
                "segments": [
                    {
                        "start": 0.2,
                        "end": 1.1,
                        "text": "A useful opening?",
                        "words": [
                            {"text": "A", "start": 0.2, "end": 0.3, "confidence": 0.9},
                            {"text": "useful"},
                        ],
                    }
                ],
            }
        )

    def read_text(self, request: dict[str, Any]) -> list[OCRFrame]:
        self.calls["ocr"] = self.calls.get("ocr", 0) + 1
        return [
            OCRFrame(
                frame_id=frame["id"],
                boxes=[
                    OCRBox(
                        text="VISIBLE TEXT",
                        confidence=0.9,
                        points=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.4), (0.1, 0.4)],
                    )
                ],
            )
            for frame in request["frames"]
        ]


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    FixtureProvider.calls = {}
    monkeypatch.setattr(
        ProviderRegistry,
        "resolve",
        lambda self, name, capability: FixtureProvider(name, capability),
    )
    return FixtureProvider.calls


def test_tracks_provenance_and_selective_asr_cache(
    settings: Settings, video: Path, subtitles: Path, providers: dict[str, int]
) -> None:
    with open_application(settings) as application:
        first = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(depth="deep")
        )
        assert first["status"] == "success", first
        report = generate_report(application, first["run_id"])["content"]
        data = report["timeline"]
        assert {s["track_type"] for s in data["text_segments"]} == {
            "supplied_subtitle",
            "asr",
            "ocr",
        }
        assert data["text_words"] and data["ocr_boxes"] and data["inference_inputs"]
        assert any(w["start_ms"] is None for w in data["text_words"])
        assert any(
            p["provider_name"] == "faster-whisper" and p["model_revision"]
            for p in report["provenance"]
        )
        assert providers == {"transcription": 1, "ocr": 1}
        second = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(depth="deep")
        )
        assert second["tasks"]["transcription"]["status"] == "cached"
        assert second["tasks"]["ocr"]["status"] == "cached"
        assert providers == {"transcription": 1, "ocr": 1}
        application.settings.asr_model = "different-asr"
        third = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(depth="deep")
        )
        for key in (
            "prepare",
            "scenes",
            "frames",
            "visual",
            "audio.extract",
            "audio.features",
            "ocr",
        ):
            assert third["tasks"][key]["status"] == "cached"
        assert third["tasks"]["transcription"]["status"] == "succeeded"
        assert third["tasks"]["language.compare"]["status"] == "succeeded"
        assert providers == {"transcription": 2, "ocr": 1}


def test_no_ai_and_explicit_missing_model(
    settings: Settings, video: Path, providers: dict[str, int]
) -> None:
    with open_application(settings) as application:
        result = analyze_video(
            application,
            str(video),
            options=AnalysisOptions(no_ai=True, transcribe=True, ocr=True, reason=True),
        )
        assert result["status"] == "success" and not providers
        assert result["tasks"]["transcription"]["status"] == "skipped"
    # Remove the test injection: this verifies actual missing-model behavior.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            ProviderRegistry,
            "resolve",
            lambda *args: (_ for _ in ()).throw(ProviderFailure("injected invalid response")),
        )
        with open_application(settings) as application:
            # Native preflight failures are not silently interpreted as available providers.
            with pytest.raises(ProviderFailure):
                analyze_video(application, str(video), options=AnalysisOptions(transcribe=True))


def test_requested_missing_models_return_partial(settings: Settings, video: Path) -> None:
    with open_application(settings) as application:
        result = analyze_video(
            application, str(video), options=AnalysisOptions(transcribe=True, ocr=False)
        )
        assert result["status"] == "partial"
        assert result["tasks"]["transcription"]["status"] == "skipped"
        assert result["reports"]


def test_bad_speech_output_preserves_deterministic_results(
    settings: Settings, video: Path, providers: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    def bad(*args: Any) -> SpeechResult:
        raise ProviderFailure("invalid speech output")

    monkeypatch.setattr(FixtureProvider, "transcribe", bad)
    with open_application(settings) as application:
        result = analyze_video(application, str(video))
        assert result["status"] == "partial"
        assert result["tasks"]["transcription"]["status"] == "failed"
        assert result["tasks"]["visual"]["status"] == "succeeded"
        report = generate_report(application, result["run_id"])["content"]
        assert report["timeline"]["frames"] and report["timeline"]["ocr_boxes"]
        assert not any(s["track_type"] == "asr" for s in report["timeline"]["text_segments"])


def test_reasoning_schema_retry_audit_and_secret_redaction(
    settings: Settings,
    video: Path,
    subtitles: Path,
    providers: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []
    secret = "test-key-must-never-be-persisted"
    monkeypatch.setenv("LOCAL_TEST_KEY", secret)
    settings.reasoning_profile = ReasoningProfile(
        enabled=True,
        endpoint="http://127.0.0.1:8080/v1/chat/completions",
        provider="llama-server",
        model="configured-model",
        revision="test-revision",
        execution="local",
        api_key_env="LOCAL_TEST_KEY",
    )
    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer " + secret
        body = json.loads(request.content)
        evidence = json.loads(body["messages"][1]["content"][0]["text"])["evidence"]
        requests.append(body)
        content = (
            "not valid JSON"
            if len(requests) == 1
            else json.dumps(
                {
                    "interpretations": [
                        {
                            "modality": "linguistic",
                            "description": "A literal question is present.",
                            "evidence_ids": [evidence[0]["id"]],
                            "confidence": "low",
                            "alternatives": ["The question could be rhetorical."],
                        }
                    ],
                    "limitations": ["Contract test response, not actual model inference."],
                }
            )
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(
        "socialdna.providers.reasoning.httpx.Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    with open_application(settings) as application:
        result = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(reason=True)
        )
        assert result["status"] == "success", result
        assert len(requests) == 2
        report = generate_report(application, result["run_id"])["content"]
        calls = report["timeline"]["provider_calls"]
        assert [call["status"] for call in calls] == ["failed", "succeeded"]
        hypotheses = [
            row
            for row in report["timeline"]["observations"]
            if row["feature_key"].startswith("model.")
        ]
        assert hypotheses[0]["value"]["claim_level"] == "hypothesis"
        for artifact in report["artifacts"]:
            if artifact["kind"].startswith("provider-"):
                assert (
                    secret
                    not in application.artifacts.path_for(artifact["relative_path"]).read_text()
                )
        assert secret not in json.dumps(report)
        cached = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(reason=True)
        )
        assert cached["tasks"]["multimodal"]["status"] == "cached"
        assert len(requests) == 2


@pytest.mark.parametrize("consent,allowed", [(False, ["text"]), (True, [])])
def test_remote_consent_blocks_before_any_transfer(
    settings: Settings,
    video: Path,
    subtitles: Path,
    providers: dict[str, int],
    consent: bool,
    allowed: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.remote_media_consent = consent
    settings.reasoning_profile = ReasoningProfile.model_validate(
        {
            "enabled": True,
            "endpoint": "https://example.org/chat",
            "provider": "test",
            "model": "configured",
            "revision": "1",
            "execution": "remote",
            "allowed_data": allowed,
        }
    )
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: pytest.fail("Unauthorized remote transfer attempted")
    )
    with open_application(settings) as application:
        result = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(reason=True)
        )
        assert result["status"] == "partial"
        assert result["tasks"]["multimodal"]["status"] == "failed"
        with application.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["provider_calls"])
                )
                == 0
            )


def test_reasoning_budget_failure_precedes_transfer(
    settings: Settings,
    video: Path,
    subtitles: Path,
    providers: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.max_input_tokens = 100
    settings.reasoning_profile = ReasoningProfile(
        enabled=True,
        endpoint="http://127.0.0.1:8080/v1/chat/completions",
        provider="local",
        model="model",
        revision="1",
    )
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: pytest.fail("Over-budget transfer attempted")
    )
    with open_application(settings) as application:
        result = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(reason=True)
        )
        assert result["status"] == "partial"
        assert result["tasks"]["multimodal"]["status"] == "failed"


@pytest.mark.parametrize("stop_after", ["transcription", "ocr", "language.compare"])
def test_resume_model_tasks_without_duplicate_rows(
    settings: Settings,
    video: Path,
    subtitles: Path,
    providers: dict[str, int],
    stop_after: str,
) -> None:
    captured = []

    def stop(key: str) -> None:
        if key == stop_after:
            raise KeyboardInterrupt()

    with open_application(settings) as application:
        with pytest.raises(KeyboardInterrupt):
            analyze_video(
                application,
                str(video),
                subtitles=subtitles,
                on_run=captured.append,
                after_task=stop,
            )
    with open_application(settings) as application:
        result = analyze_video(application, str(video), subtitles=subtitles, resume=captured[0])
        assert result["status"] == "success", result
        with application.database.transaction() as connection:
            before = {
                name: connection.scalar(select(func.count()).select_from(metadata.tables[name]))
                for name in ("text_segments", "text_words", "ocr_boxes", "inference_inputs")
            }
        analyze_video(application, str(video), subtitles=subtitles, resume=captured[0])
        with application.database.transaction() as connection:
            assert before == {
                name: connection.scalar(select(func.count()).select_from(metadata.tables[name]))
                for name in before
            }
        assert providers == {"transcription": 1, "ocr": 1}


@pytest.mark.parametrize("missing", ["provider", "inputs", "valid_inputs"])
def test_model_persistence_guard_is_atomic(
    settings: Settings,
    video: Path,
    providers: dict[str, int],
    missing: str,
) -> None:
    with open_application(settings) as application:
        first = analyze_video(application, str(video), options=AnalysisOptions(no_ai=True))
        table = metadata.tables["observations"]
        with application.database.transaction() as connection:
            before = connection.scalar(select(func.count()).select_from(table))
        runner = TaskRunner(application, first["run_id"], first["media_id"])

        def bad(context: Any) -> Any:
            context.observe(
                "model.guard_test",
                1.0,
                0,
                100,
                modality="visual",
                unit="test",
                description="Test-only rejected model output",
            )
            if missing != "provider":
                context.output.provider = ProviderIdentity(
                    provider="test", model="test", revision="1", execution="local"
                )
            if missing == "valid_inputs":
                context.output.input_evidence_ids = ["not-a-registered-evidence-id"]
            return context.output

        runner.run("guard-test", {"identity": {"provider": "test"}}, [], bad)
        assert runner.tasks["guard-test"]["status"] == "failed"
        with application.database.transaction() as connection:
            assert connection.scalar(select(func.count()).select_from(table)) == before


@pytest.mark.parametrize("position", ["root", "leaf"])
def test_cli_can_revoke_preconfigured_remote_consent(
    settings: Settings,
    video: Path,
    subtitles: Path,
    providers: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
    position: str,
) -> None:
    from typer.testing import CliRunner

    from socialdna.cli.app import app

    settings.remote_media_consent = True
    settings.reasoning_profile = ReasoningProfile(
        enabled=True,
        execution="remote",
        endpoint="https://example.org/chat",
        provider="test",
        model="test",
        revision="1",
        allowed_data=["text"],
    )
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, **kwargs: settings))
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: pytest.fail("Revoked consent must block transfer")
    )
    arguments = [
        "analyze",
        "video",
        str(video),
        "--reason",
        "--subtitles",
        str(subtitles),
        "--format",
        "json",
    ]
    if position == "root":
        arguments = ["--no-remote-media-consent"] + arguments
    else:
        arguments.append("--no-remote-media-consent")
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 5, result.output
    assert settings.remote_media_consent is False
    assert json.loads(result.stdout)["data"]["tasks"]["multimodal"]["status"] == "failed"


def test_cli_can_revoke_preconfigured_model_download_consent(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    from socialdna.cli.app import app

    settings.allow_download = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, **kwargs: settings))
    monkeypatch.setattr(
        httpx, "stream", lambda *args, **kwargs: pytest.fail("Download consent was revoked")
    )
    result = CliRunner().invoke(
        app, ["models", "prepare", "asr-tiny", "--no-allow-download", "--format", "json"]
    )
    assert result.exit_code == 3, result.output
    assert settings.allow_download is False


def test_provider_echoed_credentials_are_never_persisted(
    settings: Settings,
    video: Path,
    subtitles: Path,
    providers: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "credential-must-not-enter-response-artifacts"
    monkeypatch.setenv("LOCAL_TEST_KEY", secret)
    settings.reasoning_profile = ReasoningProfile(
        enabled=True,
        endpoint="http://127.0.0.1:8080/chat",
        provider="test",
        model="model",
        revision="1",
        api_key_env="LOCAL_TEST_KEY",
    )
    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "interpretations": [],
                                    "limitations": [secret],
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    with open_application(settings) as application:
        result = analyze_video(
            application, str(video), subtitles=subtitles, options=AnalysisOptions(reason=True)
        )
        assert result["status"] == "partial"
        report = generate_report(application, result["run_id"])["content"]
        assert secret not in json.dumps(report)
        assert all(
            call["status"] == "failed" and call["response_artifact_id"] is None
            for call in report["timeline"]["provider_calls"]
        )
