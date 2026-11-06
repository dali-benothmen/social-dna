"""Installed-package assisted-media acceptance; synthetic originals, no network."""

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


if __name__ == "__main__":
    main()
