from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from socialdna.config.settings import Settings
from socialdna.core.exceptions import InvalidMedia
from socialdna.domain.evidence import EntityRef, ImageLocator
from socialdna.media.images import decode, looks_like_image


@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_orientation_and_metadata_minimization(tmp_path: Path, orientation: int) -> None:
    path = tmp_path / "camera.jpg"
    source = Image.new("RGB", (80, 40), "red")
    source.paste(Image.new("RGB", (20, 40), "blue"), (0, 0))
    exif = Image.Exif()
    exif[274], exif[270] = orientation, "PRIVATE CAMERA METADATA"
    source.save(path, exif=exif)
    info, display = decode(path, Settings())
    expected = (40, 80) if orientation >= 5 else (80, 40)
    assert display.size == expected == (info.width, info.height)
    transforms = {
        2: Image.Transpose.FLIP_LEFT_RIGHT,
        3: Image.Transpose.ROTATE_180,
        4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE,
        6: Image.Transpose.ROTATE_270,
        7: Image.Transpose.TRANSVERSE,
        8: Image.Transpose.ROTATE_90,
    }
    with Image.open(path) as original:
        expected_pixels = original.convert("RGB")
        if orientation in transforms:
            expected_pixels = expected_pixels.transpose(transforms[orientation])
        assert display.tobytes() == expected_pixels.tobytes()
    assert "PRIVATE" not in info.model_dump_json()
    assert not display.info and not display.getexif()


def test_alpha_palette_and_bounded_display(tmp_path: Path) -> None:
    path = tmp_path / "transparent.png"
    Image.new("RGBA", (500, 250), (255, 0, 0, 0)).save(path)
    info, display = decode(path, Settings(), max_side=100)
    assert info.alpha and display.size == (100, 50)
    assert display.getpixel((0, 0)) == (255, 255, 255)
    unknown = tmp_path / "not-an-extension.bin"
    unknown.write_bytes(path.read_bytes())
    assert looks_like_image(unknown)


@pytest.mark.parametrize("reason", ["malformed", "pixels", "bytes", "animation"])
def test_unsafe_or_nonstatic_images_are_refused(tmp_path: Path, reason: str) -> None:
    path = tmp_path / "source.png"
    Image.new("RGB", (100, 100)).save(path)
    settings = Settings()
    if reason == "malformed":
        path.write_bytes(b"not an image")
    elif reason == "pixels":
        settings = Settings(max_image_pixels=100)
    elif reason == "bytes":
        settings = Settings(max_image_bytes=10)
    else:
        path = tmp_path / "animated.gif"
        Image.new("RGB", (20, 20), "red").save(
            path, save_all=True, append_images=[Image.new("RGB", (20, 20), "blue")]
        )
    with pytest.raises(InvalidMedia):
        decode(path, settings)


@pytest.mark.parametrize("region", [(-0.1, 0, 1, 1), (0, 0, 2, 1), (0, 0, 0, 1), (1, 0, 0, 1)])
def test_regions_cannot_escape_display_bounds(region: tuple[float, ...]) -> None:
    with pytest.raises(ValidationError):
        ImageLocator(subject=EntityRef(kind="media", id="a", revision_id="r"), region=region)
