"""Installed-package assisted-media acceptance; synthetic originals, no network."""

import subprocess
import sys
from pathlib import Path

from PIL import Image

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.workflow_report_service import generate
from socialdna.config.settings import Settings
from socialdna.domain.workflows import WorkflowRequest


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True)
    image = root / "owned.png"
    Image.new("RGB", (80, 60), "red").save(image)
    settings = Settings(data_dir=root / "library", offline=True)
    identity = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="analyze",
            url="https://www.instagram.com/p/ABC123/",
            media=(str(image),),
            permission_basis="creator_owned_original",
        ),
    )["workflow_id"]
    first = workflow_service.run(settings, identity)
    with open_application(settings) as app:
        saved = generate(app, identity)
    if saved["content"] != first["content"] or saved["network_attempted"]:
        raise RuntimeError("Assisted content report did not survive reopening offline")
    if not saved["content"]["analyses"][0]["report"]["evidence"]:
        raise RuntimeError("Installed analysis has no exact evidence")
    print("PASS: installed assisted media binding, real image measurements and frozen report")
    video = root / "owned.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x48:r=5:d=1",
            "-c:v",
            "ffv1",
            "-threads",
            "1",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    captions = root / "owned.srt"
    captions.write_text(
        "1\n00:00:00,100 --> 00:00:00,700\nOwned synthetic caption.\n", encoding="utf-8"
    )
    reconstruction = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="reconstruct",
            url="https://youtu.be/AAAAAAAAAAA",
            media=(str(video),),
            permission_basis="creator_owned_original",
            subtitles=str(captions),
            reconstruction={"allow_verbatim": True},
        ),
    )["workflow_id"]
    first = workflow_service.run(settings, reconstruction)
    with open_application(settings) as app:
        saved = generate(app, reconstruction)
        markdown = generate(app, reconstruction, "markdown")
    if saved["content"] != first["content"] or not saved["content"]["transcript_row_ids"]:
        raise RuntimeError("Installed reconstruction lost actual source captions or frozen output")
    if "Owned synthetic caption." not in markdown["content"]:
        raise RuntimeError("Installed reconstruction lost readable script content")
    if (
        saved["network_attempted"]
        or saved["content"]["modality_coverage"]["speech"] != "no_audio_stream"
    ):
        raise RuntimeError("Installed reconstruction invented audio or attempted acquisition")
    print("PASS: installed video reconstruction, source captions, exact cues and saved script")


if __name__ == "__main__":
    main()
