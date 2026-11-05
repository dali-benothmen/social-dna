# SocialDNA architecture and intelligence capability audit

Date: 2026-11-05

Status: audit findings and proposed revisions; not an approved implementation plan.

## Overall assessment

**The architecture requires revisions before implementing the next intelligence milestone.** It provides a useful media-analysis and reproducible-statistics foundation, but it does not yet specify a complete psychological and behavioral research engine.

The main problem is not the choice of SQLite, Qdrant, or NetworkX. It is the missing connective layer between:

- Observable creative decisions and psychological constructs.
- Content segments and audience responses.
- Statistical results and scoped research claims.
- Existing findings and subsequent evidence that supports, weakens, or contradicts them.

I reviewed both design documents, the related documentation, actual migrations, processing services, statistical code, and tests. Small read-only synthetic checks also exposed limitations in the existing analytics.

No application code, `PLAN.md`, or `ARCHITECTURE.md` was changed while conducting this audit. This document saves the audit response at the user's request.

## A. Capability coverage matrix

“Partially supported” below means concrete building blocks exist, but the complete requested capability is not adequately specified or implemented. **None of the six broad intelligence capabilities is fully supported end-to-end.**

| Capability | Coverage | Evidence in the existing system | What is still required |
|---|---|---|---|
| Deep psychological mechanism discovery | **Partially supported; scientific grounding missing** | The [psychology design](../ARCHITECTURE.md#L449) specifies cues, taxonomy-based hypotheses, alternatives, and adjudication. | Research-source records, construct operationalization, falsifiable predictions, competing-mechanism evaluation, and mechanism-specific validation. |
| Content → audience responses → performance | **Partially supported; relational audience analysis missing** | Media features join scalar performance snapshots. Comments are imported, but the [comment contract](../src/socialdna/ingestion/tabular.py#L86) contains no reaction annotations or segment links. | Comment sampling manifests, reaction/intent annotations, evidence-linked content associations, retention curves, and attribution semantics. |
| Cross-creator and cross-niche intelligence | **Partially supported, with consequential limitations** | Baselines, interactions, clustered methods, and uncertainty exist. However, [matching requires the same creator](../src/socialdna/analytics/cohorts.py#L48). | Separate within-creator and cross-creator comparison designs, historical baselines, overlap diagnostics, identifiable hierarchical models, and held-out-niche evaluation. |
| Multivariable creative-pattern discovery | **Partially supported; discovery largely missing** | Explicit pairwise interactions exist, but the [feature contract allows only six primitive predictors](../src/socialdna/domain/research.py#L58). | Semantic creative features, temporal combinations, bounded candidate discovery, nonlinear methods, stability analysis, and independent confirmation. |
| Persistent psychological/performance intelligence | **Partially designed; research memory unimplemented** | Canonical SQLite records and frozen analyses exist. Vector/graph design is substantial, but [runtime status explicitly reports retrieval unimplemented and graph deferred](../src/socialdna/storage/health.py#L143). | Universal evidence references, qualified graph relationships, revision-aware indexing, and canonical research entities. |
| Learning and revising conclusions | **Partially designed; revision workflow missing** | The design includes finding supersession; current code [reproduces frozen analyses](../src/socialdna/application/performance_service.py#L565). | Stable hypothesis identities, successive assessments, dependency tracking, reevaluation triggers, contradiction/rejection history, and experiment-result integration. |

The claim-level distinction—observation, hypothesis, association, causal finding—is appropriate. Its existence as a vocabulary does not establish the workflows and validation rules needed to enforce it.

## B. Architectural weaknesses

### 1. The psychology engine remains too close to evidence-backed labeling

The proposed three-pass engine is:

1. Extract cues.
2. Ask a reasoner to propose taxonomy mechanisms.
3. Validate references, apply restrictions, and seek counterexamples.

That can produce useful hypotheses. It does not yet explain how SocialDNA would discover and evaluate mechanisms rather than attach plausible explanations to observed content.

The schema lacks a concrete distinction between:

- **Creative technique:** showing the finished dish immediately.
- **Psychological construct:** anticipated reward or curiosity.
- **Construct measurement:** a validated questionnaire, experimental manipulation, or other justified indicator.
- **Observed response:** continued watching, a save, or an expressed intention.
- **Business outcome:** subscription or purchase.

These are not interchangeable.

For example, curiosity research has separately measured stimulus conditions, reported curiosity, and behavior. Such research can justify a hypothesis, but cannot establish that a particular cooking-video opening activated that mechanism. [Kang et al., 2009](https://www.cmu.edu/dietrich/sds/docs/loewenstein/WickCandleLearning.pdf).

The existing architecture also has no structured literature model: no study design, population, operationalization, limitations, contradictory findings, or applicability assessment.

**Important:** human agreement on a “curiosity” label measures annotation consistency. It does not establish that curiosity explains the observed performance.

### 2. A shared clock is not yet multimodal semantic understanding

The common millisecond timeline is a sound foundation. However, aligned visual, audio, and text lanes do not automatically identify relationships such as:

> A reveal coincides with a sound effect, follows a spoken promise, and precedes a retention change.

There is no explicit creative-event or cross-modal relationship model.

Current performance analysis reduces media to opening-window medians of motion, brightness, and loudness, plus duration, caption length, and publication hour. “Brightness” is not “warm lighting”; loudness is not “energetic narration.” See the [implemented feature registry](../src/socialdna/application/performance_service.py#L29).

The existing reasoning task consumes selected images and text, not the full measured audio/visual feature set, audience reactions, or analytics. Its [prompt explicitly prohibits audience-psychology and performance claims](../src/socialdna/providers/reasoning.py#L16). That is an appropriate current safety boundary, but it confirms that the requested research capability does not already exist.

Sparse sampling also creates an important uncertainty: **not detecting a cue in selected frames is not evidence that the cue was absent.**

### 3. Comments are stored, not integrated into behavioral research

The present system cannot trace:

> Segment → creative technique → mechanism hypothesis → expressed audience reaction → performance evidence.

Comments have post relationships, but no implemented:

- Questions, objections, or intention annotations.
- Quoted supporting spans.
- Versioned reaction clusters.
- Explicit versus inferred segment references.
- Collection coverage or sampling metadata.
- Link between reaction prevalence and a defined performance population.

Comment publication time is not a playback timestamp. An inferred semantic connection to an opening must not be presented as an observed timestamped reaction.

Likewise, “I need to make this tonight” is an **expressed intention**, not verified recipe use or conversion. Research distinguishes changes in intentions from subsequent behavioral changes; SocialDNA should preserve that distinction. [Webb and Sheeran, 2006](https://pubmed.ncbi.nlm.nih.gov/16536643/).

### 4. Behavioral metrics are more expressive than scalar counters

The generic metric schema can store supplied watch-time, completion, follower, or conversion values. That is useful, but specialized support is incomplete.

Missing contracts include:

- Retention curves and media-relative bins.
- Denominator and audience-cohort definitions.
- Replays, loops, skips, and aggregation semantics.
- Conversion attribution methods and windows.
- Account-level growth analysis and time-valid account-size covariates.

Current analytics accepts only post-scoped outcomes, even though account snapshots can be imported. The blanket nonnegative-value restriction also cannot directly represent signed net follower growth. See the [metric contract](../src/socialdna/ingestion/tabular.py#L97) and [post-only outcome validation](../src/socialdna/application/performance_service.py#L59).

### 5. Existing comparative statistics need remediation

Read-only checks confirmed three significant limitations.

**Cross-creator matching cannot occur.**
The matching algorithm requires creator equality. Distinct-creator groups therefore produce zero matched pairs, regardless of sample size. This is documented, but does not satisfy the requested cross-creator capability.

**Cross-niche fixed-effect models can be structurally unidentifiable.**
OLS/Poisson designs include both creator fixed effects and niche dummy variables. When niche is constant within creator, niche is absorbed by creator identity. A synthetic example with 600 posts and 20 creators fitted with one niche, but became rank-deficient when otherwise identical creators were assigned to two niches. The [design construction](../src/socialdna/analytics/statistics.py#L153) needs revision—not removal of its rank safeguard.

**The baseline is retrospective, not historical.**
The [baseline implementation](../src/socialdna/analytics/baselines.py#L32) uses other posts in the selected cohort, including later posts. In a synthetic example, adding future posts changed an earlier post’s relative score from 2.0 to 0.2.

The calculation is valid as retrospective normalization. It does not answer “Did this outperform the creator’s historical baseline at publication?”

Other gaps include publishing-period controls, changing audience size, paid distribution, post-level niche assignments, covariate balance, and missing-confounder sensitivity. Cluster-aware uncertainty does not itself remove confounding.

### 6. Validation does not yet validate the requested discoveries

Two mismatches matter:

- The future-feature check examines optional `feature_available_at` metadata, but production population construction does not supply that metadata.
- Predictive validation always fits a main-effect Ridge model—not the requested interactions or selected statistical model. See [validation logic](../src/socialdna/analytics/validation.py#L57).

Consequently, a Ridge holdout score cannot validate a discovered interaction.

There is also no implemented protection against identical or near-identical videos appearing under different post/creator IDs across validation splits, nor a held-out-niche test.

### 7. The universal evidence design does not match the implemented schema

The architecture says an evidence item may represent media, metrics, source records, and other research evidence.

Actual [evidence rows require media, a media task, and a nonempty media interval](../src/socialdna/storage/migrations/versions/v0002_timeline.py#L143).

That does not naturally accommodate:

- A comment excerpt.
- A study finding.
- An account metric.
- A statistical result.
- An experiment outcome.

Current performance reports use separate metric citations. That preserves provenance, but it is not yet the common evidence contract promised for research and graph traversal.

This should be resolved before Milestone 2 hardens indexing and graph interfaces. Dummy media records or invented timestamps would be the wrong workaround.

### 8. Persistent reports are not a continuous research process

Frozen analyses are valuable. The missing part is the process that decides what new data means for an existing hypothesis.

The design does not sufficiently specify:

- Stable hypotheses versus successive evaluations.
- What invalidates an evaluation.
- How new evidence is assessed without double-counting old evidence.
- How scope changes or contradictions are recorded.
- How a hypothesis becomes inconclusive, rejected, or superseded.
- How repeated exploratory testing is tracked across sessions.

Per-run FDR correction does not account for an untracked sequence of changed features, cohorts, outcomes, and repeated looks at overlapping data.

### 9. Documentation and acceptance criteria overstate readiness

[Milestone 5](../PLAN.md#L565) combines taxonomy, hypothesis generation, statistical discovery, hybrid querying, recommendations, and experiments into one broad milestone. Its acceptance criteria do not require the full “100 videos → additional evidence → weakened/revised finding” workflow.

There is also documentation drift: [storage documentation](storage.md#L20) still identifies revision `0003_enrichment` as current and metrics as deferred.

The test suite demonstrates substantial engineering correctness. It does not yet demonstrate the intelligence capabilities under review.

## C. Proposed improvements

These are proposed revisions, not implementation changes.

### 1. Establish a universal evidence and entity-reference contract

- **Modules:** `domain/evidence.py`, research contracts, storage migrations/repositories, reporting, and planned graph services.
- **Data model:** a canonical evidence identity with validated subtype locators for media intervals, comment spans, metric snapshots/bins, statistical terms, study excerpts, and experiment outcomes. Preserve existing evidence IDs.
- **Methods/storage/dependencies:** typed resolution and eligibility checks in SQLite; existing Pydantic/SQLAlchemy are sufficient. Require valid subtype fields rather than making every locator optional.
- **Tests:** nonexistent targets, wrong source/run, non-media citations, withdrawn evidence, and migration compatibility.
- **Milestone:** prerequisite before Milestone 2 and psychological research.

### 2. Add semantic creative events and versioned feature materialization

- **Modules:** proposed `domain/creative.py`, event/cue analyzers, timeline services, and performance feature construction.
- **Data model:** `creative_events`, technique definitions, event relationships, feature specifications, and feature values linked to exact evidence and analyzer versions. Include boundary uncertainty and sampling coverage.
- **Methods/storage/dependencies:** bounded semantic detection, temporal joins, event-directed resampling, and declared aggregations. Optional VLMs can propose candidates; existing media tools can verify timing.
- **Tests:** result-first versus ingredient-first openings, simultaneous cut/SFX events, missed sparse cues, offsets, boundary accuracy, and multimodal ablations.
- **Milestone:** early research foundation, initially limited to a few well-defined techniques.

Do not force an unfamiliar pattern into a psychological taxonomy. “Unclassified creative pattern” must be a valid result.

### 3. Introduce literature-backed, falsifiable mechanism hypotheses

- **Modules:** proposed literature/operationalization services and expanded psychology contracts.
- **Data model:** reviewed research sources, study findings, psychological constructs, operationalizations, hypothesis specifications, rival explanations, predictions, and adjudications.
- **Methods/storage/dependencies:** begin with a curated reference corpus—not autonomous literature mining. Store study context, design, limitations, supporting/contradictory findings, and relevance to the present question.
- **Tests:** fabricated citations, irrelevant studies, unsupported mechanism claims, rival explanations, and construct-validity review.
- **Milestone:** first psychology slice, before broad recommendation generation.

Keep separate assessments for extraction reliability, literature relevance, local statistical support, generalization, and causal identification. One “confidence percentage” cannot summarize these faithfully.

### 4. Build an audience-response pipeline with sampling provenance

- **Modules:** proposed `audience/{collections,annotations,clusters,linking}.py`, imports, evidence resolution, and reports.
- **Data model:** collection manifests, reaction annotations with quoted spans, cluster memberships, and content–reaction links. Record whether a link is explicit, human-adjudicated, or model-proposed.
- **Methods/storage/dependencies:** classify expressed questions, objections, intentions, and reactions; retain negatives and representative examples. Use permitted, privacy-minimized data.
- **Tests:** top-ranked-only samples, incomplete collection, sarcasm, negation, multilingual text, repeated comments, creator replies, and unsupported segment anchors.
- **Milestone:** early audience research slice.

Reports must distinguish “percentage of collected comments” from “percentage of viewers.” Even complete comments are a self-selected audience subset.

### 5. Define temporal behavioral metrics and attribution contracts

- **Modules:** metric imports, proposed retention/attribution analytics, timeline adapters, and reporting.
- **Data model:** metric series/bins with media coordinates, observation windows, source definitions, denominators, audience cohorts, availability, and replay semantics; explicit attribution observations for reported conversions.
- **Methods/storage/dependencies:** as-of account joins, compatible curve alignment, and appropriately scoped derived outcomes. NumPy/SciPy/pandas remain sufficient initially.
- **Tests:** delayed exports, incompatible denominators, coarse bins, looping/replay values, missing attribution, signed growth, and multiple posts contributing to account changes.
- **Milestone:** define contracts early; implement richer analyses only when suitable data exists.

Do not infer that the nearest published post caused account growth.

### 6. Repair comparative analytics and define the estimand

- **Modules:** existing baselines, cohorts, statistics, validation, population construction, and research specifications.
- **Data model:** explicit baseline policies/reference populations, as-of covariates, sampling frames, comparison designs, transformation specifications, and versioned context assignments.
- **Methods:** separate within-creator effects, cross-creator contextual comparisons, and cross-niche generalization. Use identifiable fixed/hierarchical models, appropriate outcome families, overlap/balance diagnostics, and prior-history baselines.
- **Storage/dependencies:** persist exact reference rows and covariate versions in SQLite; the existing statistical stack supports most initial repairs.
- **Tests:** future-data baseline invariance, nested creators/niches, within/between-creator confounding, poor overlap, and duplicate-media leakage.
- **Milestone:** Milestone 4 remediation before discovery relies on these results.

Simply removing the same-creator matching restriction would not solve cross-creator confounding.

### 7. Specify bounded multivariable discovery and independent confirmation

- **Modules:** planned discovery services, feature registry, statistics, and validation.
- **Data model:** candidate-pattern specifications, search families, candidate attempts—including null results—and exploratory/confirmatory partitions.
- **Methods:** start with declared interactions and regularized nonlinear terms. Later add bounded tree/boosting exploration if justified. Validate the actual transformation/model pipeline, with creator, time, duplicate-content, and niche holdouts appropriate to the claim.
- **Storage/dependencies:** persist candidate-generation lineage and every tested specification. Existing scikit-learn/statsmodels are adequate initially.
- **Tests:** pure-interaction effects, U-shaped relationships, correlated features, null searches, selection leakage, and patterns that fail in another niche.
- **Milestone:** after reliable semantic features and repaired comparisons.

Predictive importance or model explanations must not be presented as psychological or causal identification.

### 8. Implement revision-aware memory and research assessments

- **Modules:** planned memory services, research questions/findings, a reevaluation service, and experiment contracts.
- **Data model:** stable hypothesis identities; immutable specification, evaluation, and finding revisions; dependency links; stale markers; supporting/contradictory evidence; experiment registration and outcomes.
- **Methods:** new data identifies affected hypotheses, creates a new frozen assessment, compares it with prior assessments, and records the reason for changed support or scope. Distinguish reused data from independent confirmation.
- **Storage/dependencies:** SQLite remains authoritative. Qdrant indexes versioned representations; NetworkX projects qualified relationships. No additional database product is necessary.
- **Tests:** new data weakens or reverses a finding, historical reports remain reproducible, obsolete index work cannot resurrect deleted evidence, and experiments do not automatically promote claims to causal.
- **Milestone:** minimal revision semantics before memory implementation; complete reevaluation workflow before broad discovery/recommendations.

Proposed interfaces should include `research register`, `evaluate`, `reevaluate`, `history`, and revision-specific retrieval—not only `discover` and `show`.

For graph representation, a multivariable pattern needs its own entity. Three independent technique→outcome edges cannot faithfully represent one conditional three-feature combination.

## D. Feasibility and limitations

### Feasible with available technology

A bounded local research engine can realistically:

- Extract and annotate observable creative events.
- Align modalities and preserve uncertainty.
- Cluster permitted comments into expressed-response categories.
- Compare appropriately defined outcomes.
- Generate literature-grounded, falsifiable hypotheses.
- Retrieve similar moments and counterexamples.
- Revise scoped findings as evidence changes.

This does not require a new database stack or a universal autonomous research agent.

### Restricted data is a first-class limitation

Public competitor metrics are not equivalent to creator-authorized analytics.

- YouTube owner reports require authorization. Retention uses media-relative dimensions; its documented bins are not arbitrary millisecond measurements. Its audience-watch ratio can exceed one because of repeat viewing, so it must not automatically be treated as a monotonic survival curve. [Owner reports](https://developers.google.com/youtube/analytics/channel_reports), [retention dimensions](https://developers.google.com/youtube/analytics/dimensions#Audience_Retention), [metric definitions](https://developers.google.com/youtube/analytics/metrics#Audience_retention_metrics).
- Instagram access depends on the API path, professional-account eligibility, permissions, and authorization; private competitor insights cannot be assumed. [Meta’s official collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).
- TikTok’s Research Tools exclude ordinary creator/commercial eligibility, and archived statistics can lag. Observation timestamps alone therefore do not guarantee freshness. [TikTok Research FAQ](https://developers.tiktok.com/docs/en/research-api-faq).

A local/export-first approach remains appropriate, but missing behavioral data must constrain the question—not be replaced by model-generated estimates.

### Statistical support needs suitable populations

There is no universal “100 videos is enough” threshold. Adequacy depends on independent creators, feature variation, outcome variability, missingness, and the number of relationships investigated.

Three creators can support a useful descriptive case study. They generally cannot establish broad cross-niche generalization.

Representative inclusion of successful, ordinary, and unsuccessful posts must be an explicit collection policy. Semantic top-K retrieval must help propose candidates, not define the population used to estimate their effects.

### Creative effects and psychological mechanisms require different evidence

A randomized comparison might identify an effect of a result-first opening on retention. It would not, by itself, establish whether curiosity, reward anticipation, clarity, or another mechanism mediated that effect.

Mechanism claims require additional measurement or experimental discrimination and explicit assumptions. Observational comments and analytics can strengthen or weaken explanations; they cannot uniquely identify hidden psychological processes.

### Privacy and evidence withdrawal affect research integrity

A deletion/redaction policy must cover raw exports, comments, excerpts, summaries, embeddings, graph projections, and saved reports. Removing evidence should mark affected findings as degraded or requiring reassessment—not leave their support unchanged.

## E. Revised implementation priorities

I recommend preserving completed infrastructure while changing the next delivery sequence.

| Priority | Working deliverable | Acceptance gate |
|---|---|---|
| 1. Research-contract revision | Evidence types, creative events, constructs, audience/metric semantics, and assessment lifecycle agreed | One example can be represented without fabricated timestamps or overloaded confidence fields |
| 2. Analytics remediation | Historical baselines, explicit comparison designs, identifiable cross-niche models, production lineage | Synthetic confounding, future-data, matching, and leakage cases behave correctly |
| 3. Revised Milestone 2 | Version-aware SQL/FTS/vector/graph retrieval over actual canonical producers | Cross-video moment retrieval returns exact evidence; stale/deleted sources are excluded |
| 4. First intelligence vertical slice | One technique, reviewed mechanism alternatives, audience reactions, comparable performance, counterexamples | Produces an association or insufficient-data result—not merely persuasive explanation |
| 5. Continuous research | New evidence creates a new assessment and can weaken/reject the earlier conclusion | Initial finding → additional representative data → justified revision, with history preserved |
| 6. Broader discovery and experiments | More techniques, nonlinear combinations, niche transfer, prospective experiments | Independent confirmation, appropriate uncertainty, and qualified causal reporting |

The first intelligence slice should use the cooking example narrowly:

> Detect a result-first opening → preserve its multimodal evidence → propose competing explanations → identify expressed-intention comments → evaluate comparable outcomes → retrieve failures → recommend a discriminating experiment.

It should demonstrate at least one weakened or rejected hypothesis, not only a successful explanation.

The foundation needs evidence identity, temporal semantics, feature lineage, sampling policy, research revisions, and claim-validation contracts now. Broader taxonomies, sophisticated nonlinear models, image embeddings, autonomous literature search, distributed workers, and additional platform adapters can follow without requiring a new architecture.

## Conclusion

**The current architecture is not ready for the next intelligence implementation unchanged.**

Its storage ownership, media timeline, provenance, immutable metrics, and reproducible analyses are worth retaining. However, the psychological, audience-response, cross-creator, and continuous-learning contracts require revision, and existing comparative analytics needs remediation.

My earlier descriptions of completed milestones should not be read as evidence that these broader intelligence capabilities are already supported. Before proceeding, the plan should be revised around falsifiable research questions, typed evidence relationships, representative populations, and an explicit evaluation-and-revision lifecycle.
