# Behavioral metrics and account outcomes

Implemented in `0.0.9`, SQLite head `0009_behavioral`. The offline workflow imports
authorized aggregate analytics, preserves exact source definitions/bins, compares
compatible retention curves descriptively, and reports signed account changes and
supplied conversion attribution separately. It does not identify causal effects.

## Working commands

Import an authorized [v1 account export](performance-analytics.md) first. Existing
scalar CSV/JSON definitions and nonnegative snapshots remain unchanged. Rich
behavioral data uses explicit **v2 JSON** and its own command, not a relaxed v1 parser.

```sh
socialdna import json owned-account.json
socialdna behavioral subject ACCOUNT_ID --kind account
socialdna behavioral subject POST_ID --kind post
socialdna behavioral subject MEDIA_ID --kind media
socialdna import behavioral definitions-and-cohort.json --dry-run
socialdna import behavioral definitions-and-cohort.json
socialdna import behavioral observations.json
socialdna behavioral show SERIES_ID
socialdna analyze retention --series SERIES_ID --compare-series OTHER_SERIES_ID
socialdna analyze outcomes ACCOUNT_ID --spec account-outcomes.json
socialdna evidence resolve EVIDENCE_ID
socialdna report generate --run RUN_ID --format markdown
socialdna timeline show MEDIA_ID --behavioral
```

Use the returned real `{kind, id, revision_id}` references. Import definitions and
cohorts first; observations then use those returned refs. No forward-reference IDs
are invented. Schema-only `--dry-run` writes nothing or initializes no directory;
actual import atomically checks references, source permission, ownership, domains
and semantic compatibility before retaining canonical JSON source artifacts.

The [definitions](../examples/behavioral/definitions.json),
[observations](../examples/behavioral/observations.json) and
[outcome](../examples/behavioral/account-outcomes.json) templates demonstrate the
actual schemas. They are not evidence. Replace all placeholder refs and source,
cohort, metric, time and permission assertions with real authorized data.
Top-level `--format json` returns the normal agent envelope. Partial/unavailable
results use the existing partial exit code; missing private data is not a crash.

No API connector, scraper, dependency, model download, embedding or graph is added.
Private retention/watch/conversion data remains unavailable unless explicitly
supplied with analytics permission. Source ownership, legal authority and cohort
assertions are attributed, not independently verified by the engine.

## Versioned records and definitions

The envelope is `{schema_version: "2.0", source, records}`. Source fields are
`dataset_id`, `source_uri`, `permission_basis` (creator-owned, authorized or
public-permitted export), `analytics_permitted: true` and optional limitations.
Source URIs are metadata; the engine never fetches them.

| Record | Meaning |
|---|---|
| `behavioral_definition` | Platform-namespaced versioned meaning, subject level, semantics, unit/domain, cumulative/period/series form, numerator/denominator definitions, population basis, replay policy, aggregation and source-definition reference. |
| `audience_cohort` | Exact account revision, known/unknown eligibility, minimized aggregate dimensions and aggregation limits. No individual viewer/author records. |
| `metric_measurement` | Exact account/post, definition and cohort refs, source/reporting/collection clocks, value or explicit availability, optional count components. |
| `metric_series` | Post, definition/cohort, optional exact media, source coordinate system/convention/resolution/completeness and ordered bins. |
| `attribution_observation` | Period conversion measurement plus source attribution model/window, aggregate event-set deduplication key and supplied post credits. |

Keys identify actual scope globally within the library: use account/post-qualified
keys. Corrections create immutable observation revisions but cannot rebind subject,
definition, cohort or reporting window. Different measurements need new keys.
Same-key definition/cohort semantics are frozen; meaning/filter changes require a
new versioned key. Reimporting identical inputs is idempotent, not re-adjudication.

Counts are integer/nonnegative. Signed `net_growth` is account-scoped and
period-defined; negative values never enter old nonnegative count tables. Only
probability definitions use bounded `[0,1]` values. A replay-inclusive watch ratio
may exceed one and rise between bins: it is not automatically a survival curve,
unique-viewer fraction or completion probability. Completion requires its actual
threshold and eligible-start/play basis; different thresholds/definitions are not
silently harmonized across platforms.

Finite actual numbers are checked before float coercion. Booleans, numeric strings
and integers beyond the lossless storage range are rejected. Genuine available
zero stays zero. `not_supplied`, `not_permitted`, `not_applicable`, `failed`,
`unavailable` and `source_suppressed` remain distinct null-valued states with reasons.

Source-reported ratios without numeric denominators remain descriptive. Optional
numerator/denominator counts preserve exact definition, cohort, reporting window
and population basis; incompatible components are rejected. `origin:
ratio_components` computes only from actual compatible components. Missing or
suppressed inputs preserve missingness, and zero denominators produce an
unavailable rate, not zero/infinity. An explicitly unavailable derived measurement
does not compute a value. No binomial interval or independent-viewer sample size
is manufactured, even from supplied aggregate denominators.

## Clocks and source grids

Observations separate `window_start/window_end`, optional effective `data_cutoff`,
`collected_at`, optional `source_generated_at` and declared source lag. Actual
engine `available_at` cannot be backdated by an import. Account point snapshots
can have equal window bounds; period/series windows must be nonempty. Post windows
cannot precede publication. Collection cannot be in the future. Declared lag is
preserved as metadata, not treated as proof of freshness.

Comparisons require known effective data through the window end and aligned post
ages. A late download does not repair unknown freshness or establish historical
prediction availability. `--as-of` and `--revision` select actual known versions
for show/retention; account specs use `knowledge_cutoff`. Withheld latest inputs
never silently fall back to old permitted revisions.

Coordinates are `normalized_progress`, `media_ms` or `provider_index`. Points stay
points and half-open intervals retain both bounds. Ordinals/coordinates are unique
and ordered. Unmarked overlap is rejected; declared overlap needs a reason and
cannot enter the simple comparison. Complete grids need an expected count and
contiguous ordinals. Partial/unknown grids retain explicit coverage gaps; absent
or suppressed bins never become zero.

Media-ms coordinates require actual matching original media/duration. Normalized
coordinates are mapped for display only with a supplied exact media revision
belonging to that post. Otherwise they stay relative. Provider indexes never become
playback time. Arithmetic mappings of coarse boundaries do not create frame-level
observations. There is no default interpolation, smoothing, rebinning or invented
value between source bins.

Comparison requires exact definition/cohort revisions, known cohort, matching
coordinate/convention/resolution/grid, complete nonoverlapping grids, aligned
post-age windows and known source freshness. Incompatibility returns reasons, not
coerced data. Missing values yield missing differences. These are descriptive
differences, not independent posts/viewers or inferred causal effects.

The first comparison path stays within one exact account cohort. Reviewed cross-
account metric/cohort harmonization is not implemented.

The optional timeline lane shows media-level source-grid context beside the
current eligible R3 annotation set. A behavioral report freezes the annotation-set,
event and evidence refs it used. Later event removal changes a new analysis, not
an old report. Withdrawn or ambiguous context is withheld/disclosed rather than
replaced with an old event. Proximity between an event and dip does not prove an exit.

`analyze retention --post POST_ID` selects a single supplied series, requires an
explicit series if several exist, or persists an honest missing-retention report.
Public scalar views/saves never become silent early-retention proxies. Old video
reports and ordinary timelines do not acquire new behavioral lanes implicitly.

## Account changes and conversion attribution

`AccountOutcomeSpec` selects exact definition/cohort refs, `start/end`, optional
knowledge cutoff, and `mode: endpoint_difference | supplied_change`.

- Endpoint mode needs a follower-count definition and compatible actual snapshots
  at both exact effective endpoints. Conflicting sources, unknown cohorts, missing
  endpoints or incomplete freshness withhold the signed account-period difference.
  No nearest-date observation substitutes for a missing endpoint.
- Supplied-change mode needs a signed net-growth period definition and an actual
  measurement for that exact period. It does not derive growth from post performance.
- Per-post account-size joins use both the world cutoff and actual knowledge at
  publication. Late follower exports are not historical predictors. Account growth
  is never assigned to the nearest post.

Conversions have their own actual definitions/observations. Attribution types are
`platform_reported`, `observational_association` or `unknown`; experimentally
identified effects remain outside this slice. Known attribution needs the source's
model and lookback bounds. Credits refer to supplied posts on that account within
the lookback. Fractional weights cannot allocate more than one total. Full-credit
multi-touch observations are nonadditive; missing linkage is not imputed.

Account summaries deduplicate declared aggregate event-set keys and withhold sums
for conflicting duplicates, overlapping conversion windows, partial-window overlaps,
unknown attribution/cohorts, incompatible definitions/models, and missing or
freshness-limited values. Disjoint compatible period totals are added only when
the source definition permits `sum_disjoint`. Lookback overlap alone neither proves
duplicate nor distinct conversions. No causal effect estimate is returned.

## Persistence and boundaries

SQLite and managed raw/report artifacts remain authoritative. Canonical documents
use the universal revision registry. Immutable FK projections cover definitions,
cohorts, measurements, series/bins, attribution, signed changes and analyses,
with dependency rows and exact `behavioral_record` evidence bindings. Actual runs
freeze input/selection manifests; unchanged inputs reuse saved analyses. Exact bin
citations and R1 research reports remain source-qualified, not hypothesis evaluation.

`0009_behavioral` uses the existing atomic FK-checked evidence-parent rebuild.
Released `0001`–`0008` scripts, old scalar constraints, IDs and permitted report
bytes remain unchanged. Empty downgrade works; populated history requires verified
separate-directory restore. Withdrawal/terminal erasure eligibility propagates
through the same resolver; restore still reconciles R4 erasure before reads/backfill.
This milestone adds no new broad deletion command.

Shared Python entry points are `behavioral_service.import_document/import_into_application`,
`subject/show/analyze_retention/load_analysis` and
`performance_service.analyze_account_outcomes`. Numeric helpers live in
`analytics/{metrics,retention,attribution}.py`; CLI adapters contain no statistics.
Local limits: 4 MB/2,000 records/5,000 total bins per export, 2,000 bins per series,
5,000 selected identities per analysis and 200 series in the optional media overlay.
This is bounded lock-held local work, not a distributed analytics service.

Automatic metric harmonization, cohort inference, causal attribution, adaptive
discovery and private platform access are not claimed. Persistent research memory
remains R6.
