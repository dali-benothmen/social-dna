"""Evidence-qualified, explicitly non-executing strategy records."""

from pathlib import Path
from typing import Annotated, Any

import typer

from socialdna.application import recommendation_service as service
from socialdna.application.bootstrap import open_application
from socialdna.application.literature_service import read_spec
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.research.recommendations import RecommendationSpec
from socialdna.storage.evidence_repository import EvidenceRepository


def register(app: typer.Typer) -> None:
    recommendations = typer.Typer(
        help="Preserve original strategies, exact evidence and a next test; never execute."
    )
    app.add_typer(recommendations, name="recommendation")

    @recommendations.command("create")
    def create_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            parsed = read_spec(spec, RecommendationSpec)
            with open_application(settings) as app:
                return service.create(app, parsed)

        execute(ctx, "recommendation.create", operation, data_dir, config, output_format)

    @recommendations.command("show")
    def show_command(
        ctx: typer.Context,
        identity: str,
        revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                with app.database.transaction() as connection:
                    repo = EvidenceRepository(connection)
                    ref = (
                        repo.ref(repo.get("entity_revisions", revision))
                        if revision
                        else repo.latest("recommendation", identity)
                    )
                    if ref is None or ref.id != identity or ref.kind != "recommendation":
                        raise ConfigurationError("Exact recommendation identity/revision mismatch")
                return service.show(app, ref)

        execute(ctx, "recommendation.show", operation, data_dir, config, output_format)
