# SocialDNA

SocialDNA is a local-first social-media research engine. The implemented release is
`0.0.13`: reviewed professional production evidence and eight pinned numeric craft
recipes, joined to the existing comparison/research pipeline. See
[production evidence](docs/production-evidence.md). It extends `0.0.12`'s
incremental hypothesis reevaluation with immutable contradiction history,
bounded change tracking, restart checkpoints and preserved historical reports. See
[incremental research](docs/incremental-research.md). It extends `0.0.11`'s reviewed
source excerpts, competing predictions, immutable assessments, scoped findings and
proposed discriminating experiments. See [psychological research](docs/psychological-research.md).
It builds on `0.0.10`'s persistent citation-backed SQL/FTS memory, qualified graph
traversal and optional prepared local embeddings. No mediator or causal effect is
identified automatically; scientific validity still requires appropriate evidence.

`0.0.9` added source-defined retention series, qualified attribution and signed account
outcomes; source-qualified audience collections, reaction review and content links,
revisioned creative events, pinned multimodal recipes, versioned
media/comment/metric/statistical citations, draft registration, withdrawal-aware
reports, verified backup/restore and explicit time-aware analytics. The foundation and
historical Milestones 1, 3, and 4 retain local-video analysis, optional enrichment,
account imports, and bounded performance analytics.

The revised [architecture](ARCHITECTURE.md) and [roadmap](PLAN.md) distinguish R1's
implemented citation/statistical/creative foundation from later research capabilities.
Persistent SQL/FTS/qualified graph memory and optional local semantic retrieval are
delivered in R6; prepared-real-model acceptance and corpus relevance remain explicit
verification work. Registering a draft
does not evaluate it or establish an association or psychological mechanism.

Working capabilities:

- Exact revisioned media, comment-span and scalar-metric citations; draft question/
  hypothesis registration and persistent JSON/Markdown citation reports.
- Withdrawal eligibility checks and verified canonical backups/restores, with
  post-checkpoint withdrawal reconciliation or restricted recovery.
- Local video registration by checksum, optional managed originals, and FFprobe metadata.
- Adaptive shot detection, scene-aware evidence frames/contact sheets, visual color,
  texture and motion measurements, audio loudness/energy/spectral/pitch estimates,
  and supplied SRT/VTT subtitle tracks.
- Timestamped timeline queries and evidence-linked JSON/Markdown reports.
- Durable task dependencies, configuration/version fingerprints, selective cache reuse,
  partial failure reporting, and interrupted-run resume.
- Explicit checksum-verified model preparation/import and optional offline faster-whisper
  ASR, RapidOCR, MediaPipe pose geometry/audio candidates, and a WhisperX alignment adapter.
- Schema/evidence-validated reasoning through an explicitly configured compatible local
  server or consent-gated remote profile; transfer attempts have durable request audits.
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
- Atomic, versioned CSV/JSON account/post exports, permitted comments/tags/media references,
  immutable metric definitions, append-only snapshots, availability and raw-source provenance.
- Age/window-aligned account reports, strict engagement rates, retrospective
  leave-one-post-out creator normalization, same-creator matched comparisons,
  cluster uncertainty, guarded regression/GLM/GEE/mixed models, main-effect Ridge
  holdout checks, per-run FDR correction, and frozen, reproducible cohorts.
- Explicit version-2 historical baselines, within/distinct-creator matching with
  support/balance diagnostics, real feature/recipe availability, duplicate-safe splits,
  selected OLS/Poisson interaction-pipeline validation, durable test/holdout ledgers,
  and exact statistical term/diagnostic citations. Legacy methods remain unchanged.
- Authorized reviewed creative-event imports, uncertain original-media anchors,
  modality/coverage evidence and qualified temporal relations; opt-in literal-text
  proposals and budgeted targeted frames without invalidating primitive caches.
- Eleven pinned observable-content recipes, persistent media/post feature lineage,
  as-of annotation selection, explicit version-2 comparison joins and pinned video reports.
  Sparse sampling stays unknown; no automatic dish recognition or psychological mechanism
  validation is claimed. See [creative analysis](docs/creative-analysis.md).
- Permitted audience collection manifests, exact Unicode reaction annotations,
  versioned curated clusters with counterexamples, qualified post/event links,
  frozen collected-comment reports and an opt-in timeline context lane.
- Previewed, confirmed active-library audience erasure with terminal tombstones,
  interrupted-cleanup recovery and backup-restore reconciliation. External copies
  and backup bytes require separate cleanup. See [audience analysis](docs/audience-analysis.md).

- Explicit v2 behavioral definitions/cohorts and original-grid retention series,
  compatible rate components, qualified conversion attribution, signed account
  changes, historical account-size gates and frozen source-qualified reports.
  No interpolated retention, bins-as-viewers precision or causal attribution is
  claimed. See [behavioral analytics](docs/behavioral-analysis.md).

Psychological pattern discovery and the portable Agent Skill remain unavailable.
Persistent research memory is described in [memory operations](docs/research-memory.md).
Model interpretations are labeled
uncertain hypotheses, not psychological/performance findings or verified facts.
Cross-creator effects remain descriptive; unsupported niche/between-creator effects
and unseen-creator fixed-effect predictions are withheld. Historical baselines need
measurements genuinely known by the cutoff; late imports do not establish forecasting
availability. See [versioned analytics](docs/versioned-analytics.md) and
[legacy performance analytics](docs/performance-analytics.md) for exact limits.

The target product supports individual videos and photos, complete accounts,
captions/hashtags, within- and cross-niche research, original experiments, and durable
hypothesis revision. Photos/carousels (U1), portable Agent Skills-compatible
instructions for Codex, Claude Code, and OpenCode (U2), broader discovery and
registered experiment outcomes (R9–R10), and production/growth context extensions
(C1) remain planned. The bounded R7 assessment and R8 reevaluation paths are implemented.
The shared Python CLI already works independently of an
agent; compatibility with those three agent hosts has not been validated.

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
or database server. Install FFmpeg (including ffprobe) through your operating system's
package manager before analyzing video;
SocialDNA never installs it automatically.

## Register research and cite real sources

```bash
uv run socialdna research register --spec examples/research/question.json --dry-run --format json
uv run socialdna research register --spec examples/research/question.json --format json
# Use actual evidence/comment/snapshot IDs from your imported or analyzed library.
uv run socialdna evidence resolve EVIDENCE_ID --format json
uv run socialdna evidence cite-comment COMMENT_ID --start 0 --end 19 --format json
uv run socialdna evidence cite-metric SNAPSHOT_ID --format json
uv run socialdna research report QUESTION_ID --format json
```

The bundled question has no fabricated citations. Add returned `{id, revision_id}`
references to its evidence lists to produce a sourced registration report. R1 does
not evaluate hypotheses; withdrawal is not full retained-data erasure. See the
[R1 workflow, source rules and backup/restore guide](docs/research-foundation.md).

## Import an account and analyze performance

```bash
uv run socialdna import json examples/imports/account.json --dry-run --format json
uv run socialdna import json examples/imports/account.json --format json
# Use an account_id returned by the import.
uv run socialdna analyze account ACCOUNT_ID --metric demo.views.v1 --format json
uv run socialdna report generate --account ACCOUNT_ID --format markdown
```

These are normalized authorized exports, not automatic vendor/API imports.
Missing metrics stay missing; small samples produce descriptive results with explicit
limitations. Regression is opt-in, and observational associations are not causal findings.
Use `--analyze-media` to process imported local video references; no media is downloaded.
See [import formats](docs/import-formats.md), [analytics safeguards and commands](docs/performance-analytics.md),
and [runnable examples](examples/imports/).

## Analyze a local video

Use media you own or are authorized to analyze. No API keys or model downloads are needed.

```bash
uv run socialdna analyze video /path/to/video.mp4 --subtitles /path/to/captions.srt --format json
# The result contains media_id, run_id, task states, and managed report paths.
uv run socialdna timeline show MEDIA_ID --start 0s --end 5s --format json
uv run socialdna report generate --run RUN_ID --format markdown
```

`--subtitles` is optional; supplied subtitles are not claimed to be ASR or OCR output.
`--depth quick|standard|deep` changes regular frame-sampling density; all profiles run
the deterministic analyzers. Standard/deep also use prepared ASR/OCR models; quick
requires explicit `--transcribe`/`--ocr`. Deep requests model word timestamps. Alignment,
pose, audio classification and reasoning require explicit flags. `--no-ai` disables
all enrichment, including when models and provider profiles are configured.

By default the original stays at its source path. Add `--copy-media` to import/analyze
to retain a managed original; you can then delete your external copy without losing
the ability to analyze by media ID. Existing evidence/reports remain queryable even
when an uncopied original is absent, but new analysis/resume requires verified source bytes.

After interruption, use the printed run ID with the same options and subtitle bytes:

```bash
uv run socialdna analyze video MEDIA_ID --resume RUN_ID --format json
```

Completed tasks are reused after checksum validation; failed/incomplete tasks retry.
Changing options normally starts a new run and invalidates only affected tasks. Resume
rejects configuration/tool-version changes to protect immutable evidence. Each run has
its own report snapshots; cached extraction does not duplicate measurements or media blobs.
Reports are content-addressed objects at the paths returned by the command, not files
named after untrusted titles. See [the video pipeline](docs/video-analysis.md) for details.

## Optional local enrichment

Keep the base install small; install only the extras you need:

```bash
uv sync --locked --extra speech --extra ocr
uv run socialdna models status --format json
uv run socialdna models prepare asr-tiny --allow-download
uv run socialdna models prepare ocr-en --allow-download
uv run socialdna analyze video /path/to/video.mp4 --depth deep --offline --format json
```

Preparation downloads pinned assets and verifies SHA-256. Analysis itself never downloads
models, even if `allow_download` is configured. Auto-selected unavailable models are
skipped with reasons; explicitly requested missing models or failed inference produce
a partial result while retaining deterministic evidence. Supplied subtitles, ASR,
aligned ASR, and OCR stay separate tracks.

Do not install all extras into the engine environment: MediaPipe/WhisperX have substantial
native dependency trees and OpenCV/PyTorch compatibility requirements. Use isolated
workers as described in [local enrichment](docs/local-enrichment.md), which also covers
language/model limitations, custom manifests, consent, budgets, and real model tests.

## Commands

```bash
socialdna init
socialdna doctor --format json
socialdna storage status
socialdna storage verify --format json
socialdna import local /path/to/video.mp4 --copy-media --format json
socialdna analyze video /path/to/video.mp4 --depth quick --format json
socialdna timeline show MEDIA_ID --start 0s --end 5s --format json
socialdna report generate --run RUN_ID --format json
socialdna models status --format json
socialdna models prepare asr-tiny --allow-download
socialdna --help
socialdna --version
```

`init` is optional: all storage/media commands initialize the
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
max_media_bytes = 2000000000
max_duration_seconds = 600.0
max_decode_frames = 36000
media_timeout_seconds = 300.0
```

```bash
socialdna doctor --config /path/to/settings.toml
SOCIALDNA_DATA_DIR=/path/to/library socialdna storage verify
```

The download/remote consent settings control provider policy; this release
uses explicit local model preparation and never downloads during analysis. Remote inference
also requires a configured enabled profile, allowed evidence types, and consent.

Default storage uses `platformdirs`: typically `~/.local/share/socialdna` on Linux,
`~/Library/Application Support/socialdna` on macOS, and the local app-data directory
on Windows. `storage status` displays the resolved location.

```text
data-directory/
├── socialdna.db
├── .socialdna.lock
├── vectors/             # optional immutable-space derived Qdrant collections
├── artifacts/
│   ├── objects/         # SHA-256 addressed blobs
│   ├── frames/
│   ├── audio/
│   ├── transcripts/
│   └── thumbnails/
├── cache/
├── models/              # optional verified model bundles and installation manifests
├── reports/
└── logs/
```

SQLite is canonical, including revisioned evidence and qualified graph projections.
FTS and optional Qdrant collections are derived indexes; basic commands load no
embedding model. `storage verify` checks canonical integrity and derived-memory
consistency, not learned relevance or psychological validity. Missing vector points
can be reconciled; SQL/FTS/graph can be rebuilt from eligible canonical inputs.

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
| 3 | Required dependency unavailable, e.g. FFmpeg for video analysis |
| 4 | Storage permission denied |
| 5 | Partial analysis or media processing failure |
| 6 | Another process/client holds the storage lock |
| 7 | Provider failure |
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

Core tests require no API credentials or model downloads. Real-model tests are opt-in
and documented in [local enrichment](docs/local-enrichment.md). Media integration tests require
FFmpeg/ffprobe and skip explicitly if absent; CI installs those tools on all three OSes.
Generated owned fixtures cover scene changes, motion, tones, subtitles, VFR, shifted
timestamps, and audio offsets. Tests also exercise real SQLite/Alembic/Qdrant storage,
failure recovery, interprocess locking, restart persistence, artifacts, and CLI contracts.

See [PLAN.md](PLAN.md) for implemented history and planned milestones,
[ARCHITECTURE.md](ARCHITECTURE.md) for the revised design, and
[the migration strategy](docs/migration-strategy.md) for preservation of existing data.
The [architecture audit](docs/architecture-audit.md) is a historical assessment;
the current design and roadmap supersede its proposed ordering.

Licensed under [Apache-2.0](LICENSE).
