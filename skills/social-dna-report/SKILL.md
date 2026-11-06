---
name: social-dna-report
description: Generate or re-export a source-qualified SocialDNA report from a saved workflow ID. Use when the user asks to read, summarize or export previously captured post evidence. This release reports native YouTube metadata only, without fetching URLs, analyzing audiovisual content or inventing findings.
license: Apache-2.0
---

# Report saved evidence

Read [the workflow contract](references/workflow.md). This skill reads saved evidence;
it does not authorize acquisition. Do not install packages or change host settings.

1. Run `socialdna --offline --no-ai --format json capabilities`.
2. Obtain a saved workflow ID. If the user supplies only a URL, explain that a separate
   explicit `social-dna-ingest` capture is needed. Do not fetch it implicitly.
3. Run `socialdna --offline --no-ai workflow report WORKFLOW_ID --format markdown`.
   Read the JSON envelope's `data.content`; preserve engine coverage and limitations.
   For a new saved report task use `workflow plan --mode report --from WORKFLOW_ID`,
   then `workflow run NEW_ID` offline. Neither path contacts a source.
4. Export only to an explicit new file using `--output PATH`. Existing files are refused.
   Return the path, capture time, expiry, exact citations, unknowns and unsupported goals.

The engine rechecks source eligibility and frozen artifact integrity on every read.
Expired, withdrawn or erased evidence must not be reused from an old export as if it
were active. Never invent IDs, reconstruct a missing result, rerun statistics or fetch
fresh evidence to disguise a missing report. Keep any additional agent commentary
separate; metadata is not a script, quality judgment or explanation of virality.
