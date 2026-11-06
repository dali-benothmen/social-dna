import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from socialdna.application.setup_service import guidance
from socialdna.application.skill_service import BUNDLES, catalog
from socialdna.cli.app import app
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.workflows import IMPLEMENTED_TASKS, TASK_NAMES


def test_photo_setup_needs_neither_video_tools_models_nor_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("SOCIALDNA_YOUTUBE_API_KEY", raising=False)
    data = guidance(
        Settings(data_dir=tmp_path / "data", offline=True),
        task="analyze",
        input_kind="image",
        project_dir=tmp_path,
    )
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / ".agents").exists()
    assert all(not value for value in data["policy"].values())
    assert "video_tools" not in {item["code"] for item in data["diagnostics"]}
    assert next(d for d in data["diagnostics"] if d["code"] == "models")["state"] == "not_required"
    assert next(s for s in data["next_steps"] if s["id"] == "report")["bindings"] == {
        "run_id": "analyze.data.run_id"
    }


@pytest.mark.parametrize(
    "host,directory", [("codex", ".agents"), ("claude-code", ".claude"), ("opencode", ".opencode")]
)
def test_setup_hosts_never_install(tmp_path, host, directory):
    data = guidance(Settings(data_dir=tmp_path / "data"), host=host, project_dir=tmp_path)
    assert Path(data["destination"]) == tmp_path / directory / "skills" / "social-dna-report"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "key,offline,state",
    [(False, False, "blocked"), (True, False, "unverified"), (True, True, "blocked")],
)
def test_native_setup_does_not_certify_or_leak_credentials(
    tmp_path, monkeypatch, key, offline, state
):
    monkeypatch.setenv("CUSTOM_PRIVATE_KEY_NAME", "secret-canary" if key else "")
    result = guidance(
        Settings(
            data_dir=tmp_path / "data",
            offline=offline,
            youtube_api_key_env="CUSTOM_PRIVATE_KEY_NAME",
        ),
        url="https://youtu.be/EaYRjrQuxEk",
    )
    assert next(d for d in result["diagnostics"] if d["code"] == "native_access")["state"] == state
    assert "secret-canary" not in json.dumps(result)
    assert "CUSTOM_PRIVATE_KEY_NAME" not in json.dumps(result)
    assert next(s for s in result["next_steps"] if s["id"] == "run")["bindings"] == {
        "workflow_id": "plan.data.workflow_id"
    }
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "url", ["https://www.instagram.com/p/abc/", "https://www.tiktok.com/@demo/video/123"]
)
def test_other_platforms_are_not_claimed_connected(tmp_path, url):
    data = guidance(Settings(data_dir=tmp_path / "data"), url=url)
    assert "not fetched" in next(d for d in data["diagnostics"] if d["code"] == "source")["message"]
    assert not any(step["id"] == "run" for step in data["next_steps"])


@pytest.mark.parametrize("task", TASK_NAMES)
def test_task_catalog_and_planned_specialists_remain_truthful(tmp_path, task):
    result = guidance(Settings(data_dir=tmp_path / "data"), task="social-dna-" + task)
    if task not in IMPLEMENTED_TASKS:
        assert result["status"] == "partial"
        assert not any(step["id"] == "export" for step in result["next_steps"])
    assert len(catalog()["bundles"]) == len(BUNDLES) == 9
    assert len(catalog()["planned"]) == 6


@pytest.mark.parametrize(
    "options",
    [
        {"host": "invalid"},
        {"task": "fake"},
        {"scope": "profile"},
        {"task": "reconstruct", "input_kind": "image"},
        {"task": "analyze", "url": "https://www.instagram.com/demo/"},
        {"url": "https://youtu.be/EaYRjrQuxEk?key=secret"},
    ],
)
def test_setup_invalid_inputs_do_not_write(tmp_path, options):
    with pytest.raises(ConfigurationError):
        guidance(Settings(data_dir=tmp_path / "data"), **options)
    assert not list(tmp_path.iterdir())


def test_video_missing_tools_is_actionable_not_storage_corruption(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    result = CliRunner().invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "--format",
            "json",
            "setup",
            "--task",
            "analyze",
            "--input-kind",
            "video",
        ],
    )
    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["status"] == "partial"
    assert "ffmpeg" in json.dumps(payload["data"]["diagnostics"])
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "arguments", [["skill", "list"], ["skill", "inspect", "--name", "social-dna-analyze"]]
)
def test_catalog_and_inspection_use_real_result_envelopes_without_storage(tmp_path, arguments):
    result = CliRunner().invoke(
        app, ["--data-dir", str(tmp_path / "data"), "--format", "json", *arguments]
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["schema_version"] == "1.0"
    assert not (tmp_path / "data").exists()
