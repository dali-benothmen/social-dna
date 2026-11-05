# Source-qualified audience analysis

Implemented in `0.0.8`, SQLite head `0008_audience`. This is a bounded,
offline import → review → content-link → report workflow. It studies expressed
wording in permitted collected comments, not viewers' feelings, recipe attempts,
conversions, retention or causal effects. Human review is attributed annotation,
not independently established annotation accuracy.

## Workflow

First import an authorized [account export](performance-analytics.md) containing
comments and `source.comments_permitted: true`. Ordinary account imports remain
usable without audience manifests or models.

```sh
socialdna import json owned-account.json
socialdna audience comments --post POST_ID --limit 100
socialdna audience import-collection collection.json --dry-run
socialdna audience import-collection collection.json
socialdna audience import-annotations annotations.json --dry-run
socialdna audience import-annotations annotations.json
socialdna audience show COLLECTION_ID --annotation-key reviewed
socialdna analyze audience --collection COLLECTION_ID --annotation-key reviewed
socialdna evidence resolve EVIDENCE_ID
socialdna report generate --run RUN_ID --format markdown
```

Use the returned real IDs and exact revisions, never invented identifiers. The
comment listing supplies captured comment refs, text and `post_ref`; it does not
claim collection completeness. Pagination uses `--after NEXT_AFTER`. Withheld
records expose their identity and eligibility, not their body. No author
identifiers are added. The JSON envelope is enabled with `--format json`.

The [collection template](../examples/audience/collection.json) and
[annotation template](../examples/audience/annotations.json) are schema examples,
not evidence. Replace every placeholder reference and quote with actual captured
data; replace the declared source, sampling, dates and review assertions too.
`--dry-run` checks schema only and creates no data directory. Actual import checks
ownership, permissions, original Unicode spans and content targets before retaining
its canonical JSON source artifact. No scraping or platform connector is added.

Shared Python entry points are in `application/audience_service.py`:
`import_document(settings, path, kind, dry_run=False)`,
`import_into_application(app, CollectionSpec | AnnotationSet)`,
`comments(app, post_id, limit=1000, after="")`,
`show(app, collection_id, revision=None, as_of=None, key=None)`,
`analyze(app, collection_id, revision=None, as_of=None, key=None, literal=False)`
and `load_analysis(app, run_id)`. The CLI contains no alternate analysis logic.

## Collections and denominators

A version-1 collection declares exact post/comment revisions, permission basis,
source URI, collection time, requested publication period, ordering, filters,
sampling method, declared frame, pagination/limit/truncation, supplied count,
known total if supplied, unavailable count and deleted/moderated coverage. Source
lag and retention expiry are optional. These declarations are attributed to the
importer; the engine cannot verify platform sampling or legal authority.

`supplied_count` can exceed retained unique members; that gap is reported rather
than assigned invented exclusion reasons. Eligible comment publication times must
fit the declared period and collection time. A complete declared census requires
non-ranked known ordering, complete pagination and no truncation; even a declared
census is not the population of viewers.

Members can declare exclusion reasons, language and creator-authored status when
actually supplied. Unknown authorship remains unknown. By default, known creator
replies are excluded from aggregates and byte-for-byte identical comment bodies
are grouped once; `creator_policy: include` and
`duplicate_policy: distinct_comment_ids` are explicit alternatives. Grouping does
not normalize the original text or change span offsets. No commenter identities
are inferred, and collections are not pooled as independent audience samples.

Reports distinguish supplied rows, unique/eligible comment IDs, text groups,
duplicates, creator exclusions, unknown authorship and whole-rubric review
coverage. The denominator is actual eligible retained groups/identities, never
`known_total`, plays, reach or viewers. A reported fraction is the fraction with a
confirmed reviewed annotation in that collected sample, not a prevalence estimate.
No annotations yields null fractions. An unannotated comment is not a negative
example. `population_prevalence` is always null; no audience confidence interval
is manufactured from ranked or incomplete data.

## Reactions and curated clusters

The immutable `expressed-reactions-1` rubric defines expressed intention, question,
objection, positive reaction, negative reaction, ambiguous and other. Every
annotation cites one exact original Unicode `[start_char, end_char)` span, quote,
language/uncertainty flags, rationale, provenance and proposed/reviewed/disputed
state. Offsets count Python Unicode characters, not bytes or UTF-16 code units.
Whole-rubric coverage requires an actual full-comment reviewed span.

Only reviewed labels with negation, irony and ambiguity explicitly false enter
confirmed counts. Unknown flags do not become false. Irreducible uncertainty,
conflicting labels and full-review positive/negative disagreements remain visible;
they are not forced into a majority vote. Multiple labels may apply. “I need to
make this tonight” expresses intention, never verified action.

An annotation set records human, deterministic or model origin, author/procedure,
outcome access and optional freeze declaration. Imported model proposals require
provider/model/revision/execution identity and cannot review themselves. Human
adjudication is a new revision with human provenance, not mutation of a proposal.
An explicitly requested lightweight candidate pass is available:

```sh
socialdna analyze audience --collection COLLECTION_ID --propose-literal
```

This uses declared-English literal intention/question rules only, emits proposals,
and never counts them as reviewed results. Unknown/non-English input remains
ambiguous; no sarcasm, behavior or multilingual model accuracy is claimed. It does
not call a model, download weights or inspect performance metrics. Existing local
providers are not silently repurposed into audience classifiers.

Clusters are versioned, supplied curated memberships (`supplied_membership_v1`),
with actual reaction refs, representative/counterexample roles, a summary and
review state. At least one representative is required. Missing counterexamples
are disclosed, not proof that none exist. There is no automatic semantic clustering
or calibrated membership score in this release. Revised membership produces a
new cluster/set revision without rewriting earlier analyses.

## Content links and timelines

Links target an exact post revision or an actual R3 creative event on the
comment's post. Event targets require the exact eligible event citation. Each
link preserves alternatives, ordinal uncertainty and review state, and distinguishes:

- `explicit_reference`: a literal timestamp or quote actually present in the cited
  comment span. Timestamps must fit the actual target event's possible anchors, or
  the actual post video duration with media evidence. Quotes need literal target
  post/subtitle/OCR evidence, not a generated semantic paraphrase. Post text cites
  the exact target post revision; an event quote must cite that event's literal
  input evidence, not unrelated wording elsewhere on the post.
- `human_interpretation`: an attributed, uncertain inference with no fabricated
  playback position.
- `model_proposal`: an unreviewed model inference with declared provider provenance.

A literal `0:02` is a content reference, not proof of when the commenter watched or
reacted. Publication UTC time never becomes playback time. References to unrelated
posts/events, unsupported quotes and out-of-range timestamps are rejected.
Reports display original reaction evidence beside captured event technique,
description, modalities and anchors. This is contextual linkage, not a causal test.

```sh
socialdna timeline show MEDIA_ID --audience
```

The opt-in `audience` lane supplies qualified links and their reaction/context;
inferred links remain untimed. It is a media-level context lane, not a measured
retention track or an assertion that every link falls inside the requested display
interval. Ordinary timelines and previous video reports do not gain audience
content. R1 research registrations can cite audience records and their reports show
qualified audience context, without claiming hypothesis evaluation.

## Revisions, evidence and persistence

SQLite and managed artifacts remain authoritative. The new migration leaves
released `0001`–`0007` files unchanged and preserves prior IDs/report bytes except
explicitly authorized erasure. Exact captured refs compose as follows:

```text
permitted comment/post revisions → collection revision
comment span + rubric → reaction revision → curated cluster / qualified link
collection + ordered reactions/clusters/links → annotation-set revision
exact collection/set/rubric inputs → frozen analysis → JSON/Markdown report
```

The existing entity/evidence revision registry owns canonical JSON and provenance.
`audience_collections`, `audience_collection_members`, `audience_annotation_sets`,
`audience_set_{reactions,clusters,links}`, `reaction_annotations`, `reaction_clusters`,
`reaction_cluster_members`, `content_reaction_links` and `audience_analyses` are
immutable concrete FK projections with actual writers/readers. Ordered dependency
rows and `audience_evidence_bindings` validate exact transitive lineage.
`audience_record` citations resolve through the universal evidence service without
fake media/tasks. The audience analysis has its own real run.

Identical imports/inputs are reused; edits create revisions and new dependent
fingerprints. `--revision` and `--as-of` select exact known inputs; multiple review
keys require `--annotation-key`. Later annotations are not backdated into a prior
cutoff. Expired, erased or withdrawn latest inputs never silently fall back to an
older eligible revision. Pre-R1 captures with unknown availability cannot support
as-of claims; reimport an authorized source to establish actual availability.
Reports are frozen, but current eligibility is rechecked before reuse/reproduction.

No new dependency, embedding collection, graph or distributed worker is introduced.
Imports are capped at 2 MB, 2,000 members/annotations/links, 50 clusters with up to
200 supplied members each, and 100 posts. The optional media overlay refuses more
than 200 collections or 1,000 links. Redaction scans canonical history and is an
explicit, lock-held maintenance operation, not a web-scale erasure service.

## Withdrawal versus irreversible erasure

Withdrawal revokes new use but preserves historical bytes where retention is
permitted. Erasure is a separate destructive command, previewed by default:

```sh
socialdna audience redact --comment COMMENT_ID
socialdna audience redact --comment COMMENT_ID --confirm PREVIEW_HASH \
  --reason "Authorized erasure request" --actor "local operator"
```

Use `--source SOURCE_ID` instead to select an audience-containing source. Preview
lists exact IDs/counts and warns that whole mixed raw imports, annotation sheets,
collection snapshots and dependent reports may be removed. Confirmation must match
the current preview. There is no undo within the active library. All revisions of
the selected comment identity and registered derived copies are covered; independent
comment IDs with identical wording can remain separately authorized.

Confirmed requests create terminal tombstones before cleanup. Canonical comment
text, affected entity/evidence payloads, free-text membership reasons,
source/protocol metadata and registered
derived JSON/report/raw-source blobs are scrubbed or unlinked. SQLite secure-delete,
checkpoint and vacuum remove old text from active DB/WAL files; this is not a
physical-media secure-wipe guarantee. Immutable triggers are restored within the
same transaction. Failures remain pending and deny reuse; normal initialization
rolls cleanup forward before exposing data. Forbidden comment identities/artifacts
cannot be revived by a changed export or later backfill. Evidence retains permitted
tombstone metadata and accurately reports reproduction as unavailable.

Retention expiry blocks new use but is not automatic byte erasure. Use the explicit
erasure workflow when retention requires deletion. Raw imports held outside the
library, independently pasted text, copied reports, snapshots and backups require
separate authorized cleanup; the engine does not claim global erasure. Known local
backups are listed and produce partial overall status. Original source files are
never silently deleted.

Backups are refused while erasure cleanup is pending; reopen the library to finish
cleanup first. Verified backups created after erasure intentionally omit erased blobs. A pre-erasure
backup remains a retention obligation. Restore to a separate directory with the
latest same-lineage authority using the existing `--withdrawals-from` option:

```sh
socialdna storage restore BACKUP_DIR NEW_LIBRARY \
  --withdrawals-from CURRENT_LIBRARY
```

That option now reconciles terminal erasure journals as well as withdrawals before
normal access/backfill. Unknown authority keeps the restored library restricted;
restoration cannot certify the checkpoint is the latest retention state. R6 will
extend cleanup to future indexes/projections; none are populated by this workflow.
