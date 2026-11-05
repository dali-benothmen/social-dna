# Local storage (implemented `0.0.4`)

This page describes existing storage behavior, not the planned research schema.
Historical Milestones 0, 1, 3, and 4 are implemented. Revised R1 introduces universal
evidence contracts; R6 implements semantic/graph memory. See
[research contracts](research-contracts.md), [migration strategy](migration-strategy.md),
and the [roadmap](../PLAN.md) for planned changes.

`open_application(Settings(...))` is the lifecycle boundary used by every command.
It resolves the filesystem, rejects detected network mounts, creates a local data
directory, acquires its OS lock, applies migrations in a real SQLite transaction,
opens exactly one Qdrant Local client, and closes both stores on success or failure.
Every application context requires the lock, including storage inspection commands,
because first-use initialization and Qdrant access both require exclusive coordination.

## Canonical schema

The first migration creates:

- `creators`, `accounts`, `posts`, `media_assets`, `post_media`;
- `source_records`, `provenance_records`, `provenance_links`, `data_availability`;
- `analysis_runs`, `analysis_tasks`;
- `artifact_objects`, `artifact_references`;
- `migration_checksums`, plus Alembic's `alembic_version`.

Migration `0002_timeline` adds `media_locations`, `media_probes`, task result/dependency
tables, scenes, frames, text tracks/segments, audio segments, feature definitions,
observations, evidence items, and reports. These evidence items are media-specific:
they require a media/task identity and nonempty media interval. They are not yet a
universal evidence registry. The baseline migration is unchanged.

Revision `0003_enrichment` adds nullable paired `text_words` timing, normalized OCR-box
evidence linked to frames/text segments, `inference_inputs` source-evidence foreign keys,
and durable `provider_calls` request/response artifacts and status.

Revision `0004_analytics` is the current head. It adds `import_batches`,
`media_references`, `tags`, `post_tags`, `comments`, immutable `metric_definitions`,
append-only `metric_observations`, `derived_metrics`, `cohorts`, `cohort_members`,
`statistical_analyses`, `statistical_results`, and `account_media_runs`. Saved
statistical inputs/results and reports support reproducibility; they do not yet
provide a hypothesis-assessment lifecycle. Metric citations currently remain
separate from media evidence. Vector-registry/outbox, persistent graph, universal
evidence, and psychological research tables are still planned, not implemented.
Migration numbering is independent of roadmap milestone numbering.

All SQLAlchemy connections enable foreign keys, WAL, a bounded busy timeout,
`synchronous=FULL`, and a 1,000-page automatic WAL checkpoint threshold. The engine
disables sqlite3 legacy transaction control and issues `BEGIN` explicitly; this
makes DDL and migrations rollback with the canonical data when a migration fails.

The migration runner refuses unknown revision heads, modified applied migration
files, missing checksum records, and unversioned databases containing existing
tables. It does not stamp an arbitrary database as valid or erase it.

The frozen baseline schema lives in its migration module. `storage/schema.py`
composes the current Core metadata from that versioned slice. Future revisions
must leave released migration files unchanged and evolve the current metadata.

## Atomic artifacts and references

Artifacts are written under `artifacts/objects/<first-two-sha256-digits>/<sha256>`.
Writing streams the bytes to a temporary file, hashes and flushes them, atomically
renames the file into place, and registers a canonical SQLite row in the caller's
transaction. Existing bytes are checksum-verified before deduplication. Artifact
paths cannot resolve outside the managed artifact directory.

Reference counts include both `artifact_references` owner links and direct source/media
foreign keys. Media-task and report objects additionally have explicit owner links.
Repeatedly adding the same owner/role is idempotent. SQLite foreign
keys prevent removing an object row while a canonical reference still points to it.

If file creation succeeds but the SQLite transaction rolls back, the unregistered
file is retained. `storage verify` reports orphaned objects and staged files for
inspection. Automatic destructive cleanup is not implemented.

## Health checks

`storage status` reports the database revision/tables, Qdrant collections, resolved
paths, filesystem, and deferred graph status. `storage verify` runs SQLite integrity
and foreign-key checks, verifies table/column shape and migration checksums, probes
FTS5 using a temporary table, verifies every registered artifact checksum, detects
unregistered artifacts, and reads Qdrant's local collection metadata.

`doctor` also checks the current Python/dependency versions, disk free space,
FFmpeg/ffprobe executable versions, and optional model readiness metadata. Missing
media tools are warnings for health/storage commands; video analysis requires them
and returns dependency-unavailable exit code 3 before creating a run.

No graph relationships, semantic embeddings, or cross-store indexes are claimed
until their milestones implement and test them. This release does not provide a
backup/restore command; stop all commands before making a filesystem copy, including
the database's `-wal`/`-shm` files if present, vector directory, and artifacts.

## Concurrency and recovery

The data lock contains PID, hostname, and acquisition time. Lock metadata is written
only after the OS lock is acquired. A competing command returns exit code 6 with
retry guidance and cannot truncate the current owner's metadata. The OS releases
locks even after an interrupted process; an empty/stale lock file is harmless.

Qdrant's own exclusive directory lock is retained as a second layer of protection
against callers that bypass SocialDNA's application context. A conflicting embedded
client returns the same storage-conflict error family. Never remove a live lock file.

Configuration and filenames are passed as data. There is no shell evaluation of
media paths. Deterministic analysis performs no network request or API-key lookup.
Model preparation and explicitly configured reasoning have separate consent boundaries;
see [local enrichment](local-enrichment.md). FFmpeg protocols are restricted to local files/pipes.

Task completion, result JSON, canonical observations/evidence, provenance, and artifact
references commit together. A new run can reference an earlier successful producer via
`reused_from_task_id`; timeline queries resolve those producer IDs rather than copying
rows. Failed/incomplete attempts have no committed canonical output. The writer lock
allows interrupted tasks to be retried without a background lease-reaper service.
See [video-analysis.md](video-analysis.md) for the execution and recovery contract.

## Planned evolution, not current behavior

R1 will add typed, versioned evidence locators while preserving existing media
evidence IDs and report snapshots. R6 will add reconstructible lexical/vector/graph
projections derived from canonical SQLite revisions; it will not make Qdrant or
NetworkX authoritative. Existing released migrations must not be edited. Legacy
rows must not gain fabricated comment timestamps, retrospective feature availability,
or psychological interpretations during backfill. The staged compatibility and
withdrawal rules are defined in the [migration strategy](migration-strategy.md).
