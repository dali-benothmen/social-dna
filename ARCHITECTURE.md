# SocialDNA architecture

Revised: 2026-11-06. Implementation: **0.0.20**, database head **0017_images**. R1–R10, C1 and U1 remain completed within their documented bounds. U2 adds the [portable skill and report delivery](docs/portable-skill.md); live host behavioral checks remain a separate unexecuted gate. Verification is recorded in [PLAN.md](PLAN.md). The approved [intelligence audit](docs/architecture-audit.md), [capability audit](docs/intelligence-capability-audit.md), [experiment/strategy](docs/registered-experiments.md), [bounded discovery](docs/bounded-discovery.md), [research memory](docs/research-memory.md), [versioned analytics](docs/versioned-analytics.md) and [psychological research](docs/psychological-research.md) contracts retain their scope.

The [implementation plan](PLAN.md) defines delivery and acceptance gates. Detailed contracts live in [research contracts](docs/research-contracts.md), [statistical design](docs/statistical-design.md), [migration strategy](docs/migration-strategy.md), and the [twelve-step cooking use case](docs/research-use-case.md). The [previous architecture](docs/history/ARCHITECTURE.pre-research-revision.md) is a historical record, not a competing specification. Architecture/plan line references inside the unchanged audit refer to those pre-revision documents.

## 1. Product and non-negotiable boundaries

SocialDNA is a local-first, agent-independent Python engine, exposed through a CLI and eventually a portable Agent Skill. It investigates why content may succeed by preserving observations, operationalizing competing explanations, connecting them to appropriate audience/outcome evidence, testing qualified associations, and revising findings.

The target is unified production, audience/psychology, platform-specific distribution, publishing/search and profile/conversion intelligence. These are separate evidence domains using shared infrastructure, not four new engines or one universal ranking score. Search discovery, recommendation exposure and conversion require different objectives and measurements. Never claim proprietary algorithm-weight recovery, recommendation bypass or guaranteed virality.

The product must remain useful for a single video, photograph, carousel, caption, hashtag set, or account even when there is insufficient data for research. Ordinary analysis does not require registering a hypothesis, downloading research, fitting models, opening a graph, or embedding documents. Whole-account analysis is a resumable collection of bounded post/media tasks, not one giant model prompt.

Preserve:

- SQLite as canonical structured storage, Alembic migrations, provenance, content-addressed artifacts, synchronized media timelines, reproducible reports and analyses.
- Qdrant **Local Mode** as a derived persistent semantic index; NetworkX views backed by canonical SQLite relationships. Neither becomes a second source of truth.
- One shared engine for Codex, Claude Code and OpenCode; host instructions orchestrate the engine rather than implement separate research logic.
- Offline import and human-reviewed annotation paths. Optional local/remote models require explicit preparation, authority and budgets; no automatic downloads.
- Existing identifiers, commands, artifacts, frozen reports and migration history. Corrections produce explicitly versioned new analyses.

Do not introduce required database servers, Neo4j, PostgreSQL, a workflow cluster, an autonomous literature crawler, an unrestricted scraper, or a comprehensive psychology ontology.

Scientific boundaries are architectural invariants: missing data is not zero; extraction confidence is not scientific support; intention is not behavior; observational association is not a psychological causal explanation. Infer no individual viewer's hidden mental state or sensitive traits. Literature plausibility, annotation agreement and randomized creative effects each answer different questions.

## 2. Current foundation versus revised target

### 2.1 Implemented foundation

The current repository delivers deterministic local video processing, supplied subtitles, optional prepared local-model enrichment, strict account/post/comment/tag/metric imports, account media batches, descriptive/model-based comparisons and immutable analysis/report artifacts. R1 additionally supplies universal revisioned citations and draft registration. R3–R5 add qualified creative/audience/behavioral producers. R6 provides persistent citation-backed SQL/FTS, optional immutable-space Qdrant retrieval and qualified SQLite-backed NetworkX views. Actual pretrained-model/corpus relevance is not inferred from controlled storage tests.

The unversioned legacy path retains retrospective baselines, same-creator matching and auxiliary Ridge checks for exact reproduction. The explicit version 2 path corrects time-aware references, matching, lineage and selected OLS/Poisson validation; it withholds unidentifiable niche/between-creator effects and unseen-creator predictions. R4 supplies qualified reaction analysis, R5 source-defined behavioral series/account outcomes and R6 persistent retrieval. R7 adds a bounded reviewed-literature/rival-protocol assessment path over actual frozen analyses, not identified psychological mediators. R8 adds explicit incremental reevaluation and immutable contradiction history. Existing descriptive reasoners retain their no-psychology/performance boundary.

### 2.2 Components to preserve, adapt and add

All paths below are relative to `src/socialdna/`. A proposed filename is a responsibility boundary, not permission to scaffold unused modules.

| Treatment | Components | Revision |
|---|---|---|
| Preserve algorithms/contracts | `core/{ids,hashing,time}.py`; `media/{probe,ffmpeg,scenes,frames,audio,subtitles,timeline}.py`; existing artifact/filesystem, writer-lock, UoW and provenance primitives | Keep original-presentation timestamps, hash-addressed inputs, millisecond intervals, deterministic transforms and durable task cache/resume. Add new producers without replacing the working timeline. |
| Preserve provider isolation | `analyzers/`, `providers/`, `application/{task_runner,enrichment_service}.py` | Keep prepared manifests, declared resources, subprocess isolation, explicit consent and budgets. Extend validated input/output contracts only when needed. Existing `TaskContext` gets a backward-compatible evidence adapter, not an immediate rewrite. |
| Extend canonical storage | `storage/{schema,repositories,health}.py`, migrations; `domain/{evidence,research}.py` | Add revision-aware universal evidence, registration and first-use query projections. Never edit released migrations 0001–0011. |
| Adapt imports and reporting | `ingestion/tabular.py`; `application/{account_import_service,performance_service,report_service}.py`; `reporting/` | Preserve v1 formats/readers; add immutable source snapshots, versioned metric semantics and citations, eligibility-aware current reports and explicit new research formats. |
| Repair rather than replace analytics | `analytics/{metrics,baselines,cohorts,statistics,validation}.py` | Explicit designs, as-of history, actual feature lineage, identifiable models, duplicate-safe splits and validation of the actual selected pipeline. |
| Adapt resource bootstrap | `application/bootstrap.py`, `storage/vectors.py` | R6 opens the Qdrant client lazily; existing data-directory locking remains. |
| Add cohesive evidence/research services | Proposed `application/evidence_service.py`, `application/research_service.py`, corresponding domain contracts/repositories | R1 registration/resolution first; R7 evaluation and R8 reevaluation later. No generic agent framework. |
| Add canonical producers | Proposed creative-event, audience and behavioral service/domain modules; `analytics/{designs,features}.py`, `research/discovery.py` | Introduce in R2–R5/R9 with real imports, writers, readers and tests. Reuse existing media/analytics services. |
| Add derived memory | Proposed `memory/{lexical,vector_sync,graph,hybrid}.py`, `providers/embeddings.py`, `application/query_service.py` | R6 SQL/FTS + Qdrant outbox + bounded NetworkX projection, never application-owned hidden facts. |

The portable skill is delivered in U2 (§33). U1's bounded static analysis is documented in §32;
it does not imply general automatic visual interpretation or scientific validity.

### 2.3 Four additional capability areas

All four areas are **partially supported overall**, with specific missing producers and services. See the [code-grounded coverage matrix](docs/intelligence-capability-audit.md#1-coverage-against-working-code) for full/partial/missing subcapabilities and acceptance evidence.

| Area | Working substrate | Missing targeted foundation | Future delivery |
|---|---|---|---|
| Professional filmmaking/editing | Scenes, appearance/flow/audio proxies, subtitle tracks, reviewed creative events, eleven pinned recipes and declared comparisons | Professional shot/craft taxonomy, validated interpretation, richer pacing/subtitle/music/transition recipes | C1-A; R9 interactions/comparisons; R10 strategies |
| Platform recommendation/distribution | Platform-namespaced source metrics, cohorts, time windows, reactions and scoped comparisons | Versioned official statements, distinct platform/surface research specifications and traffic/exposure observations | C1-C; R8 version review; R9 models; R10 experiments |
| Publishing/discoverability | Post metadata/revisions, caption/hashtag evidence, UTC-hour feature | Native format/language/local clock/completeness, thumbnail variants, title/search/trend evidence and separate objectives | C1-B/C1-C, U1 images; R9/R10 |
| Profile/account conversion | Handle and supplied profile JSON history; source-defined account metrics; qualified post conversion credits/net follower changes | Typed full profile snapshots/locators, rubric-backed positioning/pillars and compatible branching funnel/cohort outcomes | C1-D, U1 images; R9/R10 |

C1 follows R7 in bounded independent slices. It is not a prerequisite for the cooking slice or initial reevaluation; unknown context must be disclosed rather than invented. R1–R6 code, schemas and completion records are preserved.

## 3. Execution architecture and communication

```text
Agent host / human
        │ versioned CLI JSON + explicit files/specifications
        ▼
Python CLI → application services → validated domain contracts
                   │                          │
                   ├─ existing task runner → media/analyzers/providers
                   ├─ feature materializer → comparison/validation engine
                   └─ research service → claim validation → immutable assessment
                                              │
                                      SQLite transaction
                              canonical rows + provenance + outbox
                                              │
                           artifacts        derived index worker
                                                 ├─ SQLite FTS
                                                 ├─ Qdrant Local
                                                 └─ SQLite graph projection
                                                         ↓
                                                bounded NetworkX view
```

Communication is in-process typed Python calls. The CLI serializes typed results through the existing success/partial/error envelope and exit-code families. Durable task/run records and SQLite outbox rows provide recovery; no message broker or resident daemon is needed. Index draining can run synchronously after a command, or via an explicit bounded maintenance command. The CLI reports index lag separately from canonical write success.

Three paths share contracts:

1. **Basic description:** import media → existing deterministic tasks → optional prepared analyzers → source-backed report. Research and indexing are optional side effects, not prerequisites.
2. **Specified research:** import authorized data → select/freeze population → materialize versioned features → evaluate registered predictions/rivals → validate claims → freeze assessment/report → project to memory.
3. **Discovery:** explicit search budget and family registration → eligible population → bounded candidate generation → training-only selection → independent validation → qualified findings. Retrieval proposes candidates; it never silently defines the statistical sample.

Each task declares input revisions, algorithm/model/config versions, dependency hashes, language, sampling coverage, resource estimate and consent class. Identical completed inputs reuse cache. A model/recipe/data change invalidates only dependent work. Imported and human-reviewed annotations are legitimate reproducible inputs, not fake outputs standing in for an absent model.

Retain one mutating process per data directory and bounded subprocess workers. Do not hold SQL write transactions during model inference or FFmpeg. Release/suspend expensive resources between stages; use explicit frame/context/token/time/memory budgets. Resume at committed task boundaries. Read-only SQL reports should not need a Qdrant handle; commands opening Local Qdrant must honor its process locking.

## 4. Canonical identity, revisions and universal evidence

### 4.1 Identity and version semantics

Use `EntityRef(kind, id, revision_id)` and `EvidenceRef(id, revision_id)` for new research. IDs are opaque stable identities, not generated from mutable prose or row positions. Revision IDs identify immutable content/interpretation. Existing UUIDs are preserved; namespace non-UUID legacy keys by entity kind.

A revision records schema version, content hash, author/analyzer/configuration, `recorded_at` and provenance. Subject/world validity time and earliest known availability are separate fields. Publication time, collection time, outcome window, media offset and software computation time cannot substitute for each other.

| Root/projection | Key and required invariants |
|---|---|
| `entity_identities` | Composite PK `(kind, entity_id)`; lifecycle metadata; registered kinds only. |
| `entity_revisions` | PK `id`; composite identity FK; unique identity/revision number; schema/hash/provenance/recorded time; validated payload or typed immutable binding. A reference must verify that its revision belongs to the stated identity and kind. |
| Typed legacy bindings | Actual FKs to immutable existing rows, with stored hashes; mutable legacy account/post/comment metadata instead needs an immutable captured payload/revision. An old row pointer alone is not a frozen revision. |
| `evidence_records` | PK `id`; source/lifecycle identity. Register each old media evidence UUID unchanged. |
| `evidence_revisions` | PK `id`; evidence identity FK; subject revision FK; locator kind/schema/hash; provenance/capture/availability; nullable producer run/task. Exactly one valid typed locator binding matching the declared kind, not an empty generic JSON citation. |
| `legacy_media_evidence_bindings` | Evidence revision FK and unique original `evidence_items.id` FK; original media/task/interval checks preserved. |
| Typed evidence bindings | Real FKs to comment/source snapshots, metric observations/series, study findings, analysis terms or experiment outcomes as their writers land. No interpolated SQL table-name lookup. |
| `evidence_links` | Owner revision FK + evidence revision FK + role + scope revision FK. Roles include observed, supporting, contradicting, alternative, context, excluded and non-discriminating. Research links require a registered scope. |

The entity registry is a small common revision substrate, not a universal unindexed EAV/JSON database. Low-volume definitions/specifications may be validated versioned documents. Frequently queried features, memberships, intervals, metric bins and dependencies receive typed normalized projections with constraints and indexes. [Research contracts](docs/research-contracts.md) supplies first-use projection keys and payload schemas.

R1 adds real media/post/comment/metric bindings and minimal question/hypothesis registration. R2 adds existing statistical-result/term bindings alongside corrected comparisons and primitive feature lineage; R3 supplies semantic recipe producers. Future kinds are introduced with their working writers. No migration must populate fictitious study, experiment, or model records.

### 4.2 Typed locators

| Evidence type | Locator and validation |
|---|---|
| Media interval | Exact media revision, half-open `[start_ms,end_ms)`, valid original timeline bounds and producing observation/task where present. |
| Frame / image region | Exact frame/photo revision; frame media offset if real; optional normalized spatial region. A photo has no fabricated duration. |
| Speech / subtitle / OCR / caption span | Exact track/text revision and segment/word/character range; declared Unicode convention and normalization map. Media location only where actually aligned. |
| Comment / audience reaction | Exact comment revision and span, or versioned reaction/cluster with resolvable member evidence and collection frame. |
| Scalar metric / series bin | Exact subject/definition/cohort/window revision, observation or bin, source provenance and capture/availability. No mandatory media/task. |
| Research source / study finding | Verified source revision, page/section/table or permitted excerpt; publication design and applicability remain separate from citation existence. |
| Statistical result | Exact immutable analysis revision plus term/contrast/diagnostic ID and model/specification version. |
| Experiment outcome | Exact design/assignment/outcome revisions and registered scope; linkage does not itself establish causal validity. |

C1 adds typed title/metadata/profile-field/link/pin and official-document statement locators only alongside real writers/resolvers. Static thumbnail/profile-image regions use U1 asset evidence, not fabricated video intervals. Current post-text bindings remain caption/hashtag only; arbitrary profile JSON is not a typed profile citation.

`EvidenceResolver.resolve(ref, purpose, as_of)` returns typed source/locator, revision, provenance, availability, eligibility and withdrawal state. It rejects dangling, wrong-kind, out-of-bounds, wrong-subject and impermissible references. SQL FKs enforce registry existence; typed binding constraints and service validation enforce semantic target integrity.

A v1 media evidence ID resolves through its immutable legacy binding. New research uses explicit revisions. Existing metric citation URIs retain a compatibility resolver; they are aliases, not excuses to fabricate media evidence or rewrite stored report bytes. A valid citation proves traceability, **not** that a claim follows from its source.

### 4.3 Claim validation

Preserve the existing ladder: observation → hypothesis → association → causal finding. Do not automatically promote between levels.

- An **observation** requires eligible direct evidence, method and coverage. Annotation may be proposed/reviewed/disputed; sparse failure to detect is not absence.
- A **hypothesis** registered in R1 may remain a draft with statement, scope and data needs, ineligible for research evaluation. An evaluation-ready R7 specification adds operationalized predictions, alternatives and falsification conditions. Literature is reviewed when available; an unreviewed proposal remains explicitly so.
- An **association** references a frozen eligible statistical design, population, effect/uncertainty, comparison method, diagnostics and missingness. Save null, contrary and insufficient results too.
- A **causal finding** requires a registered design, actual assignment/identification and outcomes, assumption/deviation checks and review. A registered experiment record alone is insufficient.

Randomizing an opening may identify an effect of that creative manipulation in the tested population. It does not identify anticipation or curiosity as the mediator without additional discriminating measurement/manipulation and identification assumptions. Inter-rater agreement validates labeling consistency, not construct validity.

Keep extraction reliability, literature applicability, local empirical support, generalization and causal identification as distinct assessed dimensions. Never conflate a model score, similarity, p-value and evidence grade into a free-form “confidence: 95%”.

## 5. Multimodal creative events and analytical features

Keep current observations/timeline as source lanes. R3 adds:

- `CreativeTechnique`: observable definition, inclusion/exclusion, content/modality eligibility, coverage requirement and annotated examples/counterexamples.
- `CreativeEvent`: technique revision, content revision, typed anchors, evidence bundle, modalities, extraction/review state and coverage.
- `CueBundle`: ordered evidence membership across visual, audio, speech, subtitles, OCR, caption and editing observations; retain discontinuities.
- `EventRelation`: before/overlap/simultaneous-with-tolerance or separately annotated semantic relation, evidence, method and qualification.
- `FeatureRecipe` and `FeatureValue`: versioned operation, inputs, aggregation/transform, typed value/unit or missing reason, subject version, full evidence lineage and availability.

Events may have point, interval, spatial or multiple discontinuous anchors. Store nominal bounds and bounded uncertainty where justified. Temporal relation “verified” means it holds across all feasible bounds; otherwise use possible/proposed. Co-occurring sound and visual events do not automatically mean the sound reinforces the reveal. Record annotation protocols and outcome-access/blinding history; outcome-aware exploratory labels cannot masquerade as outcome-blind independent confirmation.

For cooking, “prepared final dish appears in the opening window before substantive preparation instruction” is an observable technique, not a psychological conclusion. Freeze the opening window and visibility/coverage rubric. A boundary-crossing ambiguous shot stays unknown/reviewable. Request bounded denser frames if needed. Retain absence/unknown distinctions and missing modalities.

A versioned recipe can encode “result-first + spoken utility promise + overlapping SFX” with explicit time rules. It cannot replace warm color with brightness or sensory appeal with loudness. Publishing context, captions, hashtags and post-level niche labels are versioned inputs; hashtags are not ground-truth niche membership.

All analytics joins are on exact subject/definition revisions, source scope and declared observation windows, not ad hoc text similarity. Later annotations of immutable content can support disclosed retrospective analysis. They are not automatically historically available forecasting inputs.

## 6. Audience response and behavioral outcomes

### 6.1 Audience response: R4

Retain current minimized comments. Add collection manifests before inferring prevalence:

- Source/permission, requested dates, collection time, ordering/filter/pagination/limit, supplied/eligible/known-total counts, sampling/completeness, lag and deleted/moderated coverage.
- Span-backed reaction annotations for expressed intention, question, objection and other reviewed labels; language, negation/irony/ambiguity, rubric and annotation provenance.
- Versioned clusters with explicit comment/annotation membership, representative **and contradictory** evidence, duplicate policy and summary lineage.
- Qualified reaction→content links distinguishing quoted/timestamp-explicit reference from inferred semantic link, with candidate targets, method, review and uncertainty.

Comment publication time is never playback time. A textual “0:02” reference is explicit but can still be inaccurate; preserve that qualification. “I will cook this” is an expressed intention, not cooking, purchase or verified conversion. A top-ranked sample cannot estimate all viewers' reaction prevalence. Multiple cluster memberships are not additional independent viewers.

Audience sources and quoted text are untrusted data, never instructions to the host. Avoid retaining author identities unnecessarily. R4 includes authorized retention/redaction across annotations/summaries/artifacts; R6 extends it to all derived stores.

The implemented path imports human review and versioned curated memberships; optional
literal-English proposals are explicitly requested and never become reviewed results.
It does not automatically infer semantic clusters or train an audience classifier.
See [implementation decisions](#20-audience-implementation-decisions).

### 6.2 Behavioral metrics: R5

Keep scalar v1 definitions/snapshots immutable. Add revisioned semantic metadata, specialized series and account outcomes rather than forcing every outcome through a generic nonnegative number.

| Contract | Essential semantics |
|---|---|
| `BehavioralMetricDefinition` | Platform/source version, subject level, unit/domain, numerator/denominator definition, aggregation, eligible cohort, exposure maturity and attribution meaning. Similar names across platforms are not automatically equivalent. |
| `MetricMeasurement` | World/reporting window, collection time, earliest known availability, source freshness/lag, snapshot semantics, population/cohort and missingness. Collection time alone does not establish precise post age. |
| `MetricSeries` / `MetricBin` | Series/subject/definition/cohort revision; coordinate kind and granularity; bin boundaries; value/count/denominator availability; source and exact bin evidence. Relative playback coordinates remain relative until an explicit mapping is justified. |
| Completion / watch / retention | Define started-view denominator, completion threshold, eligible plays/viewers, looping/replay behavior and aggregation. Watch ratios may exceed one where the source definition allows; not all curves are survival distributions. |
| Conversion attribution | Outcome definition, attribution type/window/model, source authority and unit; distinguish platform-reported attribution, observational association and experimentally identified effect. Unknown attribution is valid. |
| Account outcomes | Signed changes use a new typed projection such as `signed_metric_changes`, with exact source snapshots and intervals. Preserve old nonnegative CHECK constraints. No nearest-post assignment of account growth. |

Never use 100 aggregate retention bins as 100 independent viewers. Unknown denominators permit source-qualified descriptive curves, not fabricated binomial precision. Retention dips can be temporally near an event without proving it caused exits; sparse bins do not support frame-level claims. Overlapping observation windows and repeated snapshots are dependent, not independent posts.

R5 leaves unavailable private analytics unavailable. A dataset with only public scalar metadata still supports constrained descriptive work and hypotheses. Creator-owned retention, completion and conversions enrich the same contracts when authorized.

## 7. Comparison design and bounded discovery

[Statistical design](docs/statistical-design.md) is normative for new analysis-specification versions. Core requirements:

1. Define the estimand, unit, population, outcome/exposure window, comparison design, covariates and permissible claims **before** fitting.
2. Separate retrospective cohort normalization from historically prior, knowledge-cutoff baselines. Persist the full reference manifest; adding future posts cannot change a frozen historical baseline.
3. Separate within-creator matching from cross-creator context matching. Cross-creator matching needs overlap, balanced observed context, maturity/cohort comparability and confounding disclosures—not merely removal of the equality constraint.
4. Audit creator/niche design rank. Creator fixed effects absorb creator-constant niche effects. Fit only identifiable within effects/interactions; use explicitly justified between/hierarchical designs for different questions.
5. Produce feature availability and source lineage in the real materializer. Optional audit fields that production never writes cannot prevent leakage.
6. Validate the actual transformations, interactions, estimator/link and prediction target. A main-effect Ridge surrogate cannot validate an interaction discovered by another model.
7. Split by relevant time, creator and duplicate-content groups; test niche transfer when claimed. Preprocessing, feature selection and tuning stay inside training folds.
8. Count independent creator/content units, dependence and uncertainty honestly. Minimum-sample thresholds are engineering gates, not evidence of power or external validity.

R2 introduces the minimal specified-analysis family/attempt and holdout-use records needed for honest confirmation. R7/R8 preserve that history during evaluation and reevaluation; R9 extends it to broader adaptive candidate searches. Error accounting cannot wait until discovery is automated.

R2 repairs specified comparisons using existing primitives. R9 introduces bounded discovery over semantic features: a small registered candidate grammar, maximum interaction order, a bounded spline/nonlinear basis and niche moderation where identifiable. Initially prefer interpretable main effects/prespecified pairwise interactions and limited spline terms over large neural causal models or unrestricted combinatorial mining.

A search manifest freezes candidates, outcomes/windows, all attempts including failures/nulls, data partition IDs, tuning budget, test family and stopping policy. Family-level FDR correction does not cover unlimited reruns. Freeze a discovery round; confirmation uses independent reserved/new data with a holdout-consumption ledger. No optional-stopping guarantee is claimed without an explicitly justified sequential design.

Retrieve failed examples from the eligible canonical population using frozen exposure/outcome definitions. Semantic top-k retrieval assists inspection but cannot select only successful cases for estimation. Report contradictory examples, selection bias, missing confounders, overlap failure and failed niche transfer rather than hiding them behind an aggregate score.

## 8. Persistent research lifecycle

### 8.1 Canonical research objects

R1 introduces `ResearchQuestion` and a minimal versioned `HypothesisSpec`: statement, population, intended claim level and data needs. R7 adds:

- Small curated `ResearchSource`/`StudyFinding` corpus with bibliographic identity, study design, population, manipulation/measure, outcome/effect, limitations, permissible excerpts and applicability review.
- `PsychologicalConstruct` and `Operationalization` definitions separating construct, measurement and creative manipulation.
- Rival `Prediction` records with discriminating contrasts, confounders and falsification/scope conditions.
- Immutable `ResearchAssessment`, `Finding`, manifests, evidence roles and dependency links.

Store a literature source once by verified bibliographic identity; multiple excerpts or citations are not independent studies. No embedding similarity or generated citation makes a paper applicable. Unreviewed literature may seed a draft, not support a claimed established mechanism. Begin with a few reviewed mechanisms, not a taxonomy covering all psychology.

### 8.2 Register → evaluate → revise

`ResearchService.register` freezes specifications. `evaluate` resolves eligible evidence, materializes a frozen population, runs the declared analysis, preserves every result, checks claim rules and commits an immutable assessment with index work. Support dispositions are `insufficient_data`, `inconclusive`, `supported_in_scope`, `weakened`, `contradicted_in_scope`, and `rejected_in_scope`, as defined in the research contracts. Mixed evidence is recorded in the rubric, not a claim of universal confirmation.

Each assessment has hypothesis/spec revision, prior-assessment reference when relevant, scope/population-selection manifest, reused/new evidence units, analysis/model versions, supporting/contradicting/non-discriminating links, alternatives, uncertainty/limitations and reasoned disposition.

R8 detects changed dependencies **and newly eligible population rows** using saved selection manifests. Corrections, new outcomes, new failed examples, annotation changes, retractions or source withdrawal mark affected current projections stale. Imports do not silently rerun expensive research or manufacture independent confirmation.

Explicit reevaluation freezes a new manifest, accounts for reused versus new units and family/holdout history, and writes a new assessment. Historical assessments never mutate. A machine-readable delta states strengthened/weakened/unchanged support, changed scope/effect/uncertainty, reasons and remaining rivals. A changed hypothesis specification is a new specification, not a covert revision to the old prediction.

R7 can recommend an experiment brief. R10 adds registered design/assignment/outcome and deviation records, ethically authorized execution data, analysis and updated assessments. It does not automatically control creator accounts or post content. Experiment analysis distinguishes intent-to-treat creative effects, compliance/exposure issues and separately justified mechanism mediation.

Keep the shared research envelope domain-neutral; psychological operationalizations are a subtype, not mandatory invented constructs for platform, packaging or profile questions. R7 records the four-domain alternative/missing-context checklist without implementing C1. Later C1 official-document statements remain distinct from academic `StudyFinding` records, local empirical findings and identified experiments. R8 tracks their applicable revisions without treating a help-page edit as proof of an algorithm change.

## 9. Storage architecture and cross-store consistency

### 9.1 SQLite authority and artifacts

Keep existing tables, WAL configuration, FK enforcement, UoW transactions, schema-version checks and data-directory locking. No graph pickle or Qdrant payload is canonical. Store large media/raw permitted imports/model outputs as hash-addressed artifacts; rows own manifests, relationships and versions.

Add normalized projections only at first use: R2 feature values, analysis/family manifests and holdout use; R3 events/anchors/relations; R4 collection memberships/reactions/links; R5 metric series/bins; R6 document/index/outbox/graph projections; R7/R8 assessment dependencies. Index subject/revision, source/availability, media/time/technique, cohort/window, hypothesis and reverse-dependency keys according to actual queries.

### 9.2 Semantic documents and Qdrant collections: R6

The original five logical document families remain useful, but are versioned, permission-aware representations:

| Logical collection family | Indexed document | Canonical links |
|---|---|---|
| `content_segments` | Bounded transcript/OCR/caption/event-bundle descriptions with modality/coverage | Media/post/event/track revisions and exact locators |
| `psychological_patterns` | Reviewed pattern/construct/hypothesis specifications and qualified descriptions | Pattern/hypothesis/assessment revisions; no unsupported generic trigger labels |
| `statistical_findings` | Scoped effects, uncertainty, diagnostics, null/contrary results | Analysis/finding/assessment revisions and population/spec |
| `audience_reactions` | Permitted reaction excerpts and versioned cluster summaries | Collection/comment/annotation/cluster revisions |
| `research_knowledge` | Reviewed study findings, limitations and permissible excerpts | Source/study/construct/operationalization revisions |
| `behavioral_observations` | Source-defined scalar metrics, series/bins and account outcomes | Exact metric/definition/cohort/window citations; not statistical or causal findings |

Physical names include an immutable embedding-space identifier, e.g. family plus space hash. No incompatible embeddings are mixed. Collections are created only when a real producer needs them; capability status distinguishes absent, empty, stale and ready. Similarity scores are retrieval scores, not truth/confidence.

An `EmbeddingSpace` freezes model/revision/license, dimensions, distance, normalization, query/document prefixes, tokenization/chunk policy and language scope. Start with one verified prepared multilingual text model; evaluate the actual corpus before choosing dimensions and quality targets. Multilingual E5 is a candidate, not an installed dependency or validated winner. Text descriptions cannot substitute for unobserved image content; optional image embeddings use a separate space and evaluation.

| SQLite index contract | Keys/state |
|---|---|
| `embedding_spaces` | Immutable space ID and complete embedding/representation specification. |
| `vector_documents` | Stable logical document ID, owner identity, representation kind/chunk key, desired revision/generation and lifecycle. |
| `vector_document_revisions` | Immutable owner entity revision, content hash, representation schema/chunk policy, bounded text/artifact locator, producer/provenance and permission state. |
| `vector_document_evidence` | Document revision ↔ exact evidence revisions with role. |
| `vector_index_entries` | PK document/space; deterministic point UUID from document+space; desired/indexed revision, generation/hash, state. |
| `vector_outbox` | Document/space/operation/generation, expected revision/hash, attempt/lease/status; unique document/space/generation. |

Qdrant payloads carry document/revision/space IDs, generation/hash, entity refs, evidence refs, modality/language, claim level, scope, eligibility and filterable subject/niche/time metadata. Large source text remains canonical in SQLite/artifacts. Each point has the space's fixed dense-vector size/distance; payload indexes are added for measured filters, not every field.

Write protocol:

1. Commit canonical revisions and minimal desired-projection change records in one SQLite transaction. Once typed bindings/dependencies are complete, reconciliation atomically publishes documents, exact evidence bindings, FTS/graph rows, vector desires/outbox and acknowledges those changes. The R6 decision below explains this two-stage producer boundary.
2. Outside the transaction, a lock-owning worker verifies source eligibility/current generation, loads the prepared model, embeds and upserts/deletes the deterministic point.
3. Acknowledge with compare-and-swap on expected revision/generation. Old work cannot acknowledge or overwrite a newer desired state; process jobs serially per document/space and skip superseded work.
4. On crash, replay idempotently. Query results hydrate through SQLite and reject stale/withdrawn/wrong-revision points even before repair.
5. Tombstones/deletion generations dominate pending work. A full rebuild starts only from eligible canonical document revisions.

There is no distributed transaction claim. An index may lag; the API reports index revision and partial coverage. SQL/FTS and graph retrieval remain available without a model; learned semantic search is unavailable rather than supplied with hash/fake vectors.

### 9.3 SQLite-backed NetworkX projection: R6

Use `graph_nodes` keyed by canonical entity revision, and `graph_edges` keyed by stable canonical relation/finding revision plus projection version. Edges store source/target revision FKs, registered relation type, scope, evidence/assessment link, qualification, claim level, temporal validity and generation. Registry rules constrain endpoint kinds and require eligible supporting lineage; graph storage does not duplicate an independent truth system.

Project account/post/media/technique/event, reaction/cluster, metric/outcome, study/construct, pattern/hypothesis/assessment/finding and experiment entities when useful. Fine-grained frame/span nodes can be SQL-hydrated rather than materializing millions of nodes by default.

Reify multivariable `Pattern` and qualified `Finding` nodes: connect their component recipes, temporal rules, tested scope, outcome, analysis and assessment. Do not reduce an interaction to several independent “technique causes performance” edges. Observed-with, hypothesized-mechanism, associated-with and experimentally-supported-effect are distinct relationships.

NetworkX is a bounded in-memory `MultiDiGraph` view, not the persistence layer. Default traversal is a small declared neighborhood, e.g. depth two / 2,000 nodes with explicit truncation; bulk graph materialization is opt-in and budgeted. Current/as-of views select eligible revisions without deleting historical qualifications. Unsupported graph queries return missing/partial, not invented transitive causal chains.

### 9.4 Retrieval, privacy and repair

Hybrid retrieval combines SQL scope/eligibility filters, FTS and optional semantic similarity; bounded graph expansion supplies relations and explicit counterevidence. Deduplicate chunks/member evidence before counting independent units. Comparison populations come from SQL manifests, never from a top-k nearest-neighbor set.

Permission withdrawal first makes canonical sources and dependents ineligible for new claims, then purges/redacts required excerpts, artifacts, summaries, FTS, vectors and graph projections. Reports have current eligibility views; frozen bytes remain historical only where retention is permitted. If lawful erasure requires deleting report/source bytes, retain only allowed tombstone/audit metadata and state that exact reproduction is no longer possible. Backups follow a declared retention policy.

Storage verification checks dangling refs, hashes, projection generations, missing artifacts and permission eligibility. Rebuildable indices cannot restore erased source content or bypass withdrawal. Backup restoration must reconcile later withdrawal/erasure obligations before normal use; unknown obligations require restricted recovery. See [migration strategy](docs/migration-strategy.md) for backup, interruption and compatibility tests.

## 10. Agent skill, commands and reports

Keep current CLI commands and result envelopes. R1's evidence/registration/report and backup/restore commands are documented in [R1 operations](docs/research-foundation.md). Delivered surfaces below remain bounded by their individual operations guides; the U2 command inventory is checked against the actual CLI.

| Workflow | Engine surface / milestone |
|---|---|
| Current basic media/account workflow | Existing `import local\|csv\|json`, `analyze video\|account`, `timeline show`, `models status\|prepare`, `compare posts\|accounts\|reproduce`, `report generate`, `doctor`, `storage status\|verify` |
| Resolve/register/report | `evidence resolve\|cite-comment\|cite-metric\|withdraw`, `research register\|show\|report`, `storage backup\|restore` — implemented R1 |
| Corrected comparisons | Existing compare commands with explicit versioned design/specification — R2 |
| Events / audience / behavior | Validated imported or reviewed annotation/series specifications and focused CLI adapters — R3–R5 |
| Retrieve / maintain memory | `query`, `graph neighbors\|path`, bounded `storage reconcile\|reindex` adapters — R6 |
| Evaluate / revise | `research evaluate\|reevaluate\|history` — R7/R8 |
| Discover / experiment | Explicit bounded discovery and experiment register/outcome adapters — R9/R10 |
| Production / growth context | Reviewed craft/context/platform/profile imports and qualified summaries — delivered C1 |
| Photos / skill | Delivered `analyze image\|carousel`; U2 `capabilities`, `skill export\|schema`, report `--output`; live host behavior remains separately unverified |

The delivered [portable skill](skills/socialdna/SKILL.md) routes to focused core/research/interface/setup references. Host differences are discovery paths and invocation guidance only. Validate actual live behavior separately: format compatibility, directory-layout tests and installed CLI execution are not proof of identical agent behavior.

Reports distinguish source-backed observations, mechanism hypotheses/rivals, scoped associations and permitted causal findings. Show missing modalities/data, collection coverage, comparison population, definitions/windows, effect uncertainty, counterexamples and claim limitations. A single-video report remains short and useful; research detail is linked/expandable rather than mandatory in every report.

R10 recommendations are structured, evidence-qualified proposals tied to uncertainty, not promises of increased reach or copied creator scripts. Any posting, external messaging, account mutation, remote upload or experiment execution needs separately scoped authority; U2 grants none of those actions.

## 11. Reference research flow

The full [cooking use case](docs/research-use-case.md) maps all twelve requested steps to schemas, services, statistical methods and permissions. In brief:

Authorized media → multimodal observations → reviewed result-first event → rival operationalizations + reviewed literature → sampled audience reactions → semantically valid metrics → within/cross-creator comparisons including failures → frozen qualified assessment → discriminating experiment brief → new outcomes and explicit reassessment.

Public metadata can identify permitted captions/tags/basic counts and candidate posts, subject to source access. It cannot substitute for authorized media, complete comments, retention, conversion attribution or viewer-level measures. Owned behavioral analytics are an optional evidence tier; the result with public-only data may appropriately remain inconclusive.

## 12. Limits, resource costs and optional scale

| Constraint | Design response / unresolved limit |
|---|---|
| Public URLs do not grant usable media or private analytics | Prefer authorized local media and exports; source adapters record permission, quota, freshness, coverage and denied fields. No credential bypass or scraping entitlement. |
| Platform definitions, authorization and quotas change | Version adapter capability/metric catalogs and validate current official documentation at implementation; no universal connector guarantee. |
| API counts/comments may be delayed or selectively returned | Preserve collection frames and source lag; do not assign false precise post-age or representative coverage. |
| Expensive video/model work | Hash caching, deterministic first pass, bounded adaptive sampling, batch worker reuse, optional prepared CPU/GPU models; no full-video VLM context by default. |
| ASR/OCR/VLM error and language/domain transfer | Keep source lanes, coverage and review state; curated gold fixtures and held-out annotation evaluations; empirical quality remains unestablished. |
| Low independent creator/sample counts | Descriptive/case-study mode, insufficient-power outcomes, explicit uncertainty; no universal minimum that makes confounding disappear. |
| Combinatorial patterns and repeated tests | Frozen bounded family, all-attempt ledger, independent confirmation, no unlimited adaptive significance mining. |
| Local vector/graph memory and single writer | Measure point count/dimension, embedding/graph RSS, lock wait and query/index latency. Bound documents/chunks and subgraphs; batch index work. |
| Storage and deletion/reproducibility conflict | Explicit retention policy and withdrawal propagation; reproducibility claims degrade honestly after erasure. |

API specifics must be confirmed per adapter. YouTube Analytics is owner-authorized; its normalized audience-retention positions and replay-aware metrics need source semantics. See the official [channel reports](https://developers.google.com/youtube/analytics/channel_reports), [dimensions](https://developers.google.com/youtube/analytics/dimensions#Audience_Retention) and [metrics](https://developers.google.com/youtube/analytics/metrics#Audience_retention_metrics). Instagram access depends on supported account/authentication/permissions; do not promise private insights for arbitrary public accounts. See [Meta's API documentation collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api). TikTok's Research API eligibility is restricted and archive freshness can differ from live counts; it is not a default commercial connector. See the [official FAQ](https://developers.tiktok.com/docs/en/research-api-faq).

Do not declare a universal local capacity ceiling from a library warning. Benchmark representative workloads first. Only demonstrated needs justify optional server-mode Qdrant, process/service APIs or a different database in a separately approved design. A future accelerator must preserve canonical contracts and exportability; no such infrastructure is required by R1–R10/U1–U2.

## 13. Migration and delivery strategy

The [migration strategy](docs/migration-strategy.md) preserves existing tables/IDs, frozen migration scripts and report semantics. Add a revision registry alongside legacy evidence, backfill deterministically and verify it before enabling new research. Do not reinterpret an old comparison as an as-of analysis; corrected designs use a new spec/method version and new result identity.

Delivery follows [PLAN.md](PLAN.md): R1 universal evidence/minimal registration; R2 correctness; R3 events; R4 reactions; R5 behavioral metrics; R6 memory; R7 first full mechanism investigation; R8 reevaluation; R9 bounded broader discovery; R10 experiments. U1/U2 preserve image and portable-skill usability. R4/R5 are deliberately separated; memory follows working canonical producers rather than encoding an inadequate evidence model.

After R7, C1 supplies four independently tested evidence extensions for professional production, publishing/packaging, platform/surface research and profiles/funnels. Corresponding R9/R10 branches require only their delivered inputs; initial R7/R8 and existing cooking discovery do not wait for all C1 slices. U2 exposes a per-domain capability manifest, not a promise that all future workflows exist.

R1's implemented proof is an upgraded old media citation plus real imported comment and metric citations, minimal question/spec registration, restart resolution and withdrawal-aware reporting. R2 adds the separately versioned correctness path described in §18; it does not reinterpret the R1/legacy delivery.

## 14. Architectural support for the six audited capabilities

“Supported” means a coherent contract, flow, delivery owner and acceptance gate now exist. It does **not** mean working software or empirical validity.

| Audited capability | Revised architectural support | Delivery / required evidence of success |
|---|---|---|
| Deep psychological mechanism discovery | **Supported as falsifiable mechanism investigation**, not automatic causal discovery: constructs, reviewed sources, operationalizations, rivals and discriminating predictions | R3/R7/R10; annotated content validity, reviewed applicability and appropriately identified empirical tests. Observational data alone cannot prove a mechanism. |
| Content → audience responses → performance | **Supported with qualified, versioned links**, selection coverage and outcome/denominator semantics | R1/R3–R5/R7; real source resolution, annotation validity, collection coverage and authorized outcome measurements. |
| Cross-creator and cross-niche intelligence | **Supported with explicit separate designs**, as-of context, identifiability and transfer validation | R2/R9; overlap/balance, sufficient independent creators, actual model validation and held-out-niche tests. |
| Multivariable creative-pattern discovery | **Supported within registered bounds**, temporal/conditional recipes, nonlinear candidates, all-attempt accounting and independent confirmation | R3/R9; recovery and false-discovery controls on synthetic fixtures plus independent real-data replication. |
| Persistent psychological/performance intelligence | **Supported by canonical revisions and derived memory**, not embeddings alone | R1/R6/R7; cross-process persistence, crash repair, qualified graph/retrieval and real relevance evaluation. |
| Learning and revising conclusions | **Supported through immutable assessments, dependencies, delta evidence and explicit weakening/rejection** | R7/R8/R10; a supported-in-scope result must be weakenable by new contrary data without rewriting history. |

All six remain incompletely implemented today, and none is established as a scientifically validated intelligence capability. Unresolved empirical work includes technique/construct validity, reviewed corpus coverage, comment-link accuracy, adequate independent datasets, causal identification and external validity. These are research obligations, not problems solved by adding schema fields.

## 15. Major decisions and tradeoffs

| Decision | Why / cost |
|---|---|
| Add universal revision/evidence substrate; preserve legacy media subtype | Resolves non-media citations and historical identity without a destructive rewrite; adds resolver and typed-binding discipline. |
| Versioned documents plus first-use relational projections | Avoids dozens of unused tables and opaque JSON-only analytics; requires strict schemas and incremental projection ownership. |
| Explicit design specs and actual-pipeline validation | Fixes superficially successful but invalid comparisons; some requested analyses must return insufficient/unsupported. |
| Small reviewed corpus and human annotations first | Enables a real psychology vertical slice without pretending model labels are mechanisms; limits initial breadth and adds review work. |
| SQL authority + derived Qdrant/NetworkX | Keeps deployment local and rebuildable; accepts index lag, local lock limits and bounded graph views. |
| Immutable assessments with eligibility projections | Preserves history and enables retraction; privacy erasure may legitimately prevent exact old reproduction. |
| Separate simple analysis from research | Preserves creator usability and predictable costs; requires explicit capability/mode reporting rather than one magical “analyze everything” command. |

## 16. Primary references and verification boundaries

Official references inform contracts, not promises that connectors/models are already implemented. API capability assumptions must be rechecked during adapter delivery.

- [SQLite foreign-key behavior](https://sqlite.org/foreignkeys.html): enforce registry/binding integrity on each connection.
- [Qdrant Local implementation](https://github.com/qdrant/qdrant-client/blob/master/qdrant_client/local/qdrant_local.py): local lifecycle/locking and operational constraints; verify against the pinned installed version.
- [scikit-learn cross-validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html): group/time-aware validation; SocialDNA additionally requires source/feature availability and actual-estimator checks.
- [Agent Skills specification](https://agentskills.io/specification): portable instruction format; actual host behavior still requires tests.
- [YouTube channel analytics reports](https://developers.google.com/youtube/analytics/channel_reports), [retention dimensions](https://developers.google.com/youtube/analytics/dimensions#Audience_Retention) and [retention metrics](https://developers.google.com/youtube/analytics/metrics#Audience_retention_metrics): owner authority, relative coordinates and metric definitions.
- [Meta's official Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api): supported account/authentication paths; no claim that every metric is available to every caller.
- [TikTok Research API FAQ](https://developers.tiktok.com/docs/en/research-api-faq): eligibility and data-freshness constraints.
- [Kang et al., 2009](https://www.cmu.edu/dietrich/sds/docs/loewenstein/WickCandleLearning.pdf): an example of operationalized curiosity research, not direct proof about cooking-video openings.
- [Webb and Sheeran, 2006](https://pubmed.ncbi.nlm.nih.gov/16536643/): intention and subsequent behavior are not interchangeable.

## 17. R1 implementation decisions and boundaries

R1 implements the common revision/citation foundation without R2 statistical repairs
or R7 mechanism evaluation. [The operational guide](docs/research-foundation.md)
documents actual commands, payloads and recovery steps.

| Implemented surface | Current module/interface |
|---|---|
| Canonical captured revisions and typed bindings | `storage/evidence_repository.py`: `EvidenceRepository.capture`, `media_evidence`, `comment_evidence`, `metric_evidence`; `backfill_evidence` |
| Citation/eligibility validation | `application/evidence_service.py`: `EvidenceResolver.resolve`, base `ClaimValidator.validate`, `withdraw` |
| Draft registration and citation reports | `application/research_service.py`: `register_research`, `show_research`, `generate_research_report`; no evaluator |
| Backup/recovery | `storage/backup.py`: canonical SQLite/artifact backup, separate-directory restore, lineage check and withdrawal replay |
| No-write validation | `storage/readonly.py`: immutable checkpoint reads with WAL/concurrent-change refusal |
| CLI | `cli/research_commands.py`: evidence, research and backup/restore adapters; normal result envelopes |

Implementation choices clarify the earlier conceptual interfaces:

- A single normalized `legacy_entity_bindings` table provides real nullable subtype
  FKs with an exactly-one constraint; the resolver additionally validates kind,
  identity, hash, ownership and source. Captured payloads freeze mutable metadata.
- Draft questions/hypotheses and citation reports are versioned entity documents.
  Reports use artifact owner links and scoped `evidence_links`, rather than fake
  `analysis_runs` or media timestamps. Functional application-service APIs follow
  the existing engine style; the proposed `ResearchService` evaluation interface
  remains future work.
- Media producers keep the existing `TaskContext`; the task transaction registers
  emitted evidence. Imports capture actual account/post/comment/definition/snapshot
  rows. A tabular media URI is not a decoded asset and is not registered as one.
- Original media evidence rows and new revision/binding/link histories receive
  immutable update/delete guards. Corrections create new revisions. Metric URI
  aliases bind exact snapshot revisions and do not follow edited post metadata.
- The terminal withdrawal journal deliberately permits target identities absent
  from an older restored checkpoint. Normal withdrawal validates target existence;
  recovery can retain detached privacy tombstones. These are not evidence claims,
  and FK-constrained canonical citations remain intact. This prevents reimports from
  reviving a post-checkpoint withdrawal.
- Backups use SQLite's backup API and verified managed artifacts; external originals,
  model weights/runtimes and rebuildable vectors are explicit omissions. Restores
  require a new directory. Same-lineage journal reconciliation or restricted
  recovery prevents an older checkpoint from silently reinstating eligibility.
- `mode=ro` alone can create SQLite WAL/SHM side files. No-write dry runs therefore
  read only quiescent checkpoints using immutable reads and reject active WAL/file
  changes. Actual writes always revalidate under the established writer lock.
- R1 withdraws new use and withholds current locator text/values, including derived
  model dependencies. It is **not full byte erasure**. Permitted historical bytes
  stay unchanged; complete audience/raw-import/report redaction remains R4, extended
  to future indices in R6. An erasure obligation cannot be discharged by withdrawal.
- Legacy merged post/account metadata has no per-field source lineage. New analyses
  fail closed when contributing source history is withdrawn; R2 can refine this
  conservatism with explicit feature lineage. Other legacy statistical limitations
  remain visible and unchanged.

## 18. Statistical correctness implementation decisions

This is a bounded, explicit version-2 implementation of the approved statistical
contract, not an alternative engine or an implementation of R3/R9. See
[operations and limits](docs/versioned-analytics.md).

| Decision | Implementation / justification |
|---|---|
| Explicit method and spec dispatch | `CorrectedPerformanceSpec` requires design/estimand, cutoffs, timing and family declarations. `performance-1` retains old algorithms; `performance-2` uses corrected helpers. Historical `0.0.4`/`0.0.5` method-1 reports can recompute with unchanged numerical libraries; source-history comparison confirmed those algorithms were identical. Recomputed results must match the frozen hash before saving. Unknown method/engine versions fail closed. |
| Full creator history, not selected groups | As-of SQL joins use captured revisions and measurements known by the cutoff; baseline selection separately enforces prior publication and publication/evaluation knowledge policy. Exact reference rows/IDs/exclusions are frozen and hashed. No semantic selection or fallback pool is used. |
| One actual model pipeline | `analytics/designs.py` owns raw interactions, training-only creator centering/scaling, identifiable context/fixed effects and selected OLS/Poisson family/target transform/covariance. Final fits and validation call the same fitter. A creator-constant niche is explicitly absorbed, not estimated alongside creator intercepts. |
| Withhold unsupported estimands | Cross-creator matching really permits distinct creators but reports descriptive effects and measured support only. Unknown confounding and shared-creator dependence preclude fabricated pair-independent uncertainty. Between/niche effects and unseen fixed-effect intercept prediction are unsupported; there is no hidden Ridge substitute or automatic hierarchical-model selection. |
| Primitive recipe lineage first | `analytics/features.py` materializes actual supplying revisions, source/evidence inputs, recipe, clocks and missingness. The first local recipe registration conservatively bounds deployability; late export capture is not publication-time knowledge. Deterministic retrospective annotation is distinct from forecasting. Semantic/categorical recipes remain R3. |
| Historical media associations | `post_media_versions` preserves decoded associations and NULL invalidations after changed supplied URIs; old cutoffs keep their old association. Existing unversioned link semantics are unchanged. Captured post revisions include topic context, including tag-only updates. |
| Exact duplicates and split intent | SHA groups purge duplicates across and within chronological/creator/joint splits. Availability purges use actual imported/observed clocks. Unknown near-duplicate coverage remains explicit. Joint requests are one joint split, not two scores presented as joint evidence. |
| Minimal durable test accounting | A fixed-family manifest and pre-fit attempt record precede computation. Final null/failed/refused outcomes persist; reserved test use is durable before scoring, including on interruption. `holdout_members` prevents renaming or overlapping posts/media from resetting a holdout. Reproduction is marked and is not independent confirmation. R9 extends this bounded ledger, rather than adding a competing one. |
| Cohesive persistence service | `application/statistical_service.py` owns corrected report/ledger/citation transactions while existing performance service owns population selection and legacy dispatch. Numeric logic remains in the shared analytics package; CLI adapters contain no statistics. |
| First-use relational projections | New feature, reference, attempt and holdout tables have working writers/readers. Existing cohort/statistical result tables are reused. Statistical analysis entities and exact term/diagnostic locators have real FKs and universal resolver validation with transitive withdrawal. No dummy media/timestamps are introduced. |
| Bounded local work | 500 selected targets and 5000 captured historical posts bound reference materialization. Creator grouping avoids repeatedly scanning unrelated creators. No dependency, server, embedding job or distributed infrastructure is added. |

The evidence locator CHECK must accept a new statistical subtype without changing
released `0005_evidence`. `0006_designs` performs a data-preserving parent-table
rebuild using [SQLite's documented procedure](https://www.sqlite.org/lang_altertable.html#otheralter):
foreign-key enforcement is disabled **before** BEGIN on a dedicated unpooled
migration connection, all schema/data changes and checksum updates are atomic,
`foreign_key_check` runs before commit, and enforcement is restored afterwards.
The application verifies a pre-upgrade backup first. Tests inject failure after
the rebuild on a populated old database and assert exact rollback, binding/ID
preservation and enforcement restoration. Populated-history downgrade is refused
in favor of verified separate-directory restore. Released migrations 0001–0005
are never edited.

These decisions deliberately retain scientific limits: post-level niche labels,
audience/paid/traffic covariates, near-duplicate discovery, new-creator marginal
prediction, broader nonlinear search, independent niche confirmation and causal
identification are not manufactured from the current exports. Missing source
freshness can support a labeled collection-proxy summary, not strict model evidence.

## 19. Creative-event implementation decisions

R3 is implemented in `0.0.7` / `0007_creative`; exact commands and boundaries are
documented in [creative analysis operations](docs/creative-analysis.md). It introduces
observable creative annotations and reusable measurements, not a second reasoning
engine, psychological ontology or general pattern search.

| Decision | Implementation and justification |
|---|---|
| Reviewed import is the required offline semantic path | Strict annotation documents refer to actual registered media hashes. Humans can certify review and scoped coverage; imported model/rule proposals cannot self-adjudicate. Author, procedure, provider identity, outcome access and freeze assertions remain visible. No new VLM/runtime is needed to finish this vertical slice. |
| Small opt-in profile, not implicit semantic classification | `cooking-opening-v1` proposes literal wording from existing ASR/subtitle/OCR/caption evidence and requests bounded actual-PTS frames. It does not recognize dishes, infer emotion from sound energy, or label warmth from brightness. Prepared optional enrichment remains the existing separate pipeline. |
| Reuse the universal revision registry | Technique definitions and annotation-set/event/coverage/relation documents use existing immutable entity identities/revisions. Query projections have real media, entity, run/task and evidence FKs; no generic disconnected JSON catalog or dummy post is introduced. |
| Coverage is independent of positive labels | `creative_coverages` and set membership freeze modality/technique/window/sampling assertions separately. Sparse non-detection stays unknown. Only explicit human exhaustive review can support an opening absence; untimed captions cannot inherit video-clock absence claims. |
| Event revisions are independent of whole imports | Stable media/set/event keys preserve unchanged event revisions and their original authorized inputs/protocol/source. Annotation sets freeze ordered memberships. A changed unrelated color label does not rewrite an existing dish cue or invalidate its result-first measurement. Identical imports are idempotent, not implicit re-adjudication. |
| Anchor uncertainty is first-class | `creative_event_anchors` preserves ordered discontinuous interval/point/spatial/untimed anchors, feasible bounds and optional nominal coordinates. All clocks are original presentation ms. No offsets are manufactured for post captions/hashtags. |
| Temporal evidence is not semantic reinforcement | Versioned interval algebra produces precedes, overlap and onset-synchrony edges. Verified requires all feasible bounds (conservatively all anchor pairs for discontinuities); possible retains ambiguity. A reversed precedes edge represents follows. No causal-looking reinforcement relation is inferred. |
| Inputs remain literal and independently resolvable | New `creative_event`, `creative_coverage` and `post_text` evidence locators share the existing resolver. Direct-media bindings cite actual registered whole-source spans when a human supplies no narrower timed inputs. Caption/hashtag bindings cite exact captured Unicode text/normalized inventory; supplied narrower observed cues must support their declared modality and timing. |
| Pinned feature grammar rather than broad discovery | Eleven recipes cover presence, first-cue order, modality-specific promises, reviewed color, strict conjunction, reviewed onset synchrony and captured hashtag counts. Definitions include exact technique revisions, temporal rule, window, unit, role and missingness. Same-version definition/recipe mutation is refused. No feature search, new estimator or R9 candidate engine is added. |
| Existing feature store, with real media-only subjects | `feature_values` now requires exactly one post or media FK. Values freeze the subject revision, recipe, relevant cue/coverage/definition/evidence/source lineage, actual availability and eligibility. Dependency hashes exclude unrelated set revisions; frozen statistical rows separately retain the full selected set. |
| Explicit analytics opt-in | Schema-2 specs map declared `creative.*` predictor names to pinned recipe IDs and an annotation key/review policy. As-of input selection and publication-time forecast gates remain R2 rules. Legacy specs, primitive recipe contents and numerical methods do not change. Unknown/outcome-aware or exploratory labels cannot be presented as independent confirmation. |
| Cache and report compatibility | Creative task/resampling fingerprints do not enter primitive task dependencies. Opt-in video reports use schema 2 and the committed annotation revision. Ordinary video reports remain schema 1. Failed creative tasks never substitute a different set. Model proposals and human imports remain distinguishable. |
| Add only exercised persistence | Canonical annotation/event/coverage/relation tables, anchor/input/membership projections, evidence bindings and media-valued recipe measurements have writers, resolvers/readers and tests. No future audience, graph or embedding tables are introduced. SQLite remains authoritative. |

The migration atomically rebuilds the evidence-locator CHECK and feature-value
parent table on the existing dedicated FK-safe migration connection, copying old rows
and preserving child links/immutable history. Pre-upgrade backups and interrupted-rebuild
rollback are verified. Released migrations 0001–0006 are unchanged. Populated libraries
refuse downgrade in favor of verified restore.

Eligibility is checked transitively for annotation sources, technique definitions and
literal inputs, including reused event revisions. Current views withhold ineligible
lanes; new measurements/comparisons/reports cannot silently fall back to an older set.
Retained historical artifacts remain immutable; withdrawal is not erasure.

The acceptance fixtures exercise real media bytes and production paths under controlled
annotations. They do not establish cooking-recognition accuracy, inter-reviewer agreement,
external model quality or psychological validity. Real-corpus annotation validation is
still required before research claims. R4 is delivered below; R5–R10 and U1/U2
remain unimplemented.

## 20. Audience implementation decisions

R4 is implemented in `0.0.8` / `0008_audience`. Exact operational contracts,
budgets, commands and examples are in [audience analysis](docs/audience-analysis.md).
The required vertical slice remains entirely offline and adds no dependency.

| Decision | Implementation and justification |
|---|---|
| Existing permitted comments remain canonical | Collection manifests reference real captured post/comment revisions. Original text, IDs and source clocks are not replaced by model-generated summaries. No author identifiers are introduced. Ownership/permission assertions are attributed, not independently verified. |
| Preserve collection context before counting | Ordering, filters, sampling frame, pagination/truncation, requested/collection times, declared versus actual counts and missing moderation coverage remain explicit. Counts use retained eligible identities or exact-text groups, not known platform totals or viewers. No viewer prevalence or binomial confidence interval is inferred. |
| Separate review coverage from label certainty | Exact Unicode spans and pinned rubric definitions support human proposed/reviewed/disputed labels. Whole-rubric review requires a full-comment span. Negation, irony, ambiguity and contradictory reviews remain uncertain even when review coverage is complete. Missing annotations are not absence. |
| Curated clustering is the first real path | Versioned supplied memberships include representative/counterexample roles and attributed summaries. Membership-score semantics are explicitly not supplied. Optional literal-English proposals remain unreviewed. No unvalidated embedding clusterer or new classifier/runtime is required. |
| Links preserve claim strength | Literal timestamp/quote, human interpretation and model proposal are different origins. Actual eligible post/event targets and exact evidence are checked. Literal timestamps fit original anchors; inferred links never acquire positions from publication time. Target context is captured beside reaction evidence, not described as causal reinforcement. |
| One engine and revision registry | Thin audience CLI adapters call shared import/show/analyze/retention services. Canonical documents use existing entity/evidence revisions; immutable FK projections preserve ordered collection/set/cluster membership, exact dependency rows and real analysis runs. No fake media/task or parallel revision system is added. |
| Lazy, bounded materialization | Identical inputs reuse a frozen analysis; changed review/collection inputs create revisions and new fingerprints. Current eligibility is checked before reuse. The opt-in timeline lane and R1 research report reader expose qualified context without changing old video/report bytes. |
| Withdrawal and erasure remain distinct | Withdrawal withholds new use while permitted archived bytes remain. Explicit erasure previews collateral whole-document/blob removal, requires current confirmation plus reason/actor, and records terminal identity/revision/evidence/artifact tombstones before scrubbing. Reproduction degradation is visible rather than hidden. |
| Crash-safe active-library cleanup | A resumable journal scrubs canonical/derived JSON and affected source/protocol metadata, removes exact managed blobs and checkpoints/vacuums SQLite. Immutable history triggers are temporarily suspended only inside the scrub transaction and restored before commit. Pending cleanup blocks normal exposure and rolls forward at startup. This does not promise physical-media wiping or deletion of independent copies. |
| Restore cannot resurrect forbidden comments | Latest same-lineage restore authority carries both withdrawal and erasure records. Replay precedes normal reads/backfill; already verified restored checkpoints are not cloned into new forbidden pre-upgrade backups. Legacy non-comment facts may be backfilled from retained structured rows, but tombstoned comments are skipped and terminal source eligibility remains enforced. |

The evidence-locator CHECK is extended by the existing atomic, FK-checked parent
rebuild procedure; released `0001`–`0007` scripts remain unchanged. Actual collection,
reaction, cluster, link, set, analysis, binding/dependency and retention tables all
have exercised writers/readers. Empty downgrade is supported; populated history
requires separate-directory restore. Qdrant/FTS/NetworkX audience projections remain
R6, so this release does not claim deletion behavior for unimplemented indexes.

Erasure covers registered active-library copies, including dependent research
reports when they cite affected audience evidence. A whole mixed raw export or
curated sheet may be removed while unrelated structured comments remain authorized.
Independent comment identities with identical wording are not treated as the same
person. External exports, pasted text, filesystem snapshots and backup bytes require
separate authorized cleanup. Expiry blocks access but does not pretend to erase
bytes automatically. These boundaries avoid silently expanding deletion scope.

Controlled fixtures test production import/revision/evidence/report/media/restore
paths, Unicode and uncertainty behavior, not annotation accuracy or psychological
validity. Behavioral series/retention/outcome semantics are delivered below; full
mechanism investigation remains R7 and later.

## 21. Behavioral implementation decisions

R5 is implemented in `0.0.9` / `0009_behavioral`; the actual operational contract is
[behavioral analysis](docs/behavioral-analysis.md). No dependency, server, model or
private-platform connector is added.

| Decision | Implementation and justification |
|---|---|
| Explicit rich imports, unchanged scalar contracts | `import behavioral` accepts schema 2.0 JSON through `ingestion/tabular.parse_behavioral`; v1 CSV/JSON definitions, nonnegative snapshots, old methods and report bytes retain their meaning. New structured domain models live in `domain/behavioral.py` rather than making the scalar parser a second statistics engine. |
| Actual subject discovery before references | `behavioral subject` returns captured account/post/media refs. Definitions and cohorts are imported first, then referenced exactly by observations. No fake intra-document IDs, media or tasks are generated. Actual ownership, platform, source permission and media association are validated before raw-source artifact retention. |
| Metric meaning precedes numerical operations | Immutable semantic definitions declare units/domains, population basis, numerator/denominator, replay, measurement and aggregation rules. Probabilities are bounded; replay-inclusive ratios may exceed one; completion needs its own threshold. Same-key semantic/cohort changes require new version keys. |
| Preserve clocks rather than infer freshness | Reporting windows, effective data cutoff, source generation/lag, collection and actual engine availability stay distinct. A late export supports a qualified retrospective description, not a historical predictor. Comparisons require known source data through the window end and aligned post ages. |
| Derive only compatible rates | Supplied aggregate components retain definitions, cohort, window and basis. Missing/suppressed/forbidden components stay unavailable; zero denominator is not zero rate. Source-reported values can remain descriptive with unknown numeric denominators. No bins-as-viewers uncertainty is produced. |
| Keep coarse grids coarse | Points, half-open bins and provider indexes preserve source convention/resolution; unmarked overlap is rejected. Normalized-to-media display mappings require exact actual media/duration and do not interpolate values or invent frame-level observations. Comparisons require an exact complete compatible grid/cohort and return explicit incompatibility instead of implicit rebinning. |
| Use current canonical creative memberships | R3 annotation-set selection supplies optional event context; removed events do not leak from old per-event rows. Behavioral analyses pin set/event refs and citations. New annotations change a new analysis fingerprint, while permitted historical reports remain frozen. Near an event is not caused by that event. |
| Separate account change from post performance | Account-outcome orchestration remains in `performance_service.py`. Exact compatible follower endpoints or an actual signed period observation produce `signed_metric_changes`; no old nonnegative CHECK is relaxed. Publication-time context uses real knowledge cutoffs. Neither nearest posts nor view counts receive inferred growth credit. |
| Attribute only what the source supplied | Conversion observations preserve source model/lookback, aggregate dedup keys and actual supplied credits. Conflicts, overlapping conversion periods, unknown scope/models, partial periods and nonadditive multi-touch data withhold totals. Disjoint sums require explicit definition authority. Experimentally identified causal effects remain unimplemented. |
| Reuse one canonical evidence/run path | Immutable definitions/cohorts/measurements/series/bins/attribution/changes/analyses use universal entity revisions and real FK projections/dependencies. Exact `behavioral_record` citations, research reports, cache fingerprints and actual runs share the existing resolver/withdrawal/restore gates. Bin membership is bulk-validated without reparsing a whole curve for every child. |

The evidence-parent CHECK is extended with the existing atomic, FK-checked rebuild;
released `0001`–`0008` scripts are unchanged. Empty downgrade is supported; populated
history requires verified separate-directory restore. The R4 erasure journal still
dominates restored source/evidence eligibility; no new general deletion command or
future-index purge behavior is claimed.

The required comparison path is bounded and descriptive within one exact account
cohort. There is no automatic reviewed cross-account metric mapping, rebinning,
survival fit, independent-viewer confidence interval or insertion of new behavioral
outcomes into R2 regression specifications. Source assertions and controlled fixtures
are not empirical platform/annotation/causal validation. R6 memory and R7+ mechanism
research remain separate deliveries.

## 22. Research-memory delivery decisions (`0.0.10`)

`0010_memory` is additive; released `0001`–`0009` scripts are frozen. It adds
`memory_changes`, bounded maintenance cursor state, immutable `embedding_spaces`,
logical `vector_documents`, versioned derived text/metadata and exact evidence
bindings, desired/indexed vector generations, a durable outbox, FTS5 and qualified
SQLite graph projections. SQL entity/evidence/projection FKs remain the authority.
Documents/FTS/graph are rebuildable, not a second canonical truth store.

| Decision | Reason and boundary |
| -- | -- |
| Two-stage transactional publisher | Canonical insert triggers append a minimal desired-projection journal in the writer's transaction, including withdrawals/tombstones. A bounded reconciler publishes documents/citations/FTS/graph/vector desires/outbox and removes processed journal rows in one later transaction. This refines the original single-transaction outbox sketch: many producers create canonical revisions before inserting typed bindings/dependencies, so embedding/document generation inside `save_entity` would validate incomplete records or couple canonical writes to optional storage. No commit can lose its pending work. Index lag is explicit. |
| One lock-owning worker, no leases | The existing whole-directory process lock serializes workers. Native inference/Qdrant I/O occurs outside SQL transactions, with generation/eligibility rechecks and compare-and-swap acknowledgement. Pending jobs replay after interruption; deterministic point IDs prevent duplicate points. Lease expiration/stealing would add complexity without enabling supported concurrency. |
| Qualified structural graph first | Actual canonical references, citations, contexts and definitions become edges carrying exact owner/evidence refs, field paths, scope and claim level. Draft hypotheses remain nodes, not evaluated mechanisms. Current edge owners are selected with canonical memberships; frozen older referenced context is not replaced with today's value. R7+ can register reified finding/assessment relations when those producers exist. No inferred causal/association/support edges are available now. |
| Bounded views and persisted maintenance cursors | NetworkX loads only bounded neighborhoods (default depth 2, at most 2,000 nodes / 4,000 edge examinations). Repair and eligibility sweeps use keyset cursors so large libraries are not stuck on the first page. Search has explicit scoped candidate/result budgets and partial coverage. Top-K is never an analysis population. |
| Separate behavioral document family | Source-defined bins/measurements/outcomes are `behavioral_observations`, not statistical findings. Representations retain exact citations, definitions and original timing; no observations become empirical findings through indexing. |
| One initial optional mean-pooling adapter | Verified local Sentence Transformers uses safe-tensor files, an audited Transformer/mean-pooling module recipe, pinned manifest/runtime/prefix/dimensions/normalization/token/chunk contracts, and isolated network-denied workers. Unsupported recipes and token overflow fail explicitly. No model weights, model-quality target or learned multilingual quality result is bundled or fabricated. The real-model test requires explicitly prepared assets and otherwise skips. |
| Deny first, scrub every derived copy | Resolver hydration denies withdrawn/expired/erased lineage before returning text or graph rows. Authorized R4 erasure scrubs document/FTS text (including old FTS segments), removes graph payloads, advances vector delete generations, deletes persistent points and vacuums their closed SQLite stores before completing the journal. Restore/rebuild obeys terminal tombstones; a worker cannot resurrect old content. Withdrawal alone is still not erasure. |
| Keep local repair operationally honest | Qdrant/model files are omitted from backups; memory text/FTS/graph inside SQLite follows canonical backup/restore reconciliation. Missing points are requeued; FTS/graph can be rebuilt from canonical records. An unreadable unknown Qdrant directory is reported for operator quarantine/recreation, never silently deleted. No distributed transaction or automatic repair of arbitrary corrupted external data is promised. |

Public adapters are `query`, `graph neighbors|path`, `memory status|register-space`
and bounded `storage reconcile|reindex`; model preparation reuses the existing
explicit manifest/checksum workflow. They call shared application services, not
agent-specific state. Canonical imports/analysis and basic no-model retrieval
never require Qdrant to open. Health checks distinguish derived damage/lag from
canonical data loss. Rebuilds are explicit and resumable, not mandatory on every
command. See [operations and verification boundaries](docs/research-memory.md).

## 23. Production and growth-context extension decisions

This design follows the [four-area audit](docs/intelligence-capability-audit.md).
C1-A/B/C/D are implemented in `0.0.13`–`0.0.16` (details below). Generic
creative annotations, platform metric namespaces and arbitrary profile JSON cannot
honestly stand in for complete craft, distribution, publishing or conversion intelligence.

| Decision | Rationale and boundary |
|---|---|
| One C1 evidence extension track, four small deliveries after R7 | Makes missing canonical inputs explicit without inflating the next psychological vertical slice or adding four parallel engines. C1-A production, C1-B publication/packaging, C1-C platform/surface evidence and C1-D profile/funnel context have independent acceptance gates. |
| Versioned typed payloads on the existing registry | Preserve R3's closed v1 creative vocabulary, account-export v1 and existing post/account metric subjects. Add professional technique schemas, publication/profile snapshots and platform statements only with writer/resolver/reader tests. No generic JSON reinterpretation or empty tables. |
| Context clocks and channel-specific outcomes | Publication/capture/knowledge/effective time, local timezone, metadata/profile variant and observation completeness must be explicit. Search, recommendation distribution, follows and business conversions have different subjects/windows/denominators; absence of data is not zero. |
| Three platform families with explicit surface scope | Reuse research validation, not ranking assumptions. Official documentation, permitted longitudinal analytics and creator experiments are separate evidence lanes with dated applicability. Hidden weights/satisfaction/eligibility remain unknown; no bypass or guaranteed reach. |
| Professional craft as measured/annotated evidence, not taste as fact | Existing low-resolution appearance/flow/audio proxies cannot establish camera operation, lighting setup or editing intent. Human-reviewed imports work offline; optional detectors require calibration, coverage and abstention. Feature interactions remain declared, versioned and tested. |
| Branching aggregate funnels with source-qualified attribution | Profile visits, follows and link clicks/conversions are not a guaranteed linear path or individual journey. New profile/link/campaign subjects need actual bindings; current post credits and follower endpoints keep their semantics. |
| Existing SQL/FTS/Qdrant/NetworkX architecture | Context documents use existing SQLite revisions and first-use projections; artifact hashes preserve authorized visual inputs. Register document builders/typed structural edges only with producers. No new collection per platform/capability, graph database, server or crawler. |

Planned SQL projection keys follow real queries: publication/profile snapshot revision → account/post and capture/effective times; ordered thumbnail/link/pin child → parent snapshot plus ordinal and real asset/post refs; platform statement revision → document version plus exact excerpt; distribution observation → actual subject/definition/cohort/window and source surface mapping. Profile/link/campaign metric bindings are additive validated subject types, not fake post IDs. Low-volume rubrics/templates stay versioned documents until indexed reads justify a table. Exact final DDL belongs to each C1 slice's migration review.

Memory builders retain source evidence, eligibility and scope; graph edges such as profile-snapshot→account, pin→post or statement→document are structural. R9/R10 assessed patterns/recommendations require qualified reified findings, not direct causal-looking technique→success edges. New context revisions invalidate only their dependencies; historical reports keep pinned context. The existing outbox, stale-generation guards and erasure/restore rules apply to all derived copies.

R9 owns bounded comparisons/discovery using these inputs; R10 owns actionable shot/edit, packaging/schedule, distribution-response and profile-conversion experiments/recommendations. Native platform tests count as randomized only when their actual assignment/outcome evidence supports that design. Account/period changes require carryover/spillover checks. U1 enables static thumbnail/profile images; U2 exposes only delivered services with explicit scope and data-access limits. See the [slice tests](docs/intelligence-capability-audit.md#4-bounded-delivery-and-verification) and [statistical safeguards](docs/statistical-design.md#13-production-distribution-publishing-and-conversion-designs--planned).

## 24. Literature-backed research delivery decisions (`0.0.11`)

R7 implements one bounded offline assessment path through the existing engine. See
[operations, actual schemas and evidence limits](docs/psychological-research.md).
It does not implement R8 reevaluation, R9 general discovery, R10 experiment outcomes,
C1 producers or U1/U2 workflows. Existing descriptive media prompts are unchanged.

| Decision | Reason and boundary |
|---|---|
| Add `research prepare` rather than reinterpret R1 registration | R1 v1 draft registration/citation reports retain their exact contract. Prepared protocols bind exact drafts, constructs, applicability reviews, predictions, context and experiment plans. Every registered rival is retained; contextual explanations need no fake construct. Preparation alone does not establish preregistration or blinded data access. |
| Strict offline human-reviewed corpus, not autonomous verification | DOI/primary URL, bibliographic metadata, permitted exact excerpt, study design/population/outcome/limitations and review attestations are immutable documents. Syntax/span/reference checks are automatic; external authenticity and applicability remain reviewer judgments. Unverified/retracted/corrected-old sources cannot support new claims. Two primary-source seed studies demonstrate traceability, not cooking-effect validity. |
| Evaluate the original R2 frozen analyses | The evaluator checks version-2 specs, original complete SQL populations, exact statistical citations and completed attempt ownership. It reuses declared families/holdouts rather than fitting a second engine, selecting top-K samples or claiming new independent confirmation. Supplementary content/reaction/owner-retention evidence must belong to that population. |
| Separate evidence dimensions and constrain conclusions | Record actual feature coverage/blinding/value lineage, reviewed literature applicability, local directional association, saved validation scope and causal non-identification separately. Unsupported or indistinguishable mechanisms remain so; significant creative associations do not prove psychological mediation. No causal findings or executed experiments are supported by R7. |
| First-use projections only | `0011_research` adds protocol/assessment/dependency indexes and typed study/research evidence bindings. Sources, findings, constructs, operationalizations and briefs use validated canonical documents. The evidence parent rebuild preserves existing triggers, including R6's insertion journal, without sorting its intentional document FK cycle. Released `0001`–`0010` migrations are unchanged. Captured history requires verified backup/restore, not downgrade. |
| Shared qualified memory and eligibility | R6 document builders index new canonical producers in existing families/spaces; findings/assessments are reified nodes with structural citations, not causal-looking technique→success edges. Retractions/withdrawal/erasure gate current content and derived reports. Status changes can revoke eligibility but do not implement R8 staleness, automatic research or reevaluation. |
| Deterministic reports and proposed experiment briefs | JSON/Markdown artifacts preserve exact population/citation/attempt context, counterexamples, uncertainty and discriminating measurements. A brief has declared variants/design and `proposed_not_executed` status; it is not a registered R10 experiment, publishing authorization or a recommendation guarantee. |

Source review and construct/annotation validity, representative audience coverage,
adequate independent real datasets and psychological identification remain empirical
obligations. Generated media labels and positive/negative/null statistical fixtures
test the software pipeline, not those scientific claims. Optional model/corpus-quality
acceptance is not inferred from storage, schema or statistical tests.

## 25. Incremental reevaluation delivery decisions (`0.0.12`)

Actual interfaces, conservative cases and budgets are documented in
[incremental research](docs/incremental-research.md). Prior delivery records above
remain historical descriptions of their own scope.

- Reuse R2's population/feature/model pipeline and R7's evaluator. Reevaluation
  rebuilds saved SQL selectors, not nearest-neighbor samples or caller-picked new
  reports. New comparisons save explicit groups; older comparisons retain their
  frozen post membership because original account selection cannot be recovered.
  The numerical engine has not changed: `0.0.10`/`0.0.11` frozen runs can reproduce
  with matching libraries and exact result checks, retaining original input bytes.
- `research_changes` is a small append-only deduplicated SQLite journal mirrored
  from existing producer events. Inspection established that R6 drains its indexing
  queue, so sharing a cursor on that queue would lose invalidation events. No new
  server or scheduler is needed. Migration backfills canonical event order and adds
  missing media-association/completion events without editing released migrations.
- `assessment_watches` freezes selector manifests and tracks bounded operational
  freshness separately. Scans start at frozen analysis knowledge cutoffs, not
  assessment publication time, to catch arrivals during delayed evaluation/restart.
  Existing frozen revisions are not new evidence; index rebuilds do not retrigger them.
  Selector identity is retained even for empty populations; same-creator historical
  reference accounts are tracked as well as target accounts/posts.
- Immutable request plans and hashes pin resumed inputs. An optional transactional
  `on_saved` callback in the existing statistical persistence path checkpoints a
  completed slot atomically with its analysis. This avoids a second analytics
  engine, ambiguous crash recovery or silently duplicating a completed fit.
- `assessment_transitions` has real prior/next/request FKs, immutable history and
  one successor per predecessor. Assessments/findings remain canonical immutable
  documents with their existing R7 identities. Lineage links join successive
  assessment identities rather than retroactively changing R7 identity rules.
- Comparisons retain changed data/feature/reference identifiers, descriptive
  effects/intervals, added/reused/removed units and original families/holdouts.
  Cumulative looks are exploratory, never independent confirmation. No inferred
  sequential error control, global mechanism rejection or causal effect is added.
  Statistical citations used for earlier displayed results remain explicit
  comparison dependencies; exact-citation withdrawal cannot leave those numbers
  usable in a successor report. Corrected literature still requires new review.
- Freshness and permission are separate: current hydration gates exclude stale or
  superseded assessment-derived SQL/FTS/vector/graph results; pinned history remains
  subject to withdrawal/retraction/erasure. Archived report bytes are not rewritten
  merely to show current operational state. Human review is required to repin
  corrected literature or semantic evidence; imports never fit models automatically.

R9/R10, C1 and U1/U2 remain unimplemented; no live adapter, model dependency,
additional vector collection or infrastructure is introduced by this delivery.

## 26. Professional production evidence (`0.0.13`)

- A separate annotation schema `2.0` adds 16 craft labels and technique-specific
  categorical values. The released v1 schema, definitions and eleven recipe payloads
  remain frozen. Common timing, source and review validation is reused, not loosened.
- Eight new pins quantify reviewed shot durations, temporal-half pacing, cut density,
  subtitle occupancy, cut/beat proximity, angle changes and close framing. Complete
  human coverage and exact intervals/partitions are required where appropriate;
  ambiguity, sparse coverage and missing denominators produce unknown, not zero.
  Apparent movement/lighting/color/focus do not recover rigs, intent or original grades.
- Existing creative projections/typed citations store the v2 documents; no DDL,
  dependency or vector collection is needed. A v2 document permits 512 events but
  does not precompute quadratic all-pairs temporal relations. Declared recipes
  selectively compute the temporal relationships they actually require. V1 relation
  behavior is unchanged; an empty v2 relation lane is explicitly qualified.
- The R2 feature join, lineage, R7 evaluator and R8 invalidation consume new pins
  directly. One evidence traversal shares its memo through statistical dependencies
  and deduplicates overlapping selected/reference inputs. No permission cache survives
  a top-level call, so same-connection withdrawal is checked again immediately.
- C1-A's generated multi-video integration validates actual import, matching,
  citations, assessment/reevaluation and historical report persistence, not empirical
  professional-label accuracy, mechanism mediation or causal performance effects.

See [production operations](docs/production-evidence.md). Broad interactions and
actionable strategies remain R9/R10; automatic detector validation is not delivered.

## 27. Publication context delivery (`0.0.14`)

- `0013_context` adds one account/post/capture projection and one typed evidence
  binding, extending the existing locator CHECK through the previously tested
  trigger-preserving rebuild. Released migrations remain unchanged. Context field
  locators cite actual strings/asset membership without fake playback coordinates.
- Explicit schemas distinguish packaging observations, completeness-qualified
  publishing inventories and dated query/trend context. Source capture, attested
  validity and engine knowledge remain separate; no import backdates availability.
  Original offsets validate against supplied IANA zones, including DST gaps/folds.
- Two pinned deterministic report recipes expose local clock and complete-inventory
  cadence. A frozen R2 comparison can align actual outcomes to exactly the same
  posts without estimating a new context effect or extending the v2 numerical engine.
  R9 owns new context regressions. Declared search/recommendation/conversion objectives
  never reinterpret generic views as verified channel-specific outcomes.
- Record-level reuse preserves unchanged source revisions when a neighboring record
  changes. Frozen reports pin context and statistical citations. R7 supplementary
  scope checks admit raw context only; R8 tracks its real dependencies. Existing
  citation builders/eligibility, structural graph, indexing journal and confirmed
  erasure machinery apply; no new collection or graph engine is introduced.
- The historical `audience redact` command also accepts registered context sources
  with the same explicit preview/confirmation and terminal tombstone workflow. It
  does not gain authority to erase original post/account/media records or backups.

See [operations and actual scope](docs/publication-context.md). Bounded asset
verification/identity is not U1 visual interpretation, and dated trend imports are
not an autonomous trend detector or evidence of a universal optimal posting time.

## 28. Platform research evidence (`0.0.15`)

- Four exercised context kinds represent official document versions, exact reviewed
  statements, source capability/mapping manifests and paired distribution observations.
  They reuse `0013_context` ownership/citation bindings; no DDL or metric reinterpretation.
  Official publisher origin checks and hashes do not replace human authenticity review.
- Explicit platform/surface/format/language/market/audience scope and source-native
  traffic mappings prevent pooling similarly named counters. R5 supplies exact period
  measures, definitions, cohort and effective/collection clocks. Same-window feedback,
  suppressed/private metrics and mixed definitions are not usable exposure evidence.
- Reports preserve official-guidance and local-observation lanes separately. They expose
  actual early/later values and lag, not a fit of hidden ranking rules. Source availability
  is separately visible: an early event window imported later is not a historical predictor.
- Context-report artifact/citation freezing is now a shared helper without changing B's
  stored payload contract. Current memory rejects superseded context dependencies, while
  pinned history survives normal version changes. Explicit source corrections/revocation
  withhold dependent use; confirmed erasure scrubs existing derived copies.

[Operations, trust boundaries and source limits](docs/platform-research.md) distinguish
these working inputs from R9 discovery and R10 causal experiments/recommendations.

## 29. Profile and owner-funnel evidence (`0.0.16`)

- Actual snapshots distinguish captured public fields, ordered links/pins, retained
  photo identity and source declarations from a frozen human rubric. Current selection
  uses source capture time within a stable snapshot key, not the arrival order of old
  corrections. Engine knowledge remains import time; exposure is not backdated.
- Source meanings require one small additive projection, `0014_profile`:
  `funnel_event_bindings` binds actual R5 definition revisions to immutable event role,
  uniqueness and source-code hash, with real context/definition FKs. It prevents
  relabeling a click counter as installs and retains only non-sensitive role/hash
  metadata after source erasure. Released migrations are unchanged.
- R5 owns actual account-period counts and source attribution. Funnel rates require
  actual compatible components/cohorts/windows and supplied nested/deduplicated joins;
  missing/suppressed or incompatible data stays unknown. Source joins are reviewed
  attestations, not automatic verification of individual journeys. No new numeric
  inference engine or quality→growth score is introduced.
- Shared context/asset/report/memory services support public fields and qualified
  measured flows as independent lanes. Account aggregates are not fake native profile,
  link or campaign subjects; those require source-specific actual bindings when used.
  Public-profile exposure remains unknown unless explicitly sourced and interval-checked.
- Frozen history, raw R7 population context, R8's existing change journal, current
  memory gating, source withdrawal and confirmed erasure reuse the existing architecture.
  Derived graph links stay structural, not causal. No connector, server or dependency.

See [formats, semantic guards and delivered limits](docs/profile-conversion.md).
U1 automatic image interpretation and R9/R10 discovery/recommendation/experiment
work remain separate; completing C1 does not claim their scientific validity.

## 30. Bounded discovery implementation decisions (`0.0.17`)

R9 is a separate versioned **model adapter/lifecycle**, not a rewrite of frozen
R2 estimands or an independent untracked analytics engine. It reuses R2's real SQL
population/materializer and universal evidence, C1's real contextual producers,
R6 memory projections and the shared family/whole-round/holdout history. Pure fitting,
partitioning and counterexample selection live in `research/`; canonical source joins,
transactions and CLI adapters stay in their existing application/storage boundaries.

1. **Marginal prediction instead of unsupported fixed-effect transfer.** Main effects,
   raw pairwise products, quadratics and a fixed small spline family share one
   train-fitted OLS/Ridge pipeline. Three inner creator-disjoint folds choose only
   predeclared candidates/alpha values; outer creator/time/joint/niche evaluation
   uses that pipeline unchanged. New creators have no invented fixed-effect intercept.
   This target is explicitly observational marginal raw-outcome prediction, not an
   adjusted within-creator causal effect. Small/rank-deficient designs refuse estimates.
2. **One frozen search round and durable failed/null attempts.** Up to 12 candidates,
   three alphas and 128 fit attempts; no adaptive expansion or early stopping.
   `0015_discovery` adds four query projections: rounds, fits, inspected-unit members
   and typed canonical bindings. Specifications/snapshots/results/patterns remain
   immutable entity revisions, cited with the existing research locator. No parent
   table rebuild, new collection, server, dependency or schema-per-model.
3. **Protected actual data, not renamed reservations.** Whole-round attempts reuse
   R2 families/attempts; actual post/media holdouts use its existing ledger. The new
   member history also protects previously trained-on rows and actual account-period
   measurements. R2 reservations consult that history; R9 checks prior fitted R2
   populations too. Interrupted/failed/renamed rounds do not release observations.
   Repeat exploration requires disclosed parent lineage; no global sequential FDR
   guarantee is inferred from per-round BY correction.
4. **C1 lanes share machinery, not outcome meanings.** Primitive/reviewed craft and
   source-attested publishing features use real explicit-window post outcomes;
   surface distribution uses compatible R5 early/later observations and actual
   knowledge clocks; profile features require the exact exposed snapshot and source-
   qualified measured funnel. Official guidance, qualitative rubrics and measured
   results remain separate. `discovery-context-1` pins literal/circular/completeness
   transformations. Source truth/declared sampling frames are not automatically verified.
5. **Prediction is not inferential replication.** A separate frozen confirmation
   specification estimates the selected fixed-OLS main/product/quadratic raw-basis
   focal contrast on untouched units, with creator-cluster uncertainty only under
   adequate support. Tuned/Ridge and reknotted-spline inferential replication are
   refused. Support, contradictory direction, inconclusiveness and insufficiency
   persist independently of the old result. No psychological assessment is promoted,
   no mediator identified and no experiment declared randomized by this path.
6. **Research memory is qualified and erasable.** Selected combinations are reified
   `creative_pattern` candidate proposals with constituent roles/scope and exact
   `discovery_search` references, explicitly not confirmed. Existing SQL/FTS/optional
   Qdrant and SQLite-backed NetworkX builders project them without causal edges.
   Withdrawals/corrections gate every read; confirmed context erasure also scrubs
   dependent search snapshots/fit diagnostics. Structural reservation IDs remain
   to prevent reuse. Exact reproduction is read-only and checks numerical versions.

The approved broad scope is delivered within these bounds, documented in
[operations](docs/bounded-discovery.md). A held-out niche is a named stress test,
not universal transfer. Near-duplicate detection, unrestricted feature mining,
online error control, richer semantic metadata features, repeated account-period
interventions, R10 recommendations/experiments and U1/U2 remain separate work.
Controlled fixtures establish software behavior, not empirical construct validity
or platform algorithm recovery. Released migrations `0001`–`0014` are unchanged.

## 31. Registered experiment and strategy decisions (`0.0.18`)

1. **Small supported design, explicit refusals.** Prospective post/account-period
   slots bind actual accounts before publication; seeded paired assignment and the
   complete source-defined outcome family are immutable. Actual R5 measurements
   later bind measured subjects, cohorts, windows and denominators. Source-native
   aggregate arms can be recorded but never become impression-level sample size or
   an unsupported causal estimator. Sequential unrandomized variants remain descriptive.
2. **Conditional evidence, not self-certified causal truth.** Execution fidelity,
   interference, concurrent changes and stopping have cited review attestations.
   Twenty independent matched blocks gate within-pair Monte Carlo swaps, Holm tests
   and Bonferroni paired-t intervals; the threshold is not a power calculation.
   Missing outcomes, deviations, repeated creators/accounts, incompatible source
   populations, degenerate uncertainty or immature lag withhold inference. C1
   publishing/surface/profile gates prevent aggregate attention replacing exposure
   or conversion. Review truth and audience independence cannot be automatically verified.
3. **Reuse the real ledger and canonical store.** `0016_experiments` adds six
   FK-backed projections for actual registrations, result streams, measured-unit
   bindings, analyses, assessments and hypotheses. No additional infrastructure,
   Qdrant collection or dependency. Protocols/snapshots/results live in immutable
   revisions and content-addressed archives. Started/failed/completed shared attempts
   persist; exact retries/reproduction are not new looks. Source corrections append
   history and are never labeled independent replication. Released migrations
   `0001`–`0015` remain unchanged.
4. **New assessment lane rather than a forged old result.** `experiment_assessment`
   binds the exact prior R7/R8 assessment and all registered rival hypotheses. It
   evaluates assignment predictions, not R7's observational feature terms or mediator
   identity. Existing `research history` exposes it separately; old assessments,
   reports, statistical schemas and R8 reevaluation logic retain their meanings.
5. **Qualify structured proposals, do not invent effectiveness.** One recommendation
   producer accepts original author/agent action proposals across four domains.
   Actual source lanes, scoped estimates/failures, official guidance, qualitative
   profile reviews, counterevidence, dates and uncertainty remain distinct. Always
   `test_first`, no numerical promised lift or external execution. C1 context gates
   growth branches. Limited cited-span overlap/claim-language guards are not a
   comprehensive originality, feasibility or semantic-validity oracle.
6. **Existing memory and retention invariants.** New kinds use real universal
   research locators, existing binding validation and qualified structural graph
   edges. Current views check superseded dependencies; historical snapshots remain
   frozen while permitted. Withdrawals gate use and confirmed erasure scrubs dependent
   source-derived payloads/artifacts rather than preserving numeric copies in query
   tables. U1/U2 and independent empirical validation are not implemented by R10.

Exact contracts, scientific assumptions and intentionally unsupported designs are
documented in [operations](docs/registered-experiments.md).

## 32. Static image and ordered carousel decisions (`0.0.19`)

1. **Share media primitives, not fabricated timelines.** Existing checksum-addressed
   media assets, locations, probes, artifacts, tasks, runs and numeric appearance
   measurements support static raster input. Image duration stays null. No static
   frame/observation/OCR row is inserted into video interval tables; video commands
   and their old timebase semantics remain unchanged.
2. **Explicit coordinate and privacy policy.** Bounded Pillow decoding applies EXIF
   orientation, preserves aspect ratio and creates a metadata-free RGB display.
   Alpha uses fixed white compositing; ICC/EXIF/GPS are not propagated. Region
   coordinates refer to that display, not rotated raw pixels. Unmodified originals
   are retained only with explicit copy authority. Unsupported/animated/multipage
   input is refused rather than silently flattened.
3. **Actual canonical inputs and first-use bindings.** `post_media_input` freezes URI,
   position, source alternative text and post/source identity. `image_analysis` and
   `carousel_analysis` bind actual runs and source revisions. `0017_images` adds three
   small FK-backed projections: static records, typed evidence bindings and universal
   task-input citations. The existing atomic evidence CHECK rebuild preserves prior
   rows, IDs, indexes and triggers; released migrations are unchanged.
4. **Prepared OCR reuses the provider, not video persistence.** The existing local
   worker reads a normalized image under a static identity. Universal input citations
   supplement legacy timed inference inputs without replacing them. Provider identity,
   manifest/runtime/configuration, exact quotes and normalized regions are retained.
   Disabled/unavailable/failed OCR is not measured absence; deterministic output survives.
5. **Ordered descriptions with explicit coverage.** Carousel positions are frozen,
   duplicate placements disclosed and per-post item limits enforced. Mixed videos,
   remote URLs, absent files and budget exclusions stay in the manifest. Versioned
   position-weighted available-item summaries do not infer viewer progression,
   completeness or performance. Source text and OCR are separate evidence lanes.
6. **Reuse existing lifecycle and retention.** Image fingerprints include method,
   options, limits and numerical/prepared-provider versions. Cache reads validate
   artifacts and universal input eligibility. JSON/escaped Markdown reports and
   account-batch dispatch reuse existing services. Withdrawal gates inputs; confirmed
   erasure scrubs static canonical payloads, reports, displays and original/reused
   task caches. No new server, dependency, collection or mandatory indexing workflow.

U1 supplies descriptive visual evidence and review prompts, not automatic expert
craft/brand interpretation, identified effects or a portable agent skill. U2 and
independent model/empirical validation remain separate. See [operations](docs/image-analysis.md).

## 33. Portable host orchestration and usable report exports (`0.0.20`)

U2 adds a single [skill bundle](skills/socialdna/SKILL.md), not a second engine or
host-specific service. Its [operations guide](docs/portable-skill.md) records host
discovery sources, installation, permissions and separate verification gates.

1. **Instruction/data boundary.** Small host-neutral instructions route to focused
   references. Imported text/model output is untrusted evidence, not shell code.
   Hosts use actual engine IDs, exact schemas and evidence eligibility, preserve
   counterevidence, and keep agent commentary distinct from measured findings.
2. **Preflight without library initialization.** `capabilities` reads PATH/settings,
   prepared asset checksums and installed runtime metadata, not SQLite or indexes.
   Optional-model failures are isolated. Four growth domains and research, reactions,
   behavior, deterministic media and optional providers have separate entries.
   States distinguish interfaces, optional preparation, missing prerequisites and
   future functionality; neither native inference nor scientific validity is implied.
   Semantic space bindings/coverage and endpoint reachability remain explicit limits.
3. **One portable distribution.** `application/skill_service.py` exports the same
   wheel-bundled source to an explicit new directory, refusing existing targets.
   `skill schema` derives contracts from engine models instead of duplicated JSON.
   Setup does not change host settings, install dependencies or grant permissions.
   Thin path/invocation guidance follows official Codex/Claude Code/OpenCode docs.
4. **Reports remain evidence artifacts.** Existing report generation and JSON/escaped
   Markdown renderers remain authoritative. `report generate --output` exports a
   new UTF-8 document, never overwrites, and preserves partial/error contracts.
   Local asset links remain local. Export copies are outside managed erasure and
   require eligibility checks before reuse. HTML is deferred because no separate
   tested consumer justifies another renderer.
5. **No schema or statistical redesign.** Database head stays `0017_images`;
   released migrations, report/envelope schemas and numerical methods are unchanged.
   Additive capability schema 1.0 is runtime metadata, not a new canonical entity.
   Frozen `0.0.19` statistical runs retain explicit compatible reproduction.
6. **Verification boundaries.** Contract tests validate references, command routes,
   flags, exit codes and generated schemas. Subprocess tests exercise all three host
   directory layouts and offline partial/cited/report workflows. Wheel/sdist smoke
   tests exercise installed resources without checkout fallback. None proves a live
   agent conversation, host tool-choice behavior, model accuracy or empirical validity;
   those gates are separately recorded rather than silently promoted to passing.
