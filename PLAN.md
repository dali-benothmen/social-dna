# SocialDNA implementation plan

Revised: 2026-11-05. Scope: approved architecture/documentation revision; no new implementation is claimed.

Runtime remains package `0.0.4`, SQLite head `0004_analytics`. Released migrations `0001_foundation`–`0004_analytics` are immutable. Legacy Milestones 0, 1, 3 and 4 are completed deliveries; their limitations remain visible. Legacy Milestones 2, 5 and 6 are **superseded, not completed**. Every R/U milestone below is **planned and unimplemented**.

Authoritative design: [ARCHITECTURE.md](ARCHITECTURE.md), [research contracts](docs/research-contracts.md), [statistical design](docs/statistical-design.md), [migration strategy](docs/migration-strategy.md), and [reference use case](docs/research-use-case.md). The [audit](docs/architecture-audit.md) records the reasons for this revision; the [previous roadmap](docs/history/PLAN.pre-research-revision.md) is historical, not an alternative active plan.

## 1. Outcome, limits and delivery rules

SocialDNA is a local-first Python engine and portable Agent Skill that investigates why content may succeed. It preserves observable evidence, evaluates competing explanations with appropriately scoped data, compares creators without hiding confounding, and revises findings as evidence changes. It is not a psychological diagnosis system, a universal virality score, or a machine for proving mechanisms from observational correlations.

The revised design preserves working media processing, synchronized timelines, provenance, artifacts, account exports, statistical tooling, reproducible reports and CLI execution. SQLite remains authoritative; persistent Qdrant Local retrieval and SQLite-backed NetworkX projections are introduced only when canonical producers and revision semantics exist. No database server, paid API, new distributed service, or automatic model download is required.

Delivery rules:

- Implement one bounded milestone at a time; finish its working end-to-end behavior and tests before claiming completion. Separate optional provider work from the required offline path.
- Add schema only alongside its first canonical writer, resolver and demonstrable reader. Designing later payloads does not require creating unused tables now.
- Preserve old IDs, frozen analyses, raw artifacts and report bytes wherever retention is permitted. Required erasure preserves only allowed tombstones/audit metadata and explicitly degrades reproduction. Corrections produce explicit new revisions; they do not silently alter historical conclusions.
- Keep basic media/account analysis fast: do not register a research question, load a graph, index embeddings or invoke a reasoner merely to describe a video.
- Missing data is not zero; absent detection under sparse sampling is not demonstrated absence; expressed intention is not behavior; association is not causation.
- Every research result declares its population, availability, estimand, evidence version, uncertainty, alternatives and limitations. `insufficient_data`, rejected and inconclusive results are successful research outcomes when honestly supported.
- Implementation changes require unit/integration/contract/end-to-end verification, migration/compatibility checks, documentation updates and a scoped working commit when authorized. This document revision does not authorize implementation yet.

## 2. Preserved implementation and historical deliveries

| Legacy delivery | Implemented and preserved | Recorded verification at delivery |
|---|---|---|
| M0, `0.0.1`, 2026-11-04 | Installable CLI; settings/IDs/output contracts; SQLite/UoW/migrations; provenance and sources; artifacts; locking; Qdrant lifecycle and health checks | 45 tests; lint/type/build/isolated-install checks |
| M1, `0.0.2`, 2026-11-04 | Local video registration/probing; deterministic scenes/frames/visual/audio measurements; supplied subtitles; shared timeline; durable task cache/resume; evidence-backed JSON/Markdown reports | 77 tests plus targeted recovery/cache regressions; installed cross-process video/report checks |
| M3, `0.0.3`, 2026-11-04, deliberately before M2 | Optional prepared local ASR/OCR/pose/audio adapters; provider isolation; consent/budget/provenance gates; model/task/report integration | 116 tests including real CPU ASR/OCR and isolated MediaPipe; optional alignment/VLM quality not empirically established |
| M4, `0.0.4`, 2026-11-05, deliberately before M2 | Strict CSV/JSON account/post/comment/tag/metric exports; immutable snapshots; local-media account batches; guarded descriptive/model paths; frozen analytics and JSON/Markdown reports | 164-test full run including local-model smoke; final targeted hardening raised collected tests to 166; lint/type/build/offline-install checks |

These are historical test records, not tests rerun for this design-only revision. Only Linux/Python 3.11 was locally executed at those deliveries; configured CI platforms are not claimed as observed results.

M4 delivered its scoped implementation, but its retrospective baseline, same-creator matcher, cross-niche design and model-validation mismatch need R2 remediation. Existing reports remain reproducible and are not retroactively relabeled as corrected. The old M2 memory design and broad M5/M6 delivery bundles are replaced below, rather than treated as satisfied by the completed work.

## 3. Dependency-aware delivery sequence

| ID | Working result | Hard dependencies | Status |
|---|---|---|---|
| R1 | Universal evidence with usable metric/comment citations and minimal research registration | Current `0.0.4` | Planned; first ready for implementation |
| R2 | Correct historical baselines, comparison designs, feature timing and actual-pipeline validation | R1 | Planned |
| R3 | Semantic creative events and reproducible multimodal feature recipes | R1; R2 for analytics joins | Planned |
| R4 | Audience collection provenance, reaction annotations and qualified content links | R1, R3 | Planned |
| R5 | Behavioral metric series, denominators, attribution and account outcomes | R1, R2; R3 for event overlays | Planned |
| R6 | Persistent SQL/FTS/Qdrant/SQLite-backed NetworkX research memory | R1–R4; R5 for behavioral projections | Planned |
| R7 | First complete, literature-backed psychological research vertical slice | R2–R6 | Planned |
| R8 | Incremental hypothesis reevaluation and preserved contradiction history | R7 | Planned |
| R9 | Bounded nonlinear, cross-creator and cross-niche discovery | R2, R3, R6–R8 | Planned |
| R10 | Registered experiment outcomes and evidence-qualified recommendations | R7–R9 | Planned |
| U1 | Individual photo/carousel analysis reusing existing media contracts | R1 | Planned, parallel usability track |
| U2 | Portable Codex/Claude Code/OpenCode skill and usable reports | U1, R2; capability-gated integration with later R milestones | Planned, parallel usability track |

Audience comments and behavioral metrics are split into R4/R5 because sampling/semantic annotation and metric time-series validity are different testable products. Memory follows canonical producers and revision contracts, rather than freezing the current media-only evidence model. A small literature corpus, hypothesis registration and experiment proposal appear in R7; general discovery and experiment-outcome analysis wait for R9/R10. U1/U2 prevent research infrastructure from postponing ordinary creator workflows.

R6 must work without prepared embeddings through SQL/FTS/graph retrieval; semantic acceptance additionally requires a verified prepared local embedding model. R7 must work with authorized local media, imported human annotations and curated research when no VLM is installed. Creator-owned retention is an optional richer evidence branch, never an invented prerequisite substitute.

## 4. Cross-cutting interfaces and compatibility gates

Preserve current commands and output/exit-code families: `init`, `doctor`, `storage status|verify`, `import local|csv|json`, `analyze video|account`, `timeline show`, `models status|prepare`, `compare posts|accounts|reproduce`, and `report generate --run|--account`. New behavior is additive or uses explicit versioned specification fields. Old comparison specifications retain legacy semantics for exact reproduction; corrected analyses use a new specification/method version. Old reports never acquire a new interpretation just because software was upgraded.

New command sketches in the milestone sections are proposed interfaces, not available commands. The exact argument surface is stabilized by contract tests at the implementing milestone. All agents call the same Python services/CLI; agent instructions contain no alternate statistics, hidden browser scraping or host-specific database logic.

Each future migration must preserve released migration checksums and old evidence identities, upgrade a fixture from every released head, survive an interrupted upgrade, and pass `storage verify`. Back up and validate before upgrades; destructive retention/redaction is explicit and audited. See [migration strategy](docs/migration-strategy.md).

Research materialization is lazy and budgeted. The canonical research layer must accept observed, inferred and human-adjudicated inputs with distinguishable provenance. Index jobs carry generation/revision and eligibility tokens. A deleted/withdrawn source cannot be resurrected by old work. Research-graph relationships carry a finding/assessment identity, scope, qualification and evidence; multiple input features form a pattern entity, not independent causal-looking edges.

## 5. R1 — Universal evidence and minimum research contracts

Status: **planned, unimplemented; first implementation milestone**.

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

Status: **planned, unimplemented**.

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

Status: **planned, unimplemented**.

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

Status: **planned, unimplemented**.

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

Status: **planned, unimplemented**.

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

Status: **planned, unimplemented; replaces legacy M2**.

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

## 11. R7 — First complete psychological research vertical slice

Status: **planned, unimplemented**.

### Objective

Answer the bounded question “Why might showing a finished meal in the first seconds be associated with better performance?” with competing, falsifiable explanations and real evidence—not persuasive trigger labels.

### Existing components affected

Universal evidence, semantic events/recipes, audience and behavioral records, comparison services, memory document builders and reports. Keep media reasoners' current no-psychology/performance boundary; add a separate evidence-constrained research service rather than silently broadening descriptive prompts.

### New components and schemas/interfaces

Add reviewed literature import/curation, `psychology/{constructs,operationalizations,hypotheses}.py`, research evaluation/assessment services and a research report model. Canonical payloads and necessary query projections cover study/source findings with design/population/measurement/limitations, construct definitions, operationalized predictions, rival-hypothesis links, immutable assessments, scoped findings, support/contradiction links and proposed experiment specifications; low-volume definitions need not each have a dedicated table. Evidence for study excerpts/statistical terms uses the universal registry. Evaluation records test-family membership and holdout consumption through R2's minimal ledger.

Proposed interfaces: `research register|evaluate|show`, curated-study import and grounded report generation. Extraction reliability, literature applicability, local association, generalization and causal identification remain distinct assessments, not one confidence score.

### Dependencies and tasks

Depends on R2–R6. Begin with a small human-reviewed corpus and limited anticipation/sensory appeal/curiosity/cognitive-fluency explanations; each is a candidate, not assumed present. Use optional configured reasoning, never mandatory hosted APIs. Tasks: encode real study evidence/limits; define competing predictions; assemble eligible evidence; compare representative populations and failures; evaluate or withhold associations; write immutable assessment and a discriminating experiment proposal. Human annotations/imports provide the no-VLM path.

### Acceptance criteria

The full twelve-step cooking scenario in [research use case](docs/research-use-case.md) is represented; reevaluation is previewed here and executed in R8. A mechanism has a literature source, applicability judgment and falsifiable prediction, or remains explicitly unsupported. Public-only data yields a constrained question/result; unavailable retention is not guessed. The reference fixture produces at least one weakened, rejected or inconclusive explanation and preserves counterexamples. Causal language is blocked without eligible causal evidence, and a creative A/B effect does not by itself prove a mediator.

### Automated tests

Fabricated/irrelevant/withdrawn study citations; locator validation; technique/construct/response/outcome distinctions; rival predictions; null/negative evidence; unavailable-owner metrics; no-provider offline execution; statistical result qualification; report claim-level gates; sampling-frame versus top-K separation; cross-process assessment/report reproduction.

### Demonstrable end-to-end behavior

Authorized video/event evidence → rival mechanism predictions and reviewed literature → sampled-comment reactions → age-aligned comparable outcomes → same/other-creator comparisons and unsuccessful examples → immutable scoped association or insufficient-data finding → proposed experiment distinguishing explanations. Every conclusion opens its exact evidence and states what would change the conclusion.

## 12. R8 — Incremental hypothesis reevaluation

Status: **planned, unimplemented**.

### Objective

Make persistent knowledge an explicit evaluation-and-revision process: new evidence can weaken or reject an old conclusion while historical assessments remain reproducible.

### Existing components affected

R1 registration, R7 assessment services, import/task completion hooks, evidence eligibility, memory synchronization and research reports.

### New components and schemas/interfaces

Add `research/reevaluation.py`, dependency/invalidation service and comparison/history rendering. Extend canonical dependencies from hypothesis/specification/assessment to data versions, features, population, model, literature and source eligibility. Store reevaluation requests, immutable assessment inputs/results, new-versus-reused evidence membership, supersession/contradiction links, reasons and scoped status transitions. A stale marker is mutable operational state; published assessments are immutable records.

Proposed interfaces: `research reevaluate <id>`, `research history <id>`, and revision-specific retrieval. New data can enqueue eligible work; costly reevaluation is explicit or subject to a user-set budget, never an unbounded background agent.

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

### Dependencies and tasks

Depends on R2/R3/R6–R8; retain existing scikit-learn/statsmodels first. Tasks: bounded declared interactions and spline/regularized nonlinear terms; only later justified bounded trees/boosting; nested train-only selection; chronological/creator/content-duplicate splits and held-out niches where feasible; stability and counterexample analysis; planned test-family correction; session-spanning search ledger and repeat-look restrictions. No automatic causal interpretation of prediction/importance.

### Acceptance criteria

Pure interactions and U-shaped effects can be investigated by the actual selected pipeline. A feature combination can succeed within one niche and fail in another without being promoted to universal truth. A depleted holdout is not reused silently. Too few independent creators/niches yields descriptive scope/insufficiency. All attempted candidates, not just successful ones, remain auditable.

### Automated tests

Null searches and false-discovery behavior; pure interaction/U-shape; correlated/redundant features; nesting/selection leakage; duplicate media; creator and held-out-niche transfer; contradictory examples; fixed search budget; repeated attempts/holdout reuse; scope-qualified graph patterns; seeded reproducibility and small-cluster refusal.

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

### Dependencies and tasks

Depends on R7–R9; no publishing API or autonomous external action. Tasks: register bounded design; import creator-authorized results; validate assignment/measurement/attrition; analyze planned estimands; record deviations and threats; feed results into a new hypothesis assessment; generate original technique alternatives while preserving creative versus psychological uncertainty.

### Acceptance criteria

A sound randomized design may support a scoped creative effect; a curiosity/anticipation mechanism requires additional discriminating measurement/identification. Posting two variants sequentially is not mislabeled randomization. Recommendations cite applicable findings and failures and can state “test first.” Publishing, recruiting, spending or contacting viewers remains outside analysis authorization.

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

Depends on U1/R2 for the first core usability delivery; later R3–R10 only enable corresponding workflows after their tests pass. At implementation time use the skill-creator guidance and verify the then-current host compatibility rules. Tasks: installation/doctor guides; local video/photo/account comparisons; caption/hashtag evidence; permission/data-access questions; cited reports; safe experiment proposals; JSON errors and resource estimates; packaging/migration/restart hardening. No mandatory hosted service.

### Acceptance criteria

All three hosts can call the same engine and interpret stable results using documented invocation patterns. A core-only install analyzes video/photo/account exports and reports limits without attempting absent research or semantic commands. Later research workflows check capabilities and exact evidence rather than inventing support. Expensive/remote/publishing actions require appropriate explicit scope/consent.

### Automated tests

Skill link/reference/command contract validation; capability-gated workflow fixtures; installed wheel/sdist offline smoke; Linux/macOS/Windows CI and supported Python versions; JSON parsing and exit codes; HTML/Markdown escaping/accessibility; permission/remote-consent regression; cross-process persistence. Live host smoke checks are separately recorded and never inferred from static validation.

### Demonstrable end-to-end behavior

Follow a host-neutral skill workflow to analyze a local video/photo/account export, compare creators under R2 rules and produce a cited report. In a research-ready installation, invoke the cooking workflow and show hypothesis history; in a core-only installation, explain the unavailable capability precisely and stop that branch.

## 17. Release and verification gates

The old `v0.1`–`v0.4` milestone labels are withdrawn planning gates, not promised releases. Package `0.0.4` and existing data stay unchanged by this revision. Each implementation sets its package/specification/migration versions deliberately; an R ID is not a schema revision number.

A research-preview release requires R1–R8 plus the corresponding U2 workflow: one complete cooking use case, eligible universal citations, representative comparisons, persistent retrieval, a falsifiable literature-backed explanation and a demonstrable weakened/rejected revision. Broader-discovery/experiment-ready status requires R9/R10; public `1.0` additionally requires U1/U2 hardening and documented platform/data-access limitations. No milestone is considered complete solely because a model produced plausible prose.

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

The first implementation-ready milestone is **R1**. All architecture revisions above are documentation only until implementation is explicitly requested.
