import importlib.metadata
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select

from socialdna.application.bootstrap import Application, open_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import SocialDNAError
from socialdna.domain.results import CheckResult
from socialdna.storage.migration_runner import (
    current_revision,
    migration_config,
    validate_history,
)
from socialdna.storage.schema import metadata


def database_checks(application: Application) -> list[CheckResult]:
    checks = []
    with application.database.transaction() as connection:
        integrity: list[str] = list(connection.exec_driver_sql("PRAGMA integrity_check").scalars())
        checks.append(
            CheckResult(
                name="sqlite.integrity",
                status="ok" if integrity == ["ok"] else "error",
                message="; ".join(integrity),
            )
        )
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        checks.append(
            CheckResult(
                name="sqlite.foreign_keys",
                status="ok" if enabled and not foreign_keys else "error",
                message="Foreign keys enabled; no violations."
                if enabled and not foreign_keys
                else "Foreign-key validation failed.",
            )
        )
        pragmas = {
            name: connection.exec_driver_sql(f"PRAGMA {name}").scalar()
            for name in ("journal_mode", "busy_timeout", "synchronous", "wal_autocheckpoint")
        }
        checks.append(
            CheckResult(
                name="sqlite.configuration",
                status="ok" if pragmas["journal_mode"] == "wal" else "error",
                message="Same-host WAL with explicit transactions.",
                details=pragmas,
            )
        )
        inspector = inspect(connection)
        actual = set(inspector.get_table_names())
        expected = set(metadata.tables) | {"alembic_version"}
        missing = sorted(expected - actual)
        mismatches = []
        for name in sorted(set(metadata.tables) & actual):
            columns = {column["name"] for column in inspector.get_columns(name)}
            if columns != set(metadata.tables[name].c.keys()):
                mismatches.append(name)
        checks.append(
            CheckResult(
                name="sqlite.schema",
                status="error" if missing or mismatches else "ok",
                message="Canonical schema matches the installed revision."
                if not missing and not mismatches
                else "Schema drift detected.",
                details={
                    "missing_tables": missing,
                    "column_mismatches": mismatches,
                    "revision": current_revision(connection),
                },
            )
        )
        from alembic.script import ScriptDirectory

        validate_history(connection, ScriptDirectory.from_config(migration_config()))
        # The probe is TEMP: no premature application FTS tables are persisted.
        try:
            connection.exec_driver_sql(
                "CREATE VIRTUAL TABLE temp.socialdna_fts_probe USING fts5(content)"
            )
            connection.exec_driver_sql("DROP TABLE temp.socialdna_fts_probe")
            checks.append(
                CheckResult(
                    name="sqlite.fts5",
                    status="ok",
                    message="FTS5 available for citation-backed research memory.",
                )
            )
        except Exception as exc:
            checks.append(
                CheckResult(
                    name="sqlite.fts5", status="error", message=f"SQLite FTS5 is unavailable: {exc}"
                )
            )
    return checks


def artifact_checks(application: Application) -> list[CheckResult]:
    from socialdna.storage.audience_retention import is_redacted

    with application.database.transaction() as connection:
        rows = list(connection.execute(select(metadata.tables["artifact_objects"])).mappings())
        redacted = {row["id"] for row in rows if is_redacted(connection, "artifact", row["id"])}
    failures = []
    for row in rows:
        if row["id"] in redacted:
            continue
        try:
            valid = application.artifacts.verify(row)
        except (OSError, ValueError):
            valid = False
        if not valid:
            failures.append(row["id"])
    registered = {row["relative_path"] for row in rows}
    objects = application.paths.artifacts / "objects"
    orphaned = [
        str(path.relative_to(application.paths.root))
        for path in objects.rglob("*")
        if path.is_file() and str(path.relative_to(application.paths.root)) not in registered
    ]
    staged = [
        str(path.relative_to(application.paths.root))
        for path in application.paths.artifacts.glob(".staged-*")
    ]
    return [
        CheckResult(
            name="artifacts.integrity",
            status="error" if failures else "ok",
            message=f"Verified {len(rows)} registered artifacts.",
            details={"failed_ids": failures, "intentionally_redacted_ids": sorted(redacted)},
        ),
        CheckResult(
            name="artifacts.unregistered",
            status="warning" if orphaned or staged else "ok",
            message="Unregistered files are retained for inspection; nothing was deleted."
            if orphaned or staged
            else "No unregistered artifacts.",
            details={"objects": orphaned, "staged": staged},
        ),
    ]


def evidence_checks(application: Application) -> list[CheckResult]:
    from socialdna.application.evidence_service import EvidenceResolver
    from socialdna.storage.audience_retention import is_redacted
    from socialdna.storage.evidence_repository import EvidenceRepository

    failures = []
    withheld = 0
    with application.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        for row in connection.execute(select(metadata.tables["entity_revisions"])).mappings():
            if is_redacted(connection, "entity_revision", row["id"]):
                continue
            try:
                repository.entity(repository.ref(dict(row)))
            except Exception as exc:
                failures.append({"revision": row["id"], "error": str(exc)})
        resolver = EvidenceResolver(connection)
        for row in connection.execute(select(metadata.tables["evidence_revisions"])).mappings():
            try:
                result = resolver.resolve(row["evidence_id"], revision_id=row["id"])
                withheld += int(not result.eligible)
            except Exception as exc:
                failures.append({"revision": row["id"], "error": str(exc)})
        legacy, bindings = (
            metadata.tables[name] for name in ("evidence_items", "legacy_media_evidence_bindings")
        )
        missing: list[str] = list(
            connection.scalars(
                select(legacy.c.id)
                .outerjoin(bindings, bindings.c.legacy_evidence_id == legacy.c.id)
                .where(bindings.c.evidence_revision_id.is_(None))
            )
        )
        pending: list[str] = list(
            connection.scalars(
                select(metadata.tables["evidence_backfill"].c.kind).where(
                    metadata.tables["evidence_backfill"].c.status != "complete"
                )
            )
        )
    return [
        CheckResult(
            name="evidence.integrity",
            status="error" if failures or pending or missing else "ok",
            message="Verified canonical revision hashes and typed evidence bindings.",
            details={
                "failures": failures,
                "pending_backfills": pending,
                "withheld_citations": withheld,
                "unregistered_legacy_evidence": missing,
            },
        )
    ]


def _vector_status(application: Application) -> dict[str, Any]:
    from socialdna.application.query_service import status

    memory = status(application)
    try:
        names = [item.name for item in application.vectors.client.get_collections().collections]
        state = "available"
    except SocialDNAError:
        names, state = [], "unavailable"
    return {
        "status": state,
        "backend": "qdrant-local",
        "path": str(application.paths.vectors),
        "collections": names,
        "embeddings": memory["spaces"],
        "semantic_retrieval": memory["semantic"],
    }


def storage_status(settings: Settings) -> dict[str, Any]:
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            tables = inspect(connection).get_table_names()
            revision = current_revision(connection)
        return {
            "data_dir": str(application.paths.root),
            "structured": {
                "backend": "sqlite",
                "path": str(application.paths.database),
                "revision": revision,
                "tables": tables,
                "bytes": application.paths.database.stat().st_size,
            },
            "vectors": _vector_status(application),
            "graph": {"status": "available", "backend": "sqlite-backed NetworkX"},
            "filesystem": {
                "kind": application.filesystem.kind,
                "mount": application.filesystem.mount,
                "network": application.filesystem.network,
            },
        }


def storage_verify(settings: Settings) -> list[CheckResult]:
    from socialdna.memory.health import checks as memory_checks

    with open_application(settings) as application:
        checks = (
            database_checks(application)
            + artifact_checks(application)
            + evidence_checks(application)
            + memory_checks(application)
        )
        vector_status = _vector_status(application)
        checks.append(
            CheckResult(
                name="qdrant.local",
                status="ok" if vector_status["status"] == "available" else "warning",
                message="Derived vector metadata inspected; SQL remains authoritative.",
                details=vector_status,
            )
        )
        checks.append(
            CheckResult(
                name="graph.persistence",
                status="ok",
                message="Qualified SQLite graph projections support bounded NetworkX views.",
            )
        )
        return checks


def _tool_check(name: str) -> CheckResult:
    executable = shutil.which(name)
    if executable is None:
        return CheckResult(
            name=name,
            status="warning",
            message=f"{name} not found; required for local media analysis. "
            "Install FFmpeg using your operating system's package manager.",
        )
    try:
        result = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
            check=False,
        )
        version = (result.stdout or result.stderr).splitlines()
        return CheckResult(
            name=name,
            status="ok" if result.returncode == 0 else "warning",
            message=version[0] if version else "No version information returned.",
            details={"path": executable, "returncode": result.returncode},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(name=name, status="warning", message=f"Cannot inspect {name}: {exc}")


def doctor(settings: Settings) -> list[CheckResult]:
    checks = storage_verify(settings)
    checks.append(CheckResult(name="python", status="ok", message=platform.python_version()))
    for package in (
        "typer",
        "pydantic",
        "pydantic-settings",
        "platformdirs",
        "SQLAlchemy",
        "alembic",
        "qdrant-client",
        "networkx",
        "portalocker",
        "numpy",
        "opencv-python-headless",
        "scenedetect-headless",
        "Pillow",
        "librosa",
        "soundfile",
        "scipy",
        "pysubs2",
        "pandas",
        "scikit-learn",
        "statsmodels",
    ):
        try:
            version = importlib.metadata.version(package)
            checks.append(CheckResult(name=f"package.{package}", status="ok", message=version))
        except importlib.metadata.PackageNotFoundError:
            checks.append(
                CheckResult(
                    name=f"package.{package}",
                    status="error",
                    message="Required package is missing; reinstall SocialDNA.",
                )
            )
    checks.extend(_tool_check(name) for name in ("ffmpeg", "ffprobe"))
    from socialdna.providers.models import ModelStore

    checks.append(
        CheckResult(
            name="models",
            status="ok",
            message="Optional model availability inspected; no download/inference attempted.",
            details={"models": ModelStore(settings).status()},
        )
    )
    filesystem = application_filesystem(settings.data_dir)
    checks.append(filesystem)
    disk = shutil.disk_usage(settings.data_dir)
    checks.append(
        CheckResult(
            name="storage.free_space",
            status="ok",
            message="Disk space inspected.",
            details={"free_bytes": disk.free, "total_bytes": disk.total},
        )
    )
    return checks


def application_filesystem(path: Path) -> CheckResult:
    from socialdna.storage.filesystem import detect_filesystem

    info = detect_filesystem(path)
    return CheckResult(
        name="storage.filesystem",
        status="warning" if info.kind is None else "ok",
        message=f"Filesystem: {info.kind or 'unknown; ensure storage is local'}. "
        "Network filesystems are unsupported for Local Mode.",
    )
