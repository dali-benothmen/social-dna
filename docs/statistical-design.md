# Statistical design and validation

Status: the bounded R2 comparison/lineage/validation path is preserved in `0.0.7`, with explicit R3 [creative-recipe joins](creative-analysis.md); see [operations and supported limits](versioned-analytics.md). This document also specifies later capabilities, including broader discovery in R9; it is not a claim that all designs below are available. Existing unversioned analyses retain their original semantics. See [architecture](../ARCHITECTURE.md), [research contracts](research-contracts.md), [roadmap](../PLAN.md) and [cooking use case](research-use-case.md).

This specification defines analytical eligibility and interpretation. Passing a software test, obtaining a full-rank fit, or exceeding an engineering sample threshold does not demonstrate construct validity, causal identification, adequate power or external validity.

## 1. The analysis contract

Every new analysis-specification revision freezes:

| Field | Required meaning |
|---|---|
| Question and estimand | Target population; exposure/contrast; outcome definition, unit and window; descriptive association, predictive target or identified causal contrast. |
| Unit and dependence | Post/media/account/experiment-assignment unit; creator clusters; repeated snapshots/windows; duplicate-content families; audience cohort when known. |
| Selection | Canonical SQL population policy and exact input IDs, filters, permission scope, exclusions and coverage. Semantic retrieval is not the sample frame. |
| Time policy | Publication/context cutoff, feature availability mode, outcome maturity/window, baseline lookback, source lag and as-of joins. |
| Exposure/features | Exact recipes, source revisions, typed values/units, ambiguity/missingness, transformations, interaction/temporal definition and input evidence. |
| Outcome | Exact metric definition revision, subject level, numerator/denominator/cohort, attribution and missingness. |
| Comparison design | Within-creator, cross-creator matched context, pooled/hierarchical, descriptive normalization or prospective experiment; overlap and identifiability requirements. |
| Covariates | Predeclared confounders/context, timing, interactions/moderators, handling of unavailable covariates and measurement limitations. |
| Model pipeline | Design matrix, preprocessing, encoding, family/link, exposure offset, estimator, covariance, prediction target and diagnostics. |
| Validation | Splits/grouping/purge policy, training-only selection/tuning, exact fitted pipeline, metric/contrast, independent confirmation and scope claims. |
| Test-family policy | Candidate/outcome/window family, attempt budget, adjustment method, holdout consumption and stopping/confirmation rules. |
| Reproducibility | Seed, engine/library/model versions, content hashes, all attempted fits, warnings/failures and frozen manifests. |

Store unsuccessful/invalid attempts and null/contrary results, not only successful effects. Each result declares `descriptive`, `inferential_association`, `predictive_validation`, or reviewed `causal` interpretation. These are separate claims; a prediction score does not validate a mechanism.

An initial cooking estimand might be the within-creator association between reviewed result-first exposure and a **source-defined seven-day outcome**, conditional on declared context, among eligible cooking posts. The estimand is not “the causal effect of anticipation.” A cross-creator normalized comparison is a different estimand and must be reported separately.

## 2. Units, identity and source eligibility

A post is not always an independent content item. Reposts of the same media under different IDs/creators must share a duplicate family. Exact media hashes supply the first gate; near-duplicate candidates use a declared review/similarity procedure and versioned membership. Unknown media identity is reported; metadata-only studies cannot claim complete duplicate control.

Default uncertainty clusters at creator when posts share an audience/production process. Creator accounts are imperfect independence proxies: shared ownership, collaborations, copied content and overlapping viewers may create further dependence. Snapshot rows, text chunks, reaction-cluster memberships and retention bins never multiply the number of independent creators/posts.

Post-level niche labels are versioned, possibly multi-label and uncertain. Do not silently assume an account's current niche applied to all historical posts. Comparison policies declare ambiguous/multi-niche handling and the population to which a result generalizes.

An outcome must be available, eligible, semantically comparable and mature at the declared analysis cutoff. Unknown values remain missing. Complete-case analysis reports selection/coverage and differences from the eligible source population; it does not quietly treat missing analytics as poor performance.

## 3. Historical baselines and outcome alignment

### 3.1 Two different baseline policies

- `retrospective_cohort`: normalize against the declared selected cohort, optionally leave-one-out. Later posts may be included by design. Valid for retrospective description, never labeled a historically available benchmark.
- `historical_as_of`: use a declared earlier reference population and only source facts demonstrably available at a specified cutoff. This is the new policy for historical benchmark claims.

For a target publication-time benchmark, reference posts must have publication time **strictly before** the target, and their eligible matured outcome measurements must have been available by that target cutoff. Earlier publication alone does not establish timely outcome knowledge. For an evaluation-time benchmark, declare that different cutoff and interpretation explicitly.

Reference history is selected from the full declared canonical population, not only the compared groups. Apply predeclared source/platform, outcome-definition, cohort/exposure maturity, lookback and permitted topic/content filters. A sparse topic-specific baseline can be insufficient; any fallback hierarchy must be specified in advance and reported.

Persist exact reference post/observation/definition IDs, cutoff, source-availability evidence, exclusions, sample size and statistics. Do not reconstruct a frozen reference set from today's database.

### 3.2 Normalization and boundary cases

Use declared robust summaries where appropriate, such as a median and explicit ratio/difference transform. Report units and estimand after transformation. A zero reference median, zero MAD, insufficient independent references or incompatible outcome definitions yields an unavailable scale/diagnostic—not arbitrary epsilon-based inflation.

A ratio to the historical median is a descriptive normalization. It does not control for promotion, changing audience or all confounders, nor make outcomes from different platforms interchangeable.

### 3.3 Exposure maturity and source lag

Select outcome snapshots by predeclared age windows/tolerances, avoiding “latest available” when that compares one-day and one-year exposure. Distinguish:

- The actual reporting/observation window and cumulative/windowed semantics.
- The source's reported effective/as-of time.
- Collection time, earliest known availability and documented freshness/lag.

If only collection time is known, label age a proxy with uncertainty. Strict maturity-matched inference is ineligible when source lag makes alignment unknowable, unless a declared bounding/sensitivity analysis justifies a more limited claim. Do not interpolate unsupported daily outcomes from cumulative snapshots.

**Regression fixture:** append high-performing future posts; an existing frozen historical baseline and new analyses at the same cutoff remain unchanged. A new retrospective policy may change and must be labeled differently.

## 4. Comparison designs

### 4.1 Within-creator

Use same-creator comparisons to study within-creator variation. Match or adjust for predeclared period, topic, duration/content format and comparable outcome maturity where available. Specify matching with/without replacement, calipers, distance, missing-data policy and estimand (e.g. exposure-group matched association).

A creator with no exposure variation cannot identify a within-creator exposure effect. Report excluded creators and the changed population.

### 4.2 Cross-creator

Do **not** implement cross-creator matching by merely dropping the existing creator-equality guard.

A valid design first establishes compatible source/outcome/cohort definitions and exposure windows. Freeze contextual strata, then match/balance on declared pre-exposure factors such as topic, format, period, duration and as-of audience size when available. Historically normalized outcomes may be compared only with their baseline uncertainty and meaning retained.

An initial interpretable method may use exact/coarsened strata plus predeclared standardized covariate distance and calipers. The specification records scale estimation, assignment algorithm, replacement and tie-breaking. Outcome values never choose matches. Nearest neighbors are not sufficient when contexts lack overlap.

Return before/after covariate distributions and standardized differences, support/overlap diagnostics, retained/dropped units, effective creator counts, baseline quality and sensitivity to calipers. No universal balance threshold establishes exchangeability. Missing promotion/collaboration/traffic-source context limits the claim; statistical adjustment does not create missing confounders.

If no defensible matches exist, return `insufficient_overlap` and descriptive contrasts rather than a fitted effect. Preserve separate within/cross estimates when both are available; disagreement is informative.

### 4.3 Context controls and estimand discipline

Potential controls include publication period, calendar season, timezone-aware publishing schedule, audience size at the cutoff, content topic/format/duration, traffic source, paid promotion and collaborations. Record unavailable controls.

Treat clock time circularly where modeled; an unknown local timezone must not become a false local-hour conclusion. Do not adjust indiscriminately for post-exposure variables such as subsequent comments, shares or follower growth when estimating an exposure association intended to exclude mediator adjustment. Record the causal/temporal rationale for controls.

## 5. Identifiable within-, between- and niche models

Before fitting, construct and audit the actual design matrix: rank, alias groups, feature variation, condition diagnostics, number of independent clusters and parameter complexity.

Creator fixed effects absorb creator-constant attributes. Therefore creator-constant niche main effects cannot be estimated alongside a complete creator fixed-effect design. Removing the rank check or using a pseudoinverse to print arbitrary niche coefficients does not repair identification.

Use a question-appropriate option:

1. **Within-creator estimand:** center eligible time-varying predictors within creator; include necessary creator effects; omit absorbed nuisance main effects explicitly. Niche-by-technique slopes may be identifiable with adequate within-creator exposure variation and creators per niche. Audit interaction rank too.
2. **Between-creator/niche estimand:** use a declared hierarchical/within-between model (e.g. group means plus within deviations) or creator-level effect synthesis with sufficient independent creators and explicit assumptions. Do not relabel this as the within-creator effect.
3. **Post-varying niche:** model true within-creator niche variation only when supported by revisioned labels and overlap; account niche metadata alone is insufficient.

Cluster-robust covariance, GEE and random effects address dependence under assumptions. They do not remove confounding or make a rank-deficient fixed-effect target identifiable. Missing support produces an explicit diagnostic and no estimate for that contrast.

**Regression fixture:** the audit's multi-creator/two-niche scenario must yield the intended identifiable within effect and an explicit unidentifiable niche main effect, or a separately specified between model. It must not quietly drop meaningful terms or claim every coefficient is estimable.

## 6. Production feature timing and lineage

R2's `FeatureMaterializer` writes each value with subject/content revision, recipe revision, input evidence revisions, measured/content-valid time, earliest demonstrable availability, materialization time, coverage/missingness and provenance. Analytics consumes these records; a manually supplied optional field in a test is not a production leakage guard.

Two modes have distinct semantics:

- `retrospective_content`: later reproducible annotation of exact immutable old content may be studied as a content characteristic. The report discloses retrospective extraction and selection risks.
- `historical_prediction`: every predictor/source snapshot and deployable recipe/model must be available under the declared decision-time policy. Unknown availability is ineligible, not assumed timely.

A frozen original media file can support retrospective features even if ASR was run later. A caption fetched after performance is known cannot prove its historical wording. Backfilled current metadata receives a known capture time and unknown historical validity. Outcomes and later audience reactions cannot enter a pre-publication content predictor.

Source permissions, mutable edits, account-size snapshots, recipe/model release dates and manual review dates are part of the policy. A leakage audit checks both value lineage and selection/feature-engineering decisions. Exclude future-derived normalization, target encoding and post-outcome manual feature selection from held-out forecasting.

Annotation lineage also records the protocol and outcome-access/blinding history. Confirmatory creative labels are frozen without outcome inspection or governed by a separately justified bias-control policy. Outcome-aware interpretation is disclosed as exploratory; freezing it afterward does not create outcome-blind confirmation. Human reviewers and model input contexts obey the same restriction.

**Integration test:** import real fixture rows → materialize production features → build an analysis population. A late-edited caption and outcome-derived reaction feature must be rejected for the historical target; a properly declared retrospective content analysis may retain qualified content features.

## 7. Model families, outcomes and actual-pipeline validation

### 7.1 Outcome-appropriate estimation

Reuse current OLS/Poisson primitives where valid; do not require new modeling packages for R2's first corrected path.

- Continuous outcomes may use a declared transformation/linear model with residual and dependence diagnostics. A log-transformed count coefficient is not a raw-count effect.
- Count GLMs require appropriate exposure/window comparability and dispersion diagnostics. Overdispersion/zero inflation can invalidate simple Poisson inference; use a justified supported alternative or withhold the inferential claim.
- Binomial models require a meaningful known success count and denominator under a justified sampling model. An arbitrary platform percentage or replay ratio cannot be treated as independent Bernoulli trials.
- Retention series require source/cohort and correlation semantics. Aggregate bins with unknown audience counts support descriptive curve comparisons, not invented survival hazards or independent bin-level inference.
- Signed account growth is an account-period outcome; it must not be forced through a nonnegative post-count model.
- Conversions distinguish platform attribution, observed association and identified experiment outcomes. A source attribution label is not causal identification.

Supported alternatives such as negative-binomial or hierarchical estimators are introduced only with a real design need, diagnostics, dependencies and tests. Unsupported requested models return an explicit status rather than silently substituting another estimator.

### 7.2 One pipeline, two distinct validation questions

The frozen `ModelSpec`/`DesignMatrixSpec` defines preprocessing, contrasts/encoding, splines/interactions, family/link, covariance/offset, regularization and prediction target. The **same** pipeline must be used for fitting and applicable validation. All preprocessing/selection/tuning occurs within training partitions.

- **Predictive validation:** score actual held-out predictions from the selected model against a declared benchmark/metric, with target scale, uncertainty and scope. Retain failures and calibration/residual diagnostics.
- **Inferential replication:** estimate the declared interaction/contrast on an independent confirmation cohort, with effect/uncertainty and a prespecified interpretation. A main-effect prediction score does not establish interaction reproducibility.

A fixed-effect model has no fitted intercept for a wholly new creator. Choose and document a supported marginal/new-group prediction model, validate within-known-creator forecasting separately, or state that the inferential model is not validated for unseen-creator prediction. Do not silently fit an auxiliary Ridge model and describe its score as validation of the original model.

GEE/mixed-model conditional and population-average predictions have different meanings; declare which target is tested. A validation subsystem must reject unsupported prediction semantics.

## 8. Independence, holdouts and diagnostics

Construct split membership before feature selection. Enforce the dimensions necessary for the claimed scope:

| Scope claim | Required protection |
|---|---|
| Future performance for known creators | Chronological splits; no training outcome/feature unavailable by prediction cutoff; purge overlapping outcome windows. |
| Transfer to new creators | Creator-disjoint folds; duplicate-content families cannot cross splits. |
| Future performance for new creators | Joint time/creator/content constraints; if infeasible, neither separate score is a substitute for the joint claim. |
| Cross-niche transfer | Held-out-niche test with declared label overlap policy, creator/content separation and adequate support. R9 owns this broader gate. |

Exact/near-duplicate groups may connect several creators. Assign connected grouping units consistently; report the resulting loss of independent samples. If split constraints leave too little data, return insufficient data and narrower descriptive results.

Freeze evaluation sets; use nested training-only selection when tuning is required. Record all model/feature/window attempts and whether a holdout was previously inspected. A reused test set is no longer pristine independent confirmation.

Report effect intervals, cluster counts, missingness, balance/overlap, rank/conditioning, dispersion/residual diagnostics, influence/outlier sensitivity and multiplicity status. Bootstrap/resampling must respect dependence and recompute training-derived transforms; do not resample individual bins/chunks as independent observations.

A minimum number of rows/clusters per parameter is a conservative implementation gate, not a power calculation. Declare a smallest meaningful effect and design/precision target when appropriate; simulate/estimate power using plausible independent-unit structure. Small case studies remain useful but cannot justify broad generalization.

## 9. Bounded discovery and repeated-testing discipline: R9

R2 supports prespecified interactions only. R9 adds a deliberately limited candidate grammar:

- Validated creative techniques/features and temporal combinations with frozen recipes.
- Predeclared main effects and pairwise interactions, bounded hierarchy/order and a maximum candidate count.
- A small fixed spline/nonlinear basis where outcome/design support it; knot selection inside training only.
- Niche moderation only where identifiable; no automatic high-dimensional “every feature × every niche × every outcome” expansion.

R2 introduces minimal declared-analysis family, attempt and holdout-use records; R7/R8 retain that history for evaluation and reevaluation. R9 extends this foundation to a canonical search-family manifest and all-attempt ledger: candidates, outcomes/windows, transformations, splits, budget, proposal source, fit status, diagnostics, p-values/intervals, adjustment membership, decisions and holdout access. Semantic/LLM proposals are logged before testing and obey the same budget.

For an initial release, freeze a discovery round, control the declared within-round family (e.g. existing BY adjustment where assumptions/interpretation are appropriate), and confirm on a separately reserved or genuinely new cohort. Multiple windows/outcomes are part of the declared family, not separate chances to report significance.

Per-run FDR correction does not provide global sequential error control over adaptive reruns. Repeated data peeking is recorded; no automatic “confirmed” promotion after repeated favorable looks. Any future online/sequential policy requires separately specified assumptions, error target, stopping rules and tests. Changing a specification opens a disclosed new exploratory round, not a rewritten prediction.

Assess selection stability, sensitivity to definitions and failed transfers. Find unsuccessful exposed examples and successful unexposed examples from the full eligible population; preserve them as counterevidence even when they are semantically distant from the most attractive examples.

## 10. Audience and mechanism interpretation

Comments may supply expressed reactions and inform hypothesis refinement. Their collection frame, selection and language/annotation uncertainty must be reported. Unless the sample design warrants it, “30% of imported comments” cannot be generalized to “30% of viewers”.

Curiosity, anticipation, sensory appeal and fluency can all predict attention. A retention association alone may be non-discriminating. A reviewed mechanism assessment must name what evidence would favor one explanation over rivals and what would weaken it. A lack of a detectable effect under low power is not strong evidence of absence.

R10 can analyze prospective creative experiments when assignment/exposure/outcomes are valid. Platform audience allocation may not be randomized even if a creator randomly chooses upload order. Retain assignment unit, implementation fidelity, contamination/spillover, repeated exposure, attrition and deviations. Mediation requires additional assumptions and measurements; an opening-variant effect alone cannot establish a psychological mediator.

## 11. Required test matrix and release gates

| Failure mode | Software acceptance test |
|---|---|
| Future-post baseline contamination | Append future posts and late-available old outcomes; historical references/scores remain fixed at the same cutoff. |
| Same-creator matcher reused across creators | Explicit cross design yields balanced different-creator fixture pairs; no-overlap fixture yields no inferential estimate. |
| Creator/niche alias | Intended within contrast recovered; absorbed main effect explicitly unavailable; separate between design not mislabeled. |
| Vacuous timing audit | Actual import/materializer pipeline produces lineage; late/missing features excluded in historical prediction. |
| Surrogate validation | Interaction-only synthetic target validates the requested pipeline/contrast; main-effect-only surrogate cannot pass the same contract. |
| Content leakage | Duplicate media under different IDs/creators never crosses protected splits; unknown near-duplicate coverage disclosed. |
| Training/test contamination | Scalers, knots, encodings and feature selection fitted solely within training; inspected holdout marked consumed. |
| Metric misuse | Missing denominator, lagged count, looping retention, overlapping windows and signed growth cannot enter incompatible models. |
| False independence | Snapshots/bins/chunks do not increase independent n; clustering and power gates use declared units. |
| Unlimited retries | Failed/null tests and all candidate/window attempts remain in one ledger; reused test data cannot claim independent confirmation. |
| Overconfident scientific interpretation | Observational effect and non-discriminating mechanism evidence cannot pass a causal/mechanism proof validator. |

Tests must exercise services/CLI, stored reload/reproduction, controlled synthetic recovery and failure fixtures. Synthetic ground truth checks implementation behavior only. Independent real-data replication, annotation/construct validity, source representativeness and domain transfer remain empirical acceptance work.

## 12. Reference

Official [scikit-learn guidance on grouped and time-aware cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html) informs split mechanics. SocialDNA's additional source-time, duplicate-content, actual-model and holdout-family requirements are design obligations specified here, not guarantees provided by the library.
