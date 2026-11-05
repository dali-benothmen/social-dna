# SocialDNA implementation plan

Revised: 2026-11-05. Scope: R1–R8 completed and verified; R8 verification is recorded in §12. Prepared-real-model acceptance remains opt-in and was not run without supplied weights; no later milestone implementation is claimed.

Runtime: package `0.0.12`, SQLite head `0012_reevaluation`. Released migrations `0001_foundation`–`0011_research` remain unchanged. Legacy Milestones 0, 1, 3 and 4 are completed deliveries; their limitations remain visible. Legacy Milestones 2, 5 and 6 are **superseded, not completed**. **R9–R10, C1 and U1/U2 remain planned and unimplemented**.

Authoritative design: [ARCHITECTURE.md](ARCHITECTURE.md), [research contracts](docs/research-contracts.md), [statistical design](docs/statistical-design.md), [migration strategy](docs/migration-strategy.md), and [reference use case](docs/research-use-case.md). The [audit](docs/architecture-audit.md) records the reasons for this revision; the [previous roadmap](docs/history/PLAN.pre-research-revision.md) is historical, not an alternative active plan.

The [four-area capability audit](docs/intelligence-capability-audit.md) adds explicit production, platform/surface distribution, publishing/discoverability and profile/conversion coverage. These are partially supported foundations today, not delivered intelligence systems. C1 supplies bounded future evidence extensions; its implementation was not added to R7.

## 1. Outcome, limits and delivery rules

SocialDNA is a local-first Python engine and portable Agent Skill that investigates why content may succeed. It preserves observable evidence, evaluates competing explanations with appropriately scoped data, compares creators without hiding confounding, and revises findings as evidence changes. It is not a psychological diagnosis system, a universal virality score, or a machine for proving mechanisms from observational correlations.

The target joins how content is produced, why audiences respond, how specific platform surfaces distribute it, how publishing/search metadata affects discovery, and how profiles convert attention into sustained growth/business outcomes. Search discovery, recommendation exposure and account conversion are separate objectives. Official platform statements, observed associations and identified experiments remain separate evidence lanes; no proprietary ranking-weight recovery or distribution guarantees.

The revised design preserves working media processing, synchronized timelines, provenance, artifacts, account exports, statistical tooling, reproducible reports and CLI execution. SQLite remains authoritative; persistent Qdrant Local retrieval and SQLite-backed NetworkX projections are introduced only when canonical producers and revision semantics exist. No database server, paid API, new distributed service, or automatic model download is required.

Delivery rules:

- Implement one bounded milestone at a time; finish its working end-to-end behavior and tests before claiming completion. Separate optional provider work from the required offline path.
- Add schema only alongside its first canonical writer, resolver and demonstrable reader. Designing later payloads does not require creating unused tables now.
- Preserve old IDs, frozen analyses, raw artifacts and report bytes wherever retention is permitted. Required erasure preserves only allowed tombstones/audit metadata and explicitly degrades reproduction. Corrections produce explicit new revisions; they do not silently alter historical conclusions.
- Keep basic media/account analysis fast: do not register a research question, load a graph, index embeddings or invoke a reasoner merely to describe a video.
- Missing data is not zero; absent detection under sparse sampling is not demonstrated absence; expressed intention is not behavior; association is not causation.
- Every research result declares its population, availability, estimand, evidence version, uncertainty, alternatives and limitations. `insufficient_data`, rejected and inconclusive results are successful research outcomes when honestly supported.
- Implementation changes require unit/integration/contract/end-to-end verification, migration/compatibility checks, documentation updates and a scoped working commit when authorized. R8 is the currently authorized implementation; C1 and later work require separate authority. Commit messages describe the engineering change without type prefixes or milestone labels.

## 2. Preserved implementation and historical deliveries

| Legacy delivery | Implemented and preserved | Recorded verification at delivery |
|---|---|---|
| M0, `0.0.1`, 2026-11-04 | Installable CLI; settings/IDs/output contracts; SQLite/UoW/migrations; provenance and sources; artifacts; locking; Qdrant lifecycle and health checks | 45 tests; lint/type/build/isolated-install checks |
| M1, `0.0.2`, 2026-11-04 | Local video registration/probing; deterministic scenes/frames/visual/audio measurements; supplied subtitles; shared timeline; durable task cache/resume; evidence-backed JSON/Markdown reports | 77 tests plus targeted recovery/cache regressions; installed cross-process video/report checks |
| M3, `0.0.3`, 2026-11-04, deliberately before M2 | Optional prepared local ASR/OCR/pose/audio adapters; provider isolation; consent/budget/provenance gates; model/task/report integration | 116 tests including real CPU ASR/OCR and isolated MediaPipe; optional alignment/VLM quality not empirically established |
| M4, `0.0.4`, 2026-11-05, deliberately before M2 | Strict CSV/JSON account/post/comment/tag/metric exports; immutable snapshots; local-media account batches; guarded descriptive/model paths; frozen analytics and JSON/Markdown reports | 164-test full run including local-model smoke; final targeted hardening raised collected tests to 166; lint/type/build/offline-install checks |

These counts are historical delivery records. R1's current verification is recorded below. Only Linux/Python 3.11 was locally executed at those deliveries; configured CI platforms are not claimed as observed results.

M4 delivered its scoped implementation, but its retrospective baseline, same-creator matcher, cross-niche design and model-validation mismatch need R2 remediation. Existing reports remain reproducible and are not retroactively relabeled as corrected. The old M2 memory design and broad M5/M6 delivery bundles are replaced below, rather than treated as satisfied by the completed work.

## 3. Dependency-aware delivery sequence

| ID | Working result | Hard dependencies | Status |
|---|---|---|---|
| R1 | Universal evidence with usable metric/comment citations and minimal research registration | Existing `0.0.4` foundation | Completed and verified, `0.0.5` |
| R2 | Correct historical baselines, comparison designs, feature timing and actual-pipeline validation | R1 | Completed and verified, `0.0.6` |
| R3 | Semantic creative events and reproducible multimodal feature recipes | R1; R2 for analytics joins | Completed and verified, `0.0.7` |
| R4 | Audience collection provenance, reaction annotations and qualified content links | R1, R3 | Completed and verified, `0.0.8` |
| R5 | Behavioral metric series, denominators, attribution and account outcomes | R1, R2; R3 for event overlays | Completed and verified, `0.0.9` |
| R6 | Persistent SQL/FTS/Qdrant/SQLite-backed NetworkX research memory | R1–R4; R5 for behavioral projections | Delivered `0.0.10`; real-model acceptance opt-in |
| R7 | First complete, literature-backed psychological research vertical slice | R2–R6 | Completed and verified, `0.0.11` |
| R8 | Incremental hypothesis reevaluation and preserved contradiction history | R7 | Completed and verified, `0.0.12` |
| C1 | Versioned production and growth-context evidence, four independent deliveries | R1–R6; after R7; U1 for static visual branches | Planned extension track; see §19 |
| R9 | Bounded nonlinear, cross-creator and cross-niche discovery, including delivered C1 dimensions | R2, R3, R6–R8; respective C1 slice for a new domain branch | Planned |
| R10 | Registered experiment outcomes and evidence-qualified creative/distribution/publishing/profile recommendations | R7–R9; respective C1 slice for a new domain branch | Planned |
| U1 | Individual photo/carousel analysis reusing existing media contracts | R1 | Planned, parallel usability track |
| U2 | Portable Codex/Claude Code/OpenCode skill and usable reports | U1, R2; capability-gated integration with later R milestones | Planned, parallel usability track |

Audience comments and behavioral metrics are split into R4/R5 because sampling/semantic annotation and metric time-series validity are different testable products. Memory follows canonical producers and revision contracts, rather than freezing the current media-only evidence model. A small literature corpus, hypothesis registration and experiment proposal appear in R7; general discovery and experiment-outcome analysis wait for R9/R10. U1/U2 prevent research infrastructure from postponing ordinary creator workflows.

R6 must work without prepared embeddings through SQL/FTS/graph retrieval; semantic acceptance additionally requires a verified prepared local embedding model. R7 must work with authorized local media, imported human annotations and curated research when no VLM is installed. Creator-owned retention is an optional richer evidence branch, never an invented prerequisite substitute.

C1 is not a prerequisite for R7 or for the existing R8/R9 cooking branch. After R7, deliver C1-A/B/C/D as small tested slices alongside U1/R8 where appropriate; advanced domain branches consume only their delivered prerequisites. R7 must record production/distribution/publishing/profile alternatives or missing context, not implement four additional engines. Export-first offline paths are required; live platform adapters remain optional.

## 4. Cross-cutting interfaces and compatibility gates

Preserve current commands and output/exit-code families: `init`, `doctor`, `storage status|verify`, `import local|csv|json`, `analyze video|account`, `timeline show`, `models status|prepare`, `compare posts|accounts|reproduce`, and `report generate --run|--account`. New behavior is additive or uses explicit versioned specification fields. Old comparison specifications retain legacy semantics for exact reproduction; corrected analyses use a new specification/method version. Old reports never acquire a new interpretation just because software was upgraded.

R1's commands are available as documented in [R1 operations](docs/research-foundation.md). Later-milestone command sketches remain proposed interfaces. The exact argument surface is stabilized by contract tests at the implementing milestone. All agents call the same Python services/CLI; agent instructions contain no alternate statistics, hidden browser scraping or host-specific database logic.

Each future migration must preserve released migration checksums and old evidence identities, upgrade a fixture from every released head, survive an interrupted upgrade, and pass `storage verify`. Back up and validate before upgrades; destructive retention/redaction is explicit and audited. See [migration strategy](docs/migration-strategy.md).

Research materialization is lazy and budgeted. The canonical research layer must accept observed, inferred and human-adjudicated inputs with distinguishable provenance. Index jobs carry generation/revision and eligibility tokens. A deleted/withdrawn source cannot be resurrected by old work. Research-graph relationships carry a finding/assessment identity, scope, qualification and evidence; multiple input features form a pattern entity, not independent causal-looking edges.

## 5. R1 — Universal evidence and minimum research contracts

Status: **completed and verified in `0.0.5` / `0005_evidence`**, 2026-11-05.

Delivered: typed versioned media/comment/metric citations and aliases; immutable captured source revisions; draft registration/show/report CLI and Python services; append-only withdrawal eligibility, derived-input checks and current-view withholding; restartable backfills; pre-upgrade backups and restricted/same-lineage reconciled restore. See [R1 operations](docs/research-foundation.md) and [implementation decisions](ARCHITECTURE.md#17-r1-implementation-decisions-and-boundaries).

Boundary clarification: R1 withdrawal revokes new use but does not erase retained bytes. Full audience/raw-import/derived-report redaction remains R4 and index cleanup R6, as assigned in the migration strategy. R1 never reports erasure as completed; historical bytes may remain only under permitted retention. No R2 statistics, R7 evaluation or R8 reevaluation was implemented.

Verification record (Linux/Python 3.11):

- Full `pytest -q`: **189 passed, 2 skipped** (the optional real-model library/interpreter was not configured).
- Final additional `tests/unit/test_research_foundation.py`: **3 passed** for escaping, exact Unicode spans and no-write WAL refusal. Total: **192 distinct passing tests**, two optional model tests skipped.
- Focused R1 integration/upgrade tests and cross-process frame→comment→metric→registration→report→withdrawal workflow passed. Upgrade fixtures cover all four released heads, original IDs/report bytes, interrupted backfill, downgrade refusal, restored withdrawal journals and restricted recovery.
- Ruff lint/format, strict mypy, unchanged released migration checksums, documentation links and `git diff --check` passed. Offline `uv lock --check` passed without dependency changes.
- Wheel and sdist build and isolated offline installs passed R1 citation/registration/report restart plus existing account analytics and real FFmpeg video/report workflows. No model downloads or platform API calls were required.

### Objective

Deliver one resolver and citation format that works for existing media evidence, a real imported comment span and a real metric snapshot without dummy media or fabricated timestamps. Register a research question and a versioned hypothesis specification without pretending evaluation is implemented.

### Existing components affected

`domain/evidence.py`, `domain/research.py`, `storage/{schema,repositories,health}.py`, `application/{account_import_service,performance_service,report_service}.py`, reporting models/renderers and additive CLI adapters. Existing timeline producers and released migrations remain intact.

### New components and schemas/interfaces

Add `application/evidence_service.py`, a cohesive research registration service and canonical research repository. Introduce an evidence identity registry, typed subtype locators for existing media/comment/metric evidence, source availability/eligibility, evidence links and withdrawal metadata. Register legacy media IDs unchanged. Use stable entity references, explicit target revision and typed locator validation; no polymorphic target is accepted without resolver validation. Introduce minimal question, hypothesis identity and immutable specification revisions actually used by registration. Later study/statistical/experiment subtype writers are added in their own milestones against the same contract.

Proposed interfaces: `evidence resolve <id>`, `research register --spec <file>`, and `research show <id>`. They return the normal JSON envelope with exact source/revision and current citation eligibility. See [research contracts](docs/research-contracts.md) for authoritative fields.

### Dependencies and tasks

Depends only on current storage/provenance/reporting contracts; use existing Pydantic/SQLAlchemy/SQLite, not new servers or models. Tasks: provide and verify a quiescent backup/restore procedure; add an additive migration; backfill registry identities idempotently; implement subtype resolution and validation; expose registration; integrate metric/comment citations into a persisted report; add withdrawal/stale hooks without implementing reevaluation.

### Acceptance criteria

An old media citation resolves under the same ID after upgrade. A comment quote and metric snapshot resolve to their real imported sources and exact revisions. Wrong subjects/runs, invalid spans and nonexistent targets are rejected. Withdrawing evidence prevents its use in a new conclusion and degrades the current report view while preserving historical immutable artifacts where retention is permitted; required erasure leaves only allowed tombstones/audit metadata and an explicit reproduction limitation. Basic media analysis does not create research entities automatically.

### Automated tests

Verified backup restoration into a separate directory including later-withdrawal reconciliation/restricted recovery and external-input inventory; upgrade/rollback and checksum invariance; legacy ID/backfill idempotency; subtype constraints and entity existence; Unicode span bounds; snapshot/source agreement; unavailable/withdrawn evidence; report escaping; CLI envelopes; no-write dry runs; separate-process persistence. Run all existing media/account/report regressions.

### Demonstrable end-to-end behavior

Import the cooking fixture and real comment/metric records → register a research question → produce a report citing one opening frame, one quoted comment and one seven-day metric → restart and resolve all three citations → withdraw one source and observe an explicit evidence limitation, not an invented replacement.

## 6. R2 — Statistical correctness and comparison repairs

Status: **completed and verified**, `0.0.6` / `0006_designs`.

Delivered:

- Explicit `schema_version: "2.0"` dispatch with estimand/design, two cutoffs, baseline/maturity/feature policies, sampling frame, covariates, family and split controls; unversioned execution remains legacy.
- Historical references from complete declared creator history, as-of source corrections and exact frozen reference manifests; separate publication/evaluation benchmarks and retrospective cohort policy.
- Outcome-blind within/distinct-creator matching, support/balance/distribution diagnostics, signed/missing covariates and honest descriptive/unsupported results.
- Persistent primitive feature lineage, recipe availability, captured topics and versioned media associations/invalidation; actual import/recipe availability gates historical prediction.
- Identifiable within-creator OLS/Poisson design with explicit absorbed nuisance context, real declared interactions and train-only transformations; the same model pipeline is used for validation. Unseen-creator intercept prediction is explicitly unsupported, not replaced with Ridge.
- Duplicate-SHA-aware chronological/creator/joint splits; declared-family attempts including null/failure/refusal states and single-use holdout reservations, with overlapping-post/media reuse refusal.
- Exact analysis/term/diagnostic citations through the existing universal resolver, transitive withdrawal, versioned reports and reference/input hash checks on reproduction.
- Data-preserving, rollback-tested migration and verified pre-upgrade backup; no new dependencies, models, network collection or servers.

Implementation map: existing analytics helpers plus `analytics/{features,designs}.py`; versioned contracts in `domain/research.py`; population and legacy dispatch in `application/performance_service.py`; persistence/ledgers in `application/statistical_service.py`; typed statistical evidence bindings in the common repository/resolver; thin existing CLI adapters and performance renderer. All new tables have exercised writers/readers.

Supported limits and decisions are recorded in [versioned analytics operations](docs/versioned-analytics.md) and [architecture decisions](ARCHITECTURE.md#18-statistical-correctness-implementation-decisions). Cross-creator matches remain descriptive without defensible exchangeability/dependence assumptions; between-creator/niche causal effects and unseen-creator prediction are withheld. GEE/mixed remain legacy, while R2 deliberately supports corrected OLS/Poisson. Near-duplicate detection, semantic predictors, automatic discovery and held-out-niche generalization are not claimed.

Verification record (Linux/Python 3.11):

- Full `pytest -q`: **224 passed, 2 skipped** in 642.72 seconds. Only opt-in native-model smoke tests were skipped because no prepared model library/isolated MediaPipe interpreter was configured.
- Focused statistical/production-lineage/evidence/upgrade suite: **45 passed**. Includes pure interaction scoring through the selected pipeline, Simpson/within-between confounding, nested niche absorption, train-only transforms, future-cutoff invariance, signed/unknown covariates, duplicate purging, consumed/overlapping holdout refusal, actual fitted-term citations, old-snapshot/media-mapping withdrawal dependencies and exact legacy `0.0.4`/`0.0.5` reproduction.
- Every released schema head 0001–0005 upgrades with preserved IDs/artifact bytes and a verified backup. Failure after the populated evidence-table rebuild rolls back exactly; FK enforcement, immutable history, downgrade refusal and restore reconciliation remain tested.
- Ruff lint/format, strict mypy, example-spec validation, local documentation links, `git diff --check` and offline locked dependency check passed. Released migration files 0001–0005 are unchanged; no dependencies were added.
- Wheel and sdist builds and isolated offline installs passed version-2 analysis → statistical citation resolution → exact reproduction across process restarts, plus the existing citation/registration, account and real FFmpeg video/report workflows. No platform API or model download was required.

This verification record closes R2; R3 delivery is recorded separately below.

### Objective

Make new historical, within-creator and cross-creator comparisons answer explicit, identifiable questions; ensure production feature timing and validation match the actual tested model. Preserve legacy results exactly.

### Existing components affected

`analytics/{metrics,baselines,cohorts,statistics,validation}.py`, `application/performance_service.py`, `domain/research.py`, account/comparison CLI adapters and performance reports. Existing snapshot import remains append-only.

### New components and schemas/interfaces

Add cohesive `analytics/designs.py` and `analytics/features.py` helpers, not a second analytics engine. Version comparison specifications with estimand, baseline policy, publication/knowledge cutoffs, population, outcome/denominator, feature availability, covariates, sampling frame, duplicate groups, split policy and model pipeline. Persist exact reference populations and as-of covariate versions with frozen statistical results. Add minimal declared test-family/attempt and holdout-use records for specified analyses, reused by R7/R8 before R9 extends adaptive discovery. A statistical evidence locator references the exact analysis/term or declared diagnostic.

Retain `analyze account`, `compare posts|accounts` and reproduction; add explicit design/specification selection instead of changing legacy meaning silently. [Statistical design](docs/statistical-design.md) defines the supported estimands and gates.

### Dependencies and tasks

Depends on R1 evidence and existing pandas/NumPy/SciPy/scikit-learn/statsmodels. Tasks: distinguish retrospective from strictly historical baselines; as-of join metrics/account context; implement named within/cross-creator designs with overlap/balance diagnostics; construct identifiable within/between/niche models; materialize real feature availability; group duplicates; validate the chosen transformations/interactions/model; retain all exclusions and insufficient-data outcomes.

### Acceptance criteria

Adding future posts cannot change a frozen historical baseline or a newly built historical baseline at the same cutoff. Distinct creators can enter a justified cross-creator design, but poor overlap or unknown confounders yield limitations/withheld inference rather than manufactured matches. Nested niche/creator fixtures either use an identifiable design or clearly withhold the estimand. No interaction is declared validated by a different main-effect model. Features lacking historical availability cannot support forecast claims. Semantic nearest neighbors never define the effect-estimation population.

### Automated tests

Future-baseline invariance; creator/niche collinearity; within/between-confounding and Simpson fixtures; matching balance and support; signed/unknown covariates; actual feature availability through production population construction; duplicate-media leakage across creator/time splits; pure-interaction validation; train-only preprocessing; declared-family/null-attempt persistence and consumed-holdout refusal; small/constant/missing data; exact legacy reproduction and report versioning.

### Demonstrable end-to-end behavior

Import same-creator and multi-creator cooking histories → request a seven-day comparison using existing duration/caption-length predictors and declared covariates → show matched support and an effect or an explicit unsupported comparison → append later posts → reproduce the frozen old analysis unchanged and compute a distinct corrected-version analysis. Semantic result-first exposure joins this pipeline in R3, not through a premature R2 detector.

## 7. R3 — Semantic creative events and multimodal recipes

Status: **completed and verified**, `0.0.7` / `0007_creative`, 2026-11-05.

Delivered:

- Strict observable technique/annotation/protocol/coverage contracts and uncertain original-media anchors, including points, spatial regions and discontinuities.
- Canonical annotation-set, event, coverage and relation revisions with immutable typed FK projections. Exact whole-video or narrower literal input citations; captured Unicode caption/normalized-hashtag citations remain untimed.
- Human-reviewed import with real ownership/duration/permission checks and bounded no-write dry runs. Imported model proposals preserve exact provider identity and cannot self-adjudicate.
- Opt-in `cooking-opening-v1` profile with literal-text proposals and source-PTS-snapped budgeted extra frames; existing primitive workflow/cache stays independent. No new mandatory or prepared VLM adapter is claimed.
- As-of/pinned event lanes, honest missingness and qualified temporal relations; opt-in schema-2 video reports preserve review/blinding/coverage and escape imported text. Ordinary schema-1 reports retain their behavior.
- Eleven pinned recipes for result/ingredient order, visible dish, modality-specific promises, reviewed color, conjunction, reveal/SFX and cut/SFX synchrony, and hashtag inventory. Persistent media/post values carry exact lineage, availability and review policy; unrelated label edits preserve unchanged values.
- Explicit recipe mappings in existing schema-2 analyses, frozen selected annotation revisions, transitive withdrawal and exact reproduction without primitive reprocessing. Numerical methods, old recipe versions and unversioned feature whitelists remain unchanged.
- Additive migration, verified pre-upgrade backups, preserved old evidence/features/analysis links, rollback after both table rebuilds and conservative populated-library downgrade refusal. No new dependencies, vector collection or graph projection.

Implementation map: new `domain/creative.py`, `analyzers/creative.py`, `analytics/creative_recipes.py`, `storage/creative_repository.py`, `application/creative_service.py`, `cli/creative_commands.py` and migration `0007_creative`; focused extensions to existing evidence, media task/timeline/report and feature/comparison paths. See [operations](docs/creative-analysis.md) and [implementation decisions](ARCHITECTURE.md#19-creative-event-implementation-decisions).

Verification record (Linux/Python 3.11):

- Full `pytest -q`: **265 passed, 2 skipped**, 704.73 seconds. Only opt-in native-model smoke tests were skipped because a prepared model library/isolated MediaPipe interpreter was not configured.
- Focused creative contracts, real-media workflows and evidence-upgrade/backup suite: **52 passed**. Includes exhaustive feasible-bound timing checks, result/ingredient/ambiguous/sparse cases, delayed subtitles versus speech, cut/SFX synchrony, missing audio, discontinuous anchors, Unicode/normalized hashtags, model/human provenance and blinding, same-version mutation refusal, as-of/selective feature reuse, cache preservation and cross-process CLI persistence.
- Final strengthened two-video comparison/statistical-withdrawal case: **1 passed**; archived report bytes remain unchanged and revoked reviewed labels block new statistical use/reproduction. Final strengthened legacy/version-2 compatibility cases: **2 passed**, including `0.0.6` corrected specs without creative fields. These strengthen existing cases, not additional distinct-test counts.
- Every released head 0001–0006 upgrades with preserved identities/report bytes and verified backup. Populated feature/evidence parent rebuilds preserve analysis links; injected failure after both rebuilds rolls back exactly with FK enforcement restored. Populated-history downgrade refusal and restore reconciliation pass.
- Ruff lint/format, strict mypy, unchanged released migration files, example validation, local documentation links and `git diff --check` passed. Offline `uv lock --check` passed with no dependency changes.
- Wheel/sdist builds and isolated offline installs pass reviewed annotation import → pinned short-video recipe → exact creative citation → opt-in analysis/pinned report → process restart/storage verification, alongside existing video/account/statistical/research workflows. No platform API, model download or new service was used.

Generated clips verify real byte/clock/storage/comparison workflows under controlled annotations, not real-world cooking recognition, inter-reviewer agreement, VLM accuracy or psychological validity. Those empirical validations are not claimed.

No subsequent milestone has been started.

### Objective

Represent observable techniques, their uncertain timing and cross-modal relationships; produce reusable analysis features without equating primitive brightness/loudness with semantic concepts or psychological states.

### Existing components affected

`media/timeline.py`, `analyzers/{base,visual,audio,language}.py`, `application/{analysis_service,enrichment_service,performance_service}.py`, provider evidence bundles and reporting. Existing measured observations, timebase and task fingerprints remain authoritative.

### New components and schemas/interfaces

Add `domain/creative.py`, `application/creative_service.py`, a cohesive `analyzers/creative.py`, and versioned recipes in `analytics/features.py`. Schema includes technique definitions, creative-event identities/revisions, modality evidence links, uncertain boundary ranges, sampling coverage, event relations, feature recipe versions and feature values with availability/source lineage. Relationships include overlap/simultaneity, precedes/follows and uncertain ordering on declared time tolerances; they do not imply causation. Unknown/unclassified technique and unobserved interval are valid states.

Proposed interfaces: annotation import for human-reviewed events; `analyze video --creative-profile <profile>`; timeline/report event lanes; feature materialization by a pinned recipe. Current quick deterministic behavior remains unchanged unless requested.

### Dependencies and tasks

Depends on R1; R2 for evaluated feature/outcome joins. Reuse FFmpeg, existing analyzers and optional prepared providers; no mandatory VLM. Tasks: specify result-first versus ingredient-first evidence; annotate sample fixtures; implement versioned event inference/import; temporal joins and coverage tracking; targeted resampling under budgets; materialize a small set of event/sequence recipes from visual, narration, subtitle, caption, motion, color and sound evidence.

### Acceptance criteria

The opening can encode a finished dish, spoken promise, text overlay and synchronized sound as separate observations connected into an event. Every semantic feature cites its actual inputs/recipe. Sparse frames cannot prove technique absence. Boundary uncertainty survives reporting and downstream analysis. Caption/hashtag language and editing sequences can be analyzed without being mislabeled as hidden psychological mechanisms.

### Automated tests

Result-first/ingredient-first/ambiguous fixtures; simultaneous cut/SFX and ordered reveal; delayed narration/subtitles; coarse sampling; interval/uncertainty validity; recipe determinism and selective invalidation; human/model provenance and outcome-blinding distinctions; multimodal ablations; exact feature availability and cache reuse.

### Demonstrable end-to-end behavior

Analyze an authorized cooking video with supplied event annotations or a prepared provider → inspect synchronized opening evidence and temporal relationships → materialize the pinned result-first feature → include it in an R2 comparison without reprocessing unchanged primitive measurements.

## 8. R4 — Audience-response integration

Status: **completed and verified in `0.0.8` / `0008_audience`**, 2026-11-05.

Delivered: strict collection manifests over existing permitted comment/post revisions;
exact Unicode reaction spans and the pinned expressed-reaction rubric; reviewed and
provider-attributed proposed annotations; versioned curated clusters with real members,
representatives and counterexamples; qualified actual post/event links; frozen
collected-comment summaries and JSON/Markdown reports; audience evidence in research
reports and an opt-in media context lane. Withdrawal is transitive. Separately confirmed
erasure removes registered active-library text/raw imports/derived reports, blocks
resurrection and replays terminal obligations before restored-library access/backfill.
See [operations and limits](docs/audience-analysis.md) and
[decisions](ARCHITECTURE.md#20-audience-implementation-decisions).

No automatic semantic classifier/clustering, audience prevalence, verified behavior,
retention analytics, embeddings/graph or psychological evaluation is claimed. Curated
memberships and optional literal-English proposals deliver the approved no-model path.
Expiry blocks new use; actual deletion requires explicit erasure. External source files,
exports and backups require separately authorized cleanup.

Implementation map: `audience/{collections,annotations,clusters,linking}.py`,
`application/audience_service.py`, `storage/{audience_repository,audience_retention}.py`,
`cli/audience_commands.py`, `reporting/audience.py` and `0008_audience`; focused
extensions to existing evidence/import/report/timeline/backup/health paths. Templates
are in `examples/audience/`; operational contracts are in the audience guide above.

Verification record (Linux/Python 3.11):

- Full `pytest -q`: **299 passed, 2 skipped** in 652 seconds. The skips require an
  explicitly prepared optional model library/interpreter; no download was attempted.
- Final focused audience/unit/migration/backup suite: **55 passed**. This includes
  two tests added after full-suite collection; **301 distinct passing tests** and
  two optional skips are covered overall. Final literal-language uncertainty unit
  checks: **17 passed**. These controlled fixtures test software/provenance behavior,
  not multilingual annotation quality or psychological validity.
- Real FFmpeg event linkage, original Unicode, ranked/partial denominators,
  creator/duplicate exclusions, uncertainty/disagreement, imported model provenance,
  curated cluster revisions, as-of selection, escaped reports and cross-process
  CLI/restart/citations passed. Withdrawal preserves permitted archived bytes.
- Confirmed comment/source erasure, corrected-history and free-text reason cleanup,
  stale confirmation/re-import refusal, interrupted cleanup/trigger restoration,
  pending-backup refusal and same-lineage pre-erasure/pre-R1 restore reconciliation
  passed. Active SQLite/managed files are checked for unique erased text.
- Upgrades from all seven released heads preserve IDs/report bytes; injected
  `0008` parent-rebuild failure rolls back with FK enforcement restored. Released
  `0001`–`0007` migration files are unchanged.
- Ruff lint/format, strict mypy (113 source files), documentation links,
  `git diff --check`, offline locked resolution and wheel/sdist builds passed.
  Isolated offline wheel/sdist installs exercise existing analytics/video/creative
  workflows plus audience review, cluster/link analysis, citations, persisted
  reports, confirmed erasure and post-erasure storage verification.

### Objective

Turn imported comments into qualified evidence of expressed reactions, questions, objections and intentions, while preserving collection bias and the distinction between explicit and inferred content links.

### Existing components affected

`ingestion/tabular.py`, `application/account_import_service.py`, universal evidence, research reports and event timelines. Preserve original comment IDs/raw source versions.

### New components and schemas/interfaces

Add `audience/{collections,annotations,clusters,linking}.py` and a thin application service. Canonical tables cover collection manifests (permissions, query/order, collection period, completeness/coverage, known limits), comment revisions, span-level reaction annotations, cluster versions/membership and qualified links to events/posts. Links declare explicit timestamp/quote, human adjudication or model inference, plus source evidence and uncertainty. Comment publication time remains wall-clock time, never playback time.

Proposed interfaces: import manifests/annotations, `analyze audience --collection <id>`, and audience sections in research reports; ordinary import still works without running models.

### Dependencies and tasks

Depends on R1/R3. Use existing text processing, optional reasoners and later embeddings; deterministic/imported annotations provide the offline path. Tasks: version collection contracts; implement a small auditable annotation rubric; preserve exact quotes; cluster and review reactions; connect only eligible content evidence; report sampling denominators and uncertainties; minimize personal data and propagate withdrawal.

### Acceptance criteria

“I need to make this tonight” can be annotated as expressed intention but never a verified recipe attempt/conversion. A semantic opening link remains visibly inferred. Top-ranked-only or incomplete collections cannot yield viewer-level prevalence. Positive, negative, ambiguous and creator-reply comments remain available; unsupported links are rejected rather than decorated with a timestamp.

### Automated tests

Incomplete/top-ranked collections; selection/coverage denominators; Unicode quotes; negation/sarcasm/multilingual/ambiguous annotations; duplicates/creator replies; inferred-versus-explicit links; timestamp confusion; versioned cluster membership; redaction/withdrawal propagation; imported and model-derived provenance.

### Demonstrable end-to-end behavior

Import a permitted comment collection with known sampling method → review expressed-intention and objection clusters → link a quoted reaction to the opening as an inference → report “of collected comments” statistics and counterexamples beside the actual creative event, without claiming viewers felt or did the same thing.

## 9. R5 — Behavioral metrics and account outcomes

Status: **completed and verified in `0.0.9` / `0009_behavioral`**, 2026-11-05.

Delivered: explicit v2 authorized behavioral JSON imports, frozen semantic metric
definitions and aggregate cohorts, original-grid series/bin evidence, actual source/
world/collection/import clocks, compatible component rates and descriptive retention
comparisons, coarse media mappings with pinned R3 event context, exact-endpoint or
supplied signed account changes, publication-time account-size knowledge gates,
conservative conversion-attribution/deduplication rules, frozen analyses/reports,
research citations and thin CLI adapters. V1 scalar schemas/statistics remain unchanged.
See [operations and templates](docs/behavioral-analysis.md) and
[decisions](ARCHITECTURE.md#21-behavioral-implementation-decisions).

Implementation map: `domain/behavioral.py`, `ingestion/tabular.parse_behavioral`,
`analytics/{metrics,retention,attribution}.py`, `storage/behavioral_repository.py`,
`application/behavioral_service.py`, account orchestration in
`application/performance_service.py`, `cli/behavioral_commands.py`,
`reporting/behavioral.py`, `0009_behavioral`, and focused evidence/report/timeline/
backup extensions. Examples live in `examples/behavioral/`.

Boundaries: no platform API access, model/embedding dependency, automatic metric or
cohort harmonization, interpolated retention, invented viewer sample sizes, causal
attribution, or growth assigned to a nearby post. The first retention comparison
requires an exact within-account cohort and source grid; R2 legacy/corrected
statistical designs do not silently acquire new behavioral outcomes. Unknown private
analytics stays unavailable. Persistent research memory remains R6.

Verification record (Linux/Python 3.11):

- Full `pytest -q`: **337 passed, 2 skipped** in 893 seconds. The skips require
  explicitly prepared optional model runtimes/weights; no download was attempted.
- Final behavioral/unit/migration/backup suite: **62 passed**; final behavioral
  unit suite: **23 passed**. Five cases added after full-suite collection cover
  known/unknown as-of joins, conflicting endpoints, templates, post-only historical
  selection and oversized-integer rejection. **342 distinct passing cases**, two
  optional skips, are covered overall; this is software validation, not evidence
  of empirical platform/causal validity.
- Real SQLite/FFmpeg and cross-process CLI workflows cover original coarse/relative
  bins, repeat ratios above one, unavailable/suppressed/zero-denominator components,
  compatibility refusal, source freshness, negative endpoint/supplied changes,
  attribution overlaps/deduplication, unknown cohorts, delayed corrections/as-of
  selection, research/bin citations and frozen report restart. Event-set changes
  affect new context without rewriting previous reports.
- Upgrades from all eight released heads preserve IDs/report bytes; injected
  populated `0009` rebuild failure rolls back and restores FK enforcement.
  Existing R4 withdrawal/erasure/backup/restore regressions pass. Released
  `0001`–`0008` files and old scalar constraints remain unchanged.
- Ruff lint/format, strict mypy (121 source files), local documentation links,
  `git diff --check`, offline locked resolution and wheel/sdist builds pass.
  Isolated offline wheel/sdist installs exercise existing analytics/video/creative/
  audience workflows plus new retention comparisons, exact bin evidence, signed
  account outcomes, report restart and storage verification.

### Objective

Represent real creator-owned retention/completion/conversion/account measurements with appropriate coordinates, definitions, denominators and attribution; do not force them into scalar nonnegative post counts.

### Existing components affected

Metric contracts/imports, `analytics/metrics.py`, cohort/outcome builders, performance reports and universal evidence. Existing immutable scalar snapshots remain usable and unchanged.

### New components and schemas/interfaces

Add cohesive `analytics/{retention,attribution}.py` helpers and versioned series contracts in `ingestion/tabular.py`; keep account-outcome orchestration in `application/performance_service.py`. Canonical series/bins declare source/platform definition revision, media-relative coordinate system, bin bounds, audience cohort, observation/window/collection times, availability, numerator/denominator semantics and replay behavior. Add explicit attribution observations and account-level outcome specifications; metric definitions declare signed-value/range semantics. A series is not assumed to be a survival curve.

Proposed interfaces: versioned series export import, account-level outcome analysis and retention/event report overlays. Existing import formats remain valid; new formats are explicitly versioned.

### Dependencies and tasks

Depends on R1/R2; R3 supplies optional event overlays. Existing numeric/statistical stack suffices. Tasks: import permitted owned analytics; validate compatible denominators/cohorts; preserve coarse bins and values above one when definition permits repeat views; align only compatible series; as-of account-size/growth joins; define attribution windows; report unsupported/unavailable data separately.

### Acceptance criteria

Negative net account growth is representable under an appropriate definition. A delayed export does not masquerade as a real-time observation. Retention is not interpolated to false millisecond precision. Missing watch-time/conversion data produces a data-access limitation. An account change is not assigned to the nearest post, and supplied attribution is reported as the source's attribution—not established causal effect.

### Automated tests

Coarse/differently scaled bins; ratio above one; denominators/cohort mismatch; missing/zero-denominator cases; completion definition differences; publication versus observation versus retrieval times; delayed corrections; signed account changes; overlapping attribution windows; withdrawn source behavior; scalar-import compatibility.

### Demonstrable end-to-end behavior

Import authorized cooking-channel retention bins and follower history → overlay a result-first event without inventing fine timing → compare a compatible retention outcome across posts → report account growth separately with its attribution limits. Repeat with public-only data and receive an honest unavailable-retention branch.

## 10. R6 — Persistent revision-aware research memory

Status: **delivered in `0.0.10` / `0010_memory`; replaces legacy M2**. Core SQL/FTS/graph and real Qdrant storage are automated-test paths. The prepared-real-model test explicitly skips without supplied verified weights/runtime; semantic relevance quality is not claimed. See [research-memory operations](docs/research-memory.md).

### Objective

Retrieve exact moments, audience evidence, metrics and research records across processes using SQL, FTS, optional persistent vectors and a qualified graph, while keeping SQLite rebuild authority and evidence eligibility.

### Existing components affected

`storage/vectors.py` lifecycle, bootstrap/locking/health, sources/artifacts/evidence and canonical producers from R1–R5. Do not duplicate old media processing or make indexing a prerequisite for analysis.

### New components and schemas/interfaces

Add `providers/embeddings.py`, `memory/{lexical,vector_sync,graph,hybrid}.py` and `application/query_service.py`. Schema includes embedding-space registry, versioned canonical documents/chunks with source evidence, vector outbox with generation/eligibility guards, FTS5 content and graph entity/relationship projections. SQLite graph rows back bounded NetworkX `MultiDiGraph` loads. Collection identity pins model/revision/dimension/pooling/normalization/prefix/chunking; changes create new immutable spaces. Index only canonical types whose writer exists; R7/R8 later register study/assessment document builders without changing this storage contract.

Proposed interfaces: `query`, `graph neighbors|path`, `storage reconcile|reindex`, model status/preparation and revision-specific filters. Graph facts cite exact evidence or assessment; retired conclusions are not served as current.

### Dependencies and tasks

Depends on R1–R4 and R5 for behavioral projections. Use existing qdrant-client/NetworkX; optional prepared local embedding runtime and SQLite FTS5. Tasks: implement SQL/FTS first; index versioned chunks; bounded hybrid fusion; qualified graph projection; transactional outbox/idempotent sync; rebuild/reconcile; eligibility/deletion checks; separate-process retrieval. No pickle graph authority and no graph server.

### Acceptance criteria

Separate processes retrieve a cooking-video opening and resolve every citation. SQL/FTS/graph remain available with no embedding model. Crashes between canonical commit, Qdrant upsert and acknowledgement recover without duplicates. Stale revisions/deleted sources cannot reappear from queued jobs. Graph queries expose conditional pattern entities and scope rather than flattened causal-looking technique→success edges. Top-K results are discovery candidates, not statistical sampling frames.

### Automated tests

Real Qdrant Local cross-process persistence; deterministic point IDs/space isolation; FTS rebuild; bounded graph reload; crash-point outbox tests; concurrent single-directory policy; withdrawal/redaction and stale-generation races; graph qualification; evidence resolution; offline missing model and explicit preparation. Deterministic test embeddings support core CI; a separate opt-in real prepared-model test validates adapter integration without claiming retrieval quality from fake vectors.

### Demonstrable end-to-end behavior

Analyze/import cooking media and audience data → index → terminate → query a result-first moment → traverse its content/reaction/metric provenance → retrieve an unsuccessful comparable example → withdraw a source → reconcile and verify it is excluded from current results while historical citation status remains inspectable.

### Delivered components and implementation decisions

- Added `domain/memory.py`, `memory/{documents,lexical,vector_sync,graph,hybrid,retention,health}.py`, `providers/embeddings.py`, `application/query_service.py`, `cli/memory_commands.py` and additive `0010_memory`. Existing `0001`–`0009` migrations are unchanged.
- Real citation-backed SQL substring/FTS retrieval, revision/cutoff/source/family filters, explicit candidate budgets, owner deduplication, qualified graph neighborhoods/paths, bounded keyset eligibility/repair sweeps and cross-process persistence. Fine-grained bare media does not get invented descriptions. Behavioral observations have a separate family, not a misleading finding label.
- Canonical insert triggers commit a minimal dirty journal with each writer. Reconciliation atomically commits documents/citations/FTS/graph/vector desires/outbox and removes processed journal rows. This two-stage publisher avoids incomplete typed bindings and model/index dependencies in canonical writers; see the R6 architecture decision. A data-directory lock serializes native vector work, so worker leases are unnecessary.
- Immutable embedding-space identities and collection namespaces; deterministic points, generation guards before/after inference, idempotent pending jobs and compare-and-swap acknowledgement. Missing points are repairable. Qdrant is lazily opened; no-model SQL/FTS/graph works independently.
- Optional verified local Transformer/mean-pooling safe-tensor adapter, isolated/offline workers, pinned runtime/prefix/token/chunk/normalization/dimension contracts and refusal of silent token truncation. No fake production embeddings, default model download or unvalidated multilingual relevance claim.
- R4 erasure now scrubs derived documents/FTS including old FTS segments, graph relations and Qdrant bytes; tombstones/delete generations dominate stale jobs/rebuilds. Restores reconcile same-lineage obligations before normal exposure. Known external backup/export retention limitations remain.
- Public `query`, `graph neighbors|path`, `memory status|register-space`, `storage reconcile|reindex` adapters, storage diagnostics and installed-distribution smoke coverage. Existing canonical audience/behavioral paths exercise their memory builders. No R7 findings, literature or mechanism evaluation was added.

### Verification results

- Final full regression: **383 passed, 3 skipped** (386 collected, 1,209.51 seconds). The skips require explicitly prepared embedding, ASR/OCR or MediaPipe assets/interpreters; no weights were downloaded. Focused crash/replay, stale-generation, physical deletion, restore/rebuild, Unicode span, graph qualification/bounds, CLI input and actual audience/behavioral/video integration checks passed.
- Real Qdrant Local storage persists across closed/reopened clients and separate CLI processes. Deterministic test embeddings verify storage/replay/space isolation only. The opt-in real prepared-model adapter/index/restart test is present but was **not executed** without supplied assets. No learned relevance or psychological/annotation-quality claim is made.
- Ruff lint and formatting passed repository-wide (193 Python files); strict mypy passed (134 source files). Documentation links, staged diff checks, offline locked dependency validation and offline wheel/sdist builds passed.
- Both **installed wheel and source-distribution** smoke workflows passed outside the checkout: existing import/analysis/statistical citation/reproduction/video/creative/behavioral/report paths plus persistent SQL/FTS/graph retrieval, citation resolution, rebuild, audience erasure and storage verification.
- Executed locally on Linux / Python **3.11.18**, SQLite **3.53.1**, qdrant-client **1.20.0**, NetworkX **3.6.1**. Windows/macOS CI execution is not claimed. Released `0001`–`0009` migration scripts remain unchanged.

A deterministic generated-video label verifies exact moment retrieval, not cooking recognition or annotation validity. Statistical comparison populations remain SQL manifests, never nearest-neighbor samples. Prepared real-model acceptance and actual-corpus relevance evaluation remain optional verification work. R7 and later implementation was not started.

## 11. R7 — First complete psychological research vertical slice

Status: **completed and verified in `0.0.11` / `0011_research`**, 2026-11-05.

Delivered operations and source-review limits: [psychological research](docs/psychological-research.md). The original milestone design below is retained; actual interface refinements are recorded here and in [architecture decisions](ARCHITECTURE.md#24-literature-backed-research-delivery-decisions-0011).

### Delivered components and boundaries

- Strict offline reviewed-literature import with DOI/primary URL metadata, exact captured Unicode excerpts, design/population/exposure/outcome/limitations, reviewer attestations and correction/retraction eligibility. A small two-study primary-source corpus is supplied; it is not direct evidence of cooking-video effects or automatic bibliographic verification.
- Typed construct/operationalization plans, applicability reviews and prepared rival protocols. All registered rivals must be retained; contextual explanations need no fictitious psychological construct. R1 draft registration/report contracts remain unchanged through an additive `research prepare` step.
- `application/{literature_service,investigation_service}.py`, `domain/investigation.py`, `psychology/{constructs,operationalizations,hypotheses}.py`, exact study/research evidence bindings and protocol/assessment/dependency projections. Migration `0011_research` preserves prior migrations and the R6 evidence-insert journal.
- Deterministic evaluation over original frozen version-2 analyses: actual feature coverage/blinding, reviewed applicability, statistical terms/intervals/family-adjusted p-values and ledger, within/cross-creator overlap or honest insufficiency, unsuccessful uses/alternative-success exemplars and four-domain contextual unknowns. Findings persist question-scoped supporting/contradicting/non-discriminating citations for local predictions, not psychological mediation. No second statistical engine or search-defined population.
- Immutable assessments and scoped findings, proposed-not-executed discriminating experiment briefs, escaped JSON/Markdown artifacts, process-restart reproduction and R6 canonical producer builders. Withdrawal/retraction and authorized audience erasure propagate; staleness/reevaluation/history was not part of that R7 delivery (see R8 below).
- Actual CLI: `research import-literature|prepare|evaluate`, extended `research show`, and `research report ASSESSMENT_ID`. No model/provider or new dependency is required. Associations do not identify a mediator; unmeasured mechanisms stay unsupported/non-discriminating.

### Verification record

- Full regression suite, partitioned across four isolated pytest processes: **408 passed, 3 skipped**, 411 collected. The skips require explicitly prepared real-model assets; no prepared-model or empirical corpus-quality result is claimed.
- Final R7 hardening rerun: **24 passed**, covering real decoded media/annotations, sampled reactions, synthetic authorized-retention grids, erasure of derived reports, source review/correction/retraction/withdrawal, frozen reports/FTS, positive/negative/null 22-creator selected-pipeline fixtures, scoped evidence roles, complete-rival/input/claim gates and real CLI prepare/evaluate/reload.
- Upgrade/backup/restore, crash rollback, empty downgrade and captured-history refusal pass, including upgrades from each released head through `0010_memory`. Released migration files are unchanged.
- `ruff check`, changed-file formatting, strict `mypy` (144 source files), offline lock verification and offline wheel/sdist builds pass. Distribution smoke verifies actual installed-package version, real corpus/citation persistence and no-model SQL/FTS operation. Scientific/annotation validity and private real-creator analytics are separate, unclaimed empirical acceptance work.

### Objective

Answer the bounded question “Why might showing a finished meal in the first seconds be associated with better performance?” with competing, falsifiable explanations and real evidence—not persuasive trigger labels.

### Existing components affected

Universal evidence, semantic events/recipes, audience and behavioral records, comparison services, memory document builders and reports. Keep media reasoners' current no-psychology/performance boundary; add a separate evidence-constrained research service rather than silently broadening descriptive prompts.

### New components and schemas/interfaces

Add reviewed literature import/curation, `psychology/{constructs,operationalizations,hypotheses}.py`, research evaluation/assessment services and a research report model. Canonical payloads and necessary query projections cover study/source findings with design/population/measurement/limitations, construct definitions, operationalized predictions, rival-hypothesis links, immutable assessments, scoped findings, support/contradiction links and proposed experiment specifications; low-volume definitions need not each have a dedicated table. Evidence for study excerpts/statistical terms uses the universal registry. Evaluation records test-family membership and holdout consumption through R2's minimal ledger.

Proposed interfaces: `research register|evaluate|show`, curated-study import and grounded report generation. Extraction reliability, literature applicability, local association, generalization and causal identification remain distinct assessments, not one confidence score.

Keep the shared question/hypothesis/assessment envelope domain-neutral, with psychological construct/operationalization fields belonging to a validated subtype. The cooking report includes a bounded checklist of production, distribution, publishing and profile-context alternatives/unknowns; unknowns qualify conclusions rather than triggering new extraction work. C1's platform-document and context producers are explicitly deferred.

### Dependencies and tasks

Depends on R2–R6. Begin with a small human-reviewed corpus and limited anticipation/sensory appeal/curiosity/cognitive-fluency explanations; each is a candidate, not assumed present. Use optional configured reasoning, never mandatory hosted APIs. Tasks: encode real study evidence/limits; define competing predictions; assemble eligible evidence; compare representative populations and failures; evaluate or withhold associations; write immutable assessment and a discriminating experiment proposal. Human annotations/imports provide the no-VLM path.

### Acceptance criteria

The full twelve-step cooking scenario in [research use case](docs/research-use-case.md) is represented; reevaluation is previewed here and executed in R8. A mechanism has a literature source, applicability judgment and falsifiable prediction, or remains explicitly unsupported. Public-only data yields a constrained question/result; unavailable retention is not guessed. The reference fixture produces at least one weakened, rejected or inconclusive explanation and preserves counterexamples. Causal language is blocked without eligible causal evidence, and a creative A/B effect does not by itself prove a mediator.

### Automated tests

Fabricated/irrelevant/withdrawn study citations; locator validation; technique/construct/response/outcome distinctions; rival predictions; null/negative evidence; unavailable-owner metrics; no-provider offline execution; statistical result qualification; report claim-level gates; sampling-frame versus top-K separation; cross-process assessment/report reproduction.

Also test non-psychological rival/context representation and explicit unavailable context without invented observations or a C1 dependency. Keep the reference cooking dataset and original acceptance scope bounded.

### Demonstrable end-to-end behavior

Authorized video/event evidence → rival mechanism predictions and reviewed literature → sampled-comment reactions → age-aligned comparable outcomes → same/other-creator comparisons and unsuccessful examples → immutable scoped association or insufficient-data finding → proposed experiment distinguishing explanations. Every conclusion opens its exact evidence and states what would change the conclusion.

## 12. R8 — Incremental hypothesis reevaluation

Status: **completed and verified in `0.0.12`, migration `0012_reevaluation`**. See [operations and limits](docs/incremental-research.md).

Delivered functionality:

- Independent append-only, deduplicated SQLite change journal mirrored from existing producers, plus media-association/completion events. R6's indexing queue remains drainable. Immutable selection manifests and bounded operational freshness watches detect changed dependencies and new account-selected posts; unrelated imports do not refit assessments.
- `research status`, `research reevaluate ASSESSMENT_ID [--spec FILE]`, and `research history QUESTION_OR_HYPOTHESIS_OR_ASSESSMENT_ID`. Explicit reevaluation rebuilds the original SQL selectors using R2 feature timing and analytics; publication cutoffs, recipe pins, families and holdout declarations are not silently changed. Pre-upgrade comparisons without saved groups conservatively retain fixed post membership.
- Frozen request plans, atomic per-analysis checkpoints, failed-request records and restart recovery. Unchanged inputs do not refit; supplementary/literature changes needing human review return `review_required`. Corrected literature can be explicitly re-reviewed through a replacement prepared protocol.
- Immutable predecessor/successor links and assessment comparisons: added/reused/removed posts and creator IDs, reused content, changed snapshots/features/references, original test ledgers, scoped support transitions and descriptive effect/interval changes. Null/reversed results can weaken or contradict a previously supported prediction; they never automatically reject a psychological mechanism.
- Current retrieval excludes stale/superseded assessment-derived memory; exact historical reports remain available subject to eligibility/erasure. `research show/report` without `--revision` follows the assessment's successor; pinned revisions retain their original bytes. No daemon, dependency or new vector collection.

Verification: **440 collected tests covered; 437 passed, 3 optional real-model checks skipped** across isolated full-suite partitions and final affected-module reruns. The 28 new reevaluation-focused unit/contract/integration cases pass, including real annotation edits, positive→weakened/contradicted statistics, metric/literature corrections, exact earlier-citation withdrawal, audience erasure, restart checkpoints, source timing gaps and frozen prior-release reproduction. Ruff, changed-file formatting, strict mypy over 149 modules, offline lock/build and installed-wheel workflow checks pass. Optional embeddings/native model assets were not supplied; no empirical psychological or model-quality validation is claimed.

The approved acceptance contract below is retained. Actual bounded limits and conservative cases are explicit in the operations guide: cumulative looks remain exploratory, consumed holdouts are not reused as fresh confirmation, and C1/R9/R10/U1/U2 are not implemented here.

### Objective

Make persistent knowledge an explicit evaluation-and-revision process: new evidence can weaken or reject an old conclusion while historical assessments remain reproducible.

### Existing components affected

R1 registration, R7 assessment services, import/task completion hooks, evidence eligibility, memory synchronization and research reports.

### New components and schemas/interfaces

Add `research/reevaluation.py`, dependency/invalidation service and comparison/history rendering. Extend canonical dependencies from hypothesis/specification/assessment to data versions, features, population, model, literature and source eligibility. Store reevaluation requests, immutable assessment inputs/results, new-versus-reused evidence membership, supersession/contradiction links, reasons and scoped status transitions. A stale marker is mutable operational state; published assessments are immutable records.

Implemented interfaces: `research reevaluate ASSESSMENT_ID`, `research history QUESTION_OR_HYPOTHESIS_OR_ASSESSMENT_ID`, `research status` and revision-specific retrieval. New data queues stale watches; costly reevaluation is explicit and bounded, never an unbounded background agent.

Once C1 writers exist, register their production/context/metadata/profile/platform-document dependencies and population selectors through this same mechanism. New guidance requests applicability review; it is not proof of an algorithm change. Do not replace historical context with today's snapshot or make C1 a prerequisite for initial cooking reevaluation.

### Dependencies and tasks

Depends on R7. Reuse SQLite/outbox/task/cache machinery, without a workflow server. Tasks: identify affected hypotheses; record pending/stale reasons; create a new frozen population; distinguish cumulative reuse from independent confirmation; compare scope/support; retain contradictory evidence and null attempts; refresh current graph/vector projections without rewriting history; propagate withdrawal.

### Acceptance criteria

The initial 100-video result can weaken after additional representative evidence. History explains whether the change came from data, annotation, metric correction, model/specification or withdrawn sources. Unchanged inputs are idempotent; unaffected hypotheses are not reprocessed. Reused observations are not counted as an independent replication. Old report bytes and frozen statistical inputs remain reproducible, subject to explicit evidence-withdrawal/redaction constraints.

### Automated tests

Positive→weakened/rejected and scope-narrowed fixtures; no-op reevaluation; incremental dependency selection; changed annotation/recipe/metric/literature; double-counting and overlapping populations; crash/restart; withdrawn support; stale index jobs; deterministic history links; immutable-assessment and archival compatibility.

### Demonstrable end-to-end behavior

Evaluate the cooking hypothesis on the declared initial population → append ordinary and unsuccessful posts/comments → see a stale assessment → explicitly reevaluate → inspect a weaker/rejected revision and the exact new evidence responsible → reopen both historical reports in a separate process.

## 13. R9 — Bounded nonlinear and cross-niche discovery

Status: **planned, unimplemented**.

### Objective

Investigate combinations and nonlinear relationships without unbounded mining, validation leakage or recycling exploratory evidence as independent confirmation.

### Existing components affected

Creative feature recipes, R2 model/validation pipelines, R7/R8 research specifications/assessments, memory/counterexample retrieval and statistical reporting.

### New components and schemas/interfaces

Add `research/{discovery,candidates,counterexamples}.py` and bounded nonlinear transformations/model adapters. Persist search-family registrations, eligible features/outcomes/populations, candidate attempts including nulls, parent-search lineage, budgets, planned/actual partitions, stopping rules and confirmatory specifications. A multi-feature pattern has its own canonical identity and graph node with constituent roles, conditions and scope.

Proposed interfaces: `research discover --spec <file>` and confirmation evaluation with a separately frozen population. Discovery reports are visibly exploratory.

After the respective C1 delivery, register domain-specific feature/outcome families for professional craft interactions, platform/surface distribution, language/local-time publishing and search/packaging, or profile/funnel conversion. Share validation and ledgers, not platform ranking rules. Each branch declares objective, surface, niche, language, audience, source-policy period, paid exposure and applicable temporal/denominator constraints. Search, recommendation distribution and conversion are not interchangeable success labels.

### Dependencies and tasks

Depends on R2/R3/R6–R8; retain existing scikit-learn/statsmodels first. Tasks: bounded declared interactions and spline/regularized nonlinear terms; only later justified bounded trees/boosting; nested train-only selection; chronological/creator/content-duplicate splits and held-out niches where feasible; stability and counterexample analysis; planned test-family correction; session-spanning search ledger and repeat-look restrictions. No automatic causal interpretation of prediction/importance.

### Acceptance criteria

Pure interactions and U-shaped effects can be investigated by the actual selected pipeline. A feature combination can succeed within one niche and fail in another without being promoted to universal truth. A depleted holdout is not reused silently. Too few independent creators/niches yields descriptive scope/insufficiency. All attempted candidates, not just successful ones, remain auditable.

### Automated tests

Null searches and false-discovery behavior; pure interaction/U-shape; correlated/redundant features; nesting/selection leakage; duplicate media; creator and held-out-niche transfer; contradictory examples; fixed search budget; repeated attempts/holdout reuse; scope-qualified graph patterns; seeded reproducibility and small-cluster refusal.

For C1-backed branches also test surface incompatibility, early-response/later-distribution leakage, incomplete posting windows, local-time/DST effects, metadata/profile edits, incompatible funnel cohorts and missing context. Test real selected pipelines; no universal ranking weights or posting-hour guarantees may emerge from pooled observational data.

### Demonstrable end-to-end behavior

Register a bounded cooking-pattern search over opening technique × narration × sound timing → discover an exploratory combination → evaluate on untouched creators/time block → test another niche → preserve success, failure or narrower scope with all tested specifications and a qualified assessment history.

## 14. R10 — Experiment outcomes and qualified recommendations

Status: **planned, unimplemented**.

### Objective

Turn scoped findings into original, testable creator experiments and ingest their outcomes without automatically promoting observational or poorly controlled comparisons to causal findings.

### Existing components affected

R7 experiment proposals/claim gates, R8 reevaluation, R9 search lineage, metric/outcome imports, universal evidence and reports/portable skill.

### New components and schemas/interfaces

Add `research/{experiments,recommendations}.py`. Store registered experiment versions, assignment unit/method, treatment variants, randomization/exposure information, primary outcomes, mechanism measurements, analysis/stopping plans, deviations, outcomes, analysis and adjudication. Recommendation records declare objective, applicability, expected uncertainty, supporting/contradicting assessment versions and the proposed discriminating test.

Proposed interfaces: `experiment register|import-results|analyze|show`, with recommendations rendered from eligible findings rather than generated without provenance.

Capability-gated variants include shot/edit/subtitle/music plans, title-thumbnail/search packaging, publishing schedule, distribution-response and profile/link/pin changes. A recommendation declares platform/surface, niche/language/audience, objective/channel, evidence date, supporting/contradicting revisions, uncertainty and feasible next test. Distinguish craft heuristics, official advice, observational findings and eligible experiments. New domains require their C1 inputs; the original cooking experiment does not wait for all four.

### Dependencies and tasks

Depends on R7–R9; no publishing API or autonomous external action. Tasks: register bounded design; import creator-authorized results; validate assignment/measurement/attrition; analyze planned estimands; record deviations and threats; feed results into a new hypothesis assessment; generate original technique alternatives while preserving creative versus psychological uncertainty.

### Acceptance criteria

A sound randomized design may support a scoped creative effect; a curiosity/anticipation mechanism requires additional discriminating measurement/identification. Posting two variants sequentially is not mislabeled randomization. Recommendations cite applicable findings and failures and can state “test first.” Publishing, recruiting, spending or contacting viewers remains outside analysis authorization.

Use the actual assignment unit: post/creative variant, impression only when a permitted native packaging experiment supplies assignment, or account/period for profile/schedule changes. Address carryover, spillover, concurrent changes, clustering and delayed outcomes. Profile pre/post counts do not prove profile-caused follows or revenue; an attention lift does not prove sustained growth. Include a non-cooking, non-psychological recommendation fixture for each delivered domain branch.

### Automated tests

Assignment-unit leakage; nonrandomized/pre-post refusal; imbalance/attrition/missing outcome cases; multiple planned outcomes/stopping deviations; mediator versus treatment-effect distinctions; result import idempotency; causal-evidence gates; recommendation provenance/originality constraints; reevaluation and withdrawn experiment evidence.

### Demonstrable end-to-end behavior

From the cooking result, register an experiment contrasting explanations → import authorized outcomes and any actual construct measurements → estimate only eligible effects → reject unsupported mechanism language → revise the hypothesis/recommendation and preserve the original proposal, deviations and outcome evidence.

## 15. U1 — Photo and carousel usability track

Status: **planned, unimplemented; may run after R1 independently of R3–R10**.

### Objective

Support individual photos and ordered carousels without forcing them onto fake video timelines or making their analysis require research registration.

### Existing components affected

Media import/artifacts/provenance, image-capable deterministic/OCR providers, post-media ordering and reports. Preserve existing video commands/timebase and primary-media behavior.

### New components and schemas/interfaces

Add cohesive image/carousel application adapters and image evidence locators (asset/frame/region rather than fabricated intervals). Version carousel feature aggregation by item/position/order; distinguish alternative text, caption, hashtags and OCR. Proposed commands: `analyze image <path-or-id>` and `analyze carousel <post-id>`, plus account batch support under explicit budgets.

### Dependencies and tasks

Depends on R1 and existing Pillow/OpenCV/optional OCR; no new model requirement. Tasks: orientation/dimensions/regions; duplicate items; order-preserving analysis; per-item and declared whole-post summaries; escaped JSON/Markdown output and cache reuse.

### Acceptance criteria

An individual photo yields evidence-backed observations offline. A carousel cites the correct ordered item/region; no unsupported “first seconds” timestamp is invented. Partial item failures are explicit and do not lose successful evidence. Basic caption/hashtag analysis stays available.

### Automated tests

Orientation/EXIF/privacy; malformed/oversized images; region bounds; duplicate/reordered carousel items; mixed assets; partial failure; existing video compatibility; cache invalidation; separate-process report/citation resolution.

### Demonstrable end-to-end behavior

Import a permitted cooking photo/carousel → analyze deterministic appearance and supplied text → inspect ordered evidence and an actionable descriptive report → reopen in another process with no research or vector work triggered.

## 16. U2 — Portable skill, reporting and product hardening

Status: **planned, unimplemented; core package after U1/R2, with later capability-gated updates**.

### Objective

Make implemented capabilities usable in Codex, Claude Code and OpenCode through one portable Agent Skills-compatible wrapper and shared Python engine, without pretending planned research commands exist.

### Existing components affected

CLI/result envelopes, configuration/doctor, reports and packaging/CI. Follow current command/permission/remote-consent boundaries and retain low-cost basic workflows.

### New components and schemas/interfaces

Add `skills/socialdna/SKILL.md` with narrowly scoped references, command/JSON schemas, host-neutral workflow guidance and capability checks; add accessible HTML reporting only if it has a real tested consumer. A capability manifest distinguishes available, unavailable, planned and optional-prepared features. Host adapters are thin invocation guidance, not duplicated services.

### Dependencies and tasks

Depends on U1/R2 for the first core usability delivery; later R3–R10/C1 only enable corresponding workflows after their tests pass. At implementation time use the skill-creator guidance and verify the then-current host compatibility rules. Tasks: installation/doctor guides; local video/photo/account comparisons; caption/hashtag evidence; permission/data-access questions; cited reports; safe experiment proposals; JSON errors and resource estimates; packaging/migration/restart hardening. No mandatory hosted service. The capability manifest reports production, platform/surface, publishing/search and profile/funnel coverage separately; it must not advertise planned C1 workflows as available.

### Acceptance criteria

All three hosts can call the same engine and interpret stable results using documented invocation patterns. A core-only install analyzes video/photo/account exports and reports limits without attempting absent research or semantic commands. Later research workflows check capabilities and exact evidence rather than inventing support. Expensive/remote/publishing actions require appropriate explicit scope/consent.

### Automated tests

Skill link/reference/command contract validation; capability-gated workflow fixtures; installed wheel/sdist offline smoke; Linux/macOS/Windows CI and supported Python versions; JSON parsing and exit codes; HTML/Markdown escaping/accessibility; permission/remote-consent regression; cross-process persistence. Live host smoke checks are separately recorded and never inferred from static validation.

### Demonstrable end-to-end behavior

Follow a host-neutral skill workflow to analyze a local video/photo/account export, compare creators under R2 rules and produce a cited report. In a research-ready installation, invoke the cooking workflow and show hypothesis history; in a core-only installation, explain the unavailable capability precisely and stop that branch.

## 17. Release and verification gates

The old `v0.1`–`v0.4` milestone labels are withdrawn planning gates, not promised releases. R1 advances the package to `0.0.5` with additive migration `0005_evidence`, preserving released migrations and old data/report identities. Each implementation sets its package/specification/migration versions deliberately; an R ID is not a schema revision number.

A research-preview release requires R1–R8 plus the corresponding U2 workflow: one complete cooking use case, eligible universal citations, representative comparisons, persistent retrieval, a falsifiable literature-backed explanation and a demonstrable weakened/rejected revision. Broader-discovery/experiment-ready status requires R9/R10; public `1.0` additionally requires U1/U2 hardening and documented platform/data-access limitations. No milestone is considered complete solely because a model produced plausible prose.

These existing release gates are preserved, not a claim that the full four-area target is covered. Advertising complete production/distribution/discoverability/profile intelligence additionally requires the respective C1/U1/R9/R10 branches, source-access coverage and empirical validation described in the [capability audit](docs/intelligence-capability-audit.md).

Common implementation verification:

- Unit/property tests for contracts, time/availability semantics, numeric methods and invalid states.
- Integration tests for canonical writes, artifact/provenance, immutable inputs, migrations, indexing/crash recovery and source withdrawal.
- Synthetic statistical fixtures with known effects, no effects, confounding, leakage, inadequate support and contradictory evidence. These test behavior, not real-world psychological validity.
- Cross-process end-to-end fixtures through installed CLI distributions, including no-model/offline operation and explicit partial/unavailable outcomes.
- Optional real-model tests on owned/authorized fixtures and a separately reviewed annotation/retrieval quality benchmark. Provider integration, annotation agreement, statistical correctness and construct validity are different measurements.
- Lint/type/build checks; no silent runtime downloads; versioned JSON/report compatibility; old-data upgrades and exact frozen-analysis reproduction.

## 18. Optional post-release expansion and unresolved limits

Official platform adapters are optional, permission-aware additions after export-first workflows. They require current API/terms verification, honest coverage/freshness manifests and normalized canonical imports; do not promise public competitor retention, conversions or private insights. A remote Qdrant adapter or worker/storage scaling is considered only after measured local bottlenecks; SQLite/Qdrant Local/NetworkX require no external services for the planned product.

Data-access, self-selected comments, small creator/niche counts, paid distribution, unavailable historical covariates, measurement error and hidden confounding can make a question unanswerable. More embeddings, larger reasoners or more posts from the same few creators do not remove these limits. A psychological mechanism remains a hypothesis unless a justified measurement/experimental identification supports it; randomized creative effects alone do not establish mediation.

The next numbered research milestone is **R9**; C1 and U1/U2 remain separately authorized extension/usability tracks. R8 does not start any of them.

## 19. C1 — Versioned production and growth-context evidence

Status: **complete — four independently tested deliveries (`0.0.13`–`0.0.16`)**. Four bounded deliveries,
not one large implementation or a requirement to build live API adapters. Detailed
boundaries are in the [capability audit](docs/intelligence-capability-audit.md#2-shared-extension-architecture--planned-not-implemented).

Current authorization: implement C1-A through C1-D as four serial deliveries, each
with working functionality, automated verification and its own professional commit.
C1-A/B/C/D are complete as bounded evidence foundations.
This does not authorize R9/R10 or U1/U2.

### Objective and integration

Supply the canonical inputs missing from professional craft, platform distribution, publishing/search and profile conversion research. Reuse R1 revisions/evidence, R2 comparisons/features, R3 annotations, R4 reactions, R5 source-defined outcomes and R6 projections. Existing R7/R8 cooking research stays independently deliverable. Each new R9/R10 domain branch depends only on its relevant C1 slice. U1 is needed for actual static thumbnail/profile-image analysis; text-only imports must work without a model or live connector.

### Modules, interfaces and delivery boundaries

Proposed file names below are responsibility boundaries, not scaffolding instructions. New record/service/CLI signatures are finalized by each slice's tested writer/reader. Add a new migration only where needed; never edit released `0001`–`0012`.

| Delivery | Planned work and candidate files | Dependencies and integration |
|---|---|---|
| C1-A: production evidence | Extend `domain/creative.py`, `application/creative_service.py`, `storage/creative_repository.py`, `cli/creative_commands.py` and `analytics/creative_recipes.py` through a new versioned professional vocabulary/rubrics and a small pinned craft recipe set. Optional detectors remain separately validated. | R1–R3/R6; after R7. Human-reviewed no-model import first; R2 can compare available features, R9 adds broader interactions. |
| C1-B: publishing/packaging context | Add cohesive `domain/context.py`, `ingestion/context.py`, `storage/context_repository.py`, `application/context_service.py` and thin CLI adapter as needed. Version metadata/language/timezone/completeness/thumbnail variants, exact title/asset locators, schedule/cadence recipes and dated keyword/trend context. | R1/R2/R3/R6; after R7; U1 for static visual lane. Preserve account-export v1 and feed eligible features into R9. |
| C1-C: platform research inputs | Add `domain/platform_research.py` and import/service helpers for official-document statements, platform/surface specifications, source capability manifests and mapped traffic-window observations. Reuse context storage/CLI patterns and R5 measurements, not a new connector framework. | R1/R5/R6 and R7 shared research envelope. Reuse R8 invalidation when delivered; R9 compares distinct surface-specific questions. No live API prerequisite. |
| C1-D: profile/funnel context | Extend context schemas/import/service for typed profile snapshots, text/photo/link/pin evidence, frozen branding/pillar rubrics and compatible funnel-stage summaries. Add actual profile/link/campaign subject bindings to behavioral contracts only when used. | R1/R5/R6; after R7; U1 for static visual lane. C1-B context helpers may be reused but unrelated publishing analytics are not required. R9/R10 consume validated summaries and attribution limits. |

### Delivered production evidence (`0.0.13`)

- Separate v2 professional schema/definitions and eight numeric recipes in
  `domain/production.py`, `analyzers/production.py` and `analytics/production_recipes.py`.
  Existing creative import/materialize/R2/R7/R8 paths consume these without changing
  v1 labels, pins, reports or released migrations. Database head remains `0012_reevaluation`.
- Six real generated videos from three creators, controlled outcome observations
  including a fast-editing failure, actual matched comparison, literature-backed
  assessment, correction/reevaluation, frozen report, restart and withdrawal are tested.
  Synthetic review/outcome fixtures validate software, not craft effectiveness.
- Exact review coverage/partition requirements preserve unknowns. No detector,
  automatic quality score or actionable growth recommendation is delivered.
  [Operations and limits](docs/production-evidence.md).
- Verification: all 462 collected tests covered across regression partitions and
  targeted final reruns (459 pass, three optional prepared-model skips); Ruff,
  strict mypy (152 modules), offline lock/build, fresh installed-wheel CLI and
  packaged/source equality checks pass. No real-model accuracy claim follows
  from skipped model smoke tests or generated fixtures.

### Delivered publishing context (`0.0.14`)

- `domain/context.py`, `application/context_service.py`, `storage/context_repository.py`
  and `cli/context_commands.py` implement real typed publication/window/trend imports,
  field/asset citations, immutable reports and two pinned local-clock/cadence recipes.
  `0013_context` adds only the exercised ownership/capture and evidence bindings.
- Actual six-post R2 matching/outcomes align with pinned context without claiming a
  new posting-time effect. Unknown zones, incomplete inventory, future trends,
  mismatched objectives and unavailable historical metadata are explicitly gated.
  Raw contexts integrate with R7 population scope and R8's existing change journal;
  reports are not reclassified as raw observations.
- All 472 collected tests covered across regression partitions/final reruns: 469
  pass and three optional prepared-model skips. Ruff, strict mypy (157 modules),
  offline lock/build and installed-wheel commands pass. An intermediate test correctly
  rejected a checksum after the *new, uncommitted* migration was changed during its
  run; all 16 memory tests pass against the final fixed migration. Released migrations
  were never modified. [Actual operations and limits](docs/publication-context.md).

### Delivered platform evidence (`0.0.15`)

- `domain/platform_research.py`, `application/platform_service.py` and
  `cli/platform_commands.py` implement reviewed official document/statement versions,
  source capabilities, explicit raw-code/surface/traffic mappings and actual R5
  early/later distribution observations. Shared context bindings require no new DDL.
- Independent platform/surface manifests and source-defined scalar comparisons retain
  event/collection/knowledge times, units, replay/population/cohort context and honest
  access refusals. Guidance is not a measured effect; no ranking weights, causal fit,
  executed experiment or guaranteed reach is produced. R9/R10 remain future work.
- Three real canonical platform fixture workflows cover compatible pairs, failed
  distribution, overlap leakage, unknown/paid traffic, idempotence, restart, exact
  official excerpts, qualified memory, document updates/corrections, withdrawal and
  confirmed erasure. All 477 collected tests covered across regression partitions
  and final reruns: 474 pass, three optional prepared-model skips. Ruff, strict mypy
  (160 modules), offline lock/build and installed-wheel/source checks pass.
  [Operations and limitations](docs/platform-research.md).

### Delivered profiles and measured funnels (`0.0.16`)

- `domain/profile.py`, `application/profile_service.py`, `storage/profile_repository.py`,
  `analytics/funnels.py` and `cli/profile_commands.py` implement dated public snapshots,
  exact photo/text/link/pin evidence, a frozen human rubric, source event definitions
  and actual R5 account-period funnels. `0014_profile` adds only the first-use immutable
  event-meaning/uniqueness binding with real definition/context FKs and code hashes.
- Qualitative assessments and actual measured follow/install/purchase outcomes remain
  distinct. Rates preserve unknown private data, invalid denominators/cohorts/windows,
  missing source joins and dedup limits. Source attribution retains its supplied model,
  windows, credits and unassigned remainder; no individual paths, nearest-post credit
  or causal profile effect is invented. Native link/campaign metric subjects remain
  source-specific first-use extensions, not synthesized from account aggregates.
- The actual integration verifies two captures, ordering/assets/Unicode evidence,
  human rubric, source-qualified measured rates, source attribution, unknown versus
  explicitly attested exposure, older corrections, missing/suppressed counts,
  stock-versus-flow, relabeling/duplicate-credit/ownership rejection, restart, frozen
  bytes, current memory, withdrawal and confirmed erasure.
- All 482 collected tests covered across full regression partitions and targeted final
  reruns: 479 pass and three optional prepared-model skips. Ruff and strict mypy (166
  source modules), offline lock/build, installed-wheel CLI and packaged/source equality
  checks pass. No detector accuracy, actual business lift or empirical causal validity
  follows from controlled fixtures. [Operations and limits](docs/profile-conversion.md).

C1 completion does not implement U1 automatic static-image interpretation, R9 broader
cross-domain discovery, R10 recommendations/prospective experiment outcomes or U2 skill
delivery. Those remain the next separately authorized roadmap work, not hidden scope
inside these four commits.

### Acceptance criteria and tests

Deliver each slice as a working import → typed evidence → feature/context report → new-process reload, with compatible old imports/reports preserved. The [slice verification matrix](docs/intelligence-capability-audit.md#4-bounded-delivery-and-verification) defines the exact demonstrations and rejection fixtures: production ambiguity/coverage; timezone/DST/incomplete cadence; official-document/surface/version and feedback leakage; profile clocks/branching funnels/denominators/credit duplication. Include source withdrawal/erasure, memory builder eligibility and no-provider CLI tests. Optional model performance and real-corpus validity require separate measured evidence, not generated-fixture assertions.

### Per-delivery acceptance and integration gates

These gates are required in this plan, not delegated solely to the audit. Fixtures
exercise real writers, evidence resolution and saved reports; synthetic labels and
outcomes test software behavior, not real-world detector or scientific validity.

| Slice | Required working acceptance scenario | Required integration and rejection tests |
|---|---|---|
| C1-A | Import reviewed, versioned professional annotations for several authorized videos from multiple creators, including ordinary/failure examples. Reproduce pinned shot-duration/pacing, subtitle and cut/beat features with exact citations; compare selected features with imported, compatible performance observations through R2. Preserve a frozen comparison after annotation edits and demonstrate R8 staleness/reevaluation. No automatic professional-quality or causal score. | `tests/integration/test_production_evidence.py`: multi-video import → numeric recipes → actual outcome comparison → report → new-process reload; old v1 imports/recipes unchanged; source withdrawal; ambiguous timing and incomplete coverage stay unknown; camera/subject motion distinct; invalid vocabulary/recipe pins rejected; optional detectors require separate held-out validation. |
| C1-B | Import dated publication/packaging/language/timezone snapshots and a complete account observation window. Produce reproducible local-time/cadence features, exact metadata citations and a comparison with compatible imported outcomes. Search, recommendation distribution and conversion remain distinct objectives. Static visual interpretation waits for U1. | `tests/integration/test_publication_context.py`: real CLI/service import/report/reload, historical edits and frozen features; DST folds/gaps and unknown zones; incomplete/omitted posting windows refuse cadence; incompatible objectives/windows and future trend/metadata leakage rejected; title spans/asset identity and old exports preserved; withdrawal/invalidation. |
| C1-C | Import reviewed official document versions/statements separately from authorized distribution observations. Produce distinct platform/surface manifests and a descriptive early-response/later-distribution comparison with exact citations, or an explicit data-access refusal. Reports distinguish official guidance, local inference and experimental evidence. Proprietary ranking weights/rules, bypass and guaranteed distribution are not deliverables. | `tests/integration/test_platform_research.py`: official excerpt versus observational result labels survive report/reload; platform/surface and metric mappings remain distinct; paid/organic/unknown traffic; non-overlapping windows and lag; reject same-window feedback leakage, unavailable/suppressed metrics and unsupported algorithm/causal claims; document correction and withdrawal propagate. |
| C1-D | Compare two dated public profile snapshots using a frozen, qualified rubric. Separately import authorized source-defined funnel observations and report compatible measured follower/business/app-install conversion rates or explicit incompatibility. A profile assessment or link click cannot substitute for a measured follow/install. | `tests/integration/test_profile_conversion.py`: profile fields/order/links/pins and exact citations; independent profile-assessment and measured-conversion outputs; actual numerator/denominator evidence, cohort/window/uniqueness and attribution checks; reject inferred individual journeys, nearest-post credit, missing private data and duplicate conversion credit; historical profile exposure unknown unless supplied; persistence, withdrawal and erasure. |

Every slice also requires unit/schema tests, no-provider CLI contracts, FK/artifact
checks, idempotent retries, existing-library compatibility and unchanged frozen
report bytes. Reuse SQL/FTS/vector/graph producers and eligibility gates; create
only first-use schema. Record actual delivered limits rather than claiming future
R9 discovery, R10 recommendations or U1 image analysis.

### Explicitly deferred scope

Broad nonlinear/cross-creator discovery belongs to R9; recommendations and creator experiment outcomes belong to R10; host workflows belong to U2. No automatic account edits, posting, experiments, scraping, new infrastructure, full professional detector suite or universal algorithm model is part of a C1 slice. Finish and verify each authorized C1 delivery before starting the next.
