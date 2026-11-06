# Capability-gated research and growth context

Check capabilities first. The core install includes the human-reviewed research
interfaces; it does not require embeddings or a VLM. An interface being available
does not mean a supplied protocol, paper, outcome or reviewed annotation exists.
For semantic retrieval additionally inspect `memory status` and the exact model's
`models status` entry. Memory status reports space pins/lag, not native runtime health.
If no prepared compatible registered space is usable, use SQL/FTS (`query --mode fts`)
or stop the semantic lane.
Never automatically download an embedder or replace representative selection with
similarity-search hits. Query/graph results remain citation-qualified retrieval, not
independent experimental evidence.

## A complete bounded cooking investigation

For a question such as why finished-meal openings might perform differently:

1. Import permitted videos, ordinary/unsuccessful examples, measured outcomes and
   reviewed opening annotations. Preserve source permissions and sampling coverage.
2. Obtain the `registration` schema. Register at least two competing explanations
   (`research register --spec question.json`), including contextual alternatives.
   Curiosity, anticipated reward, sensory appeal and clarity are proposals, not detected states.
3. Obtain the `literature` schema. Import a reviewed small corpus with exact excerpts,
   source provenance and applicability limits (`research import-literature --spec literature.json`).
   A plausible DOI is not authenticated research; review actual primary sources and
   correction/retraction status before claiming applicability.
4. Obtain the `protocol` schema. Bind actual returned revisions, constructs,
   measurement plans, falsifiable predictions and scope (`research prepare --spec protocol.json`).
   Retain every registered rival and explicitly record production/distribution/
   publishing/profile alternatives or missing context. Do not invent a mediator measurement.
5. Run the declared schema-2.0 comparison, then obtain `evaluation` and bind the exact
   protocol/comparison revisions (`research evaluate --spec evaluation.json`). Check
   eligibility, failures and unsupported rivals, not just a favorable statistic.
6. Use `research report QUESTION_ID`, `research history QUESTION_ID`, and
   `research status` to inspect persistent reports, revisions and stale assessments.
   After new/corrected evidence, use `research reevaluate QUESTION_ID --spec reevaluation.json`
   with an explicitly reviewed plan and its documented `--help`; do not rewrite old history.

If required sources/review are missing, deliver the supported descriptive report and
list missing data. Do not call registration an evaluated finding. A changed creative
effect does not identify curiosity, mediation or viewer mental state.

## Four distinct context lanes

| Lane | Engine interfaces | Claim boundary |
|---|---|---|
| Production/editing | `creative import`, `creative materialize` | Reviewed craft events and measurable recipes; not an automatic cinematographer or aesthetic judge |
| Publishing/search | `context import`, `context publication-report` | Dated packaging/timezone/cadence; relevance and discoverability are not causal reach lifts |
| Platform distribution | `platform import`, `platform report` | Official statements separate from inferred early-response/later-reach associations, per platform/surface |
| Profile/funnel | `profile import`, `profile report` | Frozen profile-quality rubrics separate from actual owner-account visits/follows/clicks/installs and source attribution |

Use each subcommand's help and actual schema/source definitions before constructing
its specification. Never substitute Instagram rules for TikTok/YouTube, inferred
distribution for search traffic, or a polished bio for measured conversion.

## Discovery and experiments

`research discover --spec discovery.json` performs a bounded, explicitly specified
search with creator/time/niche checks and an all-attempt family. It is not unlimited
mining for significance or a general nonlinear optimizer. Independent confirmation
uses `research confirm-discovery`, not a reused test set.

For a test-first creative/distribution/publishing/profile action, first present a
proposal with scope, alternatives, evidence and a measurable falsifier. Obtain the
`experiment` schema for a prospective plan (`experiment register --spec experiment.json`).
Registration persists a plan; it does not execute one. Only actual authorized measured
results belong in `experiment import-results`; analyze returned IDs with
`experiment analyze`. Honor the engine's independent-block, attribution, missing-data
and assignment limits. Nonrandom observations remain descriptive.

`recommendation create --spec recommendation.json` qualifies a structured proposal
against actual evidence. It does not learn an optimal strategy, supply a guaranteed
lift, publish, edit a profile, buy traffic, or recruit participants. Keep conclusions
within platform, niche, language, audience, dates and available evidence.
