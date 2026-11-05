# Bounded nonlinear and cross-creator/niche discovery

Delivered in `0.0.17`, database head `0015_discovery`. No model downloads, new
dependencies, connectors or servers are required. This is observational research,
not a causal estimator, proprietary ranking model or recommendation generator.

## Commands and lifecycle

```sh
socialdna --data-dir ./library research discover --spec search.json
socialdna --data-dir ./library research show-discovery SEARCH_KEY
socialdna --data-dir ./library research show-discovery SEARCH_KEY --reproduce
socialdna --data-dir ./library research confirm-discovery --spec confirmation.json
```

Use [`examples/research/discovery.json`](../examples/research/discovery.json) as a
schema-valid example; choose the actual imported metric, sampling frame, scope,
cutoffs and hypotheses before running. Its `demo` counters are not platform data.
The Python entry points are `discovery_service.discover(app, DiscoverySpec)`,
`show(app, EntityRef)`, `reproduce(app, EntityRef)` and
`discovery_confirmation.confirm(app, ConfirmationSpec)`. CLI JSON uses the usual
result envelope. Resolve returned exact evidence references with `evidence resolve`.

A search registers its complete specification, canonical SQL input snapshot,
planned/purged partitions, numerical-library versions and budget **before any fit**.
Each actual fit has a separately committed started/completed/refused/failed ledger
entry. Nulls, missingness, rank failures and insufficient samples stay visible.
Unexpected errors fail the round, rather than swallowing the error and reporting
only successful candidates. A crash leaves started entries and consumed reservations;
it does not release a holdout or silently restart a search. Inspect it and declare
an explicit new round/parent using genuinely fresh evaluation data.

`key` is single-use. `family_id` has an immutable search-family manifest. Overlap
with prior search data requires an exact `parent_search` reference; all overlapping
round keys are disclosed, not only that parent. A new family name does not reset
the observation/holdout history. Reproduction recomputes the frozen snapshot with
the same numerical libraries, verifies exact results, and does not fit current
imports or consume a second holdout. Source withdrawal/correction/erasure gates
still apply. Confirmation rounds also reproduce from their frozen specification.
Reads expose the exact `ref` and a separate `operational_freshness` field. A later
context edit hides the derived pattern in default current-memory/graph views but
does not rewrite its eligible frozen historical result or reproduction.

## Actual models and validation

- At most 12 declared candidates, six drivers/adjusters per candidate, interaction
  order two, three alpha values (`0` = OLS; positive = Ridge, maximum 100), three
  fixed inner folds, and 128 fit attempts per round. The complete planned fit
  count must fit the declared budget. No unrestricted candidate enumeration, trees,
  boosting, neural fitting, live LLM proposal generation or early stopping.
- Candidate kinds: `main`, `interaction` (two main effects plus raw product),
  `quadratic` (main effect plus raw square), or `spline` (three training-quantile
  knots, degree two, linear extrapolation). Adjusters are declared numeric features.
  Splines replace, rather than alias, the raw linear driver. No imputation.
- The **same actual marginal raw-outcome pipeline** fits and predicts, including
  its transformations, scaling and regularization. No creator fixed effects are
  fitted; prediction on new creators does not invent an intercept or substitute an
  auxiliary model. This is a new versioned model adapter, not a semantic change to
  frozen v1/v2 within-creator analyses. Creator confounding remains a limitation.
- All candidates use one complete-case union population. Outer partitions are made
  before fitting; candidate/alpha selection is entirely inside training with three
  creator-disjoint folds. Time/joint modes additionally purge overlapping outcome
  windows inside training. Every fold/alpha, its transformations and training IDs
  are retained. Stability reports the inner-fold winners, not independent replications.
- Outer policies are creator, chronological or joint. Declared `transfer_niches`
  are additionally held out; all their creators are excluded from source training
  and source tests. The supplied primary niche is one label, not an inferred or
  overlapping taxonomy. Exact-content duplicates are purged across all boundaries
  and deduplicated within outer partitions. Near-duplicate detection is not claimed.
- At least 30 training units and five training creators, five rows per basis
  parameter, and ten test units/two test creators are conservative engineering
  gates, **not power calculations**. All three inner folds must be estimable.
  Supplied creator IDs are required for fitting; account-ID proxies do not establish
  independent creator clusters. Source identity attestations are not independently verified.
  An outer score has a training-median baseline, per-niche support, out-of-range
  warnings, predictions and contrary cases drawn from the full protected population.
  A single held-out niche supports only that named transfer test, not all niches.
- Historical post prediction requires R2's actual feature/recipe availability.
  Retrospective temporal association is not a deployable forecast. Distribution
  forecasts use later-window start as the decision clock, require early inputs
  already known then, and purge training outcomes not yet available then.
- Fixed, unregularized OLS candidates can expose an exploratory creator-cluster
  focal contrast with at least 20 creators and non-perfect residuals. Tuned or
  regularized uncertainty is withheld. Quadratic/product contrasts are their actual
  focal coefficients; spline tests are joint curve associations, **not proof of
  nonlinearity relative to a linear model**. BY correction includes every declared
  candidate (failed/unavailable tests enter as p=1). It does not control adaptive
  selection, repeated rounds, multiple unregistered outcomes or sequential peeking.

Grouped/nested validation and training-fitted spline mechanics follow the official
[scikit-learn validation guide](https://scikit-learn.org/stable/modules/cross_validation.html)
and [SplineTransformer contract](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.SplineTransformer.html).
SocialDNA's source-time, dependence, reservation and claim restrictions are additional
application safeguards, not guarantees of those libraries.

## Delivered C1 input lanes

All branches declare platform, surface, native format, niche labels, language,
market, audience, objective, source/policy period and traffic context. A declaration
is not automatic verification of a population's language, audience or source truth.
Inputs come from actual canonical producers, never user-uploaded predictor arrays,
memory top-K hits or model-generated outcome values.

| Input | Eligible measured features/outcome | Important limits |
|---|---|---|
| `posts` | R2 primitive/creative features, including pinned C1-A craft recipes; C1-B circular local hour/day, exact historical title length/hashtag count and completeness-qualified cadence; actual explicit-window post outcome | Nested v2 spec supplies inputs only (`model=none`, no split). Aggregate counters mean `aggregate_attention`, not Search/Home/For You exposure. Exact publication revisions must match the selected post. Metadata needs source-attested publication-time validity; late edits are not substituted. Unknown timezone/incomplete inventory stays missing; cadence is retrospective, never a pre-publication forecasting feature. |
| `distribution` | C1-C `distribution_observation` references: actual early response → non-overlapping later exposure count | Exact platform/surface/format/language/market/audience/exposure mapping, source definitions, cohort eligibility/dimensions, relative post ages and window lengths must agree. The source period and named source/transfer niches remain explicit. Official statements are separate cited guidance, never predictors, ground-truth weights or literature proof. Retrospectively imported early values are not forecasts. Unadjusted prior exposure/allocation and feedback confounding are disclosed. |
| `funnels` | C1-D actual source-qualified aggregate rate (declared numerator/denominator signals), literal profile bio length/link count/pin count/declared pillar count | Requires source-attested exposure to the exact snapshot and compatible known source cohorts, definitions, units, windows, uniqueness/deduplication and subset joins. One period per account: repeated-period carryover/spillover models are not implemented. No human-rubric quality score, native-link/campaign fiction, individual journeys, reassigned source credits or causal profile effect. Public fields alone are insufficient without owner metrics. |

Context calculations are pinned as `discovery-context-1` with an immutable recipe
registry definition and frozen exact source references. Unknown/uncertain inputs
remain missing; a constant cadence or wholly uncollected metadata column refuses
the model instead of supplying an arbitrary zero. Thumbnail/photo bytes are source
evidence, not automatically interpreted images; U1 remains separate. Richer semantic
metadata predictors, category encoders and account-period intervention models need
new validated, pinned producers, not arbitrary dictionary feature names.

## Independent focal confirmation

`ConfirmationSpec` freezes a completed discovery reference, new input/population,
scope, direction, minimum raw-basis effect, interpretation and holdout identity.
The selected candidate/adjusters are loaded from that discovery; they cannot be
changed or tuned in confirmation. Initial replication supports fixed OLS main,
pairwise interaction and quadratic contrasts. Tuned/Ridge candidates and splines
requiring reknotted/frozen-basis replication are explicitly refused.

No confirmation unit, actual measured account event, post or exact media duplicate
may have been trained on or evaluated in an earlier search. Existing R2 consumed
holdouts and previously fitted statistical populations also block reuse. R2 checks
new discovery inspection history when reserving its own holdouts. An alias or
renamed context/family/reservation cannot create independent evidence.

The confirmation estimates the actual raw-basis focal coefficient and cluster
interval, not a main-effect surrogate's predictive score. Results are
`supports_prespecified_contrast`, `contradicts_prespecified_direction`, `inconclusive`
or explicit insufficiency. Independent observational replication is still **not**
randomization, a proven mediator or a mechanism assessment. Repeated confirmation
looks are recorded and not given a global sequential-error guarantee. R7's reviewed
rival-protocol assessments are not automatically promoted or rewritten by discovery;
R8 keeps its existing explicit reevaluation path. A later search/confirmation adds
parented evidence history without mutating the prior result.

## Storage, memory and operations

`0015_discovery` adds only `discovery_rounds`, `discovery_attempts`,
`discovery_members` (indexed observed-unit history) and `discovery_bindings`.
Canonical registered/result `discovery_search` and reified `creative_pattern`
documents use existing immutable entity/evidence revisions and `research_record`
locators/bindings; no parent table rebuild or new locator/collection/server.
Family/whole-round attempts and real post/media reservations reuse R2 tables.
Canonical snapshots contain input lineage, exact features and outcomes; fit entries
record actual training/test membership and diagnostics. Interrupted fits stay visible.

Searches and selected **candidate proposals**, including null/failed-transfer results,
project through the existing statistical-findings/pattern memory families. A pattern
has constituent driver/adjuster roles, scope and an exact search reference; it is
marked `not_confirmed`. Graph edges remain structural with qualifications, never
direct technique→success causation. Withdrawal applies transitively to reads,
citations, memory and reproduction. Confirmed C1 source erasure also scrubs dependent
search snapshots and fit details; only structural audit/reservation history survives.
External backups/exports retain the pre-existing separate-cleanup obligation.

Local post searches retain R2's 500 target/5,000 historical-post limits; context
branches are at most 500 declared canonical observations. Per-fit transactions add
SQLite writes intentionally to make failures auditable. Full-table local inspection
history checks are bounded by the library's current local scope, not a distributed
search backend. Larger histories, near-duplicate models, online error control,
automatic proposal generation, causal identification and R10 recommendations remain
outside this delivery.

Tests cover synthetic recovery/nulls/aliasing, training-only preprocessing and
selection, creator/time/niche/content purges, small-cluster refusal, all-attempt
history, real imports, fixed-effect-free prediction, new-cohort raw-contrast
replication, restart/reproduction, C1 joins, guidance/observation separation,
availability/denominator gates, scoped graph projection and erasure. Controlled
fixtures validate software behavior, **not real-world scientific effectiveness**.
