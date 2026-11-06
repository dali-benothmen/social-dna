import httpx
import pytest

from socialdna.application import workflow_maintenance
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.acquisition import CaptureFailure
from socialdna.ingestion.connectors import youtube
from socialdna.ingestion.urls import parse_url


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/EaYRjrQuxEk?si=tracking",
        "https://www.youtube.com/shorts/EaYRjrQuxEk",
        "https://m.youtube.com/watch?v=EaYRjrQuxEk&feature=share",
    ],
)
def test_youtube_aliases_have_one_canonical_identity(url) -> None:
    target = parse_url(url)
    assert target.external_id == "EaYRjrQuxEk"
    assert target.canonical_url == "https://www.youtube.com/watch?v=EaYRjrQuxEk"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.youtube.com/watch?v=EaYRjrQuxEk",
        "https://youtube.com.evil/shorts/EaYRjrQuxEk",
        "https://youtube.com:443/shorts/EaYRjrQuxEk",
        "https://user:secret@youtube.com/shorts/EaYRjrQuxEk",
        "https://127.0.0.1/watch?v=EaYRjrQuxEk",
        "https://vm.tiktok.com/abc",
        "https://youtube.com/watch?v=EaYRjrQuxEk&v=abcdefghijk",
        "https://youtube.com/shorts/EaYRjrQuxEk?API_KEY=secret",
        "file:///tmp/video",
    ],
)
def test_unsafe_or_ambiguous_urls_rejected_without_echo(url) -> None:
    with pytest.raises(ConfigurationError) as exc:
        parse_url(url)
    assert "secret" not in str(exc.value).replace("secret-bearing", "")


@pytest.mark.parametrize(
    "status,headers,body,code",
    [
        (403, {}, b"secret-provider-body", "youtube_access_denied"),
        (429, {"Retry-After": "99999"}, b"secret-provider-body", "youtube_retry_later"),
        (302, {"Location": "http://127.0.0.1/secret"}, b"", "youtube_response_unavailable"),
        (200, {"Content-Type": "text/html"}, b"secret-provider-body", "invalid_response"),
        (200, {"Content-Type": "application/json"}, b'{"items":[],"items":[]}', "invalid_response"),
        (200, {"Content-Type": "application/json"}, b'{"items":[]}', "post_not_returned"),
        (
            200,
            {"Content-Type": "application/json", "Content-Length": "9999999"},
            b"{}",
            "response_budget_exceeded",
        ),
    ],
)
def test_provider_failure_is_bounded_and_sanitized(status, headers, body, code) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers=headers, content=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CaptureFailure) as exc:
            youtube.fetch("EaYRjrQuxEk", "secret-key", client=client)
    assert exc.value.code == code and len(calls) == 1
    assert "secret" not in str(exc.value)
    if status == 429:
        assert exc.value.retry_after == 3600


def test_dns_refuses_private_api_resolution(monkeypatch) -> None:
    monkeypatch.setattr(
        youtube.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))]
    )
    with pytest.raises(CaptureFailure, match="non-public"):
        youtube.fetch("EaYRjrQuxEk", "secret-key")


def test_maintenance_exports_only_and_verifies_exact_active_units(settings, tmp_path, monkeypatch):
    exported = tmp_path / "units"
    monkeypatch.setattr(workflow_maintenance.shutil, "which", lambda _: "/usr/bin/systemctl")
    expected = workflow_maintenance.units(settings)
    for name, content in expected.items():
        exported.mkdir(exist_ok=True)
        (exported / name).write_text(content)

    def properties(program, name):
        return {
            "FragmentPath": str(exported / name),
            "NeedDaemonReload": "no",
            "DropInPaths": "",
            "ActiveState": "active",
            "Unit": name[:-6] + ".service",
        }

    monkeypatch.setattr(workflow_maintenance, "_properties", properties)
    assert workflow_maintenance.verified(settings)
    service = next(exported.glob("*.service"))
    assert "--offline" in service.read_text() and "--no-ai" in service.read_text()
    service.write_text(service.read_text() + "# changed\n")
    assert not workflow_maintenance.verified(settings)
    output = tmp_path / "export-only"
    result = workflow_maintenance.configuration(settings, output)
    assert not result["host_configuration_changed"] and output.is_dir()
    with pytest.raises(ConfigurationError):
        workflow_maintenance.configuration(settings, output)
