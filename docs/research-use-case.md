# Reference research flow: result-first cooking videos

Status: **proposed architecture acceptance scenario; not an implemented capability or a research result**. Date: 2026-11-05.

Question: **Why might showing a finished meal during the first seconds of a cooking video be associated with better performance?**

This scenario joins the [research contracts](research-contracts.md), [statistical design](statistical-design.md), canonical evidence/memory rules in [ARCHITECTURE.md](../ARCHITECTURE.md), and milestones in [PLAN.md](../PLAN.md). The architecture must be able to conclude “the available data does not distinguish these explanations” and later weaken a previously supported finding.

## Access and study frame

Use three explicit access classes; none implies permission to fetch another class:

- **P — permitted public/exported metadata:** supplied publication times, captions, hashtags, public counters, and comments only where collection/reuse is permitted. “Public” is not a license to bypass access controls or terms. Current adapter eligibility must be checked separately before deployment.
- **M — authorized media:** local video/audio, frames, subtitles, and derived observations processed within the caller's rights and consent. A public URL alone does not grant download rights. Hosted-provider transfer requires separate consent; reviewed local annotations work without hosted models.
- **O — creator-owned/authorized analytics:** supplied retention/completion curves, saves or other nonpublic counters, audience/denominator definitions, account histories, and conversion exports. Competitor ownership cannot be assumed.

Start with an explicitly selected historical period and permitted accounts, including low-, ordinary-, and high-performing posts—not only videos found by semantic search or “top posts.” Record exclusions, failed media, missing outcomes, source lag, and the collection frame. The post is the default outcome unit; repeated frames, comments, and bins do not multiply the independent video or creator count. The number of creators and independent variation, not an arbitrary video count, determines feasible comparisons.

Register two possible questions separately:

1. **Primary, if O is available:** association of a declared result-first technique with a supplied, comparable early-viewing outcome, using its exact platform definition, audience, denominator, resolution, and observation window.
2. **Fallback, only if supplied:** association with a declared seven-day metric, such as views or saves, aligned by post age and source freshness. This is a different outcome/question and does not establish early retention or a psychological mechanism.

If neither has eligible measurements, deliver a descriptive media/audience research brief with untested predictions, not an invented performance estimate. Where the primary and fallback are both explored, record both in the search/test family rather than reporting only the favorable result.

## Twelve-step data and reasoning flow

### 1. Analyze the opening's modalities

**Inputs/access:** M video, audio and supplied subtitles; P caption/hashtags. Existing deterministic and optional local analysis produce scenes, sampled frames, motion/color/loudness observations, speech, OCR, and audio-event candidates in the original presentation timebase.

**Representation/services:** existing media pipeline/timeline and media evidence revisions; `CueBundle` assembles exact visual/audio/text/observation references. `CreativeEventService` can request bounded denser sampling in the opening. Captions remain untimed post text unless the source actually supplies timing.

**Output/limit:** a synchronized opening bundle with missing modalities, sampling coverage, offset/boundary uncertainty, model/tool versions, and transfer consent. Warmth and appeal require explicit annotations; brightness is not warmth, and energetic narration is not loudness. A human/imported reviewed bundle is a valid no-model path.

**Test/falsification:** fixtures with silent media, no speech, a late subtitle offset, a single-frame reveal missed by sparse sampling, and a color/brightness distinction must preserve uncertainty rather than hallucinate cues. Primarily R3 over the existing media slice.

### 2. Identify the result-first creative technique

**Inputs/access:** step 1's M bundle and a reviewed `CreativeTechnique` definition, such as final prepared dish visible within the declared first-three-second window before substantive instructions.

**Representation/services:** `CreativeEvent` points to exact/discontinuous media anchors and evidence; `EventRelation` records reveal-before-instruction, overlapping narration, and any audio co-occurrence separately. `FeatureMaterializer` creates the declared exposure value using the technique/recipe revision.

**Output/limit:** present, reviewed absent with adequate coverage, ambiguous, or not detected with stated coverage. Model proposal and reviewer verdict remain separate revisions. This event contains no mechanism claim.

**Test/falsification:** ingredient-only, intermediate cooking, a final-dish thumbnail not present in video, and a reveal crossing the window boundary must not all count as definite exposures. R3.

### 3. Register competing mechanism explanations

**Inputs/access:** observed technique/events plus reviewed construct definitions; no additional personal data.

**Representation/services:** `ResearchQuestion`, `HypothesisSpec`, `Operationalization`, and `Prediction` revisions registered through `ResearchService.register`; rival links preserve alternative explanations and common causes such as recipe appeal, creator identity, topic, paid distribution, or production quality.

**Output/limit:** tentative anticipated-reward, sensory-appeal, curiosity/information-gap, and cognitive-fluency/clarity explanations, with observable predictions and disconfirming evidence. “The audience felt anticipation” is not an observation. If available outcomes cannot distinguish rivals, mark predictions non-discriminating.

The following are **candidate specifications to review**, not established findings or validated instruments:

| Rival | Candidate discriminating prediction | Additional observation needed | What would weaken this specification |
|---|---|---|---|
| Anticipated reward | Holding visual detail and clarity approximately fixed, a result preview changes expected enjoyment/utility before the process is watched | Consented, reviewed pre-outcome reward-expectation measurement and a feasible manipulation | No meaningful change with adequate precision, or the effect tracks only sensory-detail manipulation |
| Sensory appeal | Holding preview information fixed, a sensory-detail manipulation changes appeal and the registered outcome | Independent detail/preview conditions and reviewed appeal measurement | Preview has an effect while a valid sensory-detail manipulation has none, within the tested scope |
| Curiosity/information gap | A clearly unanswered “how” or transformation gap changes interest beyond merely showing the result; revealing everything need not do so | Manipulation checks distinguishing unresolved process information from outcome visibility; reviewed curiosity measure | Effect persists without the specified gap, or interest is explained by clarity/reward without the predicted gap contrast |
| Cognitive fluency/clarity | Holding sensory detail fixed, an informative preview improves understanding of the cooking goal/process and reduces declared uncertainty | Appropriate comprehension/clarity task; instrument review and constraints on other cue changes | Outcome differences occur without the specified comprehension/clarity change, or the control is equally informative |

These tests may be infeasible in ordinary account exports. Absence of their additional measurements means mechanism support remains limited; a comment saying “looks delicious” cannot replace the required contrast. Failure to discriminate is an acceptable scientific result.

**Test/falsification:** a reasoner cannot invent a measured construct, drop an inconvenient rival, or turn a literal reveal into proof of curiosity. Initial specifications may be human-authored and corpus-reviewed. R7.

### 4. Retrieve relevant reviewed research

**Inputs/access:** permitted citation metadata and minimal lawful excerpts from a small curated corpus, not automatic full-text mirroring.

**Representation/services:** `ResearchSource` → `StudyFinding` → construct/operationalization revisions with evidence locators, design, population, effect/uncertainty when available, limitations, and applicability review. SQL/FTS and optional vector retrieval return candidates; a reviewed applicability judgment is separately recorded.

**Output/limit:** a bibliography-grounded plausibility map with supporting, null, and contradictory studies. Evidence from trivia curiosity, for example, would need an explicit transfer argument before being used to motivate a cooking-video prediction. It cannot certify the mechanism in these videos.

**Test/falsification:** nonexistent citation, correction/retraction, irrelevant manipulation, and incorrect quoted page must fail validation or downgrade eligibility. Reviewed imports work without an embedding model; R6 retrieval, R7 corpus/evaluation.

### 5. Analyze expressed audience responses

**Inputs/access:** permitted P/O comments with collection manifests, source windows, rank/filter/pagination information, and missingness. No author identity inference.

**Representation/services:** `AudienceCollection`, comment-span evidence, `ReactionAnnotation`, cluster memberships, and `ContentReactionLink`; `AudienceService.annotate/link` preserves exact quotations and distinguishes explicit references, human interpretation, and model-proposed links.

**Output/limit:** expressions such as “I want to cook this,” recipe questions, sensory descriptions, objections, and contrary responses. Report counts only for the declared collected-comment denominator. A post-publication comment is not a pre-publication predictor; an inferred opening link is not directly observed segment response. Expressed intention is not verified action.

**Test/falsification:** “I will never cook this,” irony, duplicated comments, creator replies, ranked-only collections, and an unanchored “looks great” must not establish opening-caused intent. Missing comments leave this lane unavailable without blocking media analysis. R4; research use R7.

### 6. Connect to eligible outcomes

**Inputs/access:** O for behavioral curves/attribution; P for permitted supplied counters when used in a separately registered question. Retrieval time alone cannot establish seven-day freshness.

**Representation/services:** existing scalar snapshots plus R5 definition/cohort/measurement/series/bin/attribution contracts. `EvidenceResolver` exposes exact metric revisions; metric compatibility checks freeze source definitions, post ages/windows, denominators, audience cohorts, source lag, and unavailability.

**Output/limit:** post outcomes with exact provenance and valid comparison scope. Retention bins remain at source resolution; rewatches above one are allowed only by their definition and are not forced into survival semantics. Account growth is not assigned to the nearest post. Seven-day views/saves are not proxies for early retention.

**Test/falsification:** incompatible cohorts, zero/unknown denominators, lagged exports, coarse bins, unavailable retention, and unassigned conversions must produce exclusions or narrower questions, not zeros or guessed data. R2 repairs scalar analysis; R5 rich metrics.

### 7. Construct same-creator and cross-creator comparisons

**Inputs/access:** all eligible P/M/O records within the registered frame, including failures and ordinary posts. Same-creator and other-creator comparisons are separate analysis designs.

**Representation/services:** frozen cohorts, `FeatureValue` revisions with availability lineage, historical-baseline policy and reference rows, as-of account covariates, duplicate-media groups, and explicit `ComparisonSpec`. SQL defines the analytical population; semantic retrieval only helps inspect candidates/examples.

**Methods:** within-creator contrasts with prior-only comparable baselines; cross-creator comparisons with overlap/balance checks, publishing-period and accessible pre-exposure context, and correctly identified clustered/hierarchical models. Niche nested within creator must not produce a rank-deficient fixed-effect design. Missing paid-distribution or audience information is a confounding limitation, not silently assumed absent.

**Output/limit:** matched/adjusted populations plus exclusions, balance/overlap diagnostics, actual independent counts, and `insufficient_data` when appropriate. Separate supported scopes for within-creator, cross-creator, and cross-niche claims.

**Test/falsification:** future posts cannot alter an earlier historical baseline; cross-creator mode must produce valid comparisons or refuse for lack of overlap; creator/niche nesting and duplicate-media leakage get dedicated fixtures. R2; broader transfer in R9.

### 8. Retrieve unsuccessful uses and alternative successes

**Inputs/access:** eligible M/P/O population, not just a top-K semantic success list.

**Representation/services:** SQL outcome/technique filters plus FTS/vector retrieval and bounded graph context over exact revisions. Evidence-role links distinguish counterexamples from contradicting statistical results. Include result-first failures, ordinary outcomes, and successful videos without the technique, with comparable age/definition/baseline context.

**Output/limit:** an auditable counterexample set with selection policy, similarity reasons, missingness, and influential/outlying-case flags. An individual failure does not refute an average association; repeated structured failures can narrow scope or motivate a rival.

**Test/falsification:** outcome-blind event detection and outcome-stratified retrieval must return failures rather than explaining them away. A sparse failure library or stale evidence produces an explicit limitation. R6 retrieval; R7 evaluation; R9 systematic discovery.

### 9. Evaluate the association and the rival explanations

**Inputs/access:** frozen eligible data/evidence manifest, exact hypothesis/feature/model specifications, observed confounders, and registered validation plan.

**Representation/services:** `ResearchService.evaluate` orchestrates `statistical_analyses/results`, actual model-pipeline validation, dependency manifests, and structured rival-prediction adjudications. `ClaimValidator` gates every finding.

**Methods:** descriptive effects and cluster-aware uncertainty first; appropriate count/rate/continuous outcome family; explicit interactions/limited nonlinear terms only with support; preregistered or disclosed exploratory families including null attempts. Preprocessing and selection remain inside creator/time/duplicate-content/niche splits as required by the claim. Validate the chosen interaction/model, not an unrelated main-effect Ridge surrogate.

**Output/limit:** an association, no clear association, or insufficient data, with effect/interval, diagnostics, selection/confounding limits, counterexamples, and actual tested scope. Comment/intention patterns can triangulate explanations but cannot establish mediation. If rivals remain indistinguishable, say so.

**Test/falsification:** pure-interaction synthetic data, null data, confounding, poor overlap, strong outliers, nested creators/niches, and failed held-out transfer must not yield blanket mechanism claims. R7 bounded slice; R9 broader candidate discovery.

### 10. Persist a qualified finding and actionable report

**Inputs/access:** validated assessment and source permissions, including restrictions on retaining comment excerpts or reports.

**Representation/services:** immutable `ResearchAssessment` and `Finding` revisions; evidence-role links; dependency/selection manifests; canonical vector documents; outbox and SQLite graph rows. Graph relationships carry exact finding revision, scope, claim level, effect/uncertainty and supporting/contradicting evidence. SQLite remains authoritative.

**Output/limit:** a report such as “result-first openings were associated with the specified supplied outcome in this population; causal and mediator explanations remain unresolved.” Include tested/untested alternatives, missing modalities/analytics, counterexamples, and a concrete experiment proposal. Do not manufacture a positive result for this demonstration.

**Test/falsification:** later process reload must reproduce the assessment from its exact eligible revisions. Stale/deleted vector hits cannot resurrect evidence; withdrawal may make an old report unverifiable/restricted and must be disclosed. R6 persistence; R7 finding/report.

### 11. Recommend a discriminating experiment

**Inputs/access:** the rival-prediction map, feasible creator cooperation, and lawful/consented outcome and optional participant measurement.

**Representation/services:** R7 saves an experiment brief; R10 adds `ExperimentRegistration` and later `ExperimentOutcome` through explicit user-authorized execution/import. No automatic publishing, audience experiments, private analytics access, or participant collection.

**Methods:** propose a feasible blocked/randomized design that separates “show final result” from a relevant rival manipulation—for example, vary sensory detail independently of a clear result preview, while measuring clarity/anticipation with reviewed or explicitly unvalidated instruments. Keep recipes/duration/production/distribution comparable where feasible; register assignment unit, power/precision rationale, primary outcome, stopping policy, carryover/interference limits, and analysis before outcome inspection. Platform posting constraints may permit only a weaker quasi-experiment; disclose that downgrade.

**Output/limit:** predicted differences that could weaken each explanation and a feasible measurement plan. A randomized creative effect does not itself prove the psychological mediator; mediator measurement/manipulation and further identification assumptions remain necessary.

**Test/falsification:** an unexecuted brief cannot be reported as an experiment; missing randomization/deviations cannot be ignored; a generic performance lift cannot uniquely favor curiosity over all rivals. R7 brief; R10 registered designs and outcome analysis.

### 12. Reevaluate after new evidence

**Inputs/access:** new representative P/M/O posts, corrected definitions/annotations, a reviewed contradictory study, or permitted experiment outcomes. Include ordinary/failure posts rather than only additional successes.

**Representation/services:** dependency and population-selection manifests identify affected hypotheses; R8 marks prior projections stale, then `ResearchService.reevaluate` creates a new frozen assessment and finding revision. Persist history, reused/new independent units, prior exploratory decisions, stopping/confirmation policy, and the exact reason support changed.

**Output/limit:** a supported finding may become weaker, niche-limited, inconclusive, or rejected in scope. For example, additional comparable failures or an adjusted near-null effect can weaken the earlier association, while a generic performance lift still fails to resolve its mechanism. Do not rewrite history or call overlapping-data reanalysis independent confirmation.

**Test/falsification:** initial supported-in-scope assessment → new eligible failures → weakened/contradicted finding is a required end-to-end fixture. The old report remains revision-specific, current retrieval shows the revised qualification, and withdrawn evidence degrades eligibility. Repeated significance testing cannot silently reset the family/history. R8.

## Minimum end-to-end acceptance demonstration

Use a deterministic, permission-labelled fixture corpus with reviewed creative and reaction annotations, complete provenance, comparable scalar outcomes, ordinary/failure examples, and a reviewed miniature literature corpus. It is a software acceptance dataset, not empirical proof that result-first openings work. Optional real media/models can enrich it without replacing the no-model test path.

R7 must demonstrate steps 1–10 and an honest step-11 brief, including an insufficient/non-discriminating rival result. A creator-owned analytics fixture adds step 6's rich-metric path after R5. Missing O analytics must take the explicitly separate scalar fallback or descriptive-only path. R8 completes step 12 with evidence that changes the conclusion. R9 expands search/transfer only after this narrow workflow works; R10 adds experiment registration/outcomes without claiming automatic mechanism identification.

Basic `analyze video`, `analyze account`, caption/hashtag inspection, and existing reports stay available throughout. The research path is an explicit opt-in workflow, not a tax imposed on every video analysis. Photo analysis and the portable Agent Skill can later use these same contracts without inventing video clocks or embedding research logic in host-specific instructions.
