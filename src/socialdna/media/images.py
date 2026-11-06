"""Bounded static raster decoding and metadata-free display derivatives."""

import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from socialdna.config.settings import Settings
from socialdna.core.exceptions import InvalidMedia
from socialdna.domain.images import ImageInfo

FORMATS = ("JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF")


def looks_like_image(path: Path) -> bool:
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}:
        return True
    with path.open("rb") as stream:
        header = stream.read(16)
    return header.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8", b"BM", b"II*\x00", b"MM\x00*")) or (
        header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    )


def decode(path: Path, settings: Settings, max_side: int = 1024) -> tuple[ImageInfo, Image.Image]:
    if not path.is_file() or path.stat().st_size > min(
        settings.max_media_bytes, settings.max_image_bytes
    ):
        raise InvalidMedia("Image is missing or exceeds max_image_bytes/max_media_bytes")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path, formats=list(FORMATS)) as source:
                width, height = source.size
                if width * height > settings.max_image_pixels:
                    raise InvalidMedia("Image exceeds max_image_pixels before decoding")
                try:
                    source.seek(1)
                except EOFError:
                    source.seek(0)
                else:
                    raise InvalidMedia(
                        "Animated/multipage images need an explicit temporal/page workflow"
                    )
                orientation = int(source.getexif().get(274, 1))
                if orientation not in range(1, 9):
                    orientation = 1
                info = ImageInfo(
                    format=source.format or "unknown",
                    source_width=width,
                    source_height=height,
                    width=height if orientation >= 5 else width,
                    height=width if orientation >= 5 else height,
                    orientation_applied=orientation,
                    alpha="A" in source.getbands() or "transparency" in source.info,
                )
                source.load()
                display = ImageOps.exif_transpose(source).convert("RGBA")
                display.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                # Fixed white compositing is part of the method, not hidden image editing.
                rgb = Image.new("RGB", display.size, "white")
                rgb.paste(display, mask=display.getchannel("A"))
                rgb.info.clear()
                return info, rgb
    except InvalidMedia:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        SyntaxError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise InvalidMedia("Image is malformed, unsupported or unsafe to decode") from exc
