"""Installed-package acceptance using an explicitly synthetic HTTP transport, never live data."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import httpx

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.workflow_report_service import generate
from socialdna.config.settings import Settings
from socialdna.domain.workflows import WorkflowRequest


def main() -> None:
    settings = Settings(data_dir=Path(sys.argv[1]), offline=False)
    fixture = {
        "items": [
            {
                "id": "EaYRjrQuxEk",
                "snippet": {
                    "channelId": "UC" + "z" * 22,
                    "title": "Synthetic installed-transport fixture, not live source evidence",
                    "publishedAt": "2026-01-01T00:00:00Z",
                },
                "statistics": {"viewCount": "123"},
            }
        ]
    }
    with (
        patch.dict(os.environ, {settings.youtube_api_key_env: "synthetic-test-key"}),
        patch("socialdna.application.workflow_maintenance.verified", return_value=True),
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=fixture))
        ) as client,
    ):
        identity = workflow_service.plan(
            settings, WorkflowRequest(url="https://www.youtube.com/shorts/EaYRjrQuxEk")
        )["workflow_id"]
        result = workflow_service.run(settings, identity, client=client)
    if result["status"] != "success" or not result["network_attempted"]:
        raise RuntimeError("Installed synthetic capture/report did not complete")
    settings.offline = True
    with open_application(settings) as application:
        saved = generate(application, identity)
        markdown = generate(application, identity, "markdown")
    if saved["content"] != result["content"] or "123" not in markdown["content"]:
        raise RuntimeError("Installed frozen source report did not survive reopening")
    if workflow_service.run(settings, identity)["network_attempted"]:
        raise RuntimeError("Installed resume made an unexpected request")
    print("PASS: installed synthetic source capture, citations, frozen report and resume")


if __name__ == "__main__":
    main()
