"""Static image and ordered carousel entry points; no downloads or research setup."""

from typing import Any

import typer
from pydantic import ValidationError

from socialdna.application import image_service
from socialdna.application.bootstrap import open_application
from socialdna.cli.common import ConfigFile, DataDir, Format, execute
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.images import ImageOptions


def options(
    ctx: typer.Context, palette_bins: int, max_side: int, ocr: bool, no_ai: bool
) -> ImageOptions:
    try:
        return ImageOptions(
            palette_bins=palette_bins,
            max_side=max_side,
            ocr=ocr,
            no_ai=no_ai or bool((ctx.find_root().obj or {}).get("no_ai")),
        )
    except ValidationError as exc:
        raise ConfigurationError(str(exc)) from exc


def register(analysis: typer.Typer) -> None:
    @analysis.command("image")
    def image(
        ctx: typer.Context,
        target: str,
        copy_media: bool = False,
        resume: str | None = None,
        palette_bins: int = 8,
        max_side: int = 1024,
        ocr: bool = False,
        no_ai: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Analyze static raster bytes or an image ID with exact asset/region citations."""

        def operation(settings: Settings) -> dict[str, Any]:
            selected = options(ctx, palette_bins, max_side, ocr, no_ai)
            with open_application(settings) as app:
                return image_service.analyze_image(
                    app, target, options=selected, copy_media=copy_media, resume=resume
                )

        execute(ctx, "analyze.image", operation, data_dir, config, output_format)

    @analysis.command("carousel")
    def carousel(
        ctx: typer.Context,
        post_id: str,
        max_items: int = 20,
        palette_bins: int = 8,
        max_side: int = 1024,
        ocr: bool = False,
        no_ai: bool = False,
        data_dir: DataDir = None,
        config: ConfigFile = None,
        output_format: Format = None,
    ) -> None:
        """Analyze supplied ordered carousel items; remote and unsupported items stay explicit."""

        def operation(settings: Settings) -> dict[str, Any]:
            selected = options(ctx, palette_bins, max_side, ocr, no_ai)
            if not 1 <= max_items <= 100:
                raise ConfigurationError("max_items must be between 1 and 100")
            with open_application(settings) as app:
                return image_service.analyze_carousel(
                    app, post_id, options=selected, max_items=max_items
                )

        execute(ctx, "analyze.carousel", operation, data_dir, config, output_format)
