# Professional production evidence

Available in `0.0.13`, SQLite head `0012_reevaluation`. No new migration, dependency,
server, detector, model download or hosted API is required. The v1 creative schema,
ten definitions and eleven recipe pins remain unchanged.

## Workflow

Register authorized local video bytes, review those bytes, then import a JSON
annotation document using `schema_version: "2.0"`. The shared annotation fields,
original-media anchors, protocol and permissions follow [creative analysis](creative-analysis.md).
New categorical techniques require an exact `value` from `creative definitions`.
Every reviewed cue needs a reviewer and source evidence; omitted human inputs cite
the registered whole-video span, not invented sampled frames.

Start from the [empty review template](../examples/creative/professional-review.json),
replace its hash/permission/reviewer/procedure, and add only genuinely reviewed cues
and coverage. It intentionally asserts no detections or exhaustive coverage.

```bash
socialdna creative definitions --format json
socialdna creative import professional-review.json --dry-run --format json
socialdna creative import professional-review.json --format json
socialdna creative show MEDIA_ID --key professional-review --format json
socialdna creative materialize MEDIA_ID --key professional-review \
  --recipe creative.shot_duration_mean.v2 --recipe creative.cut_to_beat_rate.v2 --format json
```

The 16 new techniques cover shot intervals, framing, angles, composition, camera
versus subject movement, lighting appearance, color look, focus-depth appearance,
transitions, subtitle design, effects, music intervals/beats, sound mix and reviewed
sound/image relationships. They describe attributable observations, not recovered
equipment settings, intent, production quality or psychological effects. Model/rule
proposals cannot self-certify human review or exhaustive coverage.

## Frozen numeric recipes

| Pin | Meaning and requirements |
|---|---|
| `creative.shot_duration_mean.v2` | Mean seconds in a complete contiguous reviewed shot partition. |
| `creative.shot_duration_median.v2` | Median seconds in that partition. |
| `creative.pacing_change.v2` | Mean last-half shot duration / mean first-half duration − 1; classify by onset, require at least two shots per half. |
| `creative.cuts_per_minute.v2` | Reviewed cut points divided by clip minutes. |
| `creative.subtitle_occupancy.v2` | Union of reviewed visible subtitle intervals / clip duration; overlaps count once. |
| `creative.cut_to_beat_rate.v2` | Fraction of reviewed cuts within 100 ms of a reviewed beat; no cuts means unknown. Not semantic reinforcement. |
| `creative.angle_changes.v2` | Changes between categories in a contiguous reviewed angle partition. |
| `creative.close_up_presence.v2` | Reviewed close/extreme-close framing presence under full coverage. |

All use full original-clip human review for required techniques/modalities. Sparse
coverage, ambiguity, uncertain numeric timing, duplicate points or incomplete shot/
angle partitions preserve unknown values and reasons. Negative values are never
manufactured from missing observations. V2 allows up to 512 events without storing
quadratic all-pairs relations; its empty relation lane is qualified explicitly.

## Performance and incremental research

Use an existing version-2 performance/comparison spec with
`features: ["creative.shot_duration_mean", "caption_length"]` and
`creative_recipes: {"creative.shot_duration_mean": "creative.shot_duration_mean.v2"}`.
Select the real annotation key and appropriate knowledge/availability cutoff as
documented in [versioned analytics](versioned-analytics.md). The R2 pipeline retains
actual metric observations, creator matching, feature missingness, source citations
and attempt/holdout restrictions. R7/R8 consume the same results; annotation changes
mark dependent assessments stale without rewriting frozen reports. Withdrawal gates
new materialization, evidence hydration and derived memory immediately.

The automated integration creates six distinct real FFmpeg clips across three creators,
imports source-labelled synthetic counters (including a fast-editing failure), runs
actual matching and assessment/reevaluation, and verifies restart, historical bytes,
exact evidence and withdrawal. This validates the software pipeline, not real-world
craft effectiveness or annotation accuracy. Held-out reviewer agreement and empirical
performance evidence are still required. Broader discovery and actionable filmmaking
or editing recommendations remain R9/R10.

Verification for this delivery: 462 collected tests covered across full regression
partitions and final targeted reruns, with 459 passing and three optional prepared-
model skips; Ruff, strict mypy, offline lock/build and fresh installed-wheel CLI
checks pass. The wheel contains byte-identical copies of all 152 source modules.
