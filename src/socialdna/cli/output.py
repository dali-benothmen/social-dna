import json
from typing import Literal

import typer

from socialdna.domain.results import ResultEnvelope

OutputFormat = Literal["text", "json"]


def emit(result: ResultEnvelope, output_format: OutputFormat) -> None:
    if output_format == "json":
        typer.echo(result.model_dump_json())
        return
    typer.echo(f"{result.command}: {result.status}")
    for key, value in result.data.items():
        typer.echo(f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
    for issue in result.warnings:
        typer.echo(f"Warning [{issue.code}]: {issue.message}", err=True)
    for issue in result.errors:
        typer.echo(f"Error [{issue.code}]: {issue.message}", err=True)
    for action in result.next_actions:
        typer.echo(f"Next: {action}", err=True)
