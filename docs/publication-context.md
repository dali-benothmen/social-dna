# Publication, packaging and discoverability evidence

`0.0.14`, SQLite head `0013_context`. These offline imports add no dependency,
connector, model or server. Existing account exports and creative v1/v2 formats
retain their semantics. Static assets can be retained/identified, not interpreted;
visual thumbnail analysis remains U1.

## Working interfaces

```bash
socialdna behavioral subject ACCOUNT_ID --kind account --format json
socialdna behavioral subject POST_ID --kind post --format json
socialdna context import publication-context.json --dry-run --format json
socialdna context import publication-context.json --format json
socialdna context recipes --format json
socialdna context show CONTEXT_ID --format json
socialdna context cite CONTEXT_ID --field title/value --start 0 --end 7 --format json
socialdna context publication-report publication-report.json --format json
```

Python callers use `domain.context` schemas and `application.context_service`.
Start from the [schema-valid template](../examples/context/publication-context.json)
and replace all refs, clocks, declarations and source authorization. It intentionally
asserts no collected text, known zone, historical validity or complete inventory.
An export contains `schema_version: "1.0"`, `dataset_id`, `source_uri`,
`permission_basis` and a bounded `records` array. Three typed record kinds work:

- `publication_context`: exact account/post refs; original offset-bearing publication
  timestamp; optional supplied IANA timezone; format, language and its source/confidence;
  explicit title/description/caption field states; optional hashtag/keyword inventories;
  authorized thumbnail variants; declared niche/audience; capture/validity clock.
- `publishing_window`: actual account/post membership, format scope, elapsed half-open
  UTC window and explicit completeness/deleted-or-omitted coverage attestations.
- `trend_context`: account/platform/objective/surface, query, language/locale/niche/
  audience, dated source observation and basis. No automatic trends API or forecast.

Field states distinguish present, explicitly empty, absent, removed, not collected
and unavailable. `clock.captured_at` is supplied source capture, not the engine's
knowledge time. Unknown historical validity stays unknown. Observed validity cannot
be backdated; separately source-attested validity remains an attributed assertion.
Actual revisions are available no earlier than import; no import gains historical
predictive eligibility merely by supplying an old date.

Original local timestamps must include an offset. If a zone is supplied, the local
wall time and offset must match that IANA zone, rejecting DST gaps and offset
conflicts. The offset disambiguates folds. An unknown zone yields unknown local
hour/weekday, not a guessed creator/audience timezone.

Thumbnail entries require `variant`, `placement`, SHA-256 and an explicitly supplied
local `path` (relative to the import file or absolute). Up to 10 MB of valid PNG/JPEG/
WebP bytes are retained by checksum. Expiring URLs are not reproducible assets and
are not fetched. Exact asset citations verify snapshot membership, not visual meaning.
Text citations use bounded slash-separated field paths and Unicode code-point spans
in the captured spec, e.g. `title/value`, `description/value`, `hashtags/0`.

## Reports and comparisons

`PublicationReportSpec` pins exact `publications`, optional `window`/`trends`,
`objective` (`search`, `recommendation` or `conversion`), `surface`,
`outcome_mapping_basis`, an optional existing R2 `analysis_run_id`, `as_of`, and
`policy` (`retrospective` or `historical_prediction`). Set the cutoff after all
intended imports/analysis; timestamps do not authorize future knowledge.

`publication.local_clock.v1` reports local hour, weekday, original UTC offset and
DST fold. `publication.cadence.v1` divides unique posts in the explicitly complete
inventory by elapsed days. Missing completeness, omitted/deleted coverage or a
missing window yields unknown cadence; a claimed complete window cannot omit known
in-scope library posts. Uncollected external posts cannot be independently verified,
so completeness is a source attestation, not an engine guarantee.

An existing frozen version-2 R2 comparison can be attached only when its complete
post population matches exactly. The report includes actual source observations,
availability and the saved comparison, plus the pinned publishing features. It
does **not** refit a model, estimate an effect of posting hour/cadence or find an
optimal schedule. R9 owns new cross-domain fits/discovery. `channel_status` explicitly
labels the objective as declared, not verified traffic attribution; generic total
views do not become search views, recommendation reach or conversions. C1-C/D add
their distinct source mappings. Trend platform/account/objective/surface must match;
trends after the publication decision cannot explain it. Historical-prediction use
also rejects metadata not actually known at publication.

Reports are canonical context records with frozen JSON artifacts, exact dependency
citations and stable identities. Editing a snapshot does not rewrite an earlier
report. Identical records retain their original revision/source when another record
changes. R7 can cite scoped raw publishing context as supplementary observations;
R8's existing journal tracks changes through those exact IDs. A context report cannot
be attached as if it were a raw, population-scoped observation.

## Memory and lifecycle

The existing SQL/FTS/vector/graph path consumes actual typed context citations.
Exact text citations index only their permitted span; graph links are structural,
not evidence that packaging causes success. Source withdrawal denies current report,
feature/context and memory hydration without altering archived bytes.

Confirmed erasure of registered context sources reuses the existing preview/journal,
terminal tombstones and derived-copy cleanup. Preview with
`audience redact --source SOURCE_ID`; confirmation and reason are required as in
[audience retention](audience-analysis.md). The legacy command name is retained;
only registered audience/context sources qualify. Whole dependent reports and raw
mixed-source context blobs may be removed; original post/account/media records,
external exports and backups are not silently erased. Review the preview first.

Integration tests import six real canonical posts/outcomes, run a matched R2
comparison, preserve Unicode/asset citations and historical bytes through edits,
reload in a new process and exercise incomplete windows, future trends, mismatched
objectives, unknown zones, withdrawal and confirmed erasure. Synthetic fixtures
validate software, not real-world optimal schedules, ranking behavior or validity
of a source's completeness assertion.

Verification: all 472 collected tests covered across partitions/final reruns, with
469 passing and three optional prepared-model skips; Ruff, strict mypy (157 source
modules), offline lock/build, installed-wheel recipes/dry-run commands and archive/
source equality checks pass. Migration/backup and the full memory suite pass with
the final migration checksum; no released migration was edited.
