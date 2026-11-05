# Account export contract (version 1.0)

Status: version 1.0 import contract from `0.0.4`, preserved in `0.0.5`. R1 captures
source-backed immutable revisions/citations without changing export fields. Planned
R4/R5 contracts must use versioned extensions and preserve these exports;
see [research contracts](research-contracts.md), [migration strategy](migration-strategy.md),
and [PLAN.md](../PLAN.md). Proposed research records are not accepted by this importer.

SocialDNA imports **normalized, authorized local exports**, not arbitrary vendor CSV
layouts or live platform APIs. Adapt vendor columns into this documented contract;
preserve the platform's actual metric definitions and missing fields. No import
downloads media, calls an API, or runs a model. Synthetic, runnable examples are in
[`examples/imports`](../examples/imports/).

```bash
socialdna import json examples/imports/account.json --dry-run --format json
socialdna import json examples/imports/account.json --format json
socialdna import csv examples/imports/account.csv --format json
# The result includes account_ids and post_ids for subsequent commands.
socialdna analyze account ACCOUNT_ID --spec examples/imports/performance-spec.json --format json
socialdna report generate --account ACCOUNT_ID --format markdown
```

Imports are atomic: any invalid row, reference, ownership change, or conflicting
definition rejects the entire dataset. The CLI returns exit code 2 with row errors
and `written: false`; it never silently imports only the valid rows. Dry-run checks
both the file and references already in SQLite, without initialization/migrations
or canonical/artifact writes. Real imports revalidate under the application lock.
An empty dataset is invalid. Limits: UTF-8, 32 MiB/file and 100,000 records/file.

## JSON envelope

Exactly three top-level keys are accepted:

```json
{
  "schema_version": "1.0",
  "source": {
    "dataset_id": "my-stable-export-series",
    "permission_basis": "creator_owned_export",
    "source_uri": "urn:my-account:analytics-export",
    "comments_permitted": false,
    "terms": {"export_revision": "2026-11-05"}
  },
  "records": [
    {"record_type": "account", "platform": "instagram", "external_id": "00123"}
  ]
}
```

`permission_basis` is one of `creator_owned_export`, `authorized_export`,
`public_permitted`. This records the user's permission assertion; it does not
grant platform rights or bypass terms. `source_uri` is a provenance locator, never
automatically fetched. `dataset_id` stays stable across incremental exports from
the same source. JSON row numbers are 1-based record indices; row 0 is an envelope
error. NaN/infinity, unknown fields, naive timestamps, and numeric IDs are invalid.

## Shared record rules

All records have `record_type` and a lower-case `platform` slug. External IDs are
strings and preserve leading zeros; `(platform, external_id)` is the account/post
identity, not a changeable handle. Record order does not matter. References may
resolve within this import or to previously imported entities.

All timestamps use ISO 8601 with `T` and an explicit UTC offset (`Z` or `+01:00`).
They normalize to UTC microseconds. Publication time and ownership of an existing
post cannot change because stored post ages depend on them. Keep the original
offset/timezone in source terms if needed; publishing-hour analytics currently
uses UTC, not an inferred local timezone.

| Record type | Required fields beyond platform/type | Optional fields / semantics |
|---|---|---|
| `account` | `external_id` | `handle`, `creator_key`, `niche`, `profile` object |
| `post` | `external_id`, `account_external_id`, `published_at` | `content_type` (`video` default, `photo`, `carousel`, `text`), `title`, `caption`, `url` |
| `media` | `post_external_id`, `uri` | `position` integer >=0, default 0; relative paths resolve against the import file |
| `tag` | `post_external_id`, `value` | `kind`: `hashtag` (default) or `topic`; casefolded/trimmed for identity |
| `comment` | `post_external_id`, `external_id`, `body`, `published_at` | `parent_external_id` within the same post; requires `comments_permitted: true` |
| `metric_definition` | `key`, `definition` | `subject_type`: `post` (default)/`account`; `unit`: `count` (default)/`seconds`/`ratio`/`percent`; `measurement`: `cumulative` (default)/`period` |
| `metric_snapshot` | `subject_external_id`, `metric_key`, `observed_at` | `subject_type` default `post`, `value`, `availability`, `reason`, paired `window_start`/`window_end` |

Use the same explicitly supplied `creator_key` to link known accounts of one
creator across platforms. It is an application-wide identity key, not a guessed
real-person identity. Without it, statistics use account IDs as proxy clusters and
warn that independent creator counts may be overstated. Omitted mutable metadata
is preserved on update; supplied title/caption/profile values replace that field.
Tags append; absence from a later export is not a deletion instruction. Comments
are minimized text without imported author identifiers; parents/cycles are checked.
They do not yet include collection sampling/coverage, reaction annotations, or links
to media segments. Comment publication time is wall-clock time, not playback time.
The importer accepts photo/carousel post metadata and references, but this is not
photo/carousel analysis; current batch inference handles local videos only.

## Metric definitions and snapshots

Use explicit versioned keys such as `instagram.views.v1`. The key must start with
the platform slug and contain at least three dot-separated parts. Definitions are
immutable: changed semantics, unit, measurement, or subject scope needs a new key.
Count values are nonnegative integers (maximum `2**53` for lossless numeric storage).
Other values must be finite and nonnegative; percent cannot exceed 100. Ratios are
not automatically capped at 1 (some engagement-per-view formulas can exceed it).

`availability` defaults to `available`, which requires a numeric `value`. Other
states (`not_supplied`, `not_permitted`, `not_applicable`, `failed`, `unavailable`)
require null/omitted value and a reason. Boolean/numeric-string values are rejected.
Never write 0 for an unknown count. An omitted snapshot is reported as not supplied.

`observed_at` is collection time. Windows require both endpoints, with
`window_start < window_end <= observed_at`; post windows cannot precede publication.
Cumulative post windows, when supplied, start at publication. Period metrics require
windows. Post exposure age is measured at `window_end` when present, otherwise
`observed_at`, minus publication time. A correctly supplied reporting window prevents
collection delay from inflating age; without it, collection time is only a proxy and
source lag remains unknown. Current imports do not establish precise historical freshness.
Follower histories use `subject_type: account` and an account-scoped definition;
they are retained but are **not** silently substituted for historical post denominators.
Account-scoped snapshots are not currently outcomes for `analyze account`, whose
performance outcome must be post-scoped. All current values are nonnegative, so
signed net follower growth is not directly representable. Retention curves/bins,
explicit audience-cohort denominators, replay semantics, source-freshness timestamps,
and conversion-attribution contracts require planned versioned R5 extensions; do not
encode them through invented scalar values or zero-filled missing data.

## Deduplication and history

Exact `(dataset_id, file SHA-256)` imports are no-ops. External-key entities upsert.
Identical snapshot cells/values in later exports reuse the existing metric ID.
A changed value or availability at the same subject/key/time/window appends a new
snapshot with `supersedes_id`; original history stays intact. A true correction
back to an older value needs a new export revision/content: reimporting the exact
original file is still a no-op. Conflicting independent sources are retained and
excluded from analysis rather than silently averaged. UPDATEs to metric snapshots
and definitions are rejected by SQLite triggers.

Raw import bytes are retained as checksum-addressed artifacts with source,
permission, dataset, ingestion version and provenance links. Raw exports may contain
sensitive text; protect your local data directory. This milestone does not add a
deletion/anonymization UI. Metadata updates do not change historical frozen reports.

## CSV

CSV is a flat representation of the same record union, not a JSON blob in a cell.
Use a header with the union of needed record fields and leave inapplicable fields
blank. Each row also repeats `_schema_version`, `_dataset_id`, `_permission_basis`,
`_source_uri`; `_comments_permitted` is optional (`true`/`false`, default false).
Metadata must agree across every row. CSV does not have a source `terms` column;
use JSON for richer source metadata. `profile` is JSON in a quoted CSV cell.
`position` and metric-snapshot `value` cells are JSON numbers; tag `value` stays text.
Quote commas/newlines normally. Duplicate headers, uneven row widths, and unknown
columns are errors. Blank means omitted, not zero or a field-clearing instruction.
Error locations use the CSV parser's physical ending line (multiline cells can span lines).

## Local media batch

```bash
socialdna analyze account ACCOUNT_ID --metric demo.views.v1 --analyze-media --depth quick --format json
```

References alone do not invent duration/visual/audio features. `--analyze-media`
registers and analyzes local video references sequentially, then joins their saved
observations to the account cohort. Remote references remain reference-only, even
when remote-model consent is set. Missing, remote or unsupported media are explicit
failed/skipped batch entries; successful media and analytics still persist with exit
code 5 (`partial`). Missing references and posts beyond `--max-posts` are explicit
skips. Default batch limit is 100 posts (1–1000); all references of each selected post
are considered. Analytics currently uses primary media at position 0 only.

The account batch defaults to deterministic signals (`no_ai`). Explicit
`--with-local-models` enables already prepared local ASR/OCR at standard/deep depth
(quick retains its signal-only default);
global `--no-ai` still wins. No remote reasoning or downloads are enabled by this flag.
Changing a media reference invalidates its current post/media link until reanalysis;
the old media and prior reports are retained. Completed media task outputs are reused
on reruns; account batches have no independent resume/queue protocol yet.
