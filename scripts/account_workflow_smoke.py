"""Installed-package assisted profile/account smoke; synthetic inputs, no platform access."""

import json
import sys
from pathlib import Path

from PIL import Image

from socialdna.application import workflow_service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.profile_audit_service import observe
from socialdna.application.workflow_report_service import generate
from socialdna.config.settings import Settings
from socialdna.domain.workflows import WorkflowRequest


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True)
    photo = root / "synthetic.png"
    Image.new("RGB", (80, 60), "orange").save(photo)
    settings = Settings(data_dir=root / "library", offline=True)
    url = "https://www.instagram.com/example/"
    export = root / "synthetic-account.json"
    export.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "installed-synthetic-account",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:synthetic:account",
                },
                "records": [
                    {
                        "record_type": "account",
                        "platform": "instagram",
                        "external_id": "001",
                        "handle": "example",
                    },
                    {
                        "record_type": "post",
                        "platform": "instagram",
                        "external_id": "ABC123",
                        "account_external_id": "001",
                        "published_at": "2025-01-01T00:00:00Z",
                        "content_type": "photo",
                        "url": "https://www.instagram.com/p/ABC123/",
                        "title": "Synthetic ordinary post",
                    },
                    {
                        "record_type": "media",
                        "platform": "instagram",
                        "post_external_id": "ABC123",
                        "uri": str(photo),
                    },
                ],
            }
        )
    )
    if not import_dataset(settings, export, "json")["valid"]:
        raise RuntimeError("Installed account import failed")
    observed = observe(
        settings,
        url,
        external_id="001",
        captured_at="2025-02-01T00:00:00Z",
        permission_basis="creator_owned_export",
        source_description="Synthetic installed-package fixture",
        username="example",
        bio="",
        photo=photo,
    )
    profile = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="analyze",
            scope="profile",
            url=url,
            profile_revision=observed["snapshot"]["revision_id"],
        ),
    )["workflow_id"]
    audit = workflow_service.run(settings, profile)
    if audit["content"]["review_state"] != "unreviewed_proposal":
        raise RuntimeError("Installed profile report fabricated review state")
    request = WorkflowRequest(
        mode="research",
        url=url,
        goal="Study the actual synthetic corpus",
        analyze_media=True,
        permission_basis="creator_owned_original",
        context_revisions=(observed["snapshot"]["revision_id"],),
    )
    identity = workflow_service.plan(settings, request)["workflow_id"]
    first = workflow_service.run(settings, identity)
    if (
        first["content"]["posts"][0]["status"] != "media_analyzed"
        or first["content"]["research_state"] != "draft"
    ):
        raise RuntimeError("Installed account did not execute real local media/draft services")
    refresh = workflow_service.plan(
        settings, request.model_copy(update={"refresh_from": identity})
    )["workflow_id"]
    if workflow_service.run(settings, refresh)["content"]["posts"][0]["status"] != "media_reused":
        raise RuntimeError("Installed account did not reuse eligible unchanged media")
    with open_application(settings) as app:
        if generate(app, identity)["content"] != first["content"]:
            raise RuntimeError("Installed account changed its frozen report")
    print(
        "PASS: installed synthetic profile proposals, account media dispatch, cited draft, "
        "explicit reuse and frozen reload; no live acquisition"
    )


if __name__ == "__main__":
    main()
