# Platform guidance and observable distribution

`0.0.15`, database head `0013_context`. These are offline evidence writers and
source-qualified reports, not live connectors or proprietary algorithm recovery.
No dependency, migration, server, collection or new statistical engine is added.

```bash
socialdna platform templates --format json
socialdna platform import platform-inputs.json --dry-run --format json
socialdna platform import platform-inputs.json --format json
socialdna context show RECORD_ID --revision REVISION_ID --format json
socialdna context cite DOCUMENT_ID --field source_text --start 0 --end 40 --format json
socialdna platform report platform-report.json --format json
```

## Typed evidence and scope

`PlatformExport` contains `schema_version: "1.0"`, `dataset_id`, `source_uri`,
`permission_basis` and actual `records`. References must already exist; import
documents/definitions first, then records that cite the returned revisions.

| Record | Required evidence and boundary |
|---|---|
| `platform_document` | Actual research-account scope, platform/surfaces, official publisher/HTTPS origin, permitted exact captured text and SHA-256, capture scope/clock, known publication date, human-supplied review status/reviewer/basis and revision reason. The account is research scope, not ownership of the publisher. |
| `platform_statement` | Exact document revision and Unicode excerpt, one applicable surface, interpretation and limitation. Its claim level is `official_guidance`, never a study finding, observed effect or ranking-weight estimate. |
| `platform_capabilities` | Exact account, platform/surface/format/language/market/niche/audience scope; permitted analytics/access/report/method/lag; actual R5 definition refs with roles and availability; reviewed raw source-code → surface/organic/paid/collaboration/unknown mapping. A source capability is an attributed statement, not automatic API verification. |
| `distribution_observation` | Actual account/post, capability revision and source traffic code; two existing R5 scalar period measurements with exact definitions/cohort/windows, effective cutoffs, collection times and source authority. |

Origin allowlisting is URL hygiene, not authenticity verification. The engine checks
hashes, source spans, ownership, kind, timing, roles, source availability and permission
lineage. A supplied human review remains a trust boundary; no model/HTTP fetch silently
certifies a document. Unreviewed/withdrawn documents cannot support statements or reports.

Separate research templates exist for Instagram Feed/Explore/Reels/Search, TikTok
For You/Search, and YouTube Home/Suggested/Search/Shorts. Shared validation does not
imply shared ranking rules or coefficients. These names are explicit research scope;
actual native report codes require source-specific reviewed mappings.

## Working reports and refusals

`PlatformReportSpec` pins `account`, `scope`, `statements`, `observations`, traffic
context, minimum lag and actual `as_of`. Only `descriptive_observational` reports
are supported. The official lane retains document dates/clock/URL and exact claims;
the observed lane retains actual numeric pairs, source metric units/definitions,
cohort, mappings, windows, lag and citation refs. New-process reads preserve lane labels.

The comparison is a descriptive table of eligible early/later post-level observations,
including failures, not an estimated causal or proprietary ranking model. Duplicate
posts or mixed source metric definitions cannot inflate a comparison. New association
fits and broader discovery remain R9. Source creator-experiment exports are not promoted
to randomized/causal evidence; executed experiment designs/outcomes remain R10.

Response/distribution windows must be nonempty, effective-cutoff complete, period-based
and non-overlapping. Retention/completion/watch-time roles must agree with their actual
R5 meanings; share/save and exposure roles require compatible source counts. Early and
later measurements must use the exact same known source cohort/post. The raw traffic
code must be present in that cohort, not inferred from a view count.

Event time is not knowledge time. `early_known_before_later` separately reports whether
the engine actually had the early measurement before the later window. Retrospective
exports can describe time-ordered event windows, but are not prospective predictions.
Same-window feedback leakage, unavailable/suppressed/private metrics, incompatible
definitions, different platform/surface/context or ownership are rejected. Unknown
surface/traffic or insufficient lag produces explicit refused rows and, when no eligible
pairs remain, `insufficient_distribution_access`. Missing metrics do not become zero.

No report estimates hidden eligibility, satisfaction, penalties or proprietary weights,
bypasses recommendations, promises reach or guarantees virality. Official guidance is
not an empirical result, and an observational pair does not establish causal direction.

## Version history, memory and erasure

A normal new document version does not retroactively rewrite historical policy or prove
an algorithm changed. Pinned historical reports retain their source version and bytes;
default current memory hides statements/reports whose context dependencies are superseded.
A declared correction/withdrawal invalidates old source use and requires new human review.
Permission withdrawal also gates transitive report/SQL/FTS/vector/graph hydration.
Confirmed context-source erasure reuses the preview/journal/tombstone workflow described
in [publishing context](publication-context.md); dependent active-library artifacts are
removed, while external exports/backups require separate cleanup.

R7 does not reinterpret platform guidance as psychological mechanism evidence. Canonical
records, exact citations and scoped memory are available for R9. R8's existing dependency
journal can track context IDs consumed by assessed research; these descriptive context
reports do not themselves create R7 assessments or trigger automatic fits.

## Grounding and access limits

Official sources rechecked during delivery on 2026-11-05. YouTube explicitly separates
recommendation surfaces and their signals; Meta describes multiple ranking systems.
Those sources support the **design inference** that scope must stay platform/surface-
specific, not an assumption that their historical descriptions reveal current weights.
See [YouTube Help](https://support.google.com/youtube/answer/16089387?hl=en) and
[Meta's dated explanation](https://about.fb.com/news/2023/06/how-ai-ranks-content-on-facebook-and-instagram/).
[TikTok Help](https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content)
returned no readable body to the research tool during delivery; no fabricated TikTok
official statement is seeded. Authorized reviewed local captures remain importable.

No built-in adapter promises current API fields, permissions, quotas, history depth,
privacy thresholds or report compatibility. A real adapter must verify then-current
official access and retain source lag/availability. Public competitor totals cannot
substitute for private owner retention, traffic-source breakdowns or conversion analytics.

Tests exercise all three platform scopes with real canonical source-qualified R5
measurements, non-overlapping windows, unknown traffic, paid/organic separation,
corrections, restart, qualified memory, withdrawal and confirmed erasure. A permitted
short YouTube excerpt exercises exact official-source provenance. Controlled counter
fixtures test software and failure retention, not real platform distribution effects.

Verification: all 477 collected tests covered across full regression partitions and
targeted final reruns, with 474 passing and three optional prepared-model skips.
Ruff, strict mypy (160 modules), offline lock/build, installed-wheel templates and
packaged/source byte equality checks pass. No live API access or hidden-weight
recovery is inferred from these software tests.
