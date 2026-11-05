# Time-aware comparisons and model validation

Available in `0.0.6`, SQLite `0006_designs`. This is the implemented statistical
correctness slice, not psychological discovery or causal identification.
The [statistical design](statistical-design.md) remains the normative broader
contract. [Legacy analytics](performance-analytics.md) describes the deliberately
unchanged, unversioned path.

## Run an explicit version 2 analysis

Copy [the example specification](../examples/imports/historical-performance-spec.json)
and edit its cutoffs, outcome, sampling frame and family to describe your actual
data. `knowledge_cutoff` must be after the relevant imports and no later than now.
The example date is illustrative, not an instruction to backdate an import.
`publication_cutoff` independently limits which published posts are in scope.

```bash
socialdna analyze account ACCOUNT_ID --spec corrected.json --format json
socialdna compare posts --left POST_A --right POST_B --spec corrected.json --format json
socialdna compare accounts --left ACCOUNT_A --right ACCOUNT_B --spec corrected.json --format json
socialdna report generate --run RUN_ID --format markdown
socialdna compare reproduce RUN_ID --format json
socialdna evidence resolve STATISTICAL_EVIDENCE_ID --format json
```

For different creators, change **both** `design` to `cross_creator` and `estimand`
to `cross_creator_comparison`. For raw summaries use `descriptive` for both.
The default model is `none`. Model fitting requires `within_creator` and `ols` or
`poisson`; unsupported between-creator/niche estimands are not approximated by
dropping rank checks. Legacy GEE/mixed models remain available only under v1.

All existing CLI commands remain. Supplying an unversioned spec or only `--metric`
still uses v1. No old report gains a corrected interpretation automatically.

## Clock and baseline policies

- `historical_as_of` uses the complete declared SQL history of the requested
  creators, including relevant posts outside the two selected comparison groups.
  Reference publications must precede the target publication. The lookback,
  population filters, metric definition, age tolerance and window are explicit.
- `baseline_cutoff: publication` additionally requires measurements actually known
  by the target publication, not simply published earlier. An old export imported
  today usually cannot provide that benchmark; `insufficient_history` is expected.
- `baseline_cutoff: evaluation` uses measurements known by `knowledge_cutoff`,
  still only from posts published before the target. This is an evaluation-time
  benchmark, not what a creator could have known at publication.
- `retrospective_cohort` explicitly retains a selected-cohort leave-one-out
  description. It is not a historical benchmark.

Exact reference post/snapshot IDs, exclusions, cutoff, summary, sample size and
normalization are frozen. No fallback population or epsilon denominator is used.
The selector considers only corrections known by the relevant cutoff. Future
imports cannot change a fresh calculation at an unchanged past knowledge cutoff.

`maturity_policy: explicit_window` requires supplied source windows. For cumulative
snapshots the window end anchors maturity; period metrics additionally require
`window_seconds`. Source-declared windows are preserved assertions, not independent
verification of platform measurement freshness. Collection-only data can use
`collection_proxy` for descriptions, but model inference/validation is withheld.
Missing metrics and denominators remain missing, never zero.

## Production features and context

The existing primitive registry is unchanged: duration, caption length, publication
hour, opening motion/brightness and loudness. No semantic or psychological detector
is added. Account media batches still require explicit `--analyze-media`; URI-only
imports are not decoded media.

Prepare/link local media **before** choosing an evaluation cutoff if its duration
or measurements should be included. A media batch performed after a fixed past
cutoff will not backdate its new associations. Existing migrated topics/links with
no demonstrated capture time remain unknown until a new authorized capture; new
captures do not retroactively change old cutoffs.

The materializer persists subject revision, immutable recipe, input/source and
evidence revisions, content-validity information, availability, materialization
time and missingness. Availability is bounded by actual capture **and recipe
registration**, not an exported publication date. Recipe registration time is a
conservative first-local-use bound, not an invented historical model-release date.
Inherited caption fields retain their supplying revision. Captured topics and
post/media associations have history; changed unresolved media references invalidate
current duration/features without changing a previous cutoff's association.

`retrospective_content` permits later deterministic measurement of captured content,
but does not establish an old caption's original wording or a deployable historical
forecast. `historical_prediction` requires every selected feature and its recipe
to be available by that post's publication. Unknown/late values are excluded.
Training outcomes must also have become known before the test publication block.

Account niche is labeled profile context, not a post-level niche annotation.
As-of account/source versions are frozen; unobserved audience size, traffic source,
paid distribution, collaborations and timezone are explicitly unknown. No missing
confounder is imputed to a benign value.

## Matching and supported claims

Both designs use deterministic, outcome-blind, no-replacement matching with a
distance/ID tie break. Exact context defaults to platform, content type and topic
set. Unknown context cannot be exact-matched. Numeric duration/caption covariates
use pooled standardized distance, a declared caliper, publication-period caliper,
actual maturity tolerance and, for duration, an absolute seconds caliper.

Within-creator pairs require the same creator; cross-creator pairs require distinct
creators. Matching never uses outcome magnitude. The report includes before/after
distributions, missingness and standardized mean differences, retained/dropped
posts, creator count and fixed 0.5×/1×/2× caliper-support diagnostics.

At least five pairs and acceptable declared balance are required to release the
matched descriptive estimate. Otherwise the status is `insufficient_overlap` and
the estimate is withheld; unmatched summaries and candidate-pair diagnostics remain.
These are engineering gates, not proof of exchangeability or adequate power.
Cross-pair creator dependence and unknown confounding prevent a fabricated
independent-pair confidence interval or causal claim. Descriptive pair medians
remain labeled descriptions even when support is adequate.

## The actual model pipeline

The same `ModelPipeline` builds and fits the final model and each validation fit:
declared main effects/raw interactions → training-only creator centering and
scaling → creator fixed effects and identifiable varying context → OLS/Poisson.
Creator-constant niche/platform/context are explicitly absorbed rather than added
as aliased dummy columns. A creator-constant content term, rank deficiency,
ill-conditioning, small/constant/missing data, nonconvergence or invalid count
family returns an explicit insufficiency. Poisson dispersion above 2 is withheld.
No automatic family search or hidden regularization is performed.

Target transforms are `identity` or OLS `log1p`. Inverse log1p predicts a transformed
location, not an unbiased raw-scale mean. Coefficients are returned on their
declared term scales, with that outcome-scale interpretation preserved. Inference
uses creator-cluster uncertainty only with at least 20 supplied clusters; smaller
fits are descriptive with null uncertainty. Account proxies can overcount creators.
Influence diagnostics are labeled OLS-design sensitivity, not GLM influence.

Choose one split: `chronological`, `creator`, `joint`, or `none`. A scoring split
requires a selected model and `holdout_id`. Chronological/joint training purges
outcomes learned too late. Exact media SHA groups cannot cross the split, and
repeated identical media within either side are collapsed. No near-duplicate
detector is claimed; unlinked media has unknown duplicate coverage.

Creator-fixed-effect pipelines cannot predict unseen creator intercepts. Creator
and joint held-out requests therefore return `unsupported_creator_prediction`,
with no auxiliary Ridge score. Chronological validation on known creators records
the actual fitted terms, transform, family/link/covariance, training centering/scales,
post IDs, predictions, MAE and training-only median benchmark. Retrospective scoring
is explicitly **not** historical forecast evidence or independent inferential replication.

## Attempts, holdouts, citations and reproduction

`family_id` freezes a declared outcome/window/estimand and `family_terms`; all
selected main effects/interactions must belong. BY adjustment counts untested
declared terms conservatively as p=1. Repeated attempts remain exploratory; changing
family IDs does not establish global adaptive FDR control.

An attempt is recorded before fitting. Final insufficient/null/failure states are
retained. A reserved holdout is consumed before scoring, even on interruption or
an unsupported model; inspected posts or identical media cannot become a fresh
holdout by renaming it or shifting an overlapping split. Reproduction of frozen
inputs is allowed and explicitly marked, never independent confirmation.

Each corrected analysis creates universal statistical citations for its exact
terms and declared regression/validation/baseline/comparison diagnostics. The
resolver validates the real analysis/result bindings, frozen hashes and run, then
checks transitive input permission/withdrawal. A citation can describe a null or
insufficient result; it is not itself a supported mechanism claim. Archived bytes
stay unchanged; new use/reporting is blocked after input withdrawal.

Reports freeze selected rows and full reference manifests, feature-value bindings,
versions, libraries, seeds and hashes. `performance-1` dispatch preserves the old
algorithms (including historical `0.0.4`/`0.0.5` reports); `performance-2` is explicit.
Exact recomputation still requires matching supported engine/method and numerical
library versions, and recomputed results must match the frozen result hash before
a reproduced run is saved. Unknown versions fail closed; report inspection does not invent
an equivalent estimator.

## Storage and operating limits

The migration adds actual-writer tables: `post_media_versions`, `feature_recipes`,
`feature_values`, `analysis_feature_values`, `analysis_references`, `test_families`,
`test_attempts`, `holdout_uses`, `holdout_members` and statistical entity/evidence
bindings. Existing statistical result/cohort tables remain authoritative.
Completed attempts and new history tables are immutable; a started attempt has
one terminal transition. No Qdrant or graph population participates in inference.

Local runs are bounded to 500 target posts and 5000 captured historical posts.
Reference work grows with target × creator-history size; this release deliberately
does not add a distributed queue, model service or new dependency. Narrow the
declared population or compare explicit post groups when a bound is reached.
Future semantic features, audience series, broader nonlinear/transfer discovery
and mechanism evaluation remain separate milestones.
