# Incremental research and preserved history

Implemented in `0.0.12`, SQLite `0012_reevaluation`, building on the
[reviewed research workflow](psychological-research.md). This is explicit,
bounded cumulative reanalysis, not autonomous scientific discovery or independent
replication. No new model, package dependency, collection or server is required.

## Commands

```bash
socialdna research status --limit 100
socialdna research reevaluate ASSESSMENT_ID
socialdna research history QUESTION_OR_HYPOTHESIS_OR_ASSESSMENT_ID
socialdna research show ORIGINAL_ASSESSMENT_ID
socialdna research show ORIGINAL_ASSESSMENT_ID --revision ORIGINAL_REVISION_ID
socialdna research report ORIGINAL_ASSESSMENT_ID --revision ORIGINAL_REVISION_ID
```

Use the existing global `--data-dir`, `--offline` and `--format json` options as
needed. Python callers use `application.reevaluation_service.{status,reevaluate,history}`.
`show/report` without a revision follows the explicit successor chain. Historical
reports retain frozen content; freshness is separate metadata, not inserted into
old artifact bytes. Withdrawal/erasure can withhold an old report.

Default reevaluation advances only the **knowledge cutoff** to current capture
time. It preserves the publication cutoff, population filters, metric window,
baseline policy, feature/model configuration, recipe pins, rivals, test family and
holdout declarations. Account selectors admit newly imported posts within scope,
including ordinary/failure posts. New comparison runs retain their original
account/post groups. Pre-`0.0.12` comparisons lack those groups and therefore retain
**fixed frozen post membership**; no account-wide scope is inferred.

At most four analyses can run; R2's 500 selected/5,000 history post limits per
analysis and a 20,000-revision dependency closure limit still apply. Imports append
change events but never fit models. `status`
checks up to 1,000 assessments (default 100) and 1,000 journal events per watch;
direct checks consume up to 10,000 events. Incomplete checks are labelled
pending/stale; costly reevaluation refuses until the backlog is checked.
Conservative triggers can request review even when numerical inputs did not
change; this does not authorize ignoring a new source or fabricating annotations.

## Optional reviewed changes

Pass `--spec FILE` for a validated `research.reevaluation.ReevaluationSpec`:

```json
{
  "reason": "Reevaluate newly imported ordinary and unsuccessful posts",
  "max_analyses": 4
}
```

Optional fields are `protocol` (an exact prepared protocol reference), `evidence`
(replacement exact supplementary references), and `designs` (a complete ordered
list of R2 `CorrectedPerformanceSpec` objects, one per prior analysis slot).
Omission retains corresponding prior inputs; `evidence: []` explicitly removes
supplementary observations. Human review must precede a corrected study's
replacement protocol. Source editions/recipe versions are never silently repinned.
New comments do not become reviewed reaction labels automatically.
Making a new immutable recipe version available does not invalidate an assessment
which intentionally pins an older version; selecting a new recipe is an explicit
design change. Relevant annotation edits are separately detected through media
and canonical dependency identifiers.

Changed designs can narrow population/publication scope or change an allowed
model/feature recipe; comparisons record exact changed fields. Families, declared
terms, splits and holdout IDs cannot be renamed/reset through this command.
Changes incompatible with R2's immutable endpoint/family definition are refused;
register a genuinely different design separately. Repeated use of a consumed
holdout remains refused by R2. No repeat-look alpha-spending rule is invented here.

## Storage and flow

1. `research_changes` mirrors existing R6 events into an independent monotonic,
   append-only, `(kind,target_id)`-deduplicated journal. R6 may drain its work queue;
   rebuilding an index does not count as new evidence. Migration backfills canonical
   event order; prior migrations remain unchanged.
2. `assessment_watches` freezes SQL selectors and structural dependency identifiers.
   Only operational cursor, observed identifiers, state and bounded reasons change.
   Tracking starts at the earliest frozen analysis knowledge cutoff, not assessment
   publication time, so arrivals before publication/resume are not lost.
   Already-frozen revisions do not retrigger their own assessment.
3. Relevant post/account, metric, annotation, recipe/protocol/literature, media-run,
   association and eligibility events mark watches stale. Newly eligible account
   posts are found through selectors, not just reverse dependencies. Stale watches
   are the pending work queue; evidence eligibility is independently enforced.
4. Execution freezes a `reevaluation_requests` plan with exact design cutoffs and
   population/reference hashes. Only changed analysis slots refit. Each analysis
   and its request checkpoint commit atomically. A crash can leave an honest
   started/failed statistical attempt, not a fabricated completion.
5. Retry without `--spec` resumes the prior unfinished plan. Populations must match
   frozen hashes; later inputs/withdrawal cannot silently change a resumed run.
   Completed slots are reused, then assessment/findings and immutable
   `assessment_transitions` commit together. No predecessor assessment is rewritten.

Unchanged requests return `unchanged`, zero fits and no new assessment. A relevant
semantic/eligibility change needing a new reviewed input returns `review_required`
without an unsupported revision. Execution failures persist status/error type;
the original statistical ledger retains failures/refusals. Plans and completed
lineage cannot be edited.

## What a comparison means

JSON and escaped Markdown retain prior/current local judgments and observations,
new/reused/removed post and creator IDs, new posts with already-seen content hashes,
changed snapshots/features/references, reasons and original test ledgers. Creator
identity, unknown duplicates and audience overlap still limit independence.
A new post ID is not an independent replication.
Citation revisions also have explicit new/reused/removed membership. Earlier
statistical citations whose numbers are displayed in a comparison remain explicit
evidence inputs; withdrawing that exact citation withholds the derived comparison.
Old literature excerpts are not silently reused after a reviewed source correction.

The scoped rubric yields `supported_in_scope`, `weakened`, `contradicted_in_scope`
or `inconclusive`. A supported directional prediction weakens when its current
result is non-discriminating or scope narrows. A decisive opposite local association
contradicts the prediction in scope. Prediction changes are non-replications;
estimate/interval deltas are descriptive, not tests of effect change.
Non-significance does not establish absence; no global mechanism is auto-rejected.

Every cumulative comparison is `exploratory_cumulative_repeat_look`, with
`independent_confirmation: false`. Fixed-family correction is not sequential
multiple-look correction. Mediation and causal identification remain absent.
R9 expands discovery; R10 handles registered experiment outcomes. C1's future
writers can reuse the structural hooks without a new scheduler.

Current SQL/FTS/vector/graph hydration excludes stale/superseded assessment-derived
documents, including late indexing jobs. Historical retrieval still applies source
permission, retraction and authorized-erasure gates. Journals/watches retain
identifiers, not copied audience text. User-authored request metadata is not a
repository for pasted participant content.
