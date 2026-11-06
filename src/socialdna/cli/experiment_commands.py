"""Explicit analysis-only experiment lifecycle adapters."""

from pathlib import Path
from typing import Annotated, Any

import typer

from socialdna.application import experiment_service as service
from socialdna.application.bootstrap import open_application
from socialdna.application.literature_service import read_spec
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.evidence import EntityRef
from socialdna.research.experiments import ExperimentResults, ExperimentSpec
from socialdna.storage.evidence_repository import EvidenceRepository


def register(app: typer.Typer) -> None:
    experiments = typer.Typer(
        help="Register plans and analyze authorized outcomes; never execute experiments."
    )
    app.add_typer(experiments, name="experiment")

    @experiments.command("register")
    def register_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            parsed = read_spec(spec, ExperimentSpec)
            with open_application(settings) as app:
                return service.register(app, parsed)

        execute(ctx, "experiment.register", operation, data_dir, config, output_format)

    @experiments.command("import-results")
    def results_command(
        ctx: typer.Context,
        spec: Annotated[Path, typer.Option("--spec")],
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            parsed = read_spec(spec, ExperimentResults)
            with open_application(settings) as app:
                return service.import_results(app, parsed)

        execute(ctx, "experiment.import-results", operation, data_dir, config, output_format)

    def reference(app: Any, kind: str, identity: str, revision: str | None) -> EntityRef:
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            ref = (
                repo.ref(repo.get("entity_revisions", revision))
                if revision
                else repo.latest(kind, identity)
            )
            if not ref or ref.id != identity or ref.kind != kind:
                raise ConfigurationError("Exact experiment identity/kind/revision mismatch")
            return ref

    @experiments.command("analyze")
    def analyze_command(
        ctx: typer.Context,
        identity: str,
        revision: str | None = None,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            with open_application(settings) as app:
                return service.analyze(
                    app, reference(app, "experiment_results", identity, revision)
                )

        execute(ctx, "experiment.analyze", operation, data_dir, config, output_format)

    @experiments.command("show")
    def show_command(
        ctx: typer.Context,
        identity: str,
        kind: str = "experiment_registration",
        revision: str | None = None,
        reproduce: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        def operation(settings: Settings) -> dict[str, Any]:
            if kind not in (
                "experiment_registration",
                "experiment_results",
                "experiment_analysis",
                "experiment_assessment",
            ):
                raise ConfigurationError("Unsupported experiment record kind")
            with open_application(settings) as app:
                return service.show(
                    app, reference(app, kind, identity, revision), reproduce=reproduce
                )

        execute(ctx, "experiment.show", operation, data_dir, config, output_format)
