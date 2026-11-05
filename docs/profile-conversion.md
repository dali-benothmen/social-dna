# Profiles and measured account conversion

`0.0.16`, SQLite head `0014_profile`. Offline imports, qualified human assessments
and source-defined account funnels work without a model, connector or server.
Profile quality and measured follows/installs are independent output lanes.

```bash
socialdna profile rubric --format json
socialdna profile import owned-profile.json --dry-run --format json
socialdna profile import owned-profile.json --format json
socialdna context show PROFILE_ID --revision REVISION_ID --format json
socialdna context cite PROFILE_ID --field bio/value --start 0 --end 20 --format json
socialdna profile report profile-report.json --format json
```

`ProfileExport` contains schema `1.0`, `dataset_id`, `source_uri`, `permission_basis`
and bounded typed records. Import underlying account/posts/R5 definitions and metrics
first; subsequent files use the exact returned refs. Source authenticity, owner
authorization and supplied human review remain explicit trust boundaries, not automatic
OAuth verification or independent scientific validation.

Start from the [unknown-only snapshot template](../examples/profile/public-profile.json),
replace its actual refs/clock/authorization and populate only genuinely captured fields.
It asserts no profile quality, historical exposure, complete inventory or conversion count.

## Public snapshots and assessments

`profile_snapshot` captures actual account/clock, username, display name, bio, category,
positioning, owner/source-declared pillars, photo identity, ordered links and ordered
actual pinned-post refs. Text states distinguish present, explicitly empty, absent,
removed, not collected and unavailable. List states distinguish collected/empty from
not collected/unavailable. Pins must belong to that account and exist by the claimed
observation/validity time. An arbitrary historical account JSON blob is not silently
promoted to a complete profile snapshot.

Photos use explicitly supplied local PNG/JPEG/WebP bytes, SHA-256 and managed artifact
membership. The shared bounded asset capture verifies bytes, not appearance, identity,
sensitive attributes or professional branding quality. U1 owns automatic static visual
analysis. Links are captured destinations, not permission to follow them. Credentials
and known secret-bearing query parameters are refused; destination spans are not
projected into semantic indexes. Exact source text/asset citations remain available.

For one stable snapshot key, current reads/memory use the newest source capture,
breaking capture-time ties by revision. Importing a corrected older observation does
not turn it into today's profile. Explicit revision reads preserve history. Separate
source keys remain separately attributed observations, not a guarantee of current
public truth. Capture, source-attested validity and engine import knowledge remain
distinct; no snapshot automatically establishes prior audience exposure.

`profile_review` uses immutable `profile.qualitative.v1`, with six explicit criteria:
bio clarity, CTA clarity, link consistency, pin alignment, pillar consistency and
profile consistency. Every criterion retains supported/mixed/unclear/unknown state,
rationale, actual scoped citations and contrary examples. Non-unknown judgments need
evidence. Review date/procedure/reviewer/outcome access are recorded. A declared post
sample requires actual ownership and a nonempty source-time window; performance
metrics cannot substitute for profile/post-text evidence. Owner declarations are not
silently reclassified as reviewer findings.

This is human-reviewed qualitative evidence, not an automatic quality detector,
personality model, universal score or measured conversion effect. Positive judgments
do not generate follows, clicks, installs or revenue values. A changed rubric needs
a new pin; changed source evidence needs an explicit new review.

## Source-defined branching funnels

`funnel_definition` binds actual R5 behavioral definitions to source event codes,
roles and uniqueness. It preserves the exact source-definition excerpt, report,
reviewer, join basis, deduplication and limitations. Supported roles are attention,
profile visits, follows, link clicks, app installs, purchases, returning followers
and churn, when those actual source counts are supplied.

The small `funnel_event_bindings` SQL projection has real R5-definition/context FKs
and immutable event meanings. A click counter cannot be relabeled as installs, or
change uniqueness, merely by renaming a stage. Meaning changes require a genuinely
new source definition/version and review. Hashed source-code identity and generic
meaning/uniqueness survive erasure as non-sensitive anti-relabeling metadata; raw
source code/text is scrubbed with its canonical source. No new graph/store is added.

`funnel_context` references actual account-period R5 scalar measurements. Follows,
installs and purchases require actual conversion definitions, not follower stock,
signed net changes or a profile-review score. R5 continues to own metric units,
source permission, availability, cohort and effective/collection clocks. Private,
suppressed or missing counts stay unavailable; a positive bio assessment cannot
fill them. Returning-follow/churn roles require their actual source counts, not an
inference from net follower change.

Rates need compatible exact known cohorts, account units, source uniqueness/dedup,
effective windows, a positive denominator, a source-reported subset relationship and
actual linkage citations to the source-join manifest. Contradictory nested counts,
unlinked aggregates, missing owner data, unknown uniqueness, incompatible windows or
denominators yield an explicit unknown rate and reason. Shared denominators can serve
different branches; repeating one conversion numerator/counter cannot create credit.
No single linear attention→visit→follow→click→install journey is reconstructed.

Optional profile context defaults to unknown historical exposure. Source-attested
exposure requires its exact actual snapshot, a declared covering historical validity
interval and source evidence; it is still not independently audited individual exposure
or a causal effect. Account-wide data does not become a native profile-version/link/
campaign metric subject. Public link/pin context is supported; native per-link/campaign
metric subjects need their own real source-specific first-use extensions when available.
No fake post IDs or reinterpretation of R5's free-form campaign labels is introduced.

Optional R5 attribution records retain their actual source model, lookback, cohort,
window and supplied post credits. They must match actual funnel stage values/definitions;
duplicate/overlapping credit is refused. Different outcomes are kept in separate summaries.
Unassigned fractional credit is the remainder of supplied allocation, not reconstructed
individual people or newly allocated profile/post credit. Source multi-touch limits and
unallocated/unknown cases remain explicit. The engine never assigns growth to a nearest post.

## Reports, memory and lifecycle

`ProfileReportSpec` pins distinct chronological `prior`/`later` snapshots, optional
reviews of those exact versions, an optional actual owner funnel and `as_of` cutoff.
Reports contain captured-value/availability differences, qualitative profile assessments
and measured account-funnel observations separately. They do not claim that an
uncollected field was removed, that a new bio caused growth or that all stages describe
the same individuals. A source-exposure variant must belong to the compared snapshots.

Shared canonical context reports and JSON artifacts preserve exact history. Default
memory hides superseded review/context dependencies; pinned history remains subject
to permission and erasure. Raw profile snapshots can be population-scoped R7 supplementary
context, not psychological mediator evidence. New profile research/associations,
recommendations and prospective experiment outcomes remain R9/R10.

Existing SQL/FTS/Qdrant/qualified graph builders retain literal scope and distinct
`qualitative_human_assessment` versus `measured_aggregate_not_causal` labels. They do
not add quality→success causal edges. Source withdrawal withholds dependent reports
without rewriting archived bytes. Confirmed source erasure reuses the existing
preview/journal/tombstone workflow (`audience redact --source SOURCE_ID`) and removes
dependent active-library blobs/index copies. Original independent account/post/metric
sources, external exports and backups are not silently deleted; inspect the preview.

The integration compares two actual saved profile snapshots, photo/link/pin identities,
an evidence-backed frozen review, source-defined follows/installs/purchase counts and
compatible branching rates. It exercises old-observation corrections, missing private
metrics, stock-versus-flow, counter relabeling, source attribution/unassigned credit,
duplicate events, restart, memory, withdrawal and confirmed erasure. Synthetic owner
counters validate software, not actual profile effectiveness or scientific causality.

Verification: all 482 collected tests covered across full regression partitions and
targeted final reruns, with 479 passing and three optional prepared-model skips.
Ruff, strict mypy (166 source modules), offline lock/build, installed-wheel rubric/
dry-run commands and archive/source byte equality checks pass. No base dependency
was added; no released migration was changed.
