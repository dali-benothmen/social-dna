# SocialDNA implementation plan

Revised: 2026-11-06. Scope: R1–R10, all four C1 deliveries and U1 remain completed within their documented bounds. U2's portable skill/report implementation is delivered; verification is recorded in §16. Live host behavioral checks and prepared-real-model acceptance remain separate opt-in gates; no weights were downloaded or inferred.

New product work: **DX1 is implemented within its source-only bounds; live source
and real host acceptance remain open** in §20 and [operations](docs/source-workflows.md).
The target remains 14 task skills. This release adds independently exportable ingest
and saved-report skills to the existing `socialdna` bundle, not full creator research,
profile auditing or cold audiovisual URL acquisition. **DX2-A is implemented in the
assisted URL-plus-authorized-original lane**; its cold URL-only media gate remains
open. DX2-B is the next separately delivered change authorized by the current request.

Runtime: package `0.0.22`, SQLite head `0019_content`. Released migrations `0001_foundation`–`0018_workflows` remain unchanged; U2 required no database migration. Legacy Milestones 0, 1, 3 and 4 are completed deliveries; their limitations remain visible. Legacy Milestones 2, 5 and 6 are **superseded, not completed**.

Authoritative design: [ARCHITECTURE.md](ARCHITECTURE.md), [research contracts](docs/research-contracts.md), [statistical design](docs/statistical-design.md), [migration strategy](docs/migration-strategy.md), and [reference use case](docs/research-use-case.md). The [audit](docs/architecture-audit.md) records the reasons for this revision; the [previous roadmap](docs/history/PLAN.pre-research-revision.md) is historical, not an alternative active plan.

The [four-area capability audit](docs/intelligence-capability-audit.md) adds production, platform/surface distribution, publishing/discoverability and profile/conversion coverage. C1 supplies their delivered canonical evidence; R9 consumes bounded qualified features/outcomes; R10 adds [registered outcomes and evidence-qualified strategies](docs/registered-experiments.md). Full empirical validity and automatic image interpretation are not implied.

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
- Implementation changes require unit/integration/contract/end-to-end verification, migration/compatibility checks, documentation updates and a scoped working commit when authorized. DX1 and the current DX2-A/B request are approved; later DX deliveries remain planning-only until separately approved. Commit messages describe the engineering change without type prefixes or milestone labels.

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
| C1 | Versioned production and growth-context evidence, four independent deliveries | R1–R6; after R7; U1 for static visual branches | Completed and verified, `0.0.13`–`0.0.16`; see §19 |
| R9 | Bounded nonlinear, cross-creator and cross-niche discovery, including delivered C1 dimensions | R2, R3, R6–R8; respective C1 slice for a new domain branch | Completed and verified, `0.0.17` |
| R10 | Registered experiment outcomes and evidence-qualified creative/distribution/publishing/profile recommendations | R7–R9; respective C1 slice for a new domain branch | Completed and verified, `0.0.18` |
| U1 | Individual photo/carousel analysis reusing existing media contracts | R1 | Completed and verified, `0.0.19` |
| U2 | Portable Codex/Claude Code/OpenCode skill and usable reports | U1, R2; capability-gated integration with later R milestones | Delivered `0.0.20`; live host behavior separately unverified (§16) |

Audience comments and behavioral metrics are split into R4/R5 because sampling/semantic annotation and metric time-series validity are different testable products. Memory follows canonical producers and revision contracts, rather than freezing the current media-only evidence model. A small literature corpus, hypothesis registration and experiment proposal appear in R7; general discovery and experiment-outcome analysis wait for R9/R10. U1/U2 prevent research infrastructure from postponing ordinary creator workflows.

R6 must work without prepared embeddings through SQL/FTS/graph retrieval; semantic acceptance additionally requires a verified prepared local embedding model. R7 must work with authorized local media, imported human annotations and curated research when no VLM is installed. Creator-owned retention is an optional richer evidence branch, never an invented prerequisite substitute.

C1 is not a prerequisite for R7 or for the existing R8/R9 cooking branch. After R7, deliver C1-A/B/C/D as small tested slices alongside U1/R8 where appropriate; advanced domain branches consume only their delivered prerequisites. R7 must record production/distribution/publishing/profile alternatives or missing context, not implement four additional engines. Export-first offline paths are required. Live platform adapters were optional for those completed milestones; supported acquisition routes become explicit requirements of the new, separately approved DX track (§20).

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

Status: **completed and verified in `0.0.17`**. The approved
acceptance contract below is retained; delivered signatures and deliberately bounded
limits are specified in [bounded discovery operations](docs/bounded-discovery.md).

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

### Delivered implementation and verification record

- `research/{candidates,discovery,counterexamples}.py`: frozen candidate grammar,
  marginal OLS/Ridge main/interaction/quadratic/spline pipeline, three training-only
  grouped inner folds, creator/time/joint and held-out-niche partitions, exact-content
  purges, stability and full-population prediction contradictions. No auxiliary model
  is substituted for validation, and no unseen creator intercept is invented.
- `application/{discovery_inputs,discovery_service,discovery_confirmation}.py`:
  canonical R2/C1 adapters, exact frozen registration, durable all-fit ledger,
  source-aware reads/reproduction and independent fixed-OLS focal replication.
  CLI: `research discover`, `show-discovery [--reproduce]`, `confirm-discovery`.
- `0015_discovery`, schema/repository/evidence/memory integration: four small query
  projections reuse canonical revisions, research locators, test families, attempts
  and real post/media holdout tables. Source erasure scrubs dependent fit details;
  structural reservation history remains. Migrations `0001`–`0014` are unchanged.
- C1-A craft recipes are real joined inputs. C1-B historical publication features
  enter the actual selected pipeline. C1-C source-qualified response/distribution
  and C1-D exposed-profile/aggregate-rate adapters use the same model/ledger, with
  explicit compatibility and missingness refusals. Official guidance, human rubric
  quality and measured outcomes remain different evidence lanes.
- Maximum 12 candidates/three alpha values/three inner folds/128 fit attempts.
  BY covers only the frozen exploratory focal family, not adaptive reruns.
  Independent replication supports fixed OLS main/product/quadratic contrasts only;
  tuned/Ridge/spline inferential replication is withheld. Small clusters return
  descriptive insufficiency, not power or universal transfer claims.
- Required software verification: `test_discovery_models.py`, `test_discovery.py`,
  `test_discovery_context.py`, the real craft integration, migration/backup checks,
  full regression suite, strict typing/lint, offline lock/build and installed-wheel
  command checks. Verification completed 2026-11-06: **500 collected tests,
  497 passed and three optional prepared-model skips**, covering the full suite
  in four partitions plus new/final focused checks (19 passed). Final current-context
  edits/history/erasure and the supplied-creator identity refusal were rerun after
  their changes. Ruff, formatting, strict mypy (174 modules), offline lock/build,
  byte-for-byte wheel/source comparison and real installed-wheel `discover` plus
  saved-result command reproduction all pass. No provider or model download was used.

Trees/boosting, unrestricted semantic proposal generation, near-duplicate detection,
online/sequential error guarantees, repeated account-period intervention models,
R10 recommendations/experiments and independent real-world validity remain outside
this delivery. R7 mechanism assessments and R8 reevaluation semantics are preserved;
search results do not silently promote or rewrite those assessments.
The next numbered research milestone is R10; it is not started by this delivery.

## 14. R10 — Experiment outcomes and qualified recommendations

Status: **completed and verified in `0.0.18` / `0016_experiments`**.
The approved acceptance contract is retained; actual formats, commands and bounded
statistical/strategy semantics are in [operations](docs/registered-experiments.md).

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

### Delivered implementation and verification record

- `research/{experiments,recommendations}.py`: strict versioned two-arm registration,
  source-result/correction and four-domain structured proposal contracts.
- `analytics/experiments.py`, `application/experiment_service.py`: prospective matched
  assignment, actual R5 subject/definition/cohort/window joins, C1 domain exposure
  gates, complete-roster missingness, fixed stopping/lag, cited execution review and
  durable shared attempts. At least 20 independent matched blocks are required for
  the conditional assignment lane; this is not a power or source-truth guarantee.
- `storage/experiment_repository.py`, `0016_experiments`: six additive typed binding
  tables, immutable canonical snapshots/artifacts and validated actual hypotheses.
  Existing SQL/FTS/Qdrant/NetworkX, eligibility, erasure and backup paths are reused.
  Released migrations and dependency versions remain unchanged.
- `application/recommendation_service.py`, CLI adapters: actual register/import/analyze/
  show/reproduce and recommendation create/show. Structured author/agent alternatives
  retain evidence lanes, scope, failures/counterevidence, unknown lift and a next test;
  they are not automatically optimized creative or verified original prose.
- Experiment feedback appends a distinct `experiment_assessment` lane to existing
  research history with every rival and prior assessment intact. Treatment predictions
  may change; psychological mediation stays unidentified. R7/R8 semantics are unchanged.
- Controlled fixtures cover cooking effect recovery/null/opposite results, attrition,
  stopping/lag/fidelity/interference failures, actual profile pre/post follows, source
  correction/contradiction preservation, failed attempts, withdrawal/erasure, CLI
  restart/reproduction and non-cooking/non-psychological advice in all four domains.

Verification (Linux/Python 3.11; no platform calls or model downloads):

- Complete suite executed in non-overlapping partitions, plus final affected-test
  reruns: **532 passed, 3 skipped / 535 collected**. Skips require explicitly prepared
  local models. This adds 31 experiment/recommendation cases and four released-head
  upgrade cases to the prior 500-test suite.
- Ruff lint/format, strict mypy (**183 modules**), local documentation links and
  `git diff --check` passed. Offline lock verification retains the same 194 packages.
- Offline wheel/sdist builds contain all current Python modules byte-for-byte. An
  isolated wheel install, using prepared development dependencies but no source
  package imports, passed actual CLI registration → source-result import → analysis
  → cross-process reproduction → recommendation create/show → `storage verify`.
- Upgrade fixtures cover all released heads `0001`–`0015`; original report bytes,
  migration checksums, failed-upgrade rollback and existing backup/restore gates pass.
  No public 1.0, broad empirical efficacy or unexecuted OS/Python matrix is claimed.

Native-impression aggregate imports are descriptive, not an implemented causal
impression estimator. Repeated account-period carryover, multifactor/sequential
designs, mediation identification, comprehensive originality verification and
automatic external execution are not delivered. JSON archives are frozen reports;
U2's portable skill/polished UX and U1 image interpretation remain separate.

## 15. U1 — Photo and carousel usability track

Status: **completed and verified in `0.0.19` / `0017_images`**. See [operations and bounded limits](docs/image-analysis.md).

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

### Delivered components and decisions

- `domain/images.py`, `media/images.py`: bounded raster decode, all EXIF orientations,
  metadata-free RGB display derivatives, explicit alpha compositing and no fabricated duration.
- `application/image_service.py`, `storage/image_repository.py`: actual offline image
  and ordered carousel producers/readers; versioned available-item aggregation,
  exact position/region/quote citations, cache reuse, partial failures and immutable archives.
- Existing local import, shared visual measurements, TaskRunner and prepared OCR worker
  are reused. Optional universal task-input citations extend the task contract without
  changing legacy timed model inputs. There is no model download or new dependency.
- `0017_images`: three real FK-backed projections and an atomic extension of the existing
  evidence locator CHECK. Released migrations are unchanged. Source withdrawal/erasure
  gates and scrubs source-derived static records, caches, display artifacts and reports.
- `cli/image_commands.py`, `reporting/images.py`: actual `analyze image|carousel`,
  restartable JSON/escaped Markdown reports and account media-batch dispatch with
  explicit post/item limits. Alternative text, caption, hashtags and OCR stay separate.

Mixed-in videos, animated/multipage images, unsupported codecs and remote URLs are
explicit unavailable/refused items, not fake static successes. Higher-level automatic
visual interpretation, empirical quality/effectiveness validation and U2 remain outside
this delivery. Existing video/analytics/research contracts are preserved.

### Verification record

- Complete suite executed in non-overlapping partitions, then final affected media/
  account/video and migration reruns: **566 passed, 3 skipped / 569 collected** on
  Linux/Python 3.11. There are 33 new static-media cases and one additional released-
  head upgrade fixture. Skips require explicitly prepared local models; no weights
  were downloaded. Controlled OCR responses validate contracts, not recognition accuracy.
- Actual raster tests cover all eight orientation transforms, metadata stripping,
  alpha compositing, malformed/oversized/animated input, source-byte changes, corrupted
  derivative recovery, original/reused caches, transient OCR failure/resume, exact
  regions/positions, duplicate/reordered/gapped/mixed/remote/partial carousels,
  escaped text, public account batching, source withdrawal and confirmed erasure.
- Upgrade/backup/restore fixtures cover released heads `0001`–`0016`, unchanged old
  IDs/report bytes, failed DDL rollback and downgrade refusal before populated
  evidence rebuild. The regression-discovered downgrade edge is fixed in the new
  migration; no released migration was edited.
- Ruff lint/format, strict mypy (**190 source modules**), local documentation links
  and `git diff --check` pass. Offline lock verification retains 194 packages.
- Offline wheel/sdist builds match every current Python module byte-for-byte. An
  isolated wheel install using prepared development dependencies, without source
  package imports, passes image → exact citation → cached analysis → restarted report
  → partial ordered carousel → escaped Markdown → `storage verify`, with empty PATH
  and no prepared model. No unexecuted OS/Python matrix or empirical efficacy is claimed.

## 16. U2 — Portable skill, reporting and product hardening

Status: **delivered in `0.0.20`, no schema migration**. See [portable skill operations](docs/portable-skill.md). Live host behavioral smoke checks remain unexecuted, not inferred from CLI or structural tests.

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

### Delivered implementation and integration

- `skills/socialdna/SKILL.md` and focused setup/core/research/interface references,
  plus a tested command/exit-code inventory. Skill-creator guidance kept shared
  constraints short and host differences limited to discovery/invocation. Official
  host conventions were verified at delivery, including OpenCode 1 and 2.
- `domain/capabilities.py`, `application/capability_service.py` and
  `cli/skill_commands.py`: non-initializing, no-inference/no-network preflight;
  available/unavailable/planned/optional-prepared states, per-domain coverage,
  configured resource ceilings and precise source/model/policy prerequisites.
  Optional missing/corrupt models do not disable deterministic work. Prepared
  metadata is not native-model verification or corpus/evidence sufficiency.
- `application/skill_service.py`: engine-generated schemas and non-overwriting
  exports of the same bundled skill into an explicit new host directory. Wheel
  and sdist include supporting resources; no source checkout or host SDK required.
- `reporting/export.py` and `cli/app.py`: explicit UTF-8 `report generate --output`,
  preserving JSON envelopes, raw escaped Markdown, partial status/exit 5 and exact
  canonical citations. Existing files/symlinks are refused. Exported copies remain
  outside managed retention and must not be reused after withdrawal without checks.
  HTML is deliberately unimplemented: JSON/Markdown have real tested consumers.
- `scripts/check_distribution.py`, packaging and CI validate actual installed
  bundles and report workflows. The existing three-OS/two-Python matrix is retained
  with UTF-8 and bounded BLAS threads. Statistical methods remain unchanged;
  `0.0.19` frozen comparisons are explicitly included in compatible reproduction.
- Existing deterministic video, R2 comparisons and R7/R8 cooking/history tests
  remain the engine integrations, not reimplemented host logic. A core-only install
  includes reviewed research interfaces but no invented prepared semantics; absent
  inputs still withhold conclusions. No platform action or experiment is executed.

### Verification record

Locally verified on Linux/Python 3.11:

- **608 collected: 605 passed / 3 prepared-real-model skips**. Four disjoint
  regression groups produced 370, 68, 73 and 91 passes (the last also had the three
  skips). Three subsequently added cases passed separately: cross-creator CLI
  reporting, prior-release reproduction and bundled-export dry-run. Overlapping
  targeted reruns are not counted twice.
- New automated coverage is in `tests/unit/test_capabilities.py`,
  `tests/unit/test_report_export.py`, `tests/unit/test_skill_export.py`,
  `tests/contract/test_skill_contract.py` and
  `tests/end_to_end/test_portable_skill.py`. It covers policy/secret-safe failures,
  bundle links/routes/options/schemas, non-overwrite behavior, three host directory
  layouts, no-FFmpeg/no-model work, partial reports, exact citations, UTF-8/Markdown
  escaping, two-creator comparisons and cross-process schema-2.0 reproduction.
  `tests/integration/test_versioned_analytics.py` explicitly verifies both frozen
  statistical methods remain reproducible from `0.0.19`.
- Ruff lint and formatting passed (309 Python files); strict mypy passed across
  195 source modules; skill-creator structural validation and `git diff --check`
  passed. Offline lock consistency checked all 194 pinned packages; wheel/sdist
  builds passed. Both isolated offline wheel and sdist smokes passed: all three
  host-layout exports matched the complete eight-resource bundle, and static/video,
  account/versioned comparisons, creative, behavioral, audience, citations, report
  restart, persistent memory and erasure workflows succeeded. All 195 source modules
  were present in the wheel. These are engine/packaging checks, not live host chats.

CI configuration is not a claim of observed macOS/Windows or Python 3.13 runs.

Read-only CLI version checks found Codex `0.162.0-alpha.17.2`, Claude Code `2.1.296`
and OpenCode `1.19.0`. No live agent conversation, real host configuration mutation,
model download or remote request was performed. Live host behavioral acceptance,
prepared-real-model quality and empirical scientific validity remain open gates,
not implied by skill validation. See the operations guide for a future live-smoke protocol.

## 17. Release and verification gates

The old `v0.1`–`v0.4` milestone labels are withdrawn planning gates, not promised releases. R1 advances the package to `0.0.5` with additive migration `0005_evidence`, preserving released migrations and old data/report identities. Each implementation sets its package/specification/migration versions deliberately; an R ID is not a schema revision number.

A research-preview release requires R1–R8 plus the corresponding U2 workflow: one complete cooking use case, eligible universal citations, representative comparisons, persistent retrieval, a falsifiable literature-backed explanation and a demonstrable weakened/rejected revision. Broader-discovery/experiment-ready status requires R9/R10; public `1.0` additionally requires U1/U2 hardening and documented platform/data-access limitations. No milestone is considered complete solely because a model produced plausible prose.

These existing release gates are preserved, not a claim that the full four-area target is covered. Advertising complete production/distribution/discoverability/profile intelligence additionally requires the respective C1/U1/R9/R10 branches, source-access coverage and empirical validation described in the [capability audit](docs/intelligence-capability-audit.md).

Advertising the new URL-first task experience additionally requires §20's relevant
acquisition/media/account/comparison gates and actual host checks. U2's delivered
skill files, CLI tests and package checks alone do not satisfy that product promise.

Common implementation verification:

- Unit/property tests for contracts, time/availability semantics, numeric methods and invalid states.
- Integration tests for canonical writes, artifact/provenance, immutable inputs, migrations, indexing/crash recovery and source withdrawal.
- Synthetic statistical fixtures with known effects, no effects, confounding, leakage, inadequate support and contradictory evidence. These test behavior, not real-world psychological validity.
- Cross-process end-to-end fixtures through installed CLI distributions, including no-model/offline operation and explicit partial/unavailable outcomes.
- Optional real-model tests on owned/authorized fixtures and a separately reviewed annotation/retrieval quality benchmark. Provider integration, annotation agreement, statistical correctness and construct validity are different measurements.
- Lint/type/build checks; no silent runtime downloads; versioned JSON/report compatibility; old-data upgrades and exact frozen-analysis reproduction.

## 18. Optional post-release expansion and unresolved limits

Official platform adapters were optional additions to the completed export-first engine.
The proposed DX roadmap (§20) now makes a real permitted acquisition route necessary
for each advertised URL-first capability; it does not make all platforms immediately
available. Adapters require current API/terms/use-case review, honest coverage/freshness
manifests and normalized canonical imports; public competitor retention, conversions
or private insights are not promised. A remote Qdrant adapter or worker/storage scaling
is considered only after measured local bottlenecks; SQLite/Qdrant Local/NetworkX
require no external services for this design.

Data-access, self-selected comments, small creator/niche counts, paid distribution, unavailable historical covariates, measurement error and hidden confounding can make a question unanswerable. More embeddings, larger reasoners or more posts from the same few creators do not remove these limits. A psychological mechanism remains a hypothesis unless a justified measurement/experimental identification supports it; randomized creative effects alone do not establish mediation.

R1–R10, C1 and U1/U2 have bounded delivery records above/below. Future work requires
separate authorization; no next milestone starts automatically.

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

## 20. URL-first DX and task skills — proposed

Status: **DX1 implementation and automated verification; live acceptance pending**.
Runtime is `0.0.21` / `0018_workflows`. Other DX deliveries remain planned. Completed
milestone records above are preserved, not reclassified as URL-first acceptance.
Finish/test one delivery before starting the next.

The missing product contract is **task skill + account/post URLs + prompt → automatic
permitted collection/binding → existing engine → useful cited report**. The user
does not routinely author normalized JSON or manually connect CLI IDs. Source setup
and access limitations are explicit, not concealed behind invented results.
Architecture, contracts, policy research and examples are in
[URL-first workflows](docs/url-first-workflows.md) and
[ARCHITECTURE.md §34](ARCHITECTURE.md#34-url-first-dx-and-task-skills--proposed).

### Agreed 14-skill catalog and delivery ownership

The canonical discovery descriptions and routing boundaries are in
[the workflow catalog](docs/url-first-workflows.md#target-catalog-and-agent-discovery).
Names alone do not establish runtime support. Existing `socialdna` remains the
backward-compatible umbrella, not a fifteenth task skill. This revision supersedes
the proposed three-skill routing: `research` owns end-to-end investigations;
`report` assembles saved results without silently collecting or refitting.

| Task skill | Required outcome | First bounded delivery |
|---|---|---|
| `social-dna-research` | Question-driven creator investigation and qualified synthesis; explicit refresh/reevaluation | DX3-B; specialist branches in DX7 |
| `social-dna-ingest` | Explicit permitted acquisition/import, source validation and coverage | DX1 |
| `social-dna-account` | Scoped account strategy across content history, not just the visible profile | DX3-B |
| `social-dna-analyze` | Profile strengths/weaknesses/prioritized improvements **and** individual media deconstruction | Content DX2-A; profile DX3-A |
| `social-dna-reconstruct` | Source-qualified transcript and timecoded finished-video audiovisual script | DX2-B |
| `social-dna-psychology` | Competing mechanisms, reviewed literature/applicability and falsifiable predictions | DX7-B |
| `social-dna-audience` | Qualified expressed-reaction and available behavioral analysis | DX7-A |
| `social-dna-compare` | Declared subjects/contrasts with actual eligible comparisons or explicit refusal | DX4 |
| `social-dna-discover` | Bounded corpus discovery and actual robustness/transfer evaluation | DX7-D |
| `social-dna-platform` | Separate official guidance, observed distribution/search and experiments | DX7-C |
| `social-dna-strategy` | Original evidence-qualified production/growth plan and test-first actions | DX7-E |
| `social-dna-experiment` | Prospective registration and separate evaluation of supplied outcomes | DX7-F |
| `social-dna-report` | Eligible saved-result synthesis/export without hidden acquisition or new fits | DX1 |
| `social-dna-evidence` | Exact source/provenance, contradictions, duplication and revision audit | DX4 |

All analytical tasks can call shared acquisition/report/evidence operations without
requiring sibling skills to be installed. Do not trigger ingest merely because a
URL is present. Do not force research registration for a profile audit, transcript
or basic media description. An unsupported branch returns partial/unavailable with
a concrete next action, not a different task disguised as completion.

Common catalog contract tests must cover one representative request and a meaningful
boundary/refusal for each of the 14 modes: in particular profile audit → analyze/profile,
content breakdown → analyze/content, script extraction → reconstruct, history study →
account, question-led investigation → research, existing-result export → report and
source challenge → evidence. Proposed `tests/contract/test_task_routing.py` validates
typed intent/scope/operation plans and per-mode availability against real services;
it must not claim to prove host skill selection through wording/regex matches.
Separately record realistic host conversations and their actual selected task,
tool actions, citations and outcome; do not force other specialists into basic tasks.

### Sequence and completion levels

| Delivery | Working result | Dependencies | Status |
|---|---|---|---|
| DX1 | One real post URL → permitted capture/import → source-qualified saved report; ingest/report skills | Existing U2/R1; source-policy feasibility gate | Implemented `0.0.21`; live source/host gates open |
| DX2-A | Permitted media-enriched post analysis; analyze content scope | DX1; existing video/U1/provider services | Assisted lane implemented `0.0.22`; cold media/live host gates open |
| DX2-B | Finished-video transcript and audiovisual-script reconstruction | DX2-A; actual text/media tracks and optional prepared providers | Proposed |
| DX3-A | Owned/influencer profile URL → cited strengths/weaknesses audit; analyze profile scope | DX1; C1-D/U1; actual snapshot/photo access | Proposed |
| DX3-B | Bounded account/question study and explicit incremental follow-up; account/research skills | DX1, DX3-A; DX2-A/B for media/script claims; existing account/C1/memory producers | Proposed |
| DX4 | Multi-URL comparison, exact evidence audit and cited synthesis; compare/evidence skills | DX3-B, existing R2/R6–R10; source-use permissions | Proposed |
| DX5 | First-use setup guidance, portable release hardening and live host acceptance | DX1–DX4; source/model access for applicable smoke tests | Proposed |
| DX6-A | Independently delivered Instagram routes | DX1–DX5 shared contracts; actual Meta app/access approval | Proposed |
| DX6-B | Independently delivered TikTok routes | DX1–DX5 shared contracts; actual eligible TikTok app/access approval | Proposed |
| DX7-A | Audience collection/reaction/behavior workflow | DX3-B; R4/R5, permitted bounded evidence | Proposed |
| DX7-B | Literature-backed psychological investigation and explicit reevaluation | DX3-B/DX4; R7/R8, reviewed inputs | Proposed |
| DX7-C | Platform/surface distribution and search investigation | DX3-B/DX4; C1-C/R5 and actual access | Proposed |
| DX7-D | Bounded discovery and transfer/confirmation workflow | DX4; R9, declared corpus/family and support | Proposed |
| DX7-E | Evidence-qualified original strategy and production briefs | DX4; R10/relevant C1 and eligible findings | Proposed |
| DX7-F | Experiment registration, outcome intake and evaluation workflow | DX4; R10 and actual authorized execution records | Proposed |

YouTube is the **provisional** first connector, not an unrestricted data source.
Confirm the platform/use case and applicable permissions before implementation.
Source-only, media-enriched and research-qualified are distinct evidence levels.
Supplied-original/export assistance is explicitly distinguished from cold URL-only
acquisition. A partial report can be useful without satisfying a deeper requested
question. All 14 task skills share one engine; existing `socialdna` is retained.
DX2-A/B, DX3-A/B and DX7-A–F are independent serial deliveries, not authorization
for a combined change. DX7 requires its actual evidence/engine prerequisites, not
approval for every platform; offline/export-supported branches remain first-class.
DX5 packaging/host gates apply again to every skill added after DX5.

**User-confirmed platform target: Instagram, TikTok and YouTube.** DX6-A and DX6-B
are required to fulfill that target, not optional extras. Delivering YouTube first
is an incremental engineering sequence. Each platform must have a real, permission-
qualified usable path; broad support for arbitrary competitor URLs/private insights
is not guaranteed by an official API. Access blockers remain open scope, not
placeholder successes or a silent downgrade to recognizing URLs.

### DX1 — One post URL to a real, durable report

**Delivery record (2026-11-06):** implementation delivered, acceptance not closed.
Implemented safe offline URL classification; bounded official YouTube native metadata
HTTP; immutable plans and attempt tokens/cooldowns; atomic identity/publication import
and source captures; exact field citations; frozen JSON/escaped Markdown artifacts;
separate ingest/report skills with shared references assembled into each export;
policy-qualified expiry, withdrawal, erasure and restore integration. No dependency
added: existing `httpx` is reused. Envelope remains 1.0. Released migrations are unchanged.

Operational additions: `workflow maintenance` exports/verifies an exact systemd user
timer, without installing or enabling it; `workflow maintain` applies declared expiry
offline. The first live capture is gated on that timer and a secret environment key.
Linux/systemd is the only live-retention adapter in this delivery. API fields do not
enter generic metrics, analytics, FTS/Qdrant or graph research projections; native
reporting is the sole enabled use, pending any further provider approval.

Actual modules also include `application/workflow_maintenance.py` and
`storage/workflow_retention.py`. A connector base abstraction was deliberately not
added for one adapter; `CaptureManifest`/`CaptureFailure` form the shared boundary.
Tests live in `test_source_acquisition.py`, `test_source_workflows.py` and
`test_workflow_skills.py`, plus extended existing contract/migration/restore and
installed-distribution checks. Frozen `0.0.20` statistical runs remain explicitly
reproducible with unchanged numerical methods and matching library pins.

**Automated verification (Linux, Python 3.11): 656 distinct tests passed, 3 optional
prepared-model checks skipped; 659 cases covered across partitions and focused reruns.**

- Unit/contract partition: 360 passed. Integration partitions: 94 passed; 62 passed;
  77 passed with 3 prepared-real-model skips. Migration/upgrade/backup partition:
  32 passed. Source-workflow integration: 18 passed across the final 16-case run and
  two additional index-isolation/explicit-recapture cases. Archived-method focused
  rerun: 5 passed, including the new `0.0.20` variant (other cases overlap coverage).
- Separate end-to-end process/layout/research suite: 12 passed. No live source or
  agent behavior is inferred from these fixtures/subprocesses. The three skips
  require explicitly prepared embedding, ASR/OCR or MediaPipe assets/interpreters;
  no weights were downloaded or inferred.
- Ruff lint/format, strict mypy over 209 modules and `git diff --check` passed.
  Both exported task skills passed skill-creator structural validation.
- `uv sync --locked --offline` and wheel/sdist builds passed, with no added dependency.
  Rebuilt wheel and sdist independently passed
  `scripts/check_distribution.py --offline --source-workflows-only`: actual installed
  resources, all three export layouts, schemas, static reports, synthetic HTTP capture,
  exact citations, frozen native reports and resume. This is not a live host conversation.
  The broader installed smoke also completed all legacy wheel checks; its sdist run
  was deliberately interrupted during final audience-memory checks, not counted as
  a complete full-distribution pass. Final acceptance uses the scoped rebuilt artifacts.
- Exported systemd unit syntax check returned 0 (sandbox bus-access warnings present);
  no user service was installed/started. The supplied real URL passed offline
  no-write planning. API key absent and maintenance inactive in this environment.

**Open acceptance gates:** user supplied `https://www.youtube.com/shorts/EaYRjrQuxEk`.
No live API capture is certified without locally configured credentials and verified
retention maintenance. No real Codex/Claude Code/OpenCode conversation is certified
by export/layout or synthetic transport tests. Keep DX1 open for these live gates;
do not proceed to DX2 automatically. See [setup and limitations](docs/source-workflows.md).

**Implement:** offline typed URL intake; one actual permitted YouTube post-metadata
route; bounded request client and access policy; durable workflow/target/attempt/
capture/output bindings; normalized canonical import; source-native report composition;
`workflow plan|run|show|report`; independently exported `social-dna-ingest` and
`social-dna-report` bundles. Ingest acquires/imports; report reuses saved results.
Ship the minimal first-use migration, capture citations, retention and safe export
together. Do not build an account collector, downloader or research agent first.

**Modules/files:** new `domain/{workflows,acquisition}.py`, `ingestion/{urls,access_policy}.py`,
`ingestion/connectors/youtube.py`, `application/{workflow_service,workflow_report_service}.py`,
`storage/workflow_repository.py`, `cli/workflow_commands.py`, `reporting/workflow.py`,
first-use migration and `skills/social-dna-{ingest,report}/`. Extend existing CLI registration,
capabilities, skill schema/export, packaging, evidence/retention/backup integration
and `scripts/check_distribution.py` only where this first slice needs them.

**Dependencies/integration:** retain ResultEnvelope 1.0, strict v1 import, existing
account/media IDs and non-overwriting report exports. Use short locked transactions;
network acquisition is outside `open_application()`'s lock. Prefer an existing HTTP
dependency if suitable; any new dependency needs justification at implementation.
Before enabling collection, record current permitted operations, credential references,
retention obligations and whether the use case requires additional approval. Without
a legitimate live route, this delivery is blocked—not complete by URL parsing alone.

**Acceptance:**

- In a fresh installed environment with explicitly configured access, a user selects
  the skill, supplies one real post URL and a metadata-compatible question, and gets
  a persisted Markdown/JSON report with actual source fields, exact citations and
  missing-data coverage, without writing SocialDNA JSON. No prepared model required.
- Reopen in another process; show/re-export the same eligible result. Interrupted
  acquisition/import resumes without duplicate snapshots or half-completed outputs.
- A request about editing, psychology or conversion with metadata only returns a
  qualified partial result and a specific next action, not a claim of video analysis.
- Denied/unavailable/private/deleted targets and missing credentials return stable
  reasons. `--offline` never fetches; capabilities never initializes storage or probes
  authentication. Secrets never reach artifacts, prompts, reports or errors.
- Source expiry/withdrawal and confirmed erasure gate/scrub new captures and dependent
  managed reports; old released migrations/IDs/reports remain intact while permitted.
- Rendering a saved capture/report through the report skill performs no hidden fetch,
  model fit or hypothesis registration. An explicit ingest request does not launch
  unrelated media/research tasks. Neither bundle requires the other to be installed.

**Tests:** proposed `tests/unit/test_url_intake.py` (aliases, spoofed hosts, malformed
IDs, redirects/SSRF), `tests/contract/test_workflow_contract.py` (real commands, schemas,
states/envelopes), `tests/integration/test_url_workflows.py` (fixture HTTP → capture →
atomic import → report → cross-process reload, interruption, duplicate attempts,
quota/backoff, secret redaction, source changes before publication), and
`tests/integration/test_workflow_retention.py` (expiry, withdrawal, erasure, restore).
Extend migration, skill/export, capabilities and distribution tests. Run one consented
live source smoke and one real host/skill conversation separately; their evidence
cannot be substituted by recorded HTTP fixtures or directory-layout tests. If not
run, report the remaining live gates explicitly; DX5 extends this to all claimed hosts.

### DX2-A — Real media-enriched URL analysis

**Delivered scope (`0.0.22`):** [assisted media operations](docs/media-workflows.md).
One recognized YouTube/Instagram/TikTok post URL plus declared authorized local
originals dispatches real video, photo or ordered-carousel analysis without a key,
network request or model download. Profile scope and cold URL-only acquisition
remain unsupported. This is the explicitly permitted assisted alternative in the
acceptance gate below, not a claim to have delivered three live media connectors.

Added `content_workflow_service.py`, `domain/content.py`, `content_repository.py`,
`content_retention.py` and migration `0019_content`, extending workflow modes/CLI,
typed evidence resolution, erasure and independent skill export. Unknown owners and
publication times are not invented. A local ordered-carousel proxy avoids copying
native API account/publication fields into an independent media source. Conflicting
bindings require explicit replacement; planned checksums pin files/subtitles.
Run checkpoints survive interruption; frozen JSON/Markdown re-export without inference.
Canonical content records/citations use `ContentLocator`, with actual run/workflow
foreign keys and immutable projections; no new vector collection or graph backend.

Automated acceptance is in `test_content_workflows.py`: decoded FFmpeg video and
subtitles, measured image/duplicate/mixed carousel, cross-process Instagram/TikTok
assisted CLI, hash/permission/conflict refusals, cold partials, interrupted resume,
withdrawal/confirmed erasure, non-initializing dry-run, unknown owner/time and old-plan
fingerprints. Skill export and installed wheel/sdist acceptance include analyze.
Actual live URL-only media, prepared-model accuracy and real host conversations
remain distinct open gates. Final executed test counts are recorded at handoff.

**Executed verification:** 364 unit/contract tests passed; all 10 assisted-content
integration cases passed (nine together plus the added API-source isolation case).
The 50-case media/audience/memory regression partition passed after rerunning two
checksum cases against the finalized migration. Migration/backup/native-workflow
checks had 49 passes and one downgrade failure, fixed and rerun successfully;
15 focused migration/skill cases and three latest-head/downgrade cases passed.
Ruff, formatting, mypy, both distribution builds and isolated offline wheel/sdist
source/media/skill acceptance passed. The exported analyze bundle passed the skill
structural validator. No live source, model download or host conversation was run.

**Implement:** bind resolved post IDs to permitted acquired assets or independently
supplied originals; dispatch video/image/ordered-carousel through existing services;
reuse checksums, cache, modality coverage and optional prepared providers. Add
`social-dna-analyze`, with shared references included inside its exported bundle.
Deliver its content scope here; profile scope remains explicitly planned until
DX3-A. Never make the existing local analyzers unconditional URL downloaders.

**Modules/files:** extend intake/coordinator/report contracts and first connector's
explicit media capability; new media-binding helper only if shared; touch existing
`import_service.py`, `analysis_service.py`, `image_service.py` only for necessary
additive bindings. New `skills/social-dna-analyze/` and focused workflow tests.

**Dependencies/integration:** DX1; existing FFmpeg/Pillow/U1 and prepared-model gates.
Actual audiovisual access must be permitted for the selected route; a YouTube API
key is not download permission. No `yt-dlp`/scraper fallback. Source access is separate
from model-transfer consent. No mandatory VLM or new embedding/graph workflow.

**Acceptance:**

- A post URL plus a genuine permitted media route reaches real deterministic analysis
  and exact asset/time/region citations. Verify this separately from the assisted
  URL-plus-owned-file case; do not claim cold media access when only assistance works.
- The assisted case automatically binds supplied media to the resolved post with
  provenance and refuses ambiguous/conflicting bindings; the user need not edit JSON.
- Reports distinguish measured craft proxies, source text, uncertain model proposals
  and reviewed annotations. Unsupported modalities/mixed carousel items remain explicit.
- Repeated analysis reuses eligible matching caches; altered assets/configuration or
  source withdrawal cannot reuse obsolete results. Existing local commands still work.

**Tests:** `tests/integration/test_url_media_workflows.py`: actual authorized local
video/static/carousel fixtures through URL binding → engine → report → reload;
ordering/duplicates, hash mismatch, bounded bytes/decoding, interrupted acquisition,
missing models and transfer denial. Extend media/cache/retention regressions. A live
permitted media route is a separate gate for advertising URL-only media analysis;
if unavailable, ship only the accurately labeled assisted capability.

### DX2-B — Finished-video transcript and audiovisual script

**Implement:** `social-dna-reconstruct` over actual available media/text/creative
tracks. Support transcript-only, audiovisual-script and combined output with exact
original-media intervals, source text/visible text, visual/edit/audio cues, coverage
and uncertainties. Reconstruct the finished clip, not an inaccessible original
writing document. Any original adaptation is a separate strategy request.

**Modules/files:** proposed `domain/reconstruction.py`,
`application/reconstruction_service.py`, `reporting/reconstruction.py` and
`skills/social-dna-reconstruct/`; extend workflow mode/schema/bindings and existing
timeline/evidence/retention adapters. Reuse `media/{timeline,subtitles}.py`,
`application/{enrichment_service,creative_service}.py` and existing report exports.

**Dependencies/integration:** DX2-A; optional explicitly prepared ASR/OCR/alignment,
supplied caption tracks and genuinely reviewed cues. No new mandatory model or
delivered speaker identification is assumed. Add a typed cited reconstruction
producer/resolver/retention path only at first write; no new vector collection.
Verbatim extraction needs permitted access/reproduction; unsupported sources receive
a structural summary or partial result, not a bypass download.

**Acceptance:**

- A permitted post/clip produces a persisted transcript and ordered AV-script rows
  with exact media/run/track revisions and resolvable timestamps/regions.
- Speech, supplied subtitles and OCR remain distinct; disagreements, unclear words,
  null timings, sampled coverage and missing providers are shown. Translation is
  optional, separately labeled and never replaces original-language source text.
- Caption-only access does not become verified speech; unavailable ASR is not proof
  of silence. A genuinely silent/no-audio clip has no invented dialogue or speakers.
- Measured/reviewed observations and model/agent interpretations remain separate.
  No fabricated camera settings, off-screen action, intent or exhaustive coverage.
- Restart/re-export reuses eligible output; changing a selected track invalidates
  only dependent work. Withdrawal/erasure covers scripts and indexed derivatives.

**Tests:** proposed `tests/integration/test_video_reconstruction_workflows.py` and
contract cases for output/track/time-range selection; real clip → actual track
composition → cited script → new-process reload. Include subtitle/speech conflicts,
music-only/no-audio, multilingual text, missing/unaligned words, unavailable providers,
partial visual coverage, safe exports, changed inputs and erasure. Extend existing
`test_enrichment.py` / `test_creative_analysis.py` regressions. Prepared-real-model
accuracy is a separate owned/reviewed gold-sample gate, never inferred from fixtures.

### DX3-A — Profile strengths, weaknesses and improvements

**Implement:** `social-dna-analyze` profile scope for either owned or influencer
profiles. Capture/import a real supported snapshot and available photo/pin context;
return cited strengths, weaknesses, unknowns and prioritized proposals about username,
display name, photo, bio/positioning, links/CTA, pins and visible consistency. Support
strengths/improvement/balanced focus without bias from account ownership/popularity.

**Modules/files:** existing workflow/connector/report modules, C1-D
`domain/profile.py`, `application/profile_service.py` and U1 image services; proposed
`domain/profile_audit.py` and `application/profile_audit_service.py` only for the new
proposal producer. Extend the analyze bundle; use existing artifact/evidence/retention
registries rather than another profile database or scoring service.

**Dependencies/integration:** DX1, C1-D/U1 and permitted source operations. A profile
audit does not require full account enumeration, media downloads, embeddings or a
research registration. Existing `ProfileReview` is human-reviewed: automated output
must use a labeled agent/model proposal lane, never fake a reviewer attestation or
owner-declared positioning. Without interpretation capability, return source inventory
and explicit partial/review prompts, not invented judgments.

**Acceptance:**

- A supported profile URL + "find weaknesses" or "explain strengths" produces a
  snapshot-bound audit without user-authored JSON. Both owned/influencer fixtures
  retain favorable, unfavorable and unknown observations with cited examples.
- Profile-only scope does not trigger a complete post crawl. Uncollected photo,
  links or pins remain unknown, not empty; primitive photo metrics are not proof of
  branding quality, and external bio links are not implicitly fetched.
- Qualitative proposals and human reviews are distinguished. Actual authorized
  visits/follows/clicks/installs use the separate C1-D/R5 funnel lane; no conversion
  rate, promised lift or follower explanation is invented from public appearance.
- Reopen exact snapshot/audit, refresh a changed bio/pin, and expose staleness without
  silently rewriting prior permitted output. Apply withdrawal/erasure to proposals.

**Tests:** proposed `tests/integration/test_url_profile_audits.py`: source snapshot →
typed proposal → cited report → reload; both audit focuses, absent versus uncollected
assets, ambiguous positioning, unavailable model/private metrics, counterfeit review
rejection, source changes/withdrawal and no whole-account enumeration. Extend
`test_profile_contracts.py`, `test_profile_conversion.py` and profile command contracts.

### DX3-B — Bounded account study and incremental research

**Implement:** account identity resolution and permitted paginated enumeration;
scoped recent-post manifests including ordinary/failed/unavailable items; resumable
per-post dispatch; account report composition; explicit refresh with preserved
permitted history and stale-result detection. Add `social-dna-account` and the bounded
`social-dna-research` front door. Research pins a question, observed scope and actual
analysis bindings; reviewed psychological/discovery/experiment branches arrive only
with their DX7 delivery. Reuse canonical SQL/FTS/graph memory
for eligible evidence; no new vector collection or mandatory indexing.

**Modules/files:** existing workflow/connector/repository/report modules; integrate
`account_import_service.py`, account analysis and relevant C1 import services.
Add `skills/social-dna-{account,research}/`; report continues to compose saved outputs,
not acquire accounts itself. Extend the workflow operations guide.

**Dependencies/integration:** DX1, DX3-A; DX2-A/B for media/script claims. Imports remain the
same atomic engine contracts. Handle aliases resolve to stable IDs. Honor source
retention and operation permissions before reusing or analyzing captured fields.

**Acceptance:**

- One supported account URL plus a plain-language goal produces a bounded report
  without a user-created export. Show actual post counts, dates, selection/omissions,
  field availability and whether supplied media/owner insights enriched the result.
- Include ordinary posts, not just top performers; truncated recent samples cannot
  establish complete cadence, historical outcome windows or an account's causal recipe.
- A second explicit refresh imports only actual new/changed observations and reuses
  eligible unchanged media work. An interrupted page/batch resumes without silent gaps.
- Profile quality, measured conversion, official platform guidance and inferred
  patterns remain separate; unknown retention/saves/follows/install metrics stay unknown.
- The research skill can coordinate the available services without installing sibling
  bundles. Missing reviewed literature/protocols produce draft/partial research,
  not a certified mechanism. Explicit reevaluation preserves prior assessments and
  contradictions; imports alone do not refit or train the host AI.

**Tests:** `tests/integration/test_url_account_workflows.py`: multi-page account →
import → actual per-post dispatch → cited account report → process restart; identity
rename/duplicate aliases, page overlap, deleted posts, truncation, quota interruption,
explicit freshness, corrections/expiry and selective reanalysis. Include actual C1
bindings where supported and an unsupported-fields branch, not fabricated fixtures
claiming API availability. Record a consented live account acquisition smoke.

### DX4 — URL comparisons and evidence-qualified synthesis

**Implement:** `social-dna-compare` and `social-dna-evidence`; multi-subject scope
negotiation; exact canonical sample/output bindings; validated R2 comparison plans
where eligible; labeled narrative
comparison otherwise. Add optional existing R7–R10 workflows for sufficiently prepared
evidence without forcing them on basic reports. Generate user-readable recommendations
through the existing qualified proposal path when its prerequisites are met.

**Modules/files:** shared workflow/domain/report modules, existing comparison/research/
discovery/recommendation service adapters, `application/query_service.py`, exact evidence
resolvers and `skills/social-dna-{compare,evidence}/`.
Extend generated schemas and all independently packaged skill references.

**Dependencies/integration:** DX3-B, R2/R6–R10 and relevant C1 producers, plus source-use
permission for derived metrics/comparisons. Do not feed prohibited API data into
otherwise valid engine calculations. Existing registered timing/holdout/review
contracts remain authoritative; no agent-generated human attestations.

**Acceptance:**

- Two supported account URLs or two post URLs plus a question produce a reproducible
  comparative report with subject/sampling/metric/time compatibility and counterexamples.
  An eligible fixture must execute the actual comparison pipeline, not only show a
  side-by-side summary; an ineligible fixture must withhold numeric inference.
- Unequal access, cross-platform metric definitions, immature outcomes, sparse creator
  counts or missing historical features yield a scoped narrative/partial result.
- Measured associations, literature-backed hypotheses, official platform statements,
  model/host interpretation and proposed tests remain separately cited and labeled.
- Persist exact run/evidence references; reopen/reproduce while eligible. Source
  correction/withdrawal affects current reuse without silently rewriting old conclusions.
- "Why did you conclude this?" resolves exact supporting and contrary records,
  duplicates and prior revisions through SQL/evidence/qualified graph views. Retrieval
  rank and a graph path are not confidence, replication or causal proof; an audit
  does not silently acquire fresh data or accept withdrawn evidence.

**Tests:** `tests/integration/test_url_comparisons.py`: multi-URL acquisition → actual
R2 comparison → report → new-process reproduction; ordinary/failure examples,
incompatible platforms/denominators/windows, incomplete samples, prohibited derived
uses, invalid literature/review proposals and source withdrawal. Verify deep-research
refusal without losing useful basic comparison output; retain frozen legacy regressions.
Add `tests/integration/test_workflow_evidence_audits.py` for source/contradiction/history
audit through real R6/R8 services, duplicate evidence, stale indexes, withdrawal,
bounded paths and cross-process reload; reuse existing research-memory tests.

### DX5 — Portable first use and release verification

**Implement:** concise setup/connection guidance and action-oriented diagnostics;
self-contained selected-bundle exports; complete installed-wheel/sdist workflows;
live host acceptance protocol and executed checks where authorized. Keep the common
workflow/evidence references maintained once and included in every task bundle.
Earlier DX deliveries already ship usable bundles; this is hardening, not the first
time an actual skill or package works. At this point the eight delivered tasks are
ingest, report, analyze (both scopes), reconstruct, account, research, compare and
evidence. The six DX7 tasks remain planned until their own tested delivery.

**Modules/files:** `application/{skill_service,capability_service}.py`,
`cli/skill_commands.py`, `skills/`, `pyproject.toml`, `scripts/check_distribution.py`,
`docs/portable-skill.md`, workflow guide and release records. No host SDK or second engine.

**Dependencies/integration:** DX1–DX4. Preserve old `skill export DEST/socialdna` and
ResultEnvelope 1.0. Add explicit bundle selection without overwriting destinations.
Connection checks are explicit network actions, never hidden in `capabilities`.
Installing skills/changing host settings needs separate authority.

**Acceptance:**

- A fresh install exports each delivered task skill independently; it needs neither siblings nor
  a source checkout. Shared references and real commands/schemas agree across bundles.
- In each claimed host, a real conversation selects the appropriate skill, accepts a
  supported URL/prompt, runs the same engine, returns cited output and handles a denied
  or unavailable branch. Record actual host/model/access versions and observed results.
- One-time connection guidance is understandable; normal repeat requests do not require
  manual normalized exports/CLI IDs. Tokens and private data are absent from archives.
- Offline/local/export workflows remain usable without connectors/models. No automatic
  dependency installation, model preparation, paid request or remote transfer occurs.

**Tests:** extend `tests/contract/test_skill_contract.py`,
`tests/unit/test_skill_export.py`, `tests/end_to_end/test_portable_skill.py`, capability
tests and installed distribution checks for all bundles and workflows. Run the relevant
full regression/lint/type/build suite and record live source/host smoke results
separately. A missing credential/model/host means an open acceptance gate, not a pass.
Apply these same packaging/routing/host gates to every subsequent DX7 bundle;
do not mark all 14 supported by exporting empty specialist instructions in DX5.

### DX6-A / DX6-B — Independent additional platform deliveries

**Implement:** one platform at a time, using existing intake/plan/capture/report
contracts. DX6-A adds reviewed Instagram professional-account/discovery routes;
DX6-B adds a permitted TikTok route for the actual approved purpose. Include source
field mappings, authentication guidance, quota/freshness/expiry handling and only
the supported account/post/media operations. No generic browser scraper.

**Modules/files:** `ingestion/connectors/instagram.py` or `tiktok.py`, their policy/
metric catalogs, shared workflow adapters only as required, focused skill references
and `docs/` access/setup documentation. Do not create both implementations in one change.

**Dependencies/integration:** shared DX1–DX5 contracts; each provider's actual app,
account type, granted scopes and use-case approval. A new route need not duplicate
already shipped orchestration, memory, statistics or storage services.

**Acceptance for each independent delivery:** at least one permitted real URL →
capture → canonical import → useful cited report; clearly scoped supported targets
and evidence levels; capability-specific denial for unsupported consumer/private/
competitor/insight/media access; all source-policy and lifecycle checks enforced.
Verify account enumeration or media analysis before advertising those specific
operations. TikTok Research Tools are not a commercial-access fallback. No approval
means that route remains unavailable, not a placeholder labeled implemented.

**Tests for each:** provider contract fixtures for pagination, field semantics,
permissions/expiry, deleted/private content, errors, rate limits and hostile data;
`tests/integration/test_instagram_workflows.py` or `test_tiktok_workflows.py` through
real shared import/report/reload; policy denial and cross-platform comparison
refusals; separately consented live source smoke and host workflow check. Repeat
installed-bundle, retention, migration and legacy-engine regressions.

### DX7-A–F — Independent specialist workflows

Each item below is a separate serial implementation/verification/commit unit, not
one omnibus delivery. Reuse the shipped coordinator, typed requests, source policies,
citations and existing engine services. A skill can work on permitted local/export
evidence without requiring every live connector; it cannot advertise unsupported
URL acquisition. DX5's independently packaged bundle, installed distribution and
actual host-behavior gates apply to each. A route-selection mock alone is insufficient:
exercise at least one real engine result and one refusal/partial branch per task.

#### DX7-A — Audience intelligence

**Implement/files:** add `skills/social-dna-audience/` and a focused workflow adapter
to `application/audience_service.py`, `behavioral_service.py` and qualified content
links. Extend shared workflow schemas/reporting only as needed. No duplicate reaction
classifier or metric store.

**Dependencies/integration:** DX3-B, R4/R5; actual permitted collection frames,
original comment/annotation references and compatible measured behavior. Collection
is explicit and bounded, never all-comments scraping by default.

**Acceptance:** a plain-language audience question over a real imported/captured
sample produces cited reactions, counterexamples and coverage, with the actual
behavioral lane where supplied. Intention is not action; commenters are not the
whole audience; missing retention/shares/saves stay unavailable. Model labels are
proposals, not fabricated reviewed annotations or sensitive individual profiles.

**Tests:** `tests/integration/test_audience_workflows.py` through actual R4/R5 imports,
analysis, report and reload; bounded/biased samples, disabled comments, uncertain
annotations, inaccessible metrics, source withdrawal and erasure. Extend existing
`test_audience_analysis.py` / `test_behavioral_analysis.py` regressions.

#### DX7-B — Psychological investigation and follow-up

**Implement/files:** `skills/social-dna-psychology/`, explicit specialist routing in
the research workflow, existing investigation/literature/reevaluation application
services and research report adapters. The research skill now exposes
this delivered branch rather than pretending every account study proves a mechanism.

**Dependencies/integration:** DX3-B/DX4, R7/R8; genuinely reviewed literature,
operationalizations, rival predictions and actual eligible analyses. No automatic
literature crawler, invented citations or agent self-certification of human reviews.

**Acceptance:** a question over prepared evidence returns an actual registered
protocol/assessment with applicable studies, rivals, counterexamples and limitations,
or a clearly labeled draft/partial result when review is missing. New contrary
evidence explicitly reevaluates the assessment and preserves weakened/contradicted
history. Engagement is not proof of a mechanism; creative effects do not prove mediation.

**Tests:** `tests/integration/test_psychology_workflows.py` through real R7/R8 services,
not fabricated prose: irrelevant/withdrawn study, missing review, actual assessment,
contrary update, immutable history, restart and erasure. Extend existing
`test_psychological_research.py` / `test_research_reevaluation.py`.

#### DX7-C — Platform and surface research

**Implement/files:** `skills/social-dna-platform/` and coordinator/report adapters to
`application/platform_service.py` and relevant publication/behavior services. Reuse
C1-C document/statement/capability/observation contracts, not a new ranking database.

**Dependencies/integration:** DX3-B/DX4, C1-C/R5; dated permitted official sources,
platform/surface-specific metric definitions and actual distribution observations.
Each connector's downstream-use approval remains a separate prerequisite.

**Acceptance:** answer a specified platform/surface question with separately labeled
official guidance and actual descriptive/experimental evidence. Where eligible, run
the real early-response/later-distribution pipeline; missing exposure or owner data
produces a qualified guidance-only/partial answer. No identical-platform assumptions,
proprietary-weight recovery, future leakage or guaranteed reach.

**Tests:** `tests/integration/test_platform_workflows.py` for actual C1 imports →
analysis/report/reload; platform/surface mismatch, source dates/corrections, traffic
type, incompatible windows, unavailable/private metrics and withdrawal. Extend
`test_platform_research.py` / `test_publication_context.py`.

#### DX7-D — Bounded discovery

**Implement/files:** `skills/social-dna-discover/` and adapters to existing
`application/{discovery_service,discovery_inputs,discovery_confirmation}.py`.
Persist actual R9 outputs/attempt references in the same workflow bindings.

**Dependencies/integration:** DX4, R9 and respective C1 evidence; declared SQL corpus,
feature/outcome timing, candidate family, creator/time splits and actual support.
Source policies must permit derived analysis; nearest-neighbor hits are not a corpus.

**Acceptance:** execute the real bounded discovery/transfer pipeline for an eligible
fixture, preserve the whole attempted family and failures, and produce an evidence-
qualified pattern or inconclusive result. Distinguish hypothesis generation from
independent confirmation. An insufficient corpus refuses inference rather than
manufacturing a viral recipe or inflating independent creator counts.

**Tests:** `tests/integration/test_discovery_workflows.py`: real corpus → R9 search →
transfer/confirmation as eligible → cited report → reload; insufficient creators,
confounding/leakage, consumed holdout, API-use denial and stale/withdrawn inputs.
Retain `test_discovery.py` / `test_discovery_context.py` regressions.

#### DX7-E — Original evidence-qualified strategy

**Implement/files:** `skills/social-dna-strategy/` and workflow/report adapters to
`application/recommendation_service.py`. Produce original scripts/production briefs,
packaging/publishing/profile actions and a prioritized testing plan through the
existing structured proposal producer, not a second content-generation engine.

**Dependencies/integration:** DX4, R10 and relevant C1 evidence; supplied goals,
niche/language/audience/constraints and eligible findings. Retrieve earlier evidence
only when applicable; do not assume a technique transfers across creators/platforms.

**Acceptance:** persist an actual cited recommendation set with proposed actions,
support/counterevidence, applicability, missing context and next tests. Distinguish
supported recommendations from speculative ideas; never assert measured lift,
duplicate a third-party script or execute publishing/profile edits. Reconstruction
and original adaptation remain different output types.

**Tests:** `tests/integration/test_strategy_workflows.py`: actual qualified findings →
R10 proposals → report/reload; unrelated evidence, unsupported lift, missing domain
inputs, conflicting findings, source withdrawal and absent model. Structural/citation
validation does not claim comprehensive originality or scientific validity. Extend
`test_recommendations.py`.

#### DX7-F — Experiment design and outcome evaluation

**Implement/files:** `skills/social-dna-experiment/` and workflow adapters to
`application/experiment_service.py`, real R5 outcome intake and assessment/history
reports. Design/register and evaluate are explicit separate operations.

**Dependencies/integration:** DX4, R10; actual prospective design/review and supported
assignment/outcome records. No experiment execution, recruitment, paid spend, account
mutation or publication is authorized by registration.

**Acceptance:** a test request yields a genuine draft or registered prospective
protocol with variants, units, endpoints and stopping/analysis constraints. After
authorized execution outside this skill, supplied actual outcomes reach the real
supported estimator and qualified assessment/history. Missing review, invalid
assignment, insufficient support or incompatible outcomes cause refusal/partial,
not invented experiments, causal lift or fresh holdout claims.

**Tests:** `tests/integration/test_experiment_workflows.py`: real registration → later
actual outcome import → R10 evaluation → report/reload; unsupported designs,
unexecuted plans, deviations, missing outcomes, repeated tests, source correction/
withdrawal and confirmation that no external publishing/action occurs. Extend
`test_experiments.py`, `test_experiment_limits.py` and `test_experiment_history.py`.

### Completion and scope control

DX1 is deliberately a small source-only post-report product, **not** completion of
the user's full account reverse-engineering vision. A credible single-platform
URL-first account/comparison release requires DX1–DX5's applicable live gates and
an honestly stated media-access branch. DX6-A/B are independent **required** platform
deliveries for the user's three-platform target. A first-platform release is useful
but does not finish that target or justify claiming all URLs are supported.

The complete 14-task catalog additionally requires all DX7 deliveries, both analyze
scopes and the DX2-B reconstruction producer, with each task's actual distribution/
host/source gates recorded. One working host conversation does not certify all
14 tasks on all three hosts. A profile audit cannot be declared done by an account
report, nor reconstruction by exporting raw ASR text under a new heading.

All tasks reuse one selected persistent library: canonical SQLite + managed artifacts,
optional Qdrant text retrieval and SQLite-backed NetworkX graph views. New typed
outputs need exact lineage/eligibility and correction/erasure tests at first use.
Future research retrieves and explicitly reevaluates earlier evidence; it does not
automatically fine-tune the host AI or create new infrastructure per skill.

No mandatory paid provider, browser, worker cluster, server database, new graph
database, UI, autonomous monitoring or account publishing is included. If source
restrictions block a requested capability, report the limitation and present
permitted assistance; do not expand scope or silently change to an unauthorized route.

### Initial three-skill planning verification record — 2026-11-06

Documentation only: this section, ARCHITECTURE §34, the detailed URL-first design
and current-scope clarifications in README/portable-skill documentation. No application
code, skill bundle, migration, dependency or host/source configuration changed.

- `git diff --check`: passed; 130 local document-link targets checked, none missing.
- Existing skill contract/export/capability regression tests: **30 passed**.
- Full application suite, new workflow tests, live source acquisition and live host
  behavior were not run for this planning change. New DX acceptance is unimplemented,
  not established by those existing passing tests.

### Fourteen-skill planning update verification — 2026-11-06

Documentation-only revision: all 14 names agree across PLAN, ARCHITECTURE and the
canonical workflow catalog. The proposal now separates content/reconstruction,
profile/account and six specialist deliveries; README and portable-skill scope
notes agree. No application code, actual skill bundle, migration, dependency or
host/source configuration changed.

- `git diff --check` passed; 135 local document links and 22 local heading anchors
  checked, none missing.
- Catalog comparison passed: exactly the same 14 unique task names in all three
  authoritative tables, with a delivery/acceptance/test owner for each.
- Existing regression tests could not be rerun: this checkout has no `.venv`, and
  system Python has no `pytest`. No dependencies were installed. The initial
  three-skill verification record above is historical, not a current test run.
- New workflow tests, live source/host checks and model-quality acceptance remain
  future implementation gates; this documentation update does not mark them passed.
