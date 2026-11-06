# Registered experiments and qualified strategies

Delivered in `0.0.18`, SQLite head `0016_experiments` (2026-11-06).
These are analysis-only, offline workflows. Nothing is published, edited, recruited,
purchased or sent to a platform. No model, connector or additional dependency is required.

## Working workflow

1. Import authorized accounts and actual R5 behavioral definitions. Select the real
   platform, surface, format, language, market, audience, niche and objective.
2. Register a prospective two-arm design with planned slots, exact source outcome
   definitions/windows, fixed complete-roster stopping and an execution/ethics plan.
   The engine freezes seeded assignment inside matched two-slot blocks. A planned
   slot is not an already-published post and does not fabricate a post identity.
3. Execute outside SocialDNA, under separate authority. Import the actual posts,
   compatible source-defined R5 measurements and applicable C1 execution context.
4. Import source results with exact assigned-unit mappings, missingness, deviations
   and a cited execution review. This review is an attestation, **not automatic
   verification** of randomization fidelity, interference, source truth or permissions.
5. Analyze the frozen results. Ineligible comparisons remain stored and descriptive;
   they are not converted into causal conclusions or dropped because they failed.
6. Optionally link all registered R7/R8 rivals to a new experiment assessment.
   Render an evidence-qualified next strategy from structured proposals and citations.

```sh
socialdna --data-dir ./data --format json experiment register --spec experiment.json
socialdna --data-dir ./data --format json experiment import-results --spec results.json
socialdna --data-dir ./data --format json experiment analyze RESULTS_ID --revision RESULTS_REVISION
socialdna --data-dir ./data --format json experiment show ANALYSIS_ID --kind experiment_analysis --revision ANALYSIS_REVISION --reproduce
socialdna --data-dir ./data --format json recommendation create --spec recommendation.json
socialdna --data-dir ./data --format json recommendation show RECOMMENDATION_ID --revision RECOMMENDATION_REVISION
```

Uppercase IDs above are references returned by prior commands, not invented fixture IDs.
`experiment show` defaults to `experiment_registration`; use `--kind` for results,
analysis or assessment. All commands use the existing JSON envelope/error conventions.
Malformed specifications are rejected before creating a library.

## Registration contract

The executable contracts are `research/experiments.py`'s `ExperimentSpec` and
`ExperimentResults`; unknown fields are rejected. Exact JSON schemas can be obtained
through their Pydantic `model_json_schema()` methods. No pseudo-schema is accepted by CLI.

| Field | Delivered meaning |
|---|---|
| `key`, `version`, `predecessor` | Stable design identity; first version is 1. An amendment needs the exact predecessor, next version and must precede execution/results. Old bytes remain unchanged. |
| `scope` | R9 `Scope`: platform, surface, native_format, language, market, audience, niches, objective, traffic, period_start/end and source-frame basis. Account platform/niche and slot period are checked. Other population attributes remain source declarations, not inferred truth. |
| `domain` | `production`, `publishing`, `distribution` or `profile`. Profile requires conversion; distribution requires search or recommendation. |
| `assignment_unit`, `assignment_method` | `post`/`account_period` with `engine_block_randomized` or `nonrandomized`; `impression` only with `source_native`. Native aggregate imports remain descriptive in this release. |
| `variants` | Exactly two different `{key, change}` entries: first control, second treatment. |
| `units` | 2–200 unique `{key, account: EntityRef, block, starts_at}` planned slots. Engine assignment requires two slots per block and no supplied `variant`; other methods require supplied variants. |
| `outcomes` | 1–6 unique keys and distinct actual behavioral definition revisions; exactly one primary. Each declares `role`, `direction`, `minimum_meaningful_difference`, `window_seconds`, optional `window_offset_seconds` and `lag_seconds`. Mechanism outcomes additionally require an actual reviewed/unvalidated `operationalization` reference. |
| `analysis_method`, `seed`, `permutation_resamples`, `stopping` | Pinned `paired-assignment-1`, seed, 999–19999 bounded resamples (default 9999), `fixed_complete_roster_no_interim_looks`. |
| Design review | Required `precision_rationale`, `held_constant`, `interference_plan`, `authority`, `ethics_and_permissions`. A narrative rationale is not a verified power calculation. |
| `origin`, `context` | Optional eligible EvidenceRefs and real context entity revisions; not arbitrary payloads or top-K samples. |
| `prior_assessment`, `predictions` | Optional exact R7/R8 assessment and one `{hypothesis, outcome_key, direction, rationale}` per prior rival. None can silently disappear. |

Engine randomization must precede every slot. Units need actual account revisions, but
actual post revisions are supplied later, at result import. Do not upload content just
to create a prospective slot. Historical/nonrandomized comparisons may be recorded;
neither backdating nor supplying arm names makes them prospectively randomized.

## Actual results and eligibility

`ExperimentResults` requires `key`, exact `registration`, `source_uri`,
`permission_basis` (`creator_authorized_results` or
`permitted_native_experiment_export`), `collected_at`, `review` and `units`.
Corrections require the exact `supersedes` results revision and `correction_reason`.
There is one correction stream per registration; exact retries are idempotent.

Each unit result binds `unit_key`, actual measured `subject`,
`implemented_variant`, `outcomes` mapping registered keys to actual R5
`metric_measurement` references, optional actual C1 `context`, and `missing_reason`.
Omitted units/outcomes remain missing on the full frozen roster, not zeros.
Unregistered units/outcomes, wrong subjects/definitions/windows and reused
measurements within a roster are rejected. Account/post ownership and publication
slot must match; windows begin at the registered slot plus declared offset.

`review` requires reviewer, basis, eligible source evidence and explicit
`allocation_intact`, `no_spillover`, `no_carryover`, `no_concurrent_changes`,
`no_interim_looks`, `complete_roster` values. False/unknown values or any `deviations`
withhold inference. Collection must cover the final slot's outcome window plus
declared lag. Actual effective source cutoffs, source collection, definitions and
compatible known cohort eligibility/dimensions are checked separately.

Only period scalar measures are eligible: no follower stocks, unknown population
bases, retention-bin pseudo-replication or imported attribution credits. R5 retains
source numerator/denominator semantics. A per-unit source rate is a per-unit outcome,
not a pooled viewer-weighted rate. Analysis cannot manufacture private analytics.
An imported value already used in another registered experiment is disclosed and
withheld from a new inferential interpretation.

Domain gates add to these shared requirements:

- Publishing needs source-attested historical packaging or a complete account-period
  inventory covering the outcome exposure window.
- Distribution needs the actual C1 early/later measurement mapping, same
  platform/surface/traffic and compatible language/format/market/audience/niche.
  Aggregate views are not inferred recommendation exposure or recovered weights.
- Profile needs source-bound follow/install/purchase definitions and actual C1
  funnel references with exact-version source-attested profile exposure and measured
  stages. Public rubric quality alone does not measure conversion. Repeated periods
  on the same account are withheld for unsupported carryover even if counts rise.
- Production can use an actual reviewed assigned creative contrast without pretending
  a psychological mediator was measured. New action effectiveness remains untested.

## Statistical method and deliberate bounds

Inference requires at least **20 independent matched blocks** (at most 100), complete
outcomes and no recorded threats. This engineering gate is not a power guarantee.
Post pairs must share one supplied creator within each block; a creator cannot span
blocks. Account periods cannot repeat an account. Supplied ownership and interference
attestations remain assumptions; overlapping audiences cannot be automatically ruled out.

The estimand is the equal-block mean of treatment-minus-control differences. A bounded
seeded within-pair sign-swap simulation tests the sharp no-assignment-effect null,
with a +1 Monte Carlo correction. Holm-adjusted p-values include the **entire declared
outcome family**, counting unavailable tests as p=1; simultaneous paired-t intervals
use Bonferroni across that same family. See SciPy's
[paired randomization guidance](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html),
[paired mean comparison](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html)
and statsmodels' [Holm implementation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html).
Intervals rely on independent blocks and the usual approximate sampling assumptions;
they are not exact randomization confidence bounds or mediation estimates.

Support requires an adjusted p-value at most .05 and the directional simultaneous
interval exceeding the registered meaningful-difference threshold. A significant
opposite interval is contradiction; other eligible results are inconclusive.
Missing/invalid designs and degenerate block differences withhold p-values/intervals
and retain descriptive differences as `insufficient_data`.

The strongest lane is `randomized_assignment_effect_conditional_on_review`, not
unqualified causation. Sequential unrandomized uploads, tiny samples, nonrandomized
pre/post profiles, source-native arm aggregates and deviations are descriptive.
Impression totals never become independent sample size simply because they are large.
No native-impression causal estimator, multifactor design, repeated-period carryover
model, attrition correction, sequential stopping guarantee, online FDR, mediation
identification, universal transfer or sustained-growth guarantee is delivered.

Analysis records the real shared test family/attempt before fitting, including
failures. Corrections generate new analyses, never independent-replication claims.
`show --reproduce` checks the exact engine/numerical library versions and frozen
snapshot, without another fit attempt, current-data join or external action.

## Hypothesis feedback and recommendations

An optional `experiment_assessment` appends a distinct history lane to
`research history`. It binds the actual analysis, prior question/assessment and every
registered rival. Treatment predictions can be supported, contradicted, inconclusive
or insufficient; **mechanism status stays `not_identified`**, including when a measured
construct changes. R7/R8 assessments, reports and reevaluation semantics are unchanged.
`ClaimValidator.validate_experiment` accepts only the eligible conditional assignment
lane; it rejects mediator-proof language.

`RecommendationSpec` requires `key`, `domain`, full `scope`, 1–4 `actions`, 1–30
distinct `evidence` entries, `counterevidence_search`, `uncertainty` and `next_test`.
Each action names a closed domain target plus `change`, `hold_constant`, `measure`
and `falsifier`. Evidence entries carry actual EvidenceRef, support/counterevidence
role, declared direct/indirect applicability and rationale. C1 context is required for
publishing, distribution and profile branches. See `research/recommendations.py` for
the exact target vocabulary (craft/editing; packaging/schedule; observable distribution
response; profile/link/pins/positioning). Changed proposals require exact `supersedes`.

These are **structured author/agent proposals qualified by the engine**, not an
automatic trained optimizer or free-form model recommendation. Actual producer lanes,
tested outcomes/failures, evidence date, scope matches, stale sources and counterevidence
are retained. Official guidance is not a local effect; reviewed literature is not local
replication; observational findings are not randomized results; a public-profile rubric
is not actual follows/installs. Raw craft suggestions receive an unvalidated-heuristic
caveat. Missing counterevidence citations are explicitly disclosed, not proof of absence.

Every output is `test_first`, `expected_lift: null` and
`external_execution_authorized: false`. New wording/edits are not proven effective by
a cited prior result. Obvious guarantee/hidden-weight/mediator claims are rejected;
an eight-word overlap guard checks proposed change text against cited creator spans.
This is not comprehensive plagiarism detection or semantic verification of prose.

## Storage, memory and retention

Canonical immutable revisions hold registration, assignments, source snapshot,
analysis, assessment and recommendation; real universal research locators cite them.
`0016_experiments` adds six FK-backed query/binding tables, not a second research store.
Existing family/attempt, artifact, SQL/FTS, optional Qdrant and qualified NetworkX
infrastructure is reused. Structural graph edges do not imply causal relationships.
Released migrations `0001`–`0015` and dependency versions are unchanged.

Source revisions and corrected outcomes preserve old frozen bytes while permitted;
current memory/proposal freshness excludes stale dependencies. Source withdrawal gates
new use immediately. Confirmed erasure scrubs dependent canonical payloads and
artifacts, with explicit loss of reproduction; only permitted structural audit IDs
remain. JSON archives are frozen reports, not the future U2 polished report/skill UX.

Controlled tests establish software contracts, not real platform efficacy or validated
psychological mechanisms. U1/U2 and independent real-source validation remain separate.
