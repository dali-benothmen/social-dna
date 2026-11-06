# Migration, compatibility and retention strategy

Status (`0.0.20` / `0017_images`, 2026-11-06): R1–R10, C1 and U1 have canonical producers; U2 adds portable skill/report compatibility without a new migration. Released migrations `0001`–`0017` remain unchanged. Static media's three FK-backed projections and universal evidence CHECK retain their semantics. See [portable skill/report delivery](portable-skill.md), [static media](image-analysis.md), [architecture](../ARCHITECTURE.md), [roadmap](../PLAN.md) and [research contracts](research-contracts.md). Existing experiment/research schemas are unchanged.

## 1. Compatibility contract

Preserve existing canonical IDs, provenance, media timebase, task input hashes/cache, artifacts, source imports, frozen statistical analyses and report bytes wherever retention remains permitted. Do not replace working media or account storage to introduce research.

Released Alembic revisions `0001_foundation`, `0002_timeline`, `0003_enrichment` and `0004_analytics` are immutable. New migrations are additive descendants. Revision names/numbers for R work are assigned at implementation; an R milestone number is not a migration number.

Compatibility has several distinct meanings:

| Surface | Required behavior |
|---|---|
| Legacy commands | Current invocation/result envelope/exit families and basic workflows remain supported. New research is opt-in. |
| Legacy evidence identity | An original media evidence UUID resolves to its original immutable media/task/interval binding after upgrade. |
| Frozen reports | Read/render stored v1 artifacts without silently inserting corrected baselines, new claims or newer evidence revisions. |
| Frozen analysis reproduction | Use the original specification, exact input manifest and declared engine/library versions; unavailable runtime/source produces an actionable incompatibility result, not a different silent fit. |
| New corrected analysis | Explicit new design/specification/method revision and new result ID; never masquerade as exact reproduction of an old result. |
| Newer schema / old binary | An old engine must refuse an unsupported future head cleanly. Forward data compatibility does not imply safe binary downgrade. |
| Privacy withdrawal | Stop new use immediately; preserve historical bytes only if permitted. Required erasure may intentionally prevent exact reproduction. |

The historical architecture/roadmap under `docs/history/` preserve old design/status context; they are not active implementation instructions.

## 2. Additive schema sequencing

Schema is introduced with its first real writer and consumer:

| Milestone | Additive storage work |
|---|---|
| R1 | Entity identities/revisions, evidence identities/revisions, media/comment/metric typed bindings, evidence links, eligibility metadata and minimal question/hypothesis registration. |
| R2 | Primitive feature lineage/materialized values, new design/specification manifests, as-of reference populations, split/duplicate groups, minimal declared test-family/attempt and holdout-use records, and statistical-result/term evidence bindings. |
| R3 | Creative techniques/events/anchors/relations and semantic recipe projections. |
| R4 | Audience collections/memberships, reactions/clusters/qualified links and source retention/redaction lineage. |
| R5 | Behavioral definition extensions, observation context, metric series/bins, denominators/cohorts, attribution/account-period outcomes and signed changes. |
| R6 | Versioned documents, embedding spaces, desired/indexed generations/outbox, FTS and qualified graph projections. |
| R7, implemented `0011_research` | Reviewed literature/construct/protocol/assessment/finding/brief documents, typed source-excerpt/research bindings and protocol/assessment/dependency projections. Preserve R6 evidence journal/immutable triggers across the CHECK parent rebuild; allow empty-store downgrade but refuse captured history. Extend latest-authority backup/restore schema recognition. |
| R8, implemented `0012_reevaluation` | `research_changes` mirrors/drain-proofs existing producer events and backfills canonical event order; `assessment_watches`, `reevaluation_requests` and `assessment_transitions` add frozen selectors, bounded staleness, checkpointed execution and immutable lineage. No parent-table rebuild or released-migration change. Extend backup/restore latest-authority recognition. See [operations](incremental-research.md). |
| C1, after R7 | Separately versioned professional annotation schemas; publication/metadata/timezone/completeness and thumbnail/profile snapshots; official platform-document statements, surface mappings and distribution observations; compatible profile/link/campaign/funnel bindings, each only with its first writer/resolver/reader. U1 supplies static asset evidence. |
| R9–R10 | Extend the minimal family ledger to bounded adaptive candidate searches; add experiment design/assignment/outcome and assessment integration. |
| U1/U2 | Image/carousel subject bindings and report/skill compatibility metadata only where needed. |

Do not create every future locator or projection in R1. The generic identity/revision registry supplies the extension point. Low-volume future definitions remain validated versioned documents until a query/writer justifies additional tables.

C1-A (`0.0.13`) reuses the existing creative projections and adds no migration;
its professional labels require explicit annotation schema `2.0`. C1-B (`0.0.14`)
adds `0013_context`: immutable context ownership/capture and typed citation bindings,
preserving existing evidence triggers across the locator-CHECK rebuild. Any captured
history prevents downgrade; verified backups remain the recovery path. C1-C (`0.0.15`)
uses the existing context bindings for its four actual producers, with no new DDL.
C1-D (`0.0.16`) adds `0014_profile` for the actually used immutable source event/uniqueness
bindings: real R5 definition and context FKs plus event-code hash. It does not rebuild
parents or create a profile/link/campaign fake-post registry. Captured binding history
prevents downgrade. See the [capability contracts](research-contracts.md#8-production-and-growth-context-contracts)
and [slice verification matrix](intelligence-capability-audit.md#4-bounded-delivery-and-verification).
Preserve account-export v1, the closed R3 annotation v1 vocabulary and existing
post/account metric semantics; unknown labels must not silently become valid in
an old format. Existing profile JSON revisions remain historical captured data,
not retrospectively complete typed profile snapshots.

Introduce new entity/locator/subject kinds only with actual FK bindings, source/clock/missingness validation, no-model imports and a usable report. Do not backfill guessed local timezones, metadata effective dates, profile exposure, surface classifications, individual conversion paths or proprietary weights. New memory builders reuse R6 document/FTS/outbox/graph protocols, extending eligibility, erasure and restore verification for every added payload and asset. No new collection per domain and no edits to released migration scripts.

Existing `evidence_items` retains mandatory media/task/interval invariants. Non-media evidence goes through new typed locators. Existing nonnegative metric constraints remain; signed account changes use a separate new typed representation. Do not broaden old columns so previously rejected inputs silently acquire new meanings.

## 3. Upgrade protocol

### 3.1 Preflight and recoverable backup

Before any future schema upgrade:

1. Read current head/package and migration checksums; reject unknown/corrupt states.
2. Acquire the established data-directory writer lock and quiesce local model/index writers.
3. Verify SQLite integrity/FKs, artifact catalog/hash reachability and available disk space. Separate pre-existing damage from upgrade failures.
4. Produce a consistent SQLite backup through the supported backup mechanism, plus artifact catalog/content needed to restore the checkpoint. Close/snapshot Qdrant consistently if present; derived data can instead be explicitly rebuilt.
5. Record schema/package/configuration/retention manifests and verify restoration into a separate directory before declaring the backup usable. Inventory external original-media and model/runtime dependencies with hashes/availability; backups containing only managed artifacts are explicitly non-self-contained unless all required authorized inputs are included and verified. Missing dependencies constrain recomputation, even when stored reports remain readable.

R1 implements `storage backup|restore` and verified pre-upgrade backups. They preserve canonical SQLite and managed artifacts, inventory external originals, and explicitly omit prepared model runtimes/weights and rebuildable vectors. Restores require a new directory and reconcile an operator-identified same-lineage latest withdrawal journal before normal use, or remain restricted. Copying a live database file without WAL handling is not an adequate backup plan. See [R1 operations](research-foundation.md).

Backups may contain personal/source-restricted data. Record their location/retention and deletion obligations; a backup is not permission to retain withdrawn comments forever.

### 3.2 Expand, backfill, validate, enable

Apply additive DDL in a controlled transaction. Create the registry and migration-progress metadata before bounded backfills. Large backfills use idempotent batches and committed cursors rather than one hours-long write transaction.

Backfill operations have deterministic identity mappings, input hashes and unique constraints. A retry cannot create a different evidence identity or duplicate revision for the same legacy source state. Register every required legacy media evidence binding, or gate its new resolver until the verified bounded backfill completes. Existing legacy readers can continue to read untouched rows.

Validate counts, FK/kind relationships, source hashes, locator bounds, Unicode spans, immutable snapshots and representative report resolution. New research capability remains unavailable until its required bindings pass verification. Do not report a fully upgraded research store merely because DDL completed.

On interruption, resume from committed journal state. SQL transactions roll back incomplete batches; already committed batches are safe to replay. There is no need for a distributed migration coordinator.

### 3.3 Compatibility adapters and writers

Existing media producers may continue writing legacy evidence rows. A compatible transaction hook/adapter registers the same evidence ID and immutable binding. The current `TaskContext` shape is preserved until a separately tested migration is justified; source analysis algorithms do not need a universal-evidence rewrite.

New comment/metric citation writers capture exact source revisions and eligibility in the same canonical transaction. Avoid uncoordinated dual ownership: the legacy row owns its original observation; the registry points to an immutable binding or captured state. It is not a second editable copy.

At R1, minimal registration stores a question and draft hypothesis specification only. It does not invent R7's literature, construct measurements or evaluation results.

## 4. Identity and revision backfill rules

### 4.1 Immutable legacy data

Where existing media, observations, snapshots, tasks and artifacts are immutable, register typed bindings to their actual PKs with content hashes and provenance. Preserve original IDs and UTC/millisecond semantics. Stable alias mappings resolve old citation formats.

Legacy media `evidence_items.id` is reused as `evidence_records.id`. Its first immutable evidence revision binds to the old media/task/interval. New interpretations get new revisions; the v1 citation continues to resolve its original binding rather than whichever revision happens to be latest.

### 4.2 Mutable legacy metadata

A current account/post/comment row may have been upserted. Register a captured immutable payload revision, original source/import references when available and the known capture time. Do not point a historical revision at a mutable current row and call it frozen.

Do not invent historical caption wording, post niche, follower count, edit time or collection coverage that was never recorded. Mark unknown validity/availability and legacy capture status. A frozen old analysis input payload may preserve more historical detail than today's row; retain it as its original analysis source, without asserting unrecorded source history.

### 4.3 References and aliases

New research references require identity, kind and exact revision. Typed bindings enforce real target FKs; services validate the revision belongs to the stated identity/kind. Backfill never creates “media ID 0”, fake timestamps or tasks for papers/comments/metrics.

Legacy metric URI/citation readers remain supported through explicit resolvers. New canonical metric evidence receives a stable evidence identity and alias mapping where necessary; old stored report text stays byte-identical.

Withdrawn/dangling legacy sources are reported as unavailable/withdrawn with permitted audit metadata. A migration cannot repair unknown facts by fabricating them.

## 5. Formats, statistics and report compatibility

Keep strict v1 CSV/JSON import behavior. New audience manifests, series, definition metadata, research specifications and experiment records use explicit schema versions/record types and validators. The chosen minor/major format version is finalized by contract tests; new rich payloads are not silently accepted as v1 scalars.

An upgrade does not reinterpret existing `ratio`/`percent` values as binomial observations, imply denominators, map account-level values onto posts or treat collection time as a precise measurement time. Revised metadata is explicit and source-backed.

Old comparison specifications keep the retrospective baseline/same-creator/legacy validation semantics needed for exact reproduction. Reports and capability status visibly label those limitations. New R2 designs use new versions and cannot inherit an old “validated” badge.

Maintain v1 report readers and envelope schemas while adding versioned research sections/citations. A current view may append eligibility warnings outside an immutable artifact; it must not rewrite archived result bytes. A newly generated corrected report references a new analysis/report identity.

Rendering historical artifacts and recomputing analyses are separate operations. Reproduction requires compatible libraries/models and available input artifacts. If privacy erasure or unavailable original dependencies prevents it, give a precise reason and safe alternatives; never silently substitute modern data/model output.

## 6. Cross-store upgrade and crash recovery: R6

SQLite canonical state upgrades first. Qdrant and graph projections rebuild from eligible source revisions; absence/corruption of an old derived index must not destroy canonical findings.

Introduce document/space/generation keys before index jobs. Canonical writes and desired-index/outbox rows commit together. Index work occurs outside SQL transactions, under the established lock, with current-generation/permission checks and compare-and-swap acknowledgement.

Required fault states:

- Canonical commit before embedding: pending job remains visible and retryable.
- Qdrant upsert succeeds before acknowledgement: replay reuses the deterministic point; hydration accepts only the desired eligible revision.
- Source changes before old work completes: skip/ignore the superseded generation; serialize work per document/space.
- Source withdrawal with queued writes: tombstone dominates; old jobs cannot restore eligibility or source text.
- Rebuild interruption: partial generation is labeled; restart resumes/rebuilds from the canonical manifest.

Changing embedding models creates a separate immutable space/collection namespace. Do not mix vector sizes, prefixes, normalization or representation policies. Keep old space readable until a validated transition/retention policy permits removal; do not promise automatic full re-embedding on every basic command.

Implemented by additive `0010_memory` (`0.0.10`): canonical SQL triggers append
`memory_changes` in the producer's own transaction. A second bounded transaction,
after typed bindings/dependencies exist, publishes documents/citations/FTS/graph,
vector desires/outbox and acknowledges those changes atomically. This refinement
keeps canonical writers model/index-independent without losing pending work.
The whole-directory lock serializes workers, so the outbox needs retryable pending
jobs and generation CAS rather than expiring leases. Rebuild manifests and keyset
eligibility/repair cursors persist across commands. Prepared real-model acceptance
is an explicit opt-in test; fake production embeddings are never supplied. See
[memory operations](research-memory.md) and the R6 architectural decision.

The R4 deny-first erasure journal now includes derived document/FTS text, old FTS
segments, graph relations and Qdrant point bytes. SQLite secure delete, FTS rebuild
and checkpoint/vacuum complete before the journal reports active-library erasure.
Latest-authority restore reconciliation applies this scrub to SQLite memory copies
before normal reads; Qdrant/model files remain excluded from backups.

## 7. Retention, redaction and research eligibility

Distinguish **withdrawal from new use** from **erasure of retained bytes**:

1. In a canonical transaction, mark the source/revision ineligible and affected current assessments stale/withdrawn as appropriate. Record the reason and actor.
2. Exclude ineligible dependencies from new claims, retrieval and current graph/report views immediately, even if physical index cleanup is pending.
3. Purge or redact forbidden raw text, excerpts, artifacts, reaction summaries, embeddings, FTS, graph payloads and generated report bytes. Retain only policy-permitted identity/hash/tombstone metadata.
4. Drain deletion work with generation safeguards; verify no stale outbox/rebuild can resurrect content.
5. Account for backup/export retention and explain any delayed external deletion obligations.

Referential history may remain as a permitted tombstone rather than a dangling citation. Immutable decisions mean that the system does not secretly rewrite what it once concluded; they do **not** override lawful erasure. Historical sources/reports can become unverifiable or unavailable, and that degradation is explicit.

R1 supports withdrawal metadata/current citation eligibility, not full byte erasure; R4 completes audience/raw-import/derived-report redaction workflows and R6 extends cleanup across future projections. Archived bytes may remain only where retention is permitted. An erasure request cannot be satisfied by calling R1 withdrawal. Do not claim one milestone already implements a future store's purge behavior.

Implemented `0008_audience` extends the locator CHECK with `audience_record` using
the existing atomic parent-rebuild procedure. New immutable projections have actual
import/analysis/evidence readers. Erasure is an explicit exception to retained-byte
immutability: preview + current confirmation + reason/actor append a deny-first
journal/tombstones; an atomic scrub restores immutable triggers, unlinks registered
managed blobs, checkpoints/vacuums the active SQLite files and completes the journal.
Interrupted cleanup resumes before normal use. Terminal comment/artifact/source
tombstones prevent reimport/backfill resurrection. Verified backups omit already
erased blobs; restoring an older checkpoint replays the latest same-lineage journal
before backfill and does not create another forbidden pre-upgrade backup. External
backup/export bytes are not silently deleted or represented as globally erased.

## 8. Rollback and forward recovery

Implemented `0009_behavioral` adds only exercised behavioral definition/cohort,
observation, series/bin, attribution, signed-change, analysis and dependency/binding
projections. Negative account changes live outside old nonnegative scalar tables.
Its only parent rebuild extends the evidence locator CHECK with `behavioral_record`;
old IDs, child bindings, constraints and permitted reports remain intact. Upgrades
from all eight released heads and injected populated-rebuild rollback are tested.
Restore authority recognizes the new head and retains R4 terminal-erasure replay.

Before new-format writes, an additive migration may have a tested safe downgrade only if it drops no valuable data and preserves invariants. Do not assume every later revision can be reversed.

After new research data is written, an old binary cannot safely interpret it. Prefer forward repair. If rollback is necessary, restore the verified pre-upgrade backup into a **separate explicit directory**, preserve the failed/new directory for recovery, and explain which new work is absent from the restored checkpoint.

Restoration must not resurrect subsequently withdrawn eligibility or erased source material. Reconcile post-checkpoint withdrawal/erasure obligations from the latest permitted audit/tombstone metadata (including the preserved newer directory) before enabling reports, indexing or new claims; apply required redaction/purge again. If the latest obligations cannot be established, keep the restore in restricted recovery mode for integrity/manifest inspection and authorized review only. An old backup's permission flags are not current authority.

Never automatically downgrade schema, erase new tables, delete a data directory, reset the repository or overwrite a backup to make an old binary start. Destructive recovery needs exact targets and explicit authorization.

## 9. Required automated and operational verification

| Category | Acceptance |
|---|---|
| Released upgrade fixtures | Upgrade from every known head; original migration checksums unchanged; existing rows/IDs, source provenance, media coordinates and artifact hashes preserved. |
| Backfill identity | Repeated/interrupted batches converge to one mapping; immutable legacy evidence IDs resolve identically across processes. |
| Snapshot integrity | Mutable source updates create new captured revisions; old references retain old text/definitions or explicit unavailable state. |
| FK and typed locator validation | Wrong kind, mismatched identity/revision, wrong source/post, invalid span/bounds and dangling target rejected. |
| Producer compatibility | Existing task/context/cache behavior and local video/account/report commands remain working. |
| Frozen analyses/reports | Old report byte hashes and old exact-spec reproduction fixtures retained; new corrected analyses have distinct IDs/versions. |
| Upgrade failure | Inject failures before/after DDL and batch commits; resume safely; no partial research-ready status. |
| Backup/restore | Restore into another directory and run integrity/artifact/report checks before marking the backup valid; identify absent external inputs and reconcile post-checkpoint withdrawal/erasure obligations before normal use. Unknown obligations keep recovery restricted. |
| Withdrawal | New use blocked immediately; derived cleanup/rebuild obeys tombstones; lawful erasure degrades reproduction honestly. |
| Derived-store faults | Outbox replay, stale generations, interrupted rebuild, incompatible embedding spaces and missing Qdrant handled without canonical data loss. |
| Binary compatibility | Current/old binaries reject unsupported future heads clearly; no silent automatic downgrade. |

R1's first demonstrable upgrade is deliberately small: current data → verified backup → additive registry/backfill → original media citation plus imported comment and metric citations → minimal question/spec registration → restart resolution → withdrawal-aware current report. R2 and later migrations add capabilities incrementally against this compatibility foundation.

## Delivered `0016_experiments`

The six new tables are `experiment_registrations`, `experiment_results`,
`experiment_measurement_bindings`, `experiment_analyses`, `experiment_assessments`
and `experiment_hypotheses`. Actual FKs bind entity revisions, scalar measurements,
registration/results, shared attempts and prior research assessments. Payloads and
numeric source snapshots stay in canonical revisions/artifacts, not duplicated in
query columns. Recommendation records reuse the existing research envelope directly.

The migration extends frozen prior metadata and creates only these tables; old
checksums, IDs and report bytes are unchanged. Upgrade/backup/restore authority
recognizes head `0016_experiments`; downgrade refuses to discard registered history.
Confirmed source erasure scrubs dependent canonical/artifact copies while permitted
structural binding/attempt IDs remain. Existing dependency versions are unchanged.

## Delivered `0017_images`

`static_records` binds actual image/carousel analysis runs and source post-media
inputs to real entity revisions. `static_evidence_bindings` supplies the single
typed binding for `image_record` locators, including original-asset citations.
`task_citation_inputs` adds real universal provider-input citations without
manufacturing legacy timed evidence. Reports/features remain canonical revisions,
task results and managed artifacts; no numeric source copies live in query columns.

The new migration composes frozen prior metadata and uses the existing FK-disabled,
transactional/FK-checked evidence rebuild. Existing locator rows, IDs, indexes,
immutable guards and projection-journal triggers survive unchanged. Populated
canonical history refuses downgrade before any table rebuild. Backup/restore
recognizes the new head; source erasure also scrubs original/reused static task
caches and registered display/report artifacts. No old migration or dependency is edited.
