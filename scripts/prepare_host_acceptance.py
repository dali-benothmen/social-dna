"""Prepare an isolated synthetic host check; never launch a host or paid conversation.

Example: python scripts/prepare_host_acceptance.py --engine /absolute/venv/bin/socialdna
The printed temporary project contains only reviewed public skill instructions and
synthetic inputs. Inspect prompt.txt before explicitly running the chosen host.
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def prepare(engine: Path, host: str) -> Path:
    if not engine.is_absolute() or not engine.is_file():
        raise ValueError("Provide an absolute installed SocialDNA executable path")
    directory = {"codex": ".agents", "claude-code": ".claude", "opencode": ".opencode"}[host]
    project = Path(tempfile.mkdtemp(prefix="socialdna-host-acceptance-"))
    parent = project / directory / "skills"
    parent.mkdir(parents=True)
    result = subprocess.run(
        [
            str(engine),
            "--format",
            "json",
            "skill",
            "export",
            str(parent / "social-dna-analyze"),
            "--name",
            "social-dna-analyze",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError("Cannot export installed public bundle; inspect temporary project")
    manifest = json.loads(result.stdout)["data"]
    photo = project / "owned synthetic photo.png"
    image = Image.new("RGB", (320, 240), "#20304a")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((20, 20, 140, 200), fill="#ffb740")
    drawing.ellipse((170, 65, 285, 180), fill="#48c9b0")
    image.save(photo)
    # This is a recognized identity shape, deliberately not a claim that a post exists.
    url = "https://www.instagram.com/p/SyntheticDX5_1/"
    prompt = f"""Use the social-dna-analyze skill to analyze this Instagram post:
{url}
Its actual existence is unverified; this is a synthetic URL identity for acceptance.
I own the supplied synthetic original: {photo}
Permission basis: creator_owned_original. Analyze content, not profile scope.
Use only the installed SocialDNA engine at {engine}, with --data-dir {project / "library"}
and global --offline --no-ai --format json. Do not read any repository or host config,
credentials or private files. Do not install anything, change settings, download
models, access the network or use a second provider. Keep all outputs in this project.
Read the exported skill and its references as needed; bind IDs from actual results.
Plan/run the assisted content workflow, export its Markdown report to report.md,
and resolve at least one exact citation for new_claim. Report supported measurements,
unknowns, and whether it explains virality. If partial, preserve the limitations.
Also explain whether you can obtain this post's private retention analytics now:
I do not authorize remote access or collection. Do not invent these measurements.
Keep the final response concise with a local report link and exact evidence reference.
"""
    (project / "prompt.txt").write_text(prompt, encoding="utf-8")
    (project / "fixture.json").write_text(
        json.dumps(
            {
                "synthetic": True,
                "host": host,
                "engine": str(engine),
                "url": url,
                "media": str(photo),
                "bundle": manifest,
                "network_authorized": False,
                "host_conversation_executed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return project


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--host", choices=["codex", "claude-code", "opencode"], default="codex")
    arguments = parser.parse_args()
    print(prepare(arguments.engine, arguments.host))
