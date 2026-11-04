# SocialDNA Implementation Plan

Status: approved; Milestones 0–1, 3 and 4 complete; Milestone 2 deferred

Date: 2026-11-04

Architecture source: `ARCHITECTURE.md`

Repository state: account imports and performance analytics implemented as package version `0.0.4`.

## 1. Outcome and approval boundary

The implementation will deliver a local-first, evidence-grounded social-media research engine and portable Agent Skill. The first usable vertical slice will analyze an authorized local video, persist a timestamped timeline, reopen that knowledge in another process, retrieve it semantically and through a graph traversal, and generate a cited report without any external database server or paid API key.

The architecture and roadmap were approved on 2026-11-04. Implementation is limited to one milestone per change. Milestones 0–1, 3 and 4 are complete. The user explicitly requested Milestone 3 and then Milestone 4; both consume canonical SQLite/timeline interfaces without Milestone 2 indexing. Milestone 2 has not started; its release gates remain unmet.

The initial release is complete after Milestone 6. Milestones 7 and 8 are optional post-release expansion and must not delay the local-first release.

## 2. Definition of done for the initial release

A clean machine with Python 3.11+, `uv`, and FFmpeg can:

1. install the package and run `socialdna doctor`;
2. analyze a repository-owned or user-supplied local video with no API credentials;
3. persist canonical metadata, scenes, selected frames, audio features, subtitles/transcript, observations, evidence, and task state in SQLite/artifacts;
4. persist semantic entries in Qdrant Local and graph rows in SQLite;
5. terminate, start a separate CLI process, retrieve the video by semantic query, traverse its graph neighborhood, and generate a grounded report;
6. import account/post/metric history from validated CSV/JSON without converting missing values to zero;
7. compare appropriately matched posts with transparent effect sizes, uncertainty, and limitations;
8. record psychological mechanisms only as evidence-linked hypotheses unless statistical/experimental support justifies a higher claim level;
9. expose stable JSON command output that the SocialDNA Agent Skill can orchestrate in Codex and Claude Code;
10. pass unit, integration, cross-process end-to-end, packaging, migration, and documentation contract tests.

## 3. Delivery strategy

The roadmap deliberately orders a thin end-to-end system before advanced interpretation:

| Milestone | Working result | Release gate |
|---|---|---|
| 0. Repository and canonical storage | Installable CLI, auto-init, migrations, health checks, stable contracts | Complete (`0.0.1`) |
| 1. Deterministic local video vertical slice | Local video to timestamped JSON/Markdown report | Complete (`0.0.2`); first user value |
| 2. Persistent research memory | Cross-process Qdrant/graph/FTS retrieval and repair | Deferred at user request; v0.1 gate still unmet |
| 3. Local model enrichment | Optional ASR, OCR, landmarks/classifiers, provider safety | Complete out of order (`0.0.3`); v0.2 release gate still awaits memory |
| 4. Account imports and performance analytics | Multi-post baselines and defensible statistics | Complete out of order (`0.0.4`); roadmap v0.3 gate still awaits memory |
| 5. Psychology and cross-content discovery | Evidence-backed hypotheses, associations, counterexamples, hybrid research | v0.4 |
| 6. Media breadth, reports, skill, and release hardening | Photos/carousels, comparisons, HTML, portable skill, packaged v1 | v1.0 |
| 7. Official platform adapters | Permission-aware YouTube/Instagram/TikTok ingestion | Post-v1 optional |
| 8. Research Mode scale adapters | External Qdrant and optional distributed/storage backends | Post-v1 optional |

Every milestone updates documentation to describe only behavior that exists at that point.

## 4. Planned repository map

Files are introduced incrementally; empty placeholder packages are not created solely to match this tree.

```text
social-dna/
├── src/socialdna/
│   ├── cli/
│   │   ├── app.py
│   │   ├── output.py
│   │   └── errors.py
│   ├── application/
│   │   ├── bootstrap.py
│   │   ├── analysis_service.py
│   │   ├── import_service.py
│   │   ├── query_service.py
│   │   └── report_service.py
│   ├── core/
│   │   ├── ids.py
│   │   ├── hashing.py
│   │   ├── time.py
│   │   ├── enums.py
│   │   └── exceptions.py
│   ├── config/
│   │   ├── paths.py
│   │   └── settings.py
│   ├── domain/
│   │   ├── commands.py
│   │   ├── results.py
│   │   ├── media.py
│   │   ├── evidence.py
│   │   ├── research.py
│   │   └── providers.py
│   ├── storage/
│   │   ├── database.py
│   │   ├── unit_of_work.py
│   │   ├── repositories.py
│   │   ├── artifacts.py
│   │   ├── locking.py
│   │   ├── health.py
│   │   └── migrations/
│   ├── ingestion/
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── tabular.py
│   │   └── platforms/             # added only in Milestone 7
│   ├── media/
│   │   ├── probe.py
│   │   ├── ffmpeg.py
│   │   ├── scenes.py
│   │   ├── frames.py
│   │   ├── audio.py
│   │   ├── subtitles.py
│   │   └── timeline.py
│   ├── analyzers/
│   │   ├── base.py
│   │   ├── visual.py
│   │   ├── audio.py
│   │   ├── speech.py
│   │   ├── ocr.py
│   │   └── language.py
│   ├── providers/
│   │   ├── registry.py
│   │   ├── transcription.py
│   │   ├── embeddings.py
│   │   ├── vision.py
│   │   ├── audio.py
│   │   └── reasoning.py
│   ├── memory/
│   │   ├── vectors.py
│   │   ├── vector_sync.py
│   │   ├── lexical.py
│   │   ├── graph.py
│   │   └── hybrid.py
│   ├── analytics/
│   │   ├── metrics.py
│   │   ├── baselines.py
│   │   ├── cohorts.py
│   │   ├── statistics.py
│   │   └── validation.py
│   ├── psychology/
│   │   ├── taxonomy.py
│   │   ├── cues.py
│   │   └── hypotheses.py
│   ├── research/
│   │   ├── questions.py
│   │   ├── discovery.py
│   │   ├── counterexamples.py
│   │   └── findings.py
│   └── reporting/
│       ├── models.py
│       ├── json.py
│       ├── markdown.py
│       ├── html.py
│       └── templates/
├── skills/socialdna/
│   ├── SKILL.md
│   └── references/
│       ├── cli.md
│       ├── workflows.md
│       ├── psychology.md
│       ├── research-methodology.md
│       └── interpretation-rules.md
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── end_to_end/
├── docs/
├── examples/
├── pyproject.toml
├── uv.lock
├── README.md
├── ARCHITECTURE.md
├── PLAN.md
└── LICENSE
```

## 5. Cross-cutting contracts fixed before implementation

These are expensive to change after data exists, so Milestone 0 treats them as public contracts:

- SQLite owns canonical data; Qdrant and NetworkX views are derived.
- Opaque string IDs, deterministic external/vector IDs, RFC 3339 UTC datetimes, and integer millisecond half-open media intervals.
- Claim levels: observation, hypothesis, association, causal finding.
- Versioned JSON output envelope and stable exit-code families.
- Versioned feature keys, metric definitions, analyzer/model identities, and analysis profiles.
- Remote media/text transfer is opt-in and represented in configuration/provenance.
- Qdrant collections are immutable embedding spaces; model/dimension changes create a new collection.
- The Python application service layer, not Typer callbacks, owns business behavior.

## 6. Milestone 0 — Repository, contracts, and canonical storage

Completed 2026-11-04. Implemented the package, CLI, platform paths/TOML/environment configuration, stable identifiers/time/output contracts, foundational schema, transactional migrations and checksum ledger, unit of work/repositories, artifact deduplication/reference/checksum handling, process locking, Qdrant lifecycle, and health checks. Graph/timeline/vector indexing remain explicitly deferred to their planned milestones.

Verification: **45 automated tests passed** (unit/property/integration/CLI/subprocess); Ruff lint/format passed; strict mypy passed for 38 source files; wheel and source-distribution builds passed; fresh isolated installation and CLI initialization/verification passed for both distribution formats, including a fully offline repeat after priming the dependency cache. The GitHub Actions matrix is configured for Linux/macOS/Windows with Python 3.11/3.13; only Linux Python 3.11 was executed in this workspace.

Implementation decisions and justifications are recorded in `ARCHITECTURE.md` section 22. Runtime dependencies are locked in `uv.lock`. Build tooling and Python 3.11 were provisioned in `/tmp`; the system Python was not changed. No Milestone 1 media implementation or optional ML models were installed.

### What will be implemented

- Initialize the Python package, Apache-2.0 license, `uv` project, lint/type/test tooling, and console entry point.
- Implement platform-aware data directories with a `--data-dir` override and environment equivalents.
- Define Pydantic command/result contracts, stable IDs, time/interval types, output envelope, domain exceptions, and exit-code mapping.
- Implement the SQLite connection factory, SQLAlchemy Core metadata/repositories, Alembic migrations, transaction unit of work, WAL/foreign-key/busy-timeout settings, and same-host filesystem checks.
- Implement only the first schema slice: migrations, execution/provenance, sources, accounts/posts/media, artifacts, and data-availability records. The full schema is designed in `ARCHITECTURE.md`, but timeline, vector/graph, analytics, and research tables are introduced in the milestone that first exercises them so empty speculative tables do not become compatibility baggage.
- Implement content-addressed artifact paths and reference counting/checksums.
- Implement a process/data-directory writer lock.
- Implement idempotent automatic initialization and commands:

  ```text
  socialdna init
  socialdna doctor
  socialdna storage status
  socialdna storage verify
  ```

- Initialize the Qdrant directory/client metadata safely, but create physical embedding collections only when an embedding space is registered.
- Emit human-readable output by default and the versioned JSON envelope under `--format json`.

### Files involved

- `pyproject.toml`, `uv.lock`, `LICENSE`, `README.md`
- `src/socialdna/cli/{app,output,errors}.py`
- `src/socialdna/application/bootstrap.py`
- `src/socialdna/core/{ids,hashing,time,enums,exceptions}.py`
- `src/socialdna/config/{paths,settings}.py`
- `src/socialdna/domain/{commands,results,evidence,research,providers}.py`
- `src/socialdna/storage/{database,unit_of_work,repositories,artifacts,locking,health}.py`
- `src/socialdna/storage/migrations/*` (foundation slice only)
- `tests/unit/`, `tests/integration/test_initialization.py`, `tests/contract/test_cli_envelope.py`

### Dependencies

Runtime: Python 3.11+, Typer, Pydantic v2, pydantic-settings, platformdirs, SQLAlchemy 2 Core, Alembic, qdrant-client, NetworkX.
Development: pytest, pytest-cov, pytest-xdist where safe, Hypothesis for value objects/schema invariants, Ruff, mypy.
System: none for initialization; FFmpeg is detected but not installed.

### Acceptance criteria

- `uv run socialdna doctor --format json` produces schema-valid JSON in an empty temporary home.
- First use creates only the documented directories/files and applies every migration once.
- Repeating initialization is a no-op and preserves inserted sentinel data.
- A simulated migration failure rolls back or leaves a detectable/recoverable state.
- Foreign keys are active on every connection; SQLite integrity and FTS5 checks are reported.
- Qdrant Local is opened once, explicitly closed, and a second concurrent opener produces an actionable storage-conflict error rather than corruption.
- Unknown fields/metrics are represented as unavailable/absent, never zero.
- No command downloads a model, contacts a hosted provider, or installs FFmpeg.

### Tests required

- Unit: IDs, time intervals, hashes, settings precedence, JSON envelope, exit-code mapping, artifact paths.
- Property: half-open interval validation and deterministic UUID generation.
- Integration: empty/repeated initialization, all migrations up/down where supported, dirty migration detection, foreign keys, WAL settings, network-filesystem warning seam, writer lock, artifact deduplication.
- Contract: `--help`, JSON schema snapshots, stdout/stderr separation, every documented Milestone 0 command.
- Packaging: build wheel/sdist and install the wheel into an isolated environment.

### Integration with previous work

This is the base milestone. All later work uses its application bootstrap, unit of work, task state, artifact store, IDs, and output contract; later milestones do not create alternate storage/configuration paths.

## 7. Milestone 1 — Deterministic local video vertical slice

Completed 2026-11-04. Local file registration/managed copy, FFprobe metadata and source PTS, bounded FFmpeg execution, adaptive scenes/scores, scene-aware frames/contact sheets, visual/audio observations, supplied subtitle tracks, unified timeline queries, durable DAG caching/resume, and typed JSON/Markdown reports are functional. Reports include evidence, provenance, feature definitions/units and explicit unavailable-modality limitations. New revision `0002_timeline` upgrades the released foundation without modifying its checksum.

Verification: **77 automated tests passed**, plus a final two-test regression of failure recovery/selective invalidation after simplifying the cached timeline descriptor. Coverage includes generated owned fixtures; VFR/nonzero starts; delayed/short/no audio; source deletion after managed copy; changed-source rejection; partial failure/resume; interruption after each major task; selective palette invalidation; no duplicate cached measurements/media blobs; malicious filenames; bounded subprocess logs/timeouts; escaping; CLI restart persistence; and released-foundation migration preservation. Ruff lint/format passed for 77 Python files; strict mypy passed for 59 source files. Wheel and source-distribution builds and fresh isolated installs passed, including installed video analysis and a separate-process report from each format; the verification was repeated fully offline after priming the dependency cache. Runtime tests downloaded no models and used no external services. Linux Python 3.11 / FFmpeg 4.4.2 were executed here; the configured macOS/Windows/Python 3.13 CI jobs were not run in this workspace.

Architectural details and justified file-map simplifications are recorded in `ARCHITECTURE.md` section 23 and `docs/video-analysis.md`. Media import remains in `application/import_service.py`; durable task commits use Core directly, and JSON rendering uses the typed report model rather than adding placeholder ingestion/repository/renderer abstractions. No optional ML models, semantic indexing, graph construction, or Milestone 2 work is included.

### What will be implemented

- Local media registration with checksum/deduplication and default source-file reference; `--copy-media` opts into managed storage.
- FFprobe JSON parsing for containers, streams, duration, frame rate/timebase, dimensions, rotation, codecs, start offsets, and errors.
- FFmpeg subprocess wrapper with argument arrays, timeouts, bounded logs, cancellation, and artifact registration.
- PySceneDetect adaptive shot detection with stored configuration and scores.
- Scene-aware frame selection plus regular samples and perceptual deduplication.
- Audio extraction to a normalized analysis format.
- Supplied SRT/VTT parsing as separate text tracks.
- Deterministic visual observations: palette, brightness, saturation, contrast, entropy/edge density, blur proxy, aspect/framing geometry, shot durations, cut frequency, and optical-flow summary on selected intervals.
- Deterministic audio observations: loudness, RMS/energy, spectral features, onset/tempo candidates, silence, and pitch where valid.
- Unified timeline query over visual, text, and audio lanes.
- Durable analysis task DAG, task fingerprints, cache reuse, partial failure, and resume.
- Add the timeline/feature/evidence schema migration and repositories immediately before the pipeline first writes them.
- Commands:

  ```text
  socialdna import local <path>
  socialdna analyze video <path-or-id> --depth quick|standard|deep
  socialdna timeline show <media-id> --start 0s --end 5s
  socialdna report generate --run <run-id> --format json|markdown
  ```

Deep mode at this milestone means denser deterministic analysis; unsupported model-assisted tasks are explicitly skipped.

### Files involved

- `src/socialdna/application/{analysis_service,import_service,report_service}.py`
- `src/socialdna/domain/media.py`
- `src/socialdna/ingestion/{base,local}.py`
- `src/socialdna/media/{probe,ffmpeg,scenes,frames,audio,subtitles,timeline}.py`
- `src/socialdna/analyzers/{base,visual,audio}.py`
- `src/socialdna/reporting/{models,json,markdown}.py`
- `src/socialdna/storage/repositories.py` and the timeline/feature/evidence migration
- `tests/fixtures/media/`, corresponding unit/integration/end-to-end tests

### Dependencies

Python: NumPy, OpenCV headless, PySceneDetect headless, Pillow, SciPy, librosa, soundfile, a maintained SRT/VTT parser such as pysubs2, Jinja2 only if Markdown templating proves useful.
System: FFmpeg and ffprobe.
Milestone 0 storage/contracts.

### Acceptance criteria

- A small deterministic fixture video analyzes from an empty data directory without API credentials or downloaded ML models.
- Scene, frame, text, audio, observation, provenance, evidence, artifact, run, and task rows are populated with valid millisecond intervals.
- A query for the first five seconds returns synchronized lanes and evidence IDs.
- Re-running the same configuration reuses completed tasks and does not duplicate observations/artifacts.
- Changing a visual analyzer configuration invalidates only its dependent tasks.
- Removing FFmpeg yields a precise `doctor` finding and nonzero dependency exit code; no false success report is created.
- JSON and Markdown reports state which modalities ran and which were unavailable.

### Tests required

- Unit: ffprobe parsing including variable-frame-rate/non-zero-start fixtures, subtitle parsing, frame selection/deduplication, feature math, timebase conversion, task fingerprints.
- Golden numeric tests with tolerances for visual/audio features.
- Integration: FFmpeg extraction, scene detection, artifact/checksum persistence, interruption after each major task and resume.
- Security: malicious filenames, malformed media, oversized/timeout paths, HTML/Markdown escaping.
- End-to-end: analyze generated/repository-owned video and assert timestamped report evidence.

### Integration with previous work

Uses Milestone 0 initialization, repositories, task state, provenance, artifacts, and output envelope. It produces the canonical observations/vector documents/graph candidates that Milestone 2 indexes without reprocessing media.

## 8. Milestone 2 — Persistent semantic, lexical, and graph memory

### What will be implemented

- FastEmbed adapter for a revision-pinned `intfloat/multilingual-e5-small` default, including required query/passage prefixes, 512-token chunking, and explicit model preparation/status workflow.
- Immutable embedding-space registry and collection-family creation.
- Qdrant Local collections for content text, transcript text, audience summaries, research text, and optional image embeddings as defined in `ARCHITECTURE.md`.
- Canonical vector documents, deterministic point IDs, durable vector outbox, idempotent upsert/delete, retry leases, and reconciliation.
- SQLite FTS5 indexing for posts, transcripts, and findings with trigger/rebuild verification.
- Graph repositories and schema validation for permitted node/edge types.
- Bounded SQLite neighborhood retrieval and NetworkX `MultiDiGraph` materialization.
- Initial graph construction for account/post/media/scene/observation/evidence relationships.
- Add vector registry/outbox, graph, and FTS5 migrations immediately before those components are enabled.
- Hybrid candidate fusion across FTS, Qdrant, SQL filters, and graph expansion.
- Commands:

  ```text
  socialdna models status|prepare
  socialdna query <question> [structured filters]
  socialdna graph neighbors <id>
  socialdna graph path <from> <to>
  socialdna storage reconcile
  socialdna storage reindex
  ```

- Point-count and local-mode warnings before Qdrant's practical ceiling; explicit external-Qdrant recommendation rather than silent slowdown.

### Files involved

- `src/socialdna/providers/{registry,embeddings}.py`
- `src/socialdna/memory/{vectors,vector_sync,lexical,graph,hybrid}.py`
- `src/socialdna/application/query_service.py`
- `src/socialdna/storage/{health,repositories}.py`
- `src/socialdna/storage/migrations/*` for vector/graph/FTS
- `tests/integration/test_qdrant_persistence.py`
- `tests/integration/test_graph_persistence.py`
- `tests/integration/test_vector_reconciliation.py`
- `tests/end_to_end/test_cross_process_memory.py`

### Dependencies

qdrant-client, FastEmbed/ONNX Runtime as the `local-models` extra, NetworkX, SQLite with FTS5.
Milestones 0–1 canonical records and CLI contracts.

### Acceptance criteria

- With a prepared model, a completed video run indexes the documented representations and graph relations.
- A completely separate process retrieves the analyzed video semantically and traverses its graph relationships.
- Killing the process between SQLite commit, Qdrant upsert, and outbox acknowledgement is repaired by `storage reconcile` without duplicate points.
- Deleting/reindexing a target removes stale points and edges while preserving unrelated data/artifacts.
- A missing/offline embedding model leaves deterministic analysis, FTS, graph, and reports operational and reports semantic search as unavailable.
- Mixing a different model/dimension creates a new embedding space/collection and cannot corrupt the old one.
- Local Qdrant access is single-client and resource closure is covered by tests.

### Tests required

- Unit: collection names, embedding-space compatibility, deterministic point IDs, reciprocal-rank fusion, bounded graph filters.
- Integration: real Qdrant Local persistence, FTS trigger/rebuild, NetworkX reload, graph evidence, outbox crash points, reindex/delete.
- Contract: vector provider conformance and collection schema validation.
- End-to-end essential test: empty directory → analyze fixture → index vector/graph → terminate → new process → semantic retrieve → graph traverse → grounded report.
- Core CI uses an injected deterministic test embedder only to avoid network/model downloads; a scheduled/manual model test uses the real pinned local embedder and is clearly identified.

### Integration with previous work

Indexes Milestone 1's canonical timeline and report representations. The vector/graph layer never bypasses Milestone 0's SQLite unit of work and can be rebuilt solely from canonical records.

## 9. Milestone 3 — Optional local model enrichment and provider safety

Completed 2026-11-04 at the user's explicit request to work on this milestone before Milestone 2. Scope includes verified model preparation/import/status; capability-specific provider contracts; isolated CPU/native worker execution; faster-whisper ASR; RapidOCR boxes/persistence; optional WhisperX forced-alignment, MediaPipe pose and YAMNet adapters; evidence-bounded compatible-server text/vision reasoning; consent/revocation/budget/retry enforcement; transfer audits; model provenance/input-evidence gates; depth controls; cache/resume; report/timeline integration; and a manual native ASR/OCR CI workflow.

The out-of-order dependency change is recorded in `ARCHITECTURE.md` section 24. Existing canonical task/artifact/evidence interfaces provide the integration boundary; vector/graph/FTS memory is not duplicated or claimed available. Milestone 3 was delivered as pre-release `0.0.3`; the original v0.1/v0.2 release gates still require memory/release validation.

Verification: **116 tests passed in one full run with real local-model tests enabled**, including offline CPU ASR/OCR and isolated MediaPipe pose/audio using generated owned media and checksum-verified assets. SDK contracts, privacy/consent revocation, echoed-credential rejection, malformed output, budgets, atomic provenance/evidence gates, selective caching, interrupted model-task recovery and migration preservation passed. Ruff lint/format passed for 92 Python files and strict mypy passed for 69 source files. Wheel/source builds and isolated base installations passed initialization, media analysis and report-restart checks; runtime operation/model inference used no hosted APIs or downloaded assets on demand. Only Linux Python 3.11 was executed here. Real WhisperX checkpoint/GPU execution and real VLM/LLM quality evaluation were not run; their implemented adapters have offline/timing/HTTP schema contracts, not native-model evaluation claims. See `docs/local-enrichment.md` for supported usage and these limitations.

Implemented modules are `providers/{models,registry,worker,reasoning}.py`, `application/enrichment_service.py`, and `analyzers/{speech,ocr,language}.py`, with additive changes to existing contracts, settings, DAG, timeline, reports and CLI. Capability-specific provider wrappers stay cohesive rather than creating empty transcription/vision/audio modules solely to match the target tree. `0003_enrichment` adds the exercised schema; `tests/unit/test_provider*.py`, `tests/integration/test_enrichment.py`, and `tests/integration/test_real_local_models.py` cover the new paths.

### What will be implemented

- Provider registry with capability discovery, local/remote classification, model revision, supported languages, structured output validation, retries, budgets, and caching.
- `faster-whisper` optional local transcription with VAD, language detection, segment/word timing, and CPU/GPU/compute-type profiles.
- Optional WhisperX precision alignment adapter behind a separate extra; diarization remains separately gated and never identifies real people.
- RapidOCR/ONNX optional OCR with frame deduplication, box coordinates, language/model configuration, and persistence across adjacent frames.
- Optional pose/face-landmark analyzer for observable geometry/movement only; no emotion or sensitive-attribute classifier.
- Optional audio event/music classifier adapter, with uncertain interpretations kept separate from deterministic signal features.
- Vision, audio, and text reasoning protocols plus one local in-process or explicitly configured compatible provider implementation. No hosted provider is required for milestone acceptance.
- Evidence-bundle construction, contact sheets, frame/token budgets, structured Pydantic schemas, and invalid-response handling.
- Explicit remote-data consent enforcement and provenance of exactly what left the machine.
- Depth-profile resource estimates and `models prepare` downloads with checksums/offline errors.

### Files involved

- `src/socialdna/domain/providers.py`
- `src/socialdna/providers/{registry,transcription,vision,audio,reasoning}.py`
- `src/socialdna/analyzers/{speech,ocr,language}.py`
- additions to `analyzers/visual.py` and `analyzers/audio.py`
- `src/socialdna/media/timeline.py`
- `src/socialdna/config/settings.py`
- provider/evidence fixtures and contract tests

### Dependencies

Optional extras rather than the base wheel:

- `speech`: faster-whisper/CTranslate2.
- `alignment`: WhisperX and its pinned compatible dependencies.
- `ocr`: RapidOCR + ONNX Runtime.
- `landmarks`: selected maintained landmark runtime/model.
- `local-ai`: selected in-process vision/text/audio provider dependencies.

Milestones 0–2 task fingerprints, artifacts, evidence, and vector memory.

### Acceptance criteria

- Supplied subtitles and ASR remain distinct tracks and can be compared.
- Word timestamps are nullable and never fabricated when the provider supports only segment timing.
- OCR evidence points to actual frame/time/box coordinates.
- Every model-derived observation includes provider/model/revision/config provenance and a deterministic input evidence list.
- Invalid model JSON is rejected; deterministic results remain available and the report is partial.
- Local files cannot be sent to a remote provider without an enabled provider profile and consent policy.
- Changing only the ASR model reuses scene/color/audio extraction and invalidates downstream transcript/language/psychology tasks.
- `doctor` reports model availability, expected downloads, device support, and license/configuration limitations.

### Tests required

- Provider protocol/structured-output contract suite shared by implementations.
- Unit: VAD/timing normalization, OCR box normalization, evidence bundles, budget enforcement, consent decisions.
- Integration: small local ASR/OCR fixtures in opt-in test jobs; provider failure and cache reuse.
- Privacy/security: verify remote adapter receives only allowed derived data and logs no media/API secrets.
- Regression: no model path can write an observation without provenance/evidence.

### Integration with previous work

Adds optional tasks to the existing DAG and writes the same observation/evidence schema. It does not fork the timeline, report, graph, or retrieval model.

## 10. Milestone 4 — Account imports and performance analytics

Status: complete (`0.0.4`), 2026-11-05. Selected by the user while Milestone 2 remains deferred.

Delivered:

- [x] Strict versioned CSV/JSON account/post/media/tag/comment/metric contracts,
  read-only dry runs, atomic row/reference validation and idempotent external keys.
- [x] Raw-export artifacts, permission/source provenance, immutable metric definitions,
  append-only corrections and explicit availability/window/exposure-age semantics.
- [x] Bounded local-video account batches, durable media-cache reuse, partial failures,
  missing/remote-reference reporting and primary-media evidence aggregation.
- [x] Age-aligned outcomes/strict rates, cohorts, leave-one-out robust creator baselines,
  descriptive effects, seeded cluster bootstrap, matching and FDR correction.
- [x] Guarded OLS/Poisson/Gaussian GEE/random-intercept mixed-model paths, interactions,
  rank/dispersion/convergence gates and labeled influence diagnostics.
- [x] Separate chronological/creator validation, cutoff-purged outcomes and training-only
  preprocessing, with deliberately bad leakage fixtures.
- [x] Frozen cohort inputs, full specifications/versions/seeds/results, exact reproduction,
  JSON/Markdown reports, metric/source/evidence citations and cross-process CLI commands.
- [x] Frozen migration `0004_analytics`, package/lock version `0.0.4`, executable examples,
  import/analytics documentation and installed-distribution account smoke coverage.

Implementation details and tradeoffs are recorded in `ARCHITECTURE.md` section 25.
CSV parsing deliberately uses the standard library to preserve identifiers; pandas
handles analytics. Export ingestion lives in `application/account_import_service.py`
beside the existing local-media importer; account orchestration lives in
`application/performance_service.py`. The portable skill, live platform adapters,
psychological discovery, carousel-wide aggregation and semantic/graph indexing are
not included. Normalized exports are supported, not arbitrary vendor layouts.

Verification: the full regression run passed 164 tests including real offline CPU
ASR/OCR and isolated MediaPipe smoke tests (88% aggregate coverage). Final targeted
runs additionally cover the two new strict-JSON hardening tests and updated
account/comparison reproduction and escaped-path cases: 166 tests are now collected.
Ruff lint/format checks pass across 105 Python files and strict mypy across 83 source
files. Both wheel and source distributions pass isolated install, initialization,
integrity, account import/analytics/report restart and video-analysis/report checks
with network disabled after priming the dependency cache. Workspace verification is
Linux/Python 3.11/FFmpeg 4.4.2; other platforms remain covered by the CI definition,
not claimed locally executed.

### What will be implemented

- Versioned CSV and JSON import schemas for accounts, posts, media references, hashtags, comments, metric definitions, metric snapshots, follower counts, and creator-owned analytics exports.
- Dry-run validation, row-level errors, idempotent external-key deduplication, raw-import artifact retention, and permission/source provenance.
- Append-only metric snapshots with collection time, observation window, post age, platform definition, and explicit availability states.
- Batch media linking/analysis for imported account histories.
- Creator-relative robust baselines and post-age-aligned outcomes.
- Cohort construction by platform, creator, niche, content type, duration, topic, and observation window.
- Add metric, derived-metric, cohort, and statistical-analysis migrations in the same milestone as their first working use cases.
- Descriptive summaries, effect sizes, bootstrap intervals, correlation, simple regression/GLM, interactions, outlier/influence diagnostics, and matched comparison workflow.
- Cluster-aware GEE/mixed-model path only when sample/cluster preconditions are met.
- Chronological/grouped validation, leakage-safe preprocessing pipelines, and false-discovery-rate correction.
- Commands:

  ```text
  socialdna import csv|json <path> [--dry-run]
  socialdna analyze account <account-id>
  socialdna compare posts|accounts ...
  socialdna report generate --account <id>
  ```

### Files involved

- `src/socialdna/ingestion/tabular.py`
- `src/socialdna/application/import_service.py`
- `src/socialdna/analytics/{metrics,baselines,cohorts,statistics,validation}.py`
- `src/socialdna/domain/research.py`
- `src/socialdna/storage/migrations/*` for metrics/cohorts/statistical results
- `src/socialdna/reporting/{models,json,markdown}.py`
- `docs/import-formats.md`, `examples/imports/*`
- analytics/import tests and fixtures

### Dependencies

pandas, NumPy, SciPy, scikit-learn, statsmodels.
Milestones 0–1 and 3 canonical storage, media analysis, provenance and evidence.
Milestone 2 retrieval/projections remain deferred and are not required for this slice.

### Acceptance criteria

- Missing shares/saves/retention remain unavailable and never enter denominators as zero.
- Importing the same external dataset twice is idempotent; changed snapshots append without mutating history.
- A post with two years of exposure is not directly compared to a one-day post unless a declared model/window justifies it.
- Account reports display available sample size, missingness, observation-age distribution, outcome definitions, effect sizes, intervals, adjusted p-values where relevant, and limitations.
- Creator leakage and target leakage tests fail intentionally bad pipelines and pass the production one.
- Insufficient samples return descriptive results plus an `insufficient_data` limitation, not an unstable regression.
- Results and full analysis specifications are persisted and reproducible from stored inputs/configuration.

### Tests required

- Unit/property: schema validation, timezone parsing, metric formulas, missingness, baseline math, cohort membership, matching, bootstrap, FDR.
- Golden comparisons against hand-calculated small datasets and selected statsmodels/SciPy results.
- Integration: idempotent imports, snapshot history, raw provenance, batch analysis, report citations.
- Leakage: chronological and grouped split fixtures with deliberately duplicated creators/future features.
- Robustness: small n, constant values, perfect separation, collinearity, heavy outliers, missing denominators.

### Integration with previous work

Connects media observations from Milestones 1–3 to real performance snapshots, while reusing the same accounts/posts/evidence/vector/graph IDs. It creates the comparable populations required by Milestone 5.

Current implementation reuses canonical account/post/media/evidence IDs and leaves
vector/graph projections for Milestone 2; it does not claim that retrieval exists.

## 11. Milestone 5 — Psychology, cross-content discovery, and research findings

### What will be implemented

- Versioned psychological taxonomy with definitions, observable cues, exclusions, confounders, and interpretation rules.
- Deterministic cue rules for hooks, literal questions, delayed reveals, calls to action, transformations, social-proof language, utility framing, participation, and related mechanisms.
- Evidence-constrained structured hypothesis generation using configured reasoners.
- Adjudication that verifies evidence references, applies confidence rubric, generates alternatives, requests missing modalities, and enforces prohibited-inference rules.
- Research question registration, candidate relationship generation, redundant-feature grouping, cohort/statistical evaluation, multiple-testing correction, sensitivity checks, counterexample retrieval, and persistent findings.
- Add taxonomy, hypotheses, research questions/findings, evidence links, and experiment migrations with the first complete discovery workflow.
- Hybrid natural-language query planning over SQL/FTS/vector/graph with explainable component results.
- Recommendation generation only from scoped findings; each recommendation includes evidence, applicability, counterexamples, uncertainty, and a proposed experiment.
- Experiment brief creation and later outcome ingestion.
- Commands:

  ```text
  socialdna research discover --question <text> [scope options]
  socialdna research show <finding-id>
  socialdna query <research question>
  socialdna psychology show --post|--media <id>
  socialdna recommend --topic <text> --scope <...>
  ```

### Files involved

- `src/socialdna/psychology/{taxonomy,cues,hypotheses}.py`
- `src/socialdna/research/{questions,discovery,counterexamples,findings}.py`
- `src/socialdna/memory/hybrid.py`
- `src/socialdna/analytics/{statistics,validation}.py`
- `src/socialdna/reporting/*`
- `src/socialdna/storage/migrations/*` for psychology/research/experiments
- `skills/socialdna/references/{psychology,research-methodology,interpretation-rules}.md` drafted here but not yet published as a finished skill
- annotated psychology/research fixtures and evaluations

### Dependencies

No new mandatory base dependency. Uses the optional reasoning/vision/audio providers and analytics stack from prior milestones.

### Acceptance criteria

- Every mechanism hypothesis cites existing evidence and has alternatives/counterexamples or an explicit reason none were available.
- No hypothesis is rendered as an association without a linked statistical analysis; no association is rendered as causal without a registered qualifying experiment/design.
- Discovery stores all tested candidate relationships and adjusted values, not only positive results.
- Queries can reproduce an example such as “short cooking videos with curiosity hooks, warm colors, and relatively strong engagement” using measured filters, semantic representations, and scoped comparisons.
- Cross-platform/niche findings remain scoped and are not generalized automatically.
- Prohibited sensitive/mental-state inference prompts are rejected or reframed to observable behavior.
- Human-annotated evaluation reports mechanism precision/recall, evidence-span accuracy, inter-rater disagreement, and confidence calibration by taxonomy version.

### Tests required

- Unit: taxonomy validation, cue rules, claim promotion guards, confidence rubric, query planner, finding versioning.
- Contract/adversarial: hallucinated evidence IDs, unsupported causal language, sensitive trait inference, prompt injection in captions/comments.
- Statistical integration: candidate family → FDR → counterexample/sensitivity → persisted finding.
- Evaluation: frozen labeled mini-corpus with expected mechanism/evidence ranges; provider-specific jobs remain optional but structured validation is mandatory.
- End-to-end: multi-account fixture research question produces scoped observations, association or insufficient-data result, counterexamples, and an experiment brief.

### Integration with previous work

Consumes only canonical observations, evidence, metrics, cohorts, vectors, and graph relations created earlier. Findings feed back into SQLite, Qdrant research collections, and graph edges through the existing outbox/repository mechanisms.

## 12. Milestone 6 — Photo/carousel breadth, reports, Agent Skill, and v1 hardening

### What will be implemented

- Photo ingestion/analysis using the existing visual, OCR, caption, evidence, and provider pipelines.
- Ordered carousel analysis: opening-slide hook, inter-slide continuity, typography/readability, narrative progression, caption alignment, and closing call to action.
- Complete single-media, timeline, account, multi-account, psychology, cross-niche, strategy, and experiment reports in JSON/Markdown/static HTML.
- Sanitized static HTML templates with embedded local artifact copies/relative links, no remote JavaScript requirement, and accessibility basics.
- Final portable `skills/socialdna/SKILL.md` under 500 lines with concise frontmatter and progressive-disclosure references.
- CLI reference and representative schema-valid output examples generated/tested from real fixtures.
- Installation tooling/documentation for project/user skill locations in Codex and Claude Code without maintaining divergent skill content.
- Documentation completeness, packaging metadata, changelog/release process, model/license notices, contribution/security policies, and performance benchmark suite.
- Validate `uv tool install` against a built/published candidate before documenting it as supported.

### Files involved

- additions to `src/socialdna/ingestion/local.py`, `analyzers/visual.py`, `application/analysis_service.py`
- `src/socialdna/reporting/{html,templates/*}` and all report renderers
- `skills/socialdna/SKILL.md`
- `skills/socialdna/references/{cli,workflows,psychology,research-methodology,interpretation-rules}.md`
- `README.md`, `docs/*`, `examples/*`, package/release metadata
- `tests/contract/test_documented_commands.py`, report snapshots, skill validation/evals, packaging tests

### Dependencies

Jinja2 and a small HTML sanitizer/escaping strategy if not already introduced. Agent Skills reference validator used in development/CI. All prior milestones.

### Acceptance criteria

- Photos and carousels produce evidence-linked reports and enter the same retrieval/graph system as videos.
- Every documented command executes; future commands are labeled future and excluded from examples implying availability.
- HTML reports render offline, escape hostile imported/model text, retain evidence/timestamps, and remain useful with partial data.
- `SKILL.md` validates against the Agent Skills specification, routes representative requests correctly, invokes JSON CLI commands, respects permission/remote-upload gates, and interprets claim levels accurately in both Codex and Claude Code evaluations.
- Wheel/sdist installation, clean first run, all core end-to-end tests, migration from every supported prior schema, backup/restore, and documentation link checks pass.
- Base install requires no paid key, external database server, Docker, or local AI model download.
- The release notes clearly separate fully local, optional-model, hosted-provider, and future platform features.

### Tests required

- Unit/integration: photo/carousel ordering, caption/image alignment, report model completeness, sanitizer, relative assets.
- Contract: Agent Skill frontmatter/size/references, JSON schemas, command docs versus Typer command tree, examples versus actual output.
- Agent evals: single-video analysis, first-five-seconds investigation, account comparison, missing-data case, unsupported trend request, remote-upload consent, and causal overclaim trap.
- Packaging: clean Linux/macOS/Windows-compatible path tests where CI supports them; Python 3.11 through supported versions.
- End-to-end release scenario from install through cross-process report, plus backup/restore and re-query.

### Integration with previous work

Completes the initial product by reusing all established contracts. No alternate “photo database”, “carousel graph”, or agent-only engine path is introduced.

## 13. Milestone 7 — Permission-aware official platform adapters (optional post-v1)

### What will be implemented

Implement adapters one at a time, each behind an extra and feature flag. An adapter is accepted only when its permitted use, authentication, pagination, quota, retention, raw provenance, deletion, and fixture strategy are complete.

- **YouTube:** Data API metadata/public statistics and OAuth-authorized Analytics/Reporting for owned channels. Media analysis still requires a permitted local/owned media source.
- **Instagram:** authorized professional-account media metadata, comments, and insights using the supported login/permissions/access level.
- **TikTok:** approved API path appropriate to the user; Research API support is explicitly non-commercial/eligibility-gated. Creator exports/imports remain the general path.
- Backoff, conditional requests where supported, incremental cursors, token refresh abstraction, quota accounting, API-version pinning, source terms, and data deletion propagation.

### Files involved

- `src/socialdna/ingestion/platforms/{youtube,instagram,tiktok}/...`
- provider/config credentials and permission policy modules
- raw-response mappings, API schema fixtures, adapter contract tests
- platform-specific docs and examples

### Dependencies

Official or minimal HTTP/OAuth clients selected per adapter, installed as extras. No platform SDK enters the base install merely for name recognition.

### Acceptance criteria

- Adapter conformance suite proves idempotent incremental import, provenance, unknown/missing metric handling, pagination, rate-limit/backoff, token expiration, and deletion.
- Tests use recorded/synthetic sanitized responses; live tests run only with explicit credentials in protected jobs.
- No adapter downloads media, accesses consumer/private analytics, or exceeds its documented authorization.
- An unsupported account/use case returns a permission/availability explanation and an import/export alternative.

### Tests required

- Unit mapping tests for every supported API version/metric.
- OAuth/token/quota simulations, pagination, 429/retry-after, stale/lagging metrics, partial permissions.
- Live smoke per platform in a protected environment before release.
- Terms/retention/deletion checklist reviewed for each adapter version.

### Integration with previous work

Adapters emit the same `ImportBatch`/source/provenance records as CSV/JSON and then use the established media, analytics, memory, and reporting services.

## 14. Milestone 8 — Research Mode scale adapters (optional post-v1)

### What will be implemented

- Remote Qdrant implementation first, because Qdrant Local's exclusive lock and point ceiling are the earliest scaling constraint.
- Storage capability/config interface hardened from real Local Mode behavior; migration/export/reindex tooling moves canonical vector documents into the remote index.
- Background worker mode using the existing durable task/outbox model only after profiling proves the need.
- Optional object storage for artifacts.
- PostgreSQL and a graph backend only after concrete workloads exceed SQLite/bounded NetworkX and their semantics are specified. They are not blanket checkboxes.
- Multi-user authentication, authorization, tenancy, encryption, backups, and operations are required before calling Research Mode production-ready.

### Files involved

- new implementations under `memory/`, `storage/`, and `application/worker.py`
- deployment/configuration/operations docs
- migration, parity, load, resilience, and security tests

### Dependencies

Selected external clients/services are optional extras/deployments. Local Mode remains supported and does not gain service requirements.

### Acceptance criteria

- The same application/CLI contract passes backend conformance tests in Local and configured Research Mode.
- A documented export/reindex path moves a local library without changing canonical IDs/evidence citations.
- Load tests establish explicit operating envelopes, not vague “scalable” claims.
- Failure/retry behavior cannot duplicate canonical analyses, points, or graph claims.

### Tests required

- Backend contract parity, migration/reindex, load/soak, concurrent workers, network partition/retry, backup/restore, tenant isolation, and disaster recovery.

### Integration with previous work

Reuses canonical IDs, task fingerprints, vector documents, outbox, graph/evidence contracts, and CLI envelope. It replaces infrastructure implementations, not the scientific/domain model.

## 15. Test strategy across milestones

### Test pyramid

- **Unit:** pure transformations, schemas, feature math, statistics, query planning, claim guards.
- **Property:** IDs, time intervals, import/missingness invariants, idempotency, deduplication.
- **Contract:** CLI JSON, providers, vector backends, graph repositories, platform adapters, reports, skill format.
- **Integration:** SQLite migrations/transactions, FFmpeg, Qdrant Local, FTS5, NetworkX persistence, artifact store.
- **End-to-end:** isolated subprocess workflows from empty data directory, including process restart.
- **Evaluation:** annotated multimodal/psychology fixtures and agent-skill scenarios.
- **Performance:** representative short/long videos, account sizes, vector point counts, graph neighborhood sizes.

### Fixture policy

- Generate simple audiovisual fixtures deterministically with FFmpeg where possible.
- Keep one tiny, Apache-compatible repository-owned video/photo/carousel fixture for realistic decode tests.
- Store expected feature ranges rather than codec-fragile exact floats.
- Never require external APIs or model downloads in the core CI suite.
- Optional model/live-platform jobs are clearly separated and cannot make the base test suite nondeterministic.

### Essential end-to-end scenario

The release-blocking test uses subprocesses:

1. Create an empty temporary data directory.
2. Initialize automatically through `analyze video` rather than requiring `init`.
3. Analyze the authorized fixture with supplied subtitles and deterministic analyzers.
4. Assert SQLite metadata/timeline/evidence, artifacts, Qdrant points, and graph edges.
5. End the process and verify all handles are closed.
6. Start a second process.
7. Retrieve the media through semantic search and FTS.
8. Traverse its evidence-bearing graph neighborhood.
9. Generate JSON and Markdown reports.
10. Verify every substantial claim resolves to stored evidence and no unavailable task is represented as complete.

## 16. Performance and computational envelope

Benchmarks are captured per depth profile, media minute, resolution, device, analyzer/model, and cache state. Before optimizing, instrument:

- decode time and bytes read;
- number of decoded/selected/deduplicated frames;
- optical-flow/OCR/ASR/VLM time and peak memory;
- artifact bytes per media minute;
- SQLite transaction/lock time;
- vector documents/collection and search latency;
- graph neighborhood rows/nodes/edges;
- provider tokens/cost when configured.

Initial safety defaults:

- one mutating run per data directory;
- bounded video duration/resolution unless explicitly overridden;
- bounded keyframes and VLM contact-sheet size;
- bounded transcript chunk length/overlap;
- comment clusters instead of per-comment vectors;
- bounded graph depth/node count;
- local collection warnings before 20,000 points;
- inference concurrency based on device/RAM rather than CPU-count blindly.

## 17. Risks and mitigations

| Risk | Impact | Mitigation / release gate |
|---|---|---|
| Qdrant Local exceeds practical scale | slow/locked semantic search | warnings, coarse documents, one client, remote-Qdrant path, never claim unlimited scale |
| Cross-store partial failure | stale/orphaned vectors | canonical vector docs + outbox + deterministic IDs + reconcile/reindex |
| Model outputs fabricate evidence | false research claims | schema validation, evidence-ID existence checks, claim ladder, partial failure |
| Observational confounding/leakage | misleading “success formula” | post-age cohorts, clustered models, chronological/group splits, FDR, counterexamples |
| Platform access changes | broken/unauthorized imports | local/import core, adapter versioning, official APIs only, permission provenance |
| Heavy optional ML install | poor first-run experience | extras, deterministic base, explicit model preparation, doctor/resource estimates |
| FFmpeg/untrusted media | crashes/security exposure | argument arrays, timeouts, limits, temp isolation, patched supported versions |
| Storage on network filesystem | WAL/locking hazards | doctor detection/warning; supported local filesystem contract |
| PII/comment retention | privacy/compliance harm | minimization, pseudonymization, source terms, scoped delete/export |
| Taxonomy cultural/language bias | invalid psychological labels | versioned definitions, multilingual evaluation, human annotation, scope/uncertainty |
| Skill drift from CLI | agent failures | generated/contract-tested command reference and output schemas |

## 18. Documentation delivered incrementally

Each milestone updates only implemented behavior:

- `README.md`: installation, current capabilities, first run, exact limitations.
- `docs/storage.md`: layout, initialization, consistency, backup, deletion, concurrency.
- `docs/data-model.md`: IDs, timeline, claim/evidence model, migrations.
- `docs/local-analysis.md`: depth profiles, FFmpeg, optional models, resource use.
- `docs/import-formats.md`: versioned CSV/JSON schemas and examples.
- `docs/statistics.md`: outcome windows, cohorts, models, validation, causal limitations.
- `docs/providers.md`: local/remote providers, downloads, privacy, budgets.
- `docs/platforms.md`: permission/access limitations only after each adapter exists.
- `docs/agent-skill.md`: installation and JSON orchestration after validation.

Representative output examples are generated from fixtures or validated against the JSON schemas in CI; hand-written examples cannot silently drift.

## 19. Approved implementation defaults

The following defaults were approved on 2026-11-04:

1. SQLite is canonical; Qdrant and NetworkX are derived/rebuildable.
2. SQLAlchemy Core + Alembic provide transactions and migrations without adopting an ORM domain model.
3. Qdrant Local is a single-process small-data backend with an external-Qdrant escape hatch.
4. `faster-whisper` is the standard transcription extra; WhisperX is an optional alignment/diarization extra.
5. RapidOCR/ONNX is the initial OCR extra.
6. FastEmbed with revision-pinned `intfloat/multilingual-e5-small` (MIT, 384 dimensions) is the proposed local text-embedding default.
7. The base install performs deterministic analysis without downloading ML models; model downloads are explicit.
8. The initial agent integration is the portable Skill plus CLI JSON; a custom MCP server is deferred.
9. Local/user-owned files and exports are the only guaranteed ingestion path; official platform adapters are post-v1 and permission-aware.
10. The initial release is Milestones 0–6; scale/platform breadth does not block it.

Approval authorizes only the milestones selected for implementation. It does not authorize remote provider uploads, platform credentials, dependency installation outside the project, or post-v1 infrastructure by implication.
