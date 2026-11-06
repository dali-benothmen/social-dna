import json
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import InvalidMedia
from socialdna.core.hashing import canonical_json, hash_file
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.images import ImageInfo
from socialdna.domain.media import MediaInfo
from socialdna.media.ffmpeg import tool_version
from socialdna.media.probe import probe
from socialdna.storage.schema import metadata


def import_local(
    application: Application, source: Path, *, copy_media: bool = False
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise InvalidMedia(f"Local media file does not exist: {source}")
    if source.stat().st_size > application.settings.max_media_bytes:
        raise InvalidMedia("File exceeds max_media_bytes.")
    from socialdna.media.images import decode, looks_like_image

    is_image = looks_like_image(source)
    if is_image and source.stat().st_size > application.settings.max_image_bytes:
        raise InvalidMedia("Image exceeds max_image_bytes")
    checksum = hash_file(source)
    media_id, post_id = stable_id("media", checksum), stable_id("local-post", checksum)
    probes = metadata.tables["media_probes"]
    with application.database.transaction() as connection:
        existing = (
            connection.execute(select(probes).where(probes.c.media_asset_id == media_id))
            .mappings()
            .first()
        )
    info: MediaInfo | ImageInfo = (
        decode(source, application.settings)[0]
        if is_image
        else MediaInfo.model_validate_json(existing["probe_json"])
        if existing
        else probe(source, application.settings)
    )
    version = (
        package_version("Pillow")
        if is_image
        else existing["tool_version"]
        if existing
        else tool_version("ffprobe")
    )
    source_id = stable_id("local-source", str(source), checksum)
    with application.database.transaction() as connection:
        artifact_id = (
            application.artifacts.put_file(
                connection, source, kind="original-media", mime_type="application/octet-stream"
            )
            if copy_media
            else None
        )
        assets = metadata.tables["media_assets"]
        connection.execute(
            insert(assets)
            .values(
                id=media_id,
                sha256=checksum,
                media_type="image" if is_image else "video",
                original_uri=source.as_uri(),
                duration_ms=info.duration_ms if isinstance(info, MediaInfo) else None,
                width=info.width,
                height=info.height,
                streams_json=canonical_json(info.streams) if isinstance(info, MediaInfo) else "[]",
                artifact_id=artifact_id,
            )
            .on_conflict_do_nothing()
        )
        if artifact_id:
            row = application.artifacts.get(connection, artifact_id)
            connection.execute(
                assets.update()
                .where(assets.c.id == media_id)
                .values(
                    artifact_id=artifact_id,
                    managed_uri=application.artifacts.path_for(row["relative_path"]).as_uri(),
                )
            )
        connection.execute(
            insert(metadata.tables["source_records"])
            .values(
                id=source_id,
                source_kind="local",
                source_uri=source.as_uri(),
                permission_basis="user_supplied_local_file",
                terms_json="{}",
                retrieved_at=utc_now(),
                content_hash=checksum,
                raw_artifact_id=artifact_id,
            )
            .on_conflict_do_nothing()
        )
        location = metadata.tables["media_locations"]
        connection.execute(
            insert(location)
            .values(media_asset_id=media_id, local_path=str(source), source_record_id=source_id)
            .on_conflict_do_update(
                index_elements=[location.c.local_path],
                set_={"media_asset_id": media_id, "source_record_id": source_id},
            )
        )
        connection.execute(
            insert(probes)
            .values(
                media_asset_id=media_id, probe_json=info.model_dump_json(), tool_version=version
            )
            .on_conflict_do_nothing()
        )
        connection.execute(
            insert(metadata.tables["posts"])
            .values(
                id=post_id,
                platform="local",
                external_id=checksum,
                content_type="photo" if is_image else "video",
                title=source.name,
                url=source.as_uri(),
            )
            .on_conflict_do_nothing()
        )
        connection.execute(
            insert(metadata.tables["post_media"])
            .values(post_id=post_id, position=0, media_asset_id=media_id, role="primary")
            .on_conflict_do_nothing()
        )
        if is_image:
            from socialdna.storage.evidence_repository import EvidenceRepository

            provenance = stable_id("image-import", source_id)
            connection.execute(
                insert(metadata.tables["provenance_records"])
                .values(
                    id=provenance,
                    source_record_id=source_id,
                    method="static-import-1",
                    tool_name="Pillow",
                    tool_version=version,
                    created_at=utc_now(),
                )
                .on_conflict_do_nothing()
            )
            EvidenceRepository(connection).capture(
                "media", media_id, provenance, mode="source_capture"
            )
    return {
        "media_id": media_id,
        "post_id": post_id,
        "sha256": checksum,
        "copied": copy_media,
        "source_id": source_id,
        "metadata": info.model_dump(),
    }


def resolve_media(
    application: Application, target: str, *, copy_media: bool = False
) -> tuple[str, Path, MediaInfo, str]:
    if Path(target).expanduser().is_file():
        imported = import_local(application, Path(target), copy_media=copy_media)
        media_id = imported["media_id"]
    else:
        media_id = target
    assets, probes, locations = (
        metadata.tables[name] for name in ("media_assets", "media_probes", "media_locations")
    )
    with application.database.transaction() as connection:
        asset = connection.execute(select(assets).where(assets.c.id == media_id)).mappings().first()
        if asset is None:
            raise InvalidMedia(
                "Target is neither an existing local file nor a registered media ID."
            )
        if asset["media_type"] != "video":
            raise InvalidMedia("Static images require analyze image, not a video timeline")
        stored_probe = (
            connection.execute(select(probes).where(probes.c.media_asset_id == media_id))
            .mappings()
            .one()
        )
        paths: list[str] = list(
            connection.scalars(
                select(locations.c.local_path).where(locations.c.media_asset_id == media_id)
            )
        )
        if asset["artifact_id"]:
            row = application.artifacts.get(connection, asset["artifact_id"])
            paths.insert(0, str(application.artifacts.path_for(row["relative_path"])))
    info = MediaInfo.model_validate(json.loads(stored_probe["probe_json"]))
    if info.duration_ms > application.settings.max_duration_seconds * 1000:
        raise InvalidMedia("Video exceeds max_duration_seconds.")
    for location in paths:
        path = Path(location)
        if path.is_file() and path.stat().st_size <= application.settings.max_media_bytes:
            if hash_file(path) == asset["sha256"]:
                return media_id, path, info, asset["sha256"]
    raise InvalidMedia(
        "Registered media is missing or its bytes changed; "
        "supply the original file or re-import it."
    )
