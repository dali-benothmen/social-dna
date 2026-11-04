# Account performance analysis

This milestone provides local, reproducible **observations and associations**, not
causal attribution, a universal virality score, or psychological findings. It needs
normalized exports: see [import formats](import-formats.md).

```bash
socialdna analyze account ACCOUNT_ID --metric demo.views.v1 --age-days 7 --format json
socialdna analyze account ACCOUNT_ID --spec examples/imports/performance-spec.json --format json
socialdna compare posts --left POST_A --left POST_B --right POST_C --metric demo.views.v1 --format json
socialdna compare accounts --left ACCOUNT_A --right ACCOUNT_B --metric demo.views.v1 --unmatched --format json
socialdna report generate --account ACCOUNT_ID --format markdown
socialdna report generate --run RUN_ID --format json
socialdna analyze account ACCOUNT_ID --reproduce-run RUN_ID --format json
socialdna compare reproduce COMPARISON_RUN_ID --format json
```

IDs come from import output or saved report posts. Repeat `--left`/`--right` for
groups; they must be disjoint. `report --account` renders the latest saved analysis,
not a new computation. `report --run` pins an exact historical run. A successful
descriptive result can have `insufficient_data` limitations without being an
execution failure. Partial media batches return exit 5; invalid inputs return 2.

## Outcome and population specification

`--spec` accepts the strict JSON `PerformanceSpec`. Optional CLI `--metric`,
`--age-days`, `--model`, and `--unmatched` override corresponding spec fields.

| Field | Meaning/default |
|---|---|
| `metric_key` | Required versioned post outcome, scoped to one platform/definition |
| `numerator_keys` | Extra numerator components to sum; requires denominator; default empty |
| `denominator_key` | Optional required denominator; no denominator means raw metric |
| `age_days`, `age_tolerance_days` | Target post age 7 days, tolerance ±1 day; no interpolation/extrapolation |
| `window_seconds` | Required exact window width for period metrics |
| `population` | `platforms`, `creator_ids`, `niches`, `content_types`, normalized `topics`, min/max duration seconds |
| `features` | Up to six unique registered content predictors; default duration + caption length |
| `interactions` | Pairs of declared distinct predictors, e.g. `[["duration_seconds", "caption_length"]]` |
| `model` | `none` default; optional `ols`, `poisson`, `gee`, `mixed` |
| `seed`, `bootstrap_resamples` | 42 and 2000 (bounded to 200–10000) |
| `matched`, `duration_caliper_seconds` | Matched comparisons default true, duration difference <=10 s |

One post contributes at most one outcome. Select the nearest nonsuperseded snapshot
to target age within tolerance (earlier observed time breaks distance ties). No
available-at-another-age fallback: an unavailable nearest snapshot remains missing.
Two-year and one-day lifetime totals therefore do not enter a seven-day cohort.
Different platform definitions cannot be combined in an outcome. Rate components
must have identical observed time and window, compatible measurement semantics,
all known values, and a positive denominator. Every required missing component
invalidates that rate; shares/saves/retention never silently become zero.

Example strict engagement rate:

```json
{
  "metric_key": "demo.likes.v1",
  "numerator_keys": ["demo.shares.v1", "demo.saves.v1"],
  "denominator_key": "demo.views.v1",
  "age_days": 7,
  "model": "none"
}
```

## Content feature registry

Features are predefined to prevent importing performance-derived predictors:

- `duration_seconds`: primary local media duration, missing until linked/probed.
- `caption_length`: supplied caption code-point count; absent caption is missing.
- `publishing_hour_utc`: publication hour 0–23 (linear, not circular).
- `visual.motion`: median `visual.optical_flow` for sampled intervals starting in opening 3 s.
- `visual.appearance`: median `visual.brightness` with that same sampling rule.
- `audio.loudness`: median `audio.rms_dbfs` with that same sampling rule.

Aggregates come from the latest successful media run and resolve cached producer
task IDs; they cite the exact underlying evidence. They are sampled, not all-pixel
or duration-weighted measures. Only primary media is aggregated; carousel-wide
analysis and automated language/psychological feature discovery remain later work.
Imports do not reconstruct historical caption edits or verify that an exported
caption was unchanged at publication, so forecasting claims remain limited.

## Statistical safeguards

Every report retains sample/missingness counts, raw-scale summaries, median/MAD,
quartiles, exposure ages, definitions, exact snapshots, cohort members, features,
creator-relative baselines and limitations. Creator baselines use **leave-one-post-out**
reference medians/MAD for ratios/robust z-scores (minimum three reference posts);
zero reference median/MAD yields null, not an infinite score. These retrospective
baselines never become predictive features.

Uncertainty uses a seeded creator-cluster percentile bootstrap of the post median,
not frame/post-independent resampling. At least five observations and two clusters
are required; intervals remain exploratory, especially with few clusters. Single-
creator medians do not get a fabricated independent bootstrap interval. Correlation
reports descriptive post-level Spearman effects. At >=20 creator clusters a separate
permutation test on **creator-median aggregates** is reported with its own estimand
and p-value; its p-value is never attached to a different post-level effect.

Regression is opt-in. Conservative engineering preconditions (not universal proofs
of adequacy) require >=30 complete posts, >=10 posts/parameter, full-rank design,
nonconstant outcomes, no perfect prediction, and condition number <=1e8. Features
and explicit interactions adjust for supplied platform/content-type/niche categories.
OLS/Poisson add creator fixed effects when multiple creators are present.

- OLS: cluster-robust uncertainty for >=20 creators; single-creator chronological
  HAC uncertainty (maximum three lags). Few-cluster multi-creator fits are withheld.
- Poisson GLM: nonnegative count outcome only, robust uncertainty as above;
  Pearson overdispersion >2 withholds results rather than reporting a misfit.
- Gaussian exchangeable GEE and random-intercept Gaussian mixed models: >=20
  creators, each with >=3 posts, plus the design gates above.
- Warnings, nonconvergence, rank failures and nonfinite estimates return
  `insufficient_data`; no unstable regression terms are published.

These models do not eliminate selection effects or unobserved confounding. Influence
diagnostics retain high-leverage/Cook-distance post IDs; these are OLS-design
sensitivity diagnostics, not claimed GLM/random-effect influence calculations.
Benjamini–Yekutieli FDR corrects each exploratory test family (model terms and
creator-aggregate correlations separately), conservatively allowing dependent tests.
All tested terms remain stored; no positive-result filtering.

Matched comparison uses deterministic no-replacement matching on creator,
platform, niche, content type, topic set, declared window width, actual age tolerance,
and duration caliper. Matching never uses outcomes. It reports raw median paired
differences and cluster bootstrap intervals when eligible. Distinct creators cannot
form a same-creator pair: cross-creator account comparisons can legitimately have
zero matches. `--unmatched` instead gives explicitly confounded descriptive group
differences, without independence-based significance claims. With few/no pairs,
the report preserves unmatched summaries and `insufficient_data` limitations.

## Validation, persistence and limits

Predictive checks use training-only median imputation, scaling and fixed-alpha ridge
inside a scikit-learn pipeline. Outcomes are **never** imputed. Chronological holdout
uses the last publication-time block and purges training outcomes collected after
its cutoff; grouped holdout keeps creators disjoint (>=5 creators). The two checks
test different generalizations, not joint time-and-creator generalization. Duplicate
post IDs, overlapping creators in grouped splits, future predictors/outcomes, and
target-derived feature names are rejected. Small or all-missing training splits are
explicitly insufficient. Test preprocessing is never fitted separately or on all data.

Every run atomically stores its full spec, seed, library/engine versions, input hash,
cohort members, frozen post inputs, derived rate inputs, machine-readable terms and
report JSON. Reports include snapshot/source/provenance/artifact locators; media
features cite timeline evidence IDs. New imports do not mutate previous reports.
`--reproduce-run` reruns saved inputs/spec only and requires identical engine/library
versions; it never silently substitutes current data. Re-running the ordinary
account command instead includes newly imported data and reuses media task caches.

Runs are bounded to 5000 candidate posts; narrow the ID groups for larger libraries.
SQLite/artifacts are authoritative. Semantic/vector/graph projections remain deferred
with Milestone 2; analytics does not claim they exist. There is no distributed queue,
automatic platform collection, model selection/search, or causal experiment engine.
