import json
import runpy
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prepare_host_acceptance.py"
prepare = runpy.run_path(str(SCRIPT))["prepare"]


@pytest.mark.parametrize(
    "host,folder", [("codex", ".agents"), ("claude-code", ".claude"), ("opencode", ".opencode")]
)
def test_preparation_only_exports_public_instructions_and_synthetic_inputs(
    tmp_path, monkeypatch, host, folder
):
    engine = tmp_path / "socialdna"
    engine.write_text("synthetic executable placeholder, never executed")
    project = tmp_path / "temporary project"
    project.mkdir()
    monkeypatch.setattr("tempfile.mkdtemp", lambda **kwargs: str(project))
    commands = []

    def export(arguments, **kwargs):
        commands.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({"data": {"files": []}}))

    monkeypatch.setattr(subprocess, "run", export)
    result = prepare(engine, host)
    assert result == project
    assert len(commands) == 1 and commands[0][0] == str(engine)
    assert commands[0][3:5] == ["skill", "export"]
    assert (project / folder / "skills").is_dir()
    fixture = json.loads((project / "fixture.json").read_text())
    assert fixture["synthetic"] and not fixture["network_authorized"]
    assert not fixture["host_conversation_executed"]
    assert Path(fixture["media"]).is_file()
    assert "--offline --no-ai" in (project / "prompt.txt").read_text()
    assert not (project / "library").exists()
