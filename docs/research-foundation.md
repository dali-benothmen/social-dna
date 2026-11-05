# R1 — Versioned evidence and draft research registration

Implemented in `0.0.5`, SQLite revision `0005_evidence`. R1 is an offline citation
and registration foundation, **not** a psychological or statistical evaluation engine.
R2–R10 and U1/U2 remain planned. Existing video/account analysis stays available.

## What works

- Resolve original media evidence IDs through the universal registry without changing
  their original task, interval or report bytes.
- Cite exact imported comment spans using Unicode code-point offsets, not UTF-16
  offsets, normalized text or comment publication time as playback time.
- Cite scalar metric snapshots with their exact definition, subject, source, value,
  collection time, supplied reporting window and availability state.
- Register versioned research questions and draft hypothesis specifications.
- Persist JSON/Markdown citation reports, reopen them across processes, and show
  current citation eligibility without rewriting archived report artifacts.
- Revoke source/evidence use through an append-only withdrawal journal.
- Verify canonical hashes/bindings, back up before old-schema upgrades, and restore
  into a separate directory with withdrawal reconciliation or restricted recovery.

No model, platform API, server or embedding is needed. Statistical-result citations
arrive in R2; mechanism operationalizations/evaluation arrive in R7; reevaluation
arrives in R8. Registration never makes a hypothesis evaluation-ready.

## CLI workflow

Use IDs returned by existing imports, analysis reports and timeline queries. Existing
`import csv|json` schemas remain version 1.0; comment imports still require explicit
`comments_permitted: true`. Media must be owned or otherwise authorized.

```bash
socialdna evidence resolve MEDIA_EVIDENCE_ID --format json
socialdna evidence resolve MEDIA_EVIDENCE_ID --run PRODUCER_OR_REUSING_RUN_ID --format json
socialdna evidence cite-comment COMMENT_ID --start 0 --end 19 --format json
socialdna evidence cite-metric SNAPSHOT_ID --format json
socialdna evidence resolve socialdna:metric/SNAPSHOT_ID --format json
```

Creation/resolution returns `ref: {id, revision_id}`. Save both fields in new research.
`--comment-revision` chooses an exact old comment entity revision when creating a
span citation; otherwise the latest captured comment is used. Resolution accepts
`--revision`, `--media`, `--post`, `--run`, `--as-of` and
`--purpose inspect|new_claim`. Mismatched IDs/revisions/ownership are rejected.

`inspect` can successfully return `eligible: false`, limitations, and a withheld
locator. `new_claim` rejects that citation with invalid-input exit code 2. Unknown
availability or evidence later than an `--as-of` cutoff is ineligible; R1 does not
reconstruct historical wording or guarantee publication-time feature availability.

Copy [the draft specification](../examples/research/question.json) and insert actual
returned evidence references. An empty evidence list is valid for an untested draft.

```json
{
  "schema_version": "1.0",
  "key": "cooking-result-first",
  "question": "Why might a finished-meal preview be associated with performance?",
  "population": "Authorized cooking videos in the declared collection period",
  "data_needs": ["Reviewed opening techniques", "Comparable seven-day outcomes"],
  "evidence": [],
  "hypotheses": [
    {
      "key": "anticipation",
      "statement": "A preview might increase anticipated reward.",
      "population": "The declared cooking-video population",
      "intended_claim_level": "hypothesis",
      "data_needs": ["Discriminating construct measurements"],
      "evidence": []
    }
  ]
}
```

```bash
socialdna research register --spec question.json --dry-run --format json
socialdna research register --spec question.json --format json
socialdna research show QUESTION_ID --format json
socialdna research show QUESTION_ID --revision QUESTION_REVISION_ID --format json
socialdna research report QUESTION_ID --format json
socialdna research report QUESTION_ID --report-format markdown --format json
socialdna research show REPORT_ID --format json
```

All these commands use the normal result envelope. Markdown is available in the
envelope's `data.content` and a persisted artifact, rather than bypassing the envelope.
A citation report with withdrawn inputs returns partial status/exit code 5.

The registration key is a stable, case-sensitive local identity. An identical retry
reuses the same question/hypothesis revisions; changed specifications create new
revisions. Hypothesis identities are scoped to their question. Reports cite exact
revisions and describe hypotheses as drafts, even if their intended future level is
association. Causal intended levels and unsupported fields are rejected.

Specifications are bounded to 1 MB, 50 hypotheses and 100 total citation references.
No-write dry runs do not initialize/migrate/lock the data directory or create SQLite
WAL/SHM files. They require a quiescent checkpoint when validating existing references;
active/uncheckpointed WAL data is rejected rather than read incompletely. A real
registration revalidates under the existing writer lock.

## Persistence and source semantics

`entity_identities` and immutable `entity_revisions` preserve identity separately from
captured content. `legacy_entity_bindings` has actual source-row foreign keys; readers
check the kind/identity/payload hash. Mutable comments/posts/accounts are captured,
not merely referenced through a current-row pointer. Legacy backfill records unknown
historical availability rather than inventing prior versions.

`evidence_records`, immutable `evidence_revisions` and exactly one checked typed
binding represent media, comment spans and scalar snapshots. Media retains its
original evidence UUID. Metric URI aliases remain supported. Repeated immutable
measurements keep their original captured subject context despite later post edits.

New import captures and media/task registrations commit with their existing canonical
outputs. The original `TaskContext` and media algorithms remain unchanged. New
research registrations/reports use the entity registry and `evidence_links`; no fake
analysis run or fake media interval is created for them. Hypothesis/report links have
real revision foreign keys and a question scope.

`storage verify` additionally validates registry hashes, typed bindings and backfill
readiness. Missing/withdrawn citations are distinct from structural corruption.
Backfills use deterministic IDs and bounded transactions with committed cursors;
interruption resumes safely on the next normal application opening.

## Withdrawal is not erasure

```bash
socialdna evidence withdraw --source SOURCE_ID --reason "Research reuse revoked" --format json
socialdna evidence withdraw --evidence-id EVIDENCE_ID --reason "Citation withdrawn" --format json
```

Specify exactly one target and a nonblank reason; `--actor` defaults to `local-user`.
Withdrawal is terminal/idempotent in R1. It blocks new claim use, withholds current
locator text/values, propagates through model-input evidence dependencies, and makes
dependent draft/report views stale or partial. New legacy analyses/reports also
refuse withdrawn inputs; the statistical algorithms themselves are not corrected.

Merged legacy post/account metadata lacks per-field lineage. Its use fails closed
if a contributing import source is withdrawn, even when a later partial import exists.
This conservative restriction avoids silently treating inherited fields as freshly
authorized; richer feature/source lineage belongs to R2.

**Retained bytes are not erased.** Historical artifacts remain only under permitted
retention. R1 does not claim a complete privacy-erasure facility; request no forbidden
retention on that assumption. Full audience/raw-import/summary/report redaction and
later index cleanup are R4/R6 work. Required erasure must be handled before continuing
to retain those bytes; a source withdrawal is not a substitute.

## Backup and restore

Normal application opening validates released migration history and creates a verified
pre-upgrade backup before upgrading an existing supported older schema to R1. Existing
schemas 0001–0004 are unchanged. A failed backup/integrity check prevents migration.
The backups are under `DATA_DIR/backups/pre-0005-UUID`; incomplete backups are retained
for inspection and are not accepted without a verified manifest.

```bash
socialdna storage backup /new/checkpoint-directory --format json
socialdna storage restore /checkpoint-directory /new/restored-library \
  --withdrawals-from /latest/original-library --format json
```

Backup uses SQLite's backup API under the writer lock, copies/checks canonical
managed artifacts, and inventories external media. Model weights/runtimes and derived
vectors are explicitly omitted. A backup can preserve reports without being
self-contained for reanalysis. Never infer that externally referenced originals were
copied. Backup manifests carry the library's foundation-ledger lineage fingerprint.

Restore never overwrites an existing destination. The operator must identify the
latest withdrawal authority from the same lineage; its journal is replayed before
normal use. Tombstones for post-checkpoint identities remain effective even if their
source/evidence row is absent from the older backup. This is why privacy-journal
targets deliberately are not source-row FKs; normal withdrawal writers still check
existence. These are privacy obligations, not dangling claim evidence.

Without a known latest authority, restore returns partial status and creates a
restricted recovery marker. Normal application/report/index access is blocked. To
recover with a known authority, restore again into another new destination using
`--withdrawals-from`; do not delete/edit recovery markers to bypass the restriction.
The manifest and database can be inspected for authorized recovery work. R1 cannot
establish that an operator-supplied authority is globally current; choosing it is an
explicit recovery responsibility. Backups retain their own deletion/retention duties.
