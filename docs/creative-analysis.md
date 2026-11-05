# Creative events and pinned multimodal recipes

Available in `0.0.7`, database head `0007_creative`. This is the R3 observable-content
slice, not psychological discovery, automatic experiment design or semantic memory.
No dependency, model download, hosted API or new server is required.

This page documents the released ten-label v1 vocabulary and eleven pinned recipes.
`0.0.13` adds a separate [professional v2 schema](production-evidence.md) and eight
additional pins through the same services. Generic `unclassified` prose does not
create a typed technique. Broad performance discovery and actionable strategies
remain R9/R10. Existing v1 formats and frozen values remain unchanged.
R6 later adds [memory projections](research-memory.md) for these canonical records;
it does not add professional-craft recognition or evaluated mechanism findings.

## Working paths

1. Register authorized local video bytes with `import local` or `analyze video`.
2. Import a human-reviewed annotation document, or opt into literal-text proposals.
3. Inspect exact events, uncertainty, review coverage and qualified temporal relations.
4. Materialize named, version-pinned recipes. Unknown is a successful result.
5. Explicitly join those recipes to a version-2 account/comparison specification.

```bash
socialdna import local /absolute/path/cooking.mp4 --format json
socialdna creative definitions --format json
socialdna creative import review.json --dry-run --format json
socialdna creative import review.json --format json
socialdna creative show MEDIA_ID --key opening-review --format json
socialdna creative materialize MEDIA_ID --key opening-review \
  --recipe creative.result_first.v1 --recipe creative.spoken_promise.v1 --format json
socialdna evidence resolve EVENT_EVIDENCE_ID --format json
```

`--dry-run` performs bounded schema validation without creating/migrating a library,
acquiring its lock, or writing artifacts. Actual import also validates registered
SHA-256, original-media duration, real evidence ownership, modality, source eligibility
and post/media associations. The canonical validated JSON is retained as a source
artifact; original JSON whitespace is not preserved as a separate raw artifact.

## Annotation format and review

[The annotation template](../examples/creative/opening-review.json) deliberately contains
no fabricated positive event or exhaustive-coverage claim. Replace its zero hash and
reviewer/procedure/permission placeholders. Populate events only after reviewing the
registered bytes. A minimal event inside that document looks like:

```json
{
  "key": "dish-reveal",
  "technique": "finished_dish",
  "description": "Prepared final dish is visible, not raw ingredients or an intermediate step",
  "modalities": ["visual"],
  "anchors": [{
    "kind": "interval",
    "start_min_ms": 0, "start_max_ms": 80,
    "end_min_ms": 900, "end_max_ms": 1100
  }],
  "state": "reviewed",
  "reviewer": "actual-reviewer",
  "reliability": "medium"
}
```

These numbers illustrate the format, not measurements of a bundled cooking video.
Techniques have pinned definitions, inclusion/exclusion criteria, examples,
counterexamples and coverage requirements returned by `creative definitions`.

Events may be `proposed`, `reviewed` or `disputed`, with `present` or `ambiguous`
verdicts. They retain the author, procedure, declared outcome access (`blinded`,
`outcome_aware`, `unknown`) and declared freeze-before-outcomes status. Blinding is an
attributed protocol assertion, not independently audited by the engine. Model-origin
documents require an exact provider/model/revision/execution identity and cannot
self-certify reviewed events or exhaustive coverage. Human adjudication is a new
document/procedure revision under the same stable event key; the model proposal remains.

Reimporting an identical snapshot is idempotent, not a command to make an older
snapshot current again. A correction/re-adjudication needs a genuinely revised
annotation/protocol document. Unchanged event and coverage payloads retain their
original revisions and sources when another annotation changes.

### Coordinates and evidence

All timed anchors use integer **original-presentation milliseconds**, not proxy/model
time or post publication dates. Intervals are half-open and must have at least one
feasible nonempty realization. Optional nominal bounds must lie within the uncertainty
ranges. Points have no end/duration. Spatial anchors are frame-time points with
normalized nonempty boxes. Multiple anchors preserve discontinuities. Unknown bounds
require a reason; they do not receive invented nominal timestamps.

Provide `inputs: [{"ref": {"id": "...", "revision_id": "..."},
"modality": "visual", "role": "observed"}]` to cite precise existing evidence. Context
alone cannot support an asserted modality. Observed cues must cover the possible
event bounds, and text tracks cannot switch modality (subtitles are not ASR).
If a human reviewer omits timed inputs, import creates a citation to the actual
registered whole-video source span. It does **not** pretend this is a sampled frame
or an automated detection. For per-cue precision, supply narrower real citations.

Captions/hashtags require captured post revisions and exact `post_text` citations:

```bash
socialdna creative cite-text POST_ID --field caption --start 0 --end 20 --format json
socialdna creative cite-text POST_ID --field hashtag --tag-index 0 --format json
```

Character spans are Unicode code points in captured text. Hashtags explicitly cite
the captured, stripped/case-folded inventory, not fictional offsets into original
caption text. Post-text events supply `post: {kind, id, revision_id}` and an `untimed`
anchor with a reason. They never acquire video offsets. Materialize post-level recipes
with both `--post POST_ID --post-revision REVISION_ID`. A caption edited after annotation
does not silently inherit an old caption label. Hashtag counts describe inventory,
not niche/topic truth; absent historical inventory stays unknown.

### Coverage and temporal relationships

A positive reviewed cue can support presence under sparse coverage. A negative result
requires explicitly scoped exhaustive **human** review of the technique, modality and
opening interval. For a three-second opening:

```json
{
  "modality": "visual",
  "techniques": ["finished_dish", "preparation_instruction", "ingredient_display"],
  "mode": "exhaustive_review",
  "intervals": [{"start_ms": 0, "end_ms": 3000}],
  "limitation": "Reviewed original opening continuously; no independent reviewer agreement measured"
}
```

For shorter videos review the whole available duration; the recipe truncates its
opening window accordingly. Sampled/unknown coverage cannot prove absence. Untimed
post text cannot use a media-clock exhaustive-absence claim. Audio/speech assertions
or reviewed audio coverage require an actual source audio stream. Missing audio is
not evidence of a missing psychological response.

Relations are `precedes`, `overlaps`, or `simultaneous_within_tolerance`. “Follows” is
the reverse `precedes` edge. Verified relations hold across **all feasible bounds**;
possible relations hold for some, but not all. For discontinuous events the producer
uses the conservative all-anchor-pairs rule. Synchrony compares onsets (default
100 ms); it does not establish reinforcement, intention or causation.

## Opt-in profile, timeline and reports

```bash
socialdna analyze video MEDIA_ID --no-ai --creative-profile cooking-opening-v1 \
  --creative-annotations review.json --creative-frame-budget 12 --format json
socialdna timeline show MEDIA_ID --run RUN_ID --creative --format json
socialdna report generate --run RUN_ID --format markdown
```

Omit `--creative-annotations` for deterministic literal wording proposals from actual
ASR, supplied subtitle, OCR and captured-caption inputs. This profile does not perform
automatic dish/ingredient recognition, semantic sound classification, or validated
color interpretation. Prepared enrichment providers remain optional and separate;
R3 does not add a new VLM adapter. External model proposals can be imported with their
real provider provenance.

Targeted sampling snaps opening/boundary requests to actual decoded source PTS and
preserves requested static frames. Budgets are 0–48, further capped by the configured
enrichment-frame limit. Extra samples support inspection; they neither fill all
coverage gaps nor cause primitive measurements to be recomputed. Label-only edits
retain primitive/targeted-frame caches; changed boundary requests can invalidate the
targeted-frame task. Repeat creative tasks reuse their committed annotation revision.

Ordinary video runs keep schema-1 reports and the existing workflow. Opt-in runs
produce schema-2 video reports with pinned event/coverage/relation lanes. New reports
use the run's committed annotation revision, not a newer unrelated set; a failed
creative task does not fall back to old labels. `creative show` selects the latest
revision as of `--as-of`; multiple annotation keys require explicit selection. The
creative lane is the complete bounded annotation set, even when raw timeline lanes
are queried over a subinterval. Imported human citations are independent imported
evidence, not falsely attributed as produced by a video run.

Withdrawn annotation sources, events or literal inputs prevent new materialization,
comparison/reproduction use and report generation. Current creative views redact
ineligible lanes. No automatic fallback resurrects older eligible labels. Previously
retained immutable artifacts are not erased by withdrawal; redaction/erasure remains
the separately documented retention workflow.

## Recipes and analytics

Pinned recipes cover opening finished-dish presence, result-first, ingredient-first,
spoken/subtitle/caption promises, reviewed warm color, result-first plus spoken
promise, reveal/SFX and cut/SFX onset synchrony, and captured hashtag counts. Recipe
definitions include their modalities, temporal grammar, window, unit, missingness and
observable-content role. Brightness and loudness remain primitive measurements.

Result-first requires a reviewed final dish in the opening before substantive visual
preparation, exhaustive review of both relevant techniques, and unambiguous order.
Ingredient-first requires ingredients before final dish/preparation. An intermediate
or unclassified cue, unresolved boundary/order or missing component can yield unknown.
These are deliberately small prespecified views, not a searched creative ontology.

Features retain exact event/coverage/technique/evidence references, recipe contents,
source IDs, actual first-known availability, review protocols and missingness reason.
Recipe/value IDs are deterministic. The cache key excludes unrelated annotation-set
edits; a frozen statistical input separately pins the full selected set revision.
Later edits do not alter an as-of view. Retrospective content annotations are disclosed;
historical prediction also requires availability by publication. Late annotation/import
cannot be backdated. A known value first deployable after a declared knowledge cutoff
is marked ineligible, even when its numeric measurement is retained for inspection.

Use the existing schema-2 specification with explicit mappings, for example:

```json
{
  "features": ["caption_length", "creative.result_first"],
  "creative_recipes": {"creative.result_first": "creative.result_first.v1"},
  "creative_annotation_key": "opening-review",
  "creative_label_policy": "reviewed_only",
  "family_terms": ["caption_length", "creative.result_first"]
}
```

Merge these fields into a complete version-2 design, such as
[the example specification](../examples/creative/comparison-v2.json), and set real
cutoffs, outcome definitions, population/family and covariates. Run `compare posts`
or `analyze account --spec ...` normally. Unversioned specs retain their primitive
whitelist. Up to six explicitly declared predictors are supported; no new outcome-guided
search or model family is introduced. `proposals_exploratory` can permit proposal-based
presence/synchrony views but cannot create exhaustive visual review for result-first.
Reports flag unknown/outcome-aware blinding and exploratory labels, not independent
confirmation. Small/poorly observed cohorts still yield insufficient data.

## Storage and verification boundaries

SQLite owns canonical definition/event/coverage/relation revisions and their typed
FK projections. `feature_recipes` and `feature_values` reuse the existing analytics
contract; media-only values have a media FK instead of a dummy post. Migration
`0007_creative` atomically rebuilds the evidence CHECK and feature-value parent tables,
preserving old rows, child links and immutable triggers. Released migrations 0001–0006
are unchanged. Populated-library downgrade is refused; use verified backup/restore.
No Qdrant collection or graph projection is introduced.

Automated fixtures exercise real FFmpeg bytes, imports, provider identity preservation,
uncertain/discontinuous anchors, timing algebra, missing modalities, cache reuse,
selective invalidation, withdrawal, as-of availability, Unicode text, CLI restarts,
version-2 feature/outcome joins and exact reproduction. Generated color clips carry
explicit controlled annotations: they verify software contracts, **not** cooking-label
accuracy, human agreement, real-VLM quality or psychological validity. Those empirical
validations remain necessary before scientific claims from a real content corpus.
