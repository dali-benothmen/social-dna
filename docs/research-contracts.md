# Research contracts

Status: R1–R6 identity/evidence, statistics, creative/audience/behavioral producers and memory are preserved in `0.0.12`; R7's bounded reviewed-literature/protocol/assessment path is implemented, with final verification recorded in the roadmap. R8 adds explicit incremental reevaluation; R9–R10/C1 remain planned. Date: 2026-11-05. See [R1 operations](research-foundation.md), [versioned analytics](versioned-analytics.md), [creative analysis](creative-analysis.md), [audience analysis](audience-analysis.md), [behavioral analysis](behavioral-analysis.md), [research memory](research-memory.md) and [psychological research](psychological-research.md) for actual signatures/limits; prepared-real-model acceptance is opt-in and conceptual interfaces below are not all executable APIs.

This document makes the research payloads and invariants in [ARCHITECTURE.md](../ARCHITECTURE.md) concrete. It does not replace the implemented video timeline, comment imports, scalar metrics, or frozen statistical analyses. [Statistical design](statistical-design.md) defines comparison/validation methods; [migration strategy](migration-strategy.md) defines additive adoption. The complete reference flow is in [the cooking use case](research-use-case.md).

## 1. Shared identity, persistence, and interfaces

`EntityRef(kind, id, revision_id)` names a canonical, immutable entity revision. `EvidenceRef(id, revision_id)` names an immutable evidence revision; it is not a free-form URL or model-generated citation. Existing UUIDs are preserved. Exact revision IDs, source/provenance references, schema version, creation time, author/analyzer identity, configuration hash, and payload hash accompany every new revision. A changed interpretation creates a revision, never a silent overwrite.

The universal entity/evidence registry and local typed resolvers are defined in ARCHITECTURE.md. Legacy `evidence_items` remains the media subtype: papers, comments, and statistical results do not receive fictional media IDs, task IDs, or timestamps. New references must resolve to an eligible canonical revision; all persisted evidence links have foreign keys to the evidence revision registry. A typed service also validates entity kind, source scope, locator, permission, and withdrawal state.

The physical root keys are `entity_identities(kind, entity_id)`; `entity_revisions(id)` with identity foreign key, revision number, schema/hash, recorded time and provenance; `evidence_records(id)` preserving legacy evidence UUIDs; and `evidence_revisions(id)` with evidence identity, subject revision, locator schema/hash, provenance, capture time, and nullable producer run/task. Evidence-role relations use `evidence_links(owner_revision_id, evidence_revision_id, role, scope_revision_id)`. R1 supplies real bindings for existing media, posts/comments and metrics; R2 adds statistical-result/term bindings with corrected comparison writers. Future study/experiment bindings are introduced with working writers, not fabricated placeholder records.

These contracts are **not an instruction to create one table per noun**. Initially, low-volume definitions and research specifications are versioned, validated entity documents in SQLite. Introduce indexed relational projections only when a milestone queries them: event media/time/technique in R3, audience collection/member/span in R4, metric bins in R5, and question/hypothesis/assessment dependencies in R7–R8. Large media and authorized raw imports remain content-addressed artifacts. Qdrant and graph rows are rebuildable projections, not owners of these payloads.

| Proposed interface | Required behavior | First usable milestone |
|---|---|---|
| `EvidenceResolver.resolve(ref, purpose, as_of)` | Return a typed locator, source authority, provenance, eligibility, and availability; reject dangling/wrong-kind references | R1 |
| `CreativeEventService.annotate(media_ref, specification, evidence_refs)` / `verify(event_ref, adjudication)` | Persist proposed or reviewed events with coverage and boundary uncertainty; preserve both revisions | R3 |
| `FeatureMaterializer.materialize(subjects, recipe_refs, cutoff, mode)` | Return versioned values and complete input/availability lineage; never silently use a newer recipe | R2 lineage; R3 semantic recipes |
| `audience_service.import_into_application(app, AnnotationSet)` | Import exact spans, curated memberships and qualified links in one frozen set; preserve source/rubric/provider/review scope | R4, implemented |
| `ResearchService.register(question_spec, hypothesis_specs)` | Freeze question and minimal hypothesis specifications in R1; add reviewed constructs, rival predictions, and richer data needs in R7 | R1 base; R7 psychology |
| `ResearchService.evaluate(hypothesis_ref, data_manifest, analysis_spec)` | Create an immutable assessment, result references, qualified finding revision, and dependency manifest | R7 |
| `application.reevaluation_service.reevaluate(application, assessment_id, spec=None)` / `history(application, identity)` | Implemented: rebuild frozen SQL selectors; preserve prior assessments, membership, ledgers and support changes. History accepts a question/hypothesis/assessment identity. | R8 |
| `ClaimValidator.validate(claim_revision)` | Check evidence roles, lineage, scope, claim level, and causal prerequisites before save/report/index | R1 base rules; R7 research rules; R10 experiment rules |

Services return typed results and the existing CLI result envelope, including partial/unavailable components. A model can propose structured annotations; it cannot bypass validation. Human-reviewed imports and deterministic fixtures are first-class input paths. Basic media analysis does not require any research registration, literature download, or statistical fit.

### Query projections and keys

The following are logical projection names for the owning milestones to materialize. Every `*_revision_id` references `entity_revisions.id`, or `evidence_revisions.id` where explicitly named, and receives typed binding/kind validation. The registry is authoritative for identity/version; query projections do not maintain a competing revision history.

| First use | Logical projection | Keys and indexed fields |
|---|---|---|
| R3, implemented | `creative_annotation_sets`, `creative_events`, `creative_coverages`, `creative_event_relations`; ordered set memberships, event anchors/inputs and typed evidence bindings | Canonical documents live in immutable entity revisions. Projection PKs are `revision_id`; anchor/input PK `(event_revision_id, ordinal)`. Set/event media/technique/time indexes and real entity/evidence/media/run/task FKs support actual reads. Discontinuous anchors remain separate rows. |
| R2–R3, implemented | `feature_recipes`, `feature_values` | Value PK `id` hashes subject revision, pinned recipe/key, exact relevant lineage and measurement/missingness. Exactly one real post/media FK; numeric value or explicit unavailable coverage/reason. Recipe specs are immutable versioned JSON with real supplying technique refs. General categorical discovery remains future work. |
| R4, implemented | `audience_collections`, `audience_collection_members`, `audience_annotation_sets`, ordered set memberships | Document PK `revision_id`; membership PK `(collection_revision_id, ordinal)` with unique comment revision FK. Post/source ownership and spans are validated against canonical revisions. Collection key/time and set collection/key indexes support actual readers. One comment in multiple collections is not multiple independent people. |
| R4, implemented | `reaction_annotations`, `reaction_clusters`, `reaction_cluster_members`, `content_reaction_links`, `audience_analyses`, dependencies and evidence bindings | Annotation/comment/span, cluster/member, link/reaction/target and analysis/run references have real FKs; canonical JSON preserves rubric/protocol, bounds, labels, review and uncertainty. Cluster membership PK `(cluster_revision_id, reaction_revision_id)` preserves roles. Reverse dependency indexes support lineage. `audience_redactions` and terminal `audience_tombstones` support actual cleanup and restore reconciliation. |
| R5, implemented | `behavioral_metric_definitions`, `audience_cohorts`, `metric_measurements`, `metric_series`, `metric_bins`, `attribution_observations`, `signed_metric_changes`, `behavioral_analyses`, evidence bindings/dependencies | Canonical document PK `revision_id`; bins have unique `(series_revision_id, ordinal)`, original point/interval columns and exact parent FK. Observation subject/definition/window indexes support bounded selection; signed changes have exact endpoint/supplied-measurement FKs. Concrete projections validate against the shared immutable entity registry. |
| R7, implemented | `research_protocols`, `research_assessments`, `assessment_dependencies`, `study_evidence_bindings`, `research_evidence_bindings` | Protocol/assessment PK `revision_id`; real question/protocol FKs, input hash and capture time. Dependency PK `(assessment_revision_id, ordinal)` with exactly one entity/evidence FK and reverse indexes. Typed source/finding/excerpt and assessment/finding/brief citations bind actual canonical revisions. R8 adds the lineage and operational selection watches below. |
| R8, implemented | `research_changes`, `assessment_watches`, `reevaluation_requests`, `assessment_transitions` | Independent append-only event sequence, unique `(kind,target_id)`; immutable selectors with operational cursors/stale reasons; frozen request plans with transactional run checkpoints; immutable real prior/next/request FKs and unique predecessor/successor links. Scientific comparison documents remain canonical R7 assessments/findings, not mutable watch state. |

The full typed contracts in later sections supply payload fields not listed in these compact indexes. Low-frequency literature definitions, predictions, rivals, and experiment specifications do not need separate physical tables before their actual query/writer milestone. Save operations use a declared operation/specification/input hash for idempotency; identical retries reuse the immutable result, whereas genuinely changed inputs create a new revision. Unicode comment spans use one declared character-index convention with raw-to-normalized mapping; offsets from another convention cannot be silently accepted.

## 2. Creative techniques, events, and cross-modal relationships

A **technique** describes an observable creative choice; an **event** identifies its possible occurrence in particular content. Neither asserts a psychological mechanism. Example: `result_first_opening` can be detected without claiming anticipation, curiosity, or sensory reward.

| Contract | Required fields and constraints |
|---|---|
| `CreativeTechnique` | Stable slug and revision; literal definition; inclusion/exclusion rules; eligible modalities/content types; required observation coverage; annotation procedure; examples/counterexamples; provenance. Keep `unclassified` available. |
| `CreativeEvent` | Media/post revision; technique revision or unclassified description; one or more typed anchors; modality set; evidence links; state `proposed`, `reviewed`, or `disputed`; method/reviewer; annotation protocol and outcome-access/blinding record; sampling coverage; extraction reliability. No psychological or performance conclusion in the event itself. |
| `MediaAnchor` | Media revision; `interval`, `point`, or `spatial` kind; original timebase; nominal bounds/point when known; boundary uncertainty when supported; frame/spatial locator where applicable; source evidence. Photos use spatial/full-image anchors, not invented durations. |
| `CueBundle` | Ordered membership of event/observation/text/frame/audio evidence revisions; role of each member; assembly rule revision; coverage and missing modalities. Bundle identity preserves discontinuous evidence rather than joining it into one misleading continuous span. |
| `EventRelation` | Source/target event revisions; relation such as `before`, `overlaps`, `simultaneous_within_tolerance`, `introduces`, or `responds_to`; tolerance; derivation rule; evidence; `verified`, `possible`, or `proposed` status. Temporal co-occurrence does not imply semantic reinforcement or causation. |

All video/audio offsets use the existing original-presentation integer-millisecond timebase. Intervals remain half-open `[start_ms, end_ms)`. For uncertain boundaries, store `start_min_ms`, `start_max_ms`, `end_min_ms`, `end_max_ms` plus optional nominal bounds; validate ordered bounds, physical duration, and at least one feasible nonempty interval. Unknown bounds stay null with a reason, not zero. An instantaneous cut is a point anchor, not a fake zero-duration interval. Discontinuous occurrences use multiple anchors with explicit membership/order. Imported normalized-time bins retain their own coordinates until an explicit conversion is available.

For exact intervals, overlap/simultaneity follows a declared tolerance rule. With uncertain bounds, a relation is verified only if it holds for all feasible bounds; if only some bounds satisfy it, label it possible. A semantic relationship such as “SFX emphasizes reveal” needs separate annotation and evidence even when timestamps coincide.

For `result_first_opening.v1`, a starting operational definition could be “a visibly prepared final dish is shown in the first declared opening window before substantive preparation instructions.” The window, exclusion of intermediate cooking stages, montage handling, and visibility requirements are frozen in the technique revision. The initial default window may be three seconds, but changing it creates a new definition or prespecified sensitivity analysis. Boundary-crossing or ambiguous cases are reviewed/unknown, not forced into binary exposure.

The detector consumes opening frames, supplied/generated speech tracks, subtitle/OCR tracks, caption text, measured color/motion/loudness, and editing/audio-event observations as separate lanes. It may request bounded denser sampling around a candidate. A bounded VLM may propose a dish reveal or cue relationship; literal source evidence and any review remain attached. Missing speech does not erase available visual evidence. Missing cues under sparse sampling must be reported as `not_detected_with_coverage`, not verified absence.

Record the annotation protocol, who/what could access outcomes, when that access occurred, and whether the exposure label was frozen before inspection. Confirmatory labels require outcome-blind annotation or a separately justified bias-control policy. Outcome-aware labels remain usable for disclosed exploration, but cannot be presented as outcome-blind independent confirmation merely by freezing them afterward; fresh blinded adjudication/new measurement validation may be needed. Model context must obey the same policy as human annotation.

### Versioned analytical features

`FeatureRecipe` stores eligible subject type, input definitions/versions, aggregation window and boundary convention, transformation, missingness policy, value type/unit, production dependency graph, and the intended analysis role. A recipe can describe a primitive median or an event combination: result-first opening **and** warm-color annotation **and** a spoken utility promise. It must not silently equate brightness with warmth or loudness with excitement.

`FeatureValue` stores subject revision, recipe revision, typed value or explicit unavailability, every input `EvidenceRef`, coverage, analyzer/adjudication identity, annotation/blinding lineage where relevant, and two temporal concepts:

- `measurement_time` / `content_valid_at`: when the underlying fact pertains to the content or world.
- `available_at`: earliest demonstrable availability for the stated analysis mode, plus `materialized_at`: when SocialDNA computed it.

Retrospective content reconstruction and historically available prediction are different modes. A later model can annotate immutable old content for a disclosed retrospective study, but cannot be represented as a predictor available before that model/annotation existed. Mutable captions, evolving tags, follower counts, and outcomes require actual as-of snapshots. Post-outcome audience reactions cannot become pre-publication content predictors. Data that lacks required lineage is ineligible for time-valid predictive claims, not assumed timely.

R3 persists event/query projections and recipes, reusing existing observations/timeline tasks. R9 later introduces bounded candidate-pattern specifications; a pattern is a first-class combination with temporal/conditional structure, not several disconnected technique→outcome edges.

## 3. Research sources, constructs, predictions, and alternatives

Begin R7 with a small reviewed corpus and at most a few relevant mechanism families. The corpus does not need an autonomous literature crawler or a comprehensive psychology ontology. Add papers only with verifiable bibliographic identity and an explicit relevance review. A retrieved title or model memory is not a reviewed finding.

| Contract | Required fields |
|---|---|
| `ResearchSource` | Bibliographic identity/DOI or stable URL, authors/year, version, access/retrieval provenance, permitted retained material, publication/correction/retraction status, review status. Store citation metadata and minimal permitted excerpts; do not assume permission to mirror full texts. |
| `StudyFinding` | Source revision and page/section/table locator; study design; population/context; manipulation or measured exposure; construct operationalization; outcome; reported effect/uncertainty when available; limitations; direction/null result; reviewer; evidence references. Multiple findings may come from one paper. |
| `PsychologicalConstruct` | Defined construct and exclusions; aliases; relevant measurement traditions; reviewed source references. Not a statement that a viewer possessed a hidden mental state. |
| `Operationalization` | Construct revision; observable indicator/manipulation; measurement instrument/procedure; validated population and limitations where known; expected direction; discriminating conditions; alternative interpretations. Clearly mark new, unvalidated project measures. |
| `HypothesisSpec` | Stable hypothesis identity plus immutable specification revision; question revision; statement, intended claim level, target population, and data needs in R1. The R7 mechanism subtype adds technique/exposure definition, proposed construct/operationalization, estimand/outcome/window, predictions, rivals, confounders, refutation/scope conditions, literature links and applicability review. R1 does not create fictitious literature or measurements to fill future fields. |
| `Prediction` | Testable contrast; response/outcome definition; expected direction or interval; eligible population/window; observation/analysis method; informative contrary result; limits of discrimination. Generic “engagement increases” is insufficient. |

Hypotheses may be associated-only, mechanism-proposing, or experiment-oriented. Hypothesizing a mechanism does not raise the claim level above hypothesis. Statistical association between a technique and an outcome is recorded separately from support for a mediator.

The shared question/hypothesis/assessment envelope is domain-neutral. Psychological constructs and operationalizations belong to the mechanism subtype, not every production, distribution, search or profile question. R7 records those domains as alternatives/context/unknowns within its bounded cooking slice. C1 later introduces their actual producers; official platform statements are not coerced into academic `StudyFinding` records.

For the cooking question, distinct proposed explanations include anticipated reward, sensory appeal, an information gap/curiosity, and cognitive fluency/clarity. Literature may support their plausibility in other settings. A reviewer must record whether its manipulation, population, and outcome actually transfer to cooking videos. Broad interest, expressed intention, or retention alone usually fails to distinguish these explanations. If all rivals predict the same available outcome, the assessment explicitly says **non-discriminating evidence** and proposes a better test.

### Evidence grades are not model confidence

Every assessment exposes separate dimensions rather than a composite percentage:

| Dimension | Stored assessment |
|---|---|
| Extraction reliability | Coverage, review agreement, boundary/span accuracy; a model probability only with calibration method, reference set, version, and scope |
| Literature relevance | Ordinal reviewed applicability and design limitations with cited findings; not paper counts as proof |
| Local empirical support | Effect estimate/interval, independent-unit counts, diagnostics, missingness and selected population; `insufficient_data` is valid |
| Generalization | Which creator/time/niche holdouts were actually tested; failed transfers and untested scopes |
| Causal identification | Observational/experimental design, assignment/identification assumptions, manipulation checks and violations |

An ordinal rubric records its definition and reviewer; it is not a calibrated likelihood. High inter-rater consistency validates annotation reproducibility, not a psychological mechanism. Provider logits, semantic similarity, cluster membership scores, effect sizes, p-values, and posterior probabilities must retain their different meanings and never share a generic `confidence` interpretation.

## 4. Audience-response evidence

Reuse permitted, minimized `comments` and their import provenance. Add collection context before drawing audience-level conclusions. A comment creation timestamp is a publication time, not a playback location. Do not add author identifiers merely to facilitate clustering; replies and known creator-authored status can be included only when supplied and permitted.

| Contract | Required fields and constraints |
|---|---|
| `AudienceCollection` | Source/post revisions; permission/retention policy; requested period; collection time; ordering/filter parameters; pagination/limit/truncation; supplied/eligible/known-total counts; sampling method; completeness `complete_for_declared_frame`, `partial`, or `unknown`; source lag when known; excluded/deleted/moderated coverage; raw artifact/provenance references. |
| `ReactionAnnotation` | Comment revision and quoted original Unicode character span; annotation-spec revision; language; label such as expressed intention/question/objection/reaction; negation/irony/ambiguity flags; proposed/reviewed/disputed state; method and span evidence. Normalized offsets cannot substitute for original-source positions. |
| `ReactionCluster` / membership | Versioned cluster definition/summary; collection scope; annotation/comment member revisions and roles; clustering method/version; membership score semantics; representative and contradictory excerpts; duplicate policy. Summaries cannot exist without resolvable members. |
| `ContentReactionLink` | Reaction revision, target post/event revision, evidence, method, alternatives, uncertainty, reviewer; origin `explicit_reference`, `human_interpretation`, or `model_proposal`. An explicit supplied “0:02” reference preserves its text and parsed location but does not prove when the writer watched or reacted. |

A collected-comment rate has an explicit denominator: for example, 8 of 120 eligible collected comments contain an expressed-intention annotation. It is not 8 of 120 viewers, nor an unbiased population estimate when ranked comments were sampled. Duplicate spam, threaded dependence, creator replies, multilingual performance, negation, and disagreement are reported or handled by declared policies. If the same comment is imported twice, distinct collection membership does not turn it into two independent reactions.

“I need to make this tonight” is expressed intention. Verified preparation, a follow, a save, and a purchase require separately sourced observations. A model-proposed link to the opening does not upgrade the comment into direct evidence that the opening caused intention. Annotation/retrieval can use all permitted text; causal claims cannot.

R4 introduces collection manifests, typed span evidence, memberships, and link services. A no-model reviewed-annotation import is the first working route. Optional classifiers/clustering follow the same contracts. Reannotation creates new revisions; cluster summaries/embeddings and dependent assessments are invalidated accordingly.

Implemented R4 uses `audience_record` locators for collection/reaction/cluster/link/set/
analysis revisions, in addition to the literal R1 comment-span citations. Curated
cluster membership is `supplied_membership_v1`, with membership scores explicitly
not supplied. No embeddings/assessments exist yet to invalidate. The actual
annotation/link import boundary is `import_into_application(app, AnnotationSet)`;
separate conceptual `annotate`/`link` design sketches are not executable APIs.

## 5. Behavioral metric contracts

Existing scalar metric snapshots remain append-only and usable. Extend them through a new versioned import/definition contract, not a reinterpretation of old values. R1 defines evidence adapters for existing snapshots; R5 supplies specialized series, denominator, signed-domain, cohort, and attribution producers.

| Contract | Required fields and constraints |
|---|---|
| `BehavioralMetricDefinition` | Namespaced platform/version key; subject type; count/duration/rate/index/net-change semantics; unit/domain; cumulative/period/series kind; numerator/denominator definitions; audience/play/session/cohort basis; inclusion/exclusion and replay/loop rules; source definition/reference; applicable aggregation and comparison rules. |
| `MetricMeasurement` | Subject/definition revision; value or availability reason; measurement window; effective source data cutoff where known; source revision; retrieval/collection time; source-reported generation time/lag where supplied; `available_at`; cohort/denominator references; provenance. Existing `observed_at` retains its legacy meaning, not automatically all these times. |
| `AudienceCohort` | Source-defined eligibility/filter specification; platform/account/content context; time bounds; dimensions such as geography/device only if supplied and permitted; aggregation/privacy limits; stable cohort definition hash. An unknown cohort is explicit and may prevent comparison. |
| `MetricSeries` | Subject/media revision; definition; measurement window; cohort and denominator; coordinate kind; bin convention and resolution; source completeness; missing bins; interpolation/rebinning policy; source artifact and provenance. |
| `MetricBin` | Series revision and ordinal; source coordinate start/end or source point; typed value/availability; bin-specific denominator if supplied; source locator; optional converted media interval with transformation provenance. Unique ordinal/coordinates, ordered valid bounds, and no unmarked overlap. |
| `AttributionObservation` | Observed conversion definition/count/value; supplied touchpoint/post/campaign linkage; attribution source/method/model; lookback/measurement windows; allocation/credit weights; denominator when relevant; deduplication key and provenance. Missing attribution is not imputed. |

### Coordinate and denominator rules

- Video retention may be supplied as exact media intervals, normalized progress, or a fixed set of provider points/bins. Preserve original coordinates and source resolution. Convert normalized coordinates only against a known matching media revision/duration. Do not manufacture millisecond precision or infer values between coarse bins by default.
- A retention definition must specify whether the value is a share of unique viewers, plays, starts, or another source denominator. A repeat-watch ratio may exceed one and need not be monotonic. Only definitions that truly represent bounded probabilities get `[0,1]` constraints; survival models require justified semantics, not the word “retention.”
- Completion requires the source’s completed-event threshold and eligible-start/play denominator. Watch time divided by duration is not automatically completion probability. Rate components need compatible cohorts, windows, and definitions; mismatches block derivation.
- Missing, not permitted, unavailable, failed, not applicable, and source-suppressed are distinct states. A missing bin is not zero. Incomplete or unknown source freshness constrains age-aligned comparisons even when retrieval time is recent.
- Signed net follower/account growth has a signed numeric domain in the new definition, with exact endpoints or a supplied period measurement. Keep the old nonnegative import schema valid as version 1; do not silently allow negative count snapshots. Account growth remains account-scoped. Difference between endpoint snapshots is a derived measurement, not post attribution.
- Reported conversions retain the provider/export attribution model and its assumptions. Fractional credits, overlapping windows, and multi-touch observations require deduplication/aggregation rules. Source-reported attribution is not a causal effect estimate; the nearest post is not assigned credit by default.

Metric compatibility is a service decision recorded in the analysis manifest: matching definition revisions or a reviewed explicit mapping, aligned post ages/windows, compatible denominators/cohorts, and known source freshness. Different platforms' “views” remain different metrics unless a justified harmonization is declared. When retention is absent, a permitted seven-day views/save outcome may answer a **different question**, never act as a silent proxy for early retention.

Implemented R5 uses explicit v2 JSON imports and exact-reference definitions/cohorts;
it does not implement reviewed cross-account mappings or implicit rebinning. Retention
comparisons are descriptive within an exact account cohort/grid, with no independent-
viewer sample size or binomial interval. Exact `behavioral_record` citations share the
universal resolver, current eligibility and R1 research report path. R2 specifications
do not silently reinterpret their old scalar outcomes as behavioral measurements.

## 6. Research lifecycle and revision semantics

| Entity | Stable identity and immutable revision content |
|---|---|
| `ResearchQuestion` | Question identity; scope/target population, unit, data-access frame, estimand/outcomes/windows, inclusion/sampling policy, intended exploratory/confirmatory role. Administrative status is an audited projection, not a rewrite of its original specification. |
| `Hypothesis` | Identity under a question; successive `HypothesisSpec` revisions. Changing a mechanism, outcome, population, or test is a new specification, not an undisclosed retry of the old hypothesis. |
| `ResearchAssessment` | Hypothesis/question revisions; analysis/spec/model/recipe versions; frozen data/split/evidence manifests; literature/rival assessments; effect/diagnostic/result references; support disposition; dimensions of evidence quality; limitations; prior assessment and change rationale. |
| `Finding` | Stable claim identity; immutable revisions with scope/estimand, claim level, statement, assessment/result references, support/contradiction evidence, limitation references, and predecessor/supersession reason. New evidence can narrow, weaken, or reject the statement. |
| `DependencyManifest` | Exact source, entity/evidence, technique/recipe, cohort, model, study, analysis and policy revisions used; role; selection query/version; completeness/watermark of the observed data universe; new-versus-reused independent-unit membership. |
| `ExperimentRegistration` / `ExperimentOutcome` | Registered design/assignment unit, contrasts, primary/secondary outcomes, sample/analysis/stopping policies, predicted rival differences, measurement/permission/ethics requirements; later allocation/exposure/outcome data, deviations, diagnostics, analysis and evidence references. |

Assessment support dispositions are `insufficient_data`, `inconclusive`, `supported_in_scope`, `weakened`, `contradicted_in_scope`, and `rejected_in_scope`. They refer to a defined prediction/specification, not global psychological truth. Statistical non-significance alone does not prove absence or mandate rejection. Scope or uncertainty changes can weaken a claim even without a sign reversal. Rejection requires a recorded rubric/criterion and evidence; broadening a rejected specification creates a new exploratory revision.

`current`, `stale`, `withdrawn`, and `superseded` are separate eligibility/freshness states, not evidence grades. Existing frozen analyses remain historical objects. Saving a new assessment never recomputes or overwrites them.

### Trigger → reassess → explain

1. Registration freezes accessible sources, population policy, exposure/outcome definitions, rival predictions, and the search/validation plan. Unknown data needs are explicit.
2. Evaluation resolves and freezes eligible evidence, writes every attempted analysis/result including null/failed tests, validates the claim, and saves the assessment and finding revision atomically with index work.
3. New eligible posts, source corrections, changed annotations/recipes, literature corrections, experiment results, or permission withdrawal identify affected assessments through dependency links **and the stored population-selection manifest**. The latter detects newly eligible rows that were not prior dependencies.
4. Mark the assessment projection stale with a reason; queue or suggest reevaluation. Basic imports do not silently rerun expensive studies or repeatedly claim new confirmations.
5. Reevaluation creates a new frozen manifest, explicitly separates reused and genuinely new units, preserves the exploration/test family and stopping history, and applies the registered sequential/confirmation policy. A changed specification is disclosed as such.
6. Save the new assessment and finding revision with a machine-readable comparison: support strengthened/weakened/unchanged, effect/scope/uncertainty changes, changed inputs, and remaining rivals. Historical retrieval remains possible; current retrieval defaults exclude ineligible/withdrawn support.

R1 implements minimal question/hypothesis registration and retrieval without evaluation. R7 extends registration for mechanism research and implements evaluate plus revision-specific retrieval and one immutable assessment path. R8 implements triggers, staleness, reevaluation/history, and explicit weakening/rejection. R9 extends bounded discovery; R10 implements registered prospective experiment outcomes. R7 may recommend an experiment brief, but a recommended brief is not a registered or executed experiment.

Implemented R7 refinement: `research prepare` adds a typed `ResearchProtocol` over exact R1 question/hypothesis revisions instead of changing the v1 draft importer. All registered rivals must be retained. `investigation_service.evaluate` consumes existing version-2 frozen analyses and their original attempts/holdouts; it does not fit a second engine or claim independent confirmation. Human source/applicability review is a trust boundary, not automated citation verification. See [actual schemas and claim gates](psychological-research.md).

Implemented R8 refinement: [incremental research](incremental-research.md) uses
append-only deduplicated change events, bounded selection/dependency watches,
hash-pinned request plans and transactional checkpoints. It supports exploratory
cumulative reevaluation only, not a new sequential-confirmation design. Source or
semantic changes requiring human review do not automatically repin references.
Old comparison runs without saved groups retain fixed post membership. Current
hydration rejects stale/superseded assessment-derived documents; exact history
remains subject to permission and erasure gates. Assessments/findings preserve
their R7 identity rules; explicit immutable links connect successive records.

A randomized creative manipulation can, if design and data checks permit, support a causal claim about that manipulation in its tested scope. It does not identify the psychological mediator by itself. Mechanism claims additionally need discriminating measurements/manipulations, appropriate mediation/identification assumptions, and limitations. No automatic promotion occurs because an experiment record exists.

### Withdrawal and reproducibility

Removal/redaction propagates to excerpts, summaries, artifacts, representations, graph projections, and report eligibility. A tombstone can retain non-sensitive identity/hash and the reason history was degraded, subject to policy. Do not retain forbidden raw material merely to promise exact reproduction. Historical manifests remain explainable, but reports must state when source withdrawal makes an old finding unverifiable or no longer reportable. These lifecycle rules share the deletion/outbox safeguards in ARCHITECTURE.md and migration-strategy.md.

## 7. Contract acceptance gates

No milestone can substitute successful schema validation for empirical research validity. Required contract-level fixtures include:

- An ambiguous reveal straddling the opening-window boundary, a discontinuous montage, a point cut, and a simultaneous audio event with uncertain onset.
- A photograph, a paper excerpt, a comment span, and a statistical term cited without fabricated video intervals.
- A top-ranked partial comment collection, duplicated comment memberships, an ironic intention, and an unsupported moment link.
- A source-lagged snapshot, missing denominator, repeat-watch value above one, signed account growth, and unassigned conversions.
- A hypothesis with multiple observationally indistinguishable rivals and an explicitly insufficient-data conclusion.
- An initial supported-in-scope finding followed by new failures that weaken or contradict it, while old reports preserve exact eligible revisions.
- A withdrawn source whose stale vector work cannot restore it and whose dependent conclusion loses eligibility or support.

The corresponding milestone tests must also cover real service calls, CLI envelopes, persisted reloads, and human/imported annotations without optional model dependencies. Scientific validation datasets and calibration studies remain separate deliverables; their existence cannot be inferred from passing software tests.

## 8. Production and growth-context contracts

C1-A is implemented in `0.0.13`: `ProductionAnnotationSet` schema `2.0`, 16
technique-specific professional definitions and eight pinned recipes. See
[actual formats and conservative missingness rules](production-evidence.md).
V1 remains frozen. C1-B (`0.0.14`) implements `ContextExport` with publication,
publishing-window and dated-trend records, exact `ContextLocator` citations and frozen
`PublicationReportSpec` reports. See [working fields and boundaries](publication-context.md).
C1-C (`0.0.15`) adds `PlatformExport` and `PlatformReportSpec` with distinct official
document/statement, source-capability and observed-distribution types on the same
registry. See [source review, time windows and lane boundaries](platform-research.md).
C1-D (`0.0.16`) implements `ProfileExport` snapshots/reviews/source event definitions/
funnel contexts and `ProfileReportSpec`. Exact public fields and qualitative judgments
remain separate from R5 account-period counts, qualified rates and source attribution.
Native per-link/campaign metric subjects are not synthesized from account aggregates.
See [actual semantic guards and limits](profile-conversion.md).
The [four-area audit](intelligence-capability-audit.md#2-shared-extension-architecture--planned-not-implemented)
defines their coverage; [PLAN.md §19](../PLAN.md#19-c1--versioned-production-and-growth-context-evidence)
assigns writers, dependencies and tests. Reuse shared revision/evidence identity
rather than creating a new research engine.

| Planned contract family | Required extension and invariant |
|---|---|
| C1-A professional technique/rubric and recipes | Explicit new annotation/definition version beyond R3's ten-label vocabulary; shot/region/time/coverage, outcome-blinding and review provenance; measured proxies distinct from interpreted craft. Pinned pacing, subtitle, music/transition and interaction recipes preserve exact supplying revisions and missingness. Existing v1 semantics remain frozen. |
| C1-B publication/metadata context | Actual post/account refs, native format/language, title/caption/tag/keyword and thumbnail variants; capture/known-validity/publication clocks; original offset and supplied IANA timezone; account observation-window completeness; dated trend/query sources. Exact title/static-asset locators, not caption or fake-video reuse. |
| C1-C platform surfaces/documents/statements | Platform/surface/format/market/language/cohort/objective and source versions; official URL/publisher/content hash/retrieval and known effective dates, excerpt locator, review/supersession. Documented statements, observed associations and experiments keep distinct evidence types. |
| C1-C distribution observations | Typed actual subject, source-defined metric/denominator/cohort/window, source traffic code plus versioned surface mapping, organic/paid/unknown context, eligibility/availability/lag. Search traffic, impressions, reach and views are not interchangeable; unknown source stays unknown. |
| C1-D profile snapshot/rubric | Actual account revision, typed handle/name/bio/photo/ordered links/pins/CTA fields, field presence and source-validity/capture clocks. Exact field/link/pin/static-image evidence; owner declarations distinct from interpreted positioning/pillars/consistency. |
| C1-D funnel and outcome context | Defined stage/branch, actual subject/profile variant/link/campaign when supplied, compatible cohort/windows/uniqueness/denominators and deduplication/attribution. No individual path inferred from aggregates, no nearest-post follower credit, no invented private conversion rate. |

Each family requires its canonical writer, FK/kind/ownership validation, typed evidence resolver, idempotent reader/report and eligibility/erasure tests before memory indexes it. Profile/link/campaign metric subjects extend the current post/account registry only with real producers; a free-form campaign label is not a registered subject. Low-volume specifications remain validated documents; query projections are first-use additions. U1 supplies real static-image evidence; R8 tracks revisions once writers exist; R9 analyzes scoped comparisons and R10 produces qualified recommendations/experiment outcomes. U2 cannot expose planned contracts as working commands.
