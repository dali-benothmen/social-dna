# SocialDNA

SocialDNA is a planned local-first social-media research engine. This release implements
**Milestone 0: the package, CLI contracts, and canonical storage foundation**.

Working capabilities:

- Automatic, idempotent SQLite initialization with Alembic migrations, transactional
  DDL, migration checksums, foreign keys, WAL, and bounded lock waiting.
- Persistent Qdrant Local metadata, one embedded client per application lifetime,
  and process-safe access without a database server.
- Canonical foundation tables for accounts, posts, media, sources, provenance,
  availability, analysis execution, and managed artifacts.
- A Python artifact store with SHA-256 deduplication, atomic file writes,
  reference counting, and checksum verification.
- Storage health checks, FTS5 capability detection, Python dependency versions,
  and FFmpeg/ffprobe detection.
- Text output for people and a versioned JSON envelope for agents.

Video analysis, embeddings, semantic retrieval, persistent graph queries, analytics,
and the Agent Skill are subsequent milestones. They are not available in this release.

## Install from this checkout

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required. The project is not yet
published to PyPI, so `uv tool install socialdna` is not advertised as a supported command.

```bash
uv sync --locked
uv run socialdna doctor
uv run socialdna storage status --format json
```

To install the current checkout as an isolated command-line tool:

```bash
uv tool install .
socialdna doctor
```

Initialization requires no system media tools, API key, model download, Docker,
or database server. FFmpeg/ffprobe are only detected at this milestone. Install
FFmpeg through your operating system's package manager before future media analysis;
SocialDNA never installs it automatically.

## Commands

```bash
socialdna init
socialdna doctor --format json
socialdna storage status
socialdna storage verify --format json
socialdna --help
socialdna --version
```

`init` is optional: `doctor`, `storage status`, and `storage verify` initialize the
data directory on first use. Help and version do not create storage. Global options
may precede the command or follow a leaf command:

```bash
socialdna --data-dir ./research-data --format json storage status
socialdna storage status --data-dir ./research-data --format json
```

Use a local filesystem. Known network mounts are rejected because SQLite WAL and
embedded Qdrant locking require local access. On systems where mount type cannot
be detected, `doctor` tells you to confirm the storage is local.

## Configuration

Precedence is command-line options, `SOCIALDNA_*` environment variables, an explicit
TOML file, then platform defaults. No `.env` file is read implicitly.

```toml
[socialdna]
data_dir = "/absolute/path/to/research-data"
lock_timeout = 2.0
busy_timeout_ms = 5000
offline = true
allow_download = false
remote_media_consent = false
```

```bash
socialdna doctor --config /path/to/settings.toml
SOCIALDNA_DATA_DIR=/path/to/library socialdna storage verify
```

The download/remote consent settings define future provider policy; Milestone 0
contains no model/provider inference and makes no remote calls regardless of these settings.

Default storage uses `platformdirs`: typically `~/.local/share/socialdna` on Linux,
`~/Library/Application Support/socialdna` on macOS, and the local app-data directory
on Windows. `storage status` displays the resolved location.

```text
data-directory/
├── socialdna.db
├── .socialdna.lock
├── vectors/             # embedded Qdrant metadata; no embedding collections yet
├── artifacts/
│   ├── objects/         # SHA-256 addressed blobs
│   ├── frames/
│   ├── audio/
│   ├── transcripts/
│   └── thumbnails/
├── cache/
├── models/              # no models downloaded by this release
├── reports/
└── logs/
```

SQLite is canonical. Qdrant is a derived index; its initial collections remain empty
until embedding spaces are implemented. Graph storage is reported as deferred until
Milestone 2. `storage verify` checks only capabilities implemented at this milestone
and does not claim semantic retrieval or graph persistence has been verified.

## Machine output and exit codes

`--format json` prints one JSON document to stdout, including command failures.
Human warnings use stderr only in text mode. The envelope has `schema_version`,
`command`, `status`, nullable `run_id`, `data`, `evidence`, `warnings`, `limitations`,
`errors`, and `next_actions`. Its JSON Schema is checked into
`tests/contract/fixtures/result-envelope.schema.json`.

| Exit code | Meaning |
|---|---|
| 0 | Operation succeeded; optional-tool warnings may be present |
| 1 | Unexpected internal error |
| 2 | Invalid CLI input or configuration |
| 3 | Required dependency/model unavailable (reserved for relevant operations) |
| 4 | Storage permission denied |
| 5 | Partial analysis (reserved for later analysis commands) |
| 6 | Another process/client holds the storage lock |
| 7 | Provider failure (reserved for later providers) |
| 8 | Storage integrity or schema validation failure |

All Local Mode commands currently take one data-directory lock, including inspection
commands, because they initialize storage and open Qdrant Local. Lock ownership is
released by the OS on process exit. Never delete a live lock file; wait for the other
process to finish. Use separate data directories for independent libraries.

## Python API

The engine works independently of an agent:

```python
from pathlib import Path
from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.storage.unit_of_work import unit_of_work

with open_application(Settings(data_dir=Path("./research-data"))) as application:
    with unit_of_work(application.database) as repository:
        account_id = repository.upsert_account("local", "example-creator", handle="creator")

    with application.database.transaction() as connection:
        artifact_id = application.artifacts.put_bytes(
            connection,
            b"Source material supplied by the owner",
            kind="raw",
            mime_type="text/plain",
        )
        application.artifacts.add_reference(
            connection,
            artifact_id,
            owner_type="account",
            owner_id=account_id,
            role="source",
        )
```

Application and transaction context managers close resources and roll back canonical
writes when exceptions occur. A file written just before a failed database transaction
can remain unregistered; `storage verify` reports it for inspection and never deletes it.

## Development and verification

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
uv run python scripts/check_distribution.py
```

The core tests require no API credentials, model downloads, or FFmpeg. They exercise
real SQLite/Alembic/Qdrant storage, migration failure recovery, interprocess locking,
restart persistence, artifacts, CLI output, and schema contracts.

See [PLAN.md](PLAN.md) for completed work and future milestones, and
[ARCHITECTURE.md](ARCHITECTURE.md) for the approved design and implementation decisions.

Licensed under [Apache-2.0](LICENSE).
