# Result, report and error contract

Run argument arrays where the host supports them. Otherwise quote literal local
paths/IDs; never concatenate captured content into a shell command. Progress and
resource estimates go to stderr. Machine calls must specify `--format json`; stdout
then contains one ResultEnvelope, with no progress preamble. Help/version are not
envelopes. Preserve stderr separately when reporting failures.

The envelope's `schema_version` is `1.0`; `command`, `status`, optional `run_id`,
`data`, `evidence`, `warnings`, `limitations`, `errors` and `next_actions` are stable
fields. `data` has command-specific contracts, not a universal report shape. Parse
the engine result before following its IDs. Check both process exit and status:

| Exit | Meaning | Agent response |
|---|---|---|
| 0 | Success (warnings may remain) | Inspect warnings and evidence limits |
| 1 | Internal failure | Preserve error; no success claim or automatic expensive retry |
| 2 | Invalid input/configuration | Correct the supplied fields; do not invent data |
| 3 | Required dependency unavailable | Stop that branch; offer preparation only with permission |
| 4 | Permission/consent refused | Do not relax policy or resend data |
| 5 | Partial result or media processing failure | Inspect status/data; keep usable evidence, disclose gaps |
| 6 | Storage conflict | Avoid concurrent writers; retry only when the conflict is resolved |
| 7 | Provider failure | Retain basic results; bounded retry only within agreed scope |
| 8 | Storage integrity failure | Stop writes and diagnose; do not erase/reinitialize |

Exit 5 alone does not prove usable partial data: a failure envelope can have `status:
error`. Never discard a valid partial report merely because the process returned 5.
Do not chain the workflow with `&&` if later reporting should retain partial results.

## Reports

```text
socialdna --data-dir /absolute/library --offline --format json report generate --run RUN_ID --format json --output /absolute/analysis.json
socialdna --data-dir /absolute/library --offline --format json report generate --run RUN_ID --format markdown --output /absolute/analysis.md
socialdna --data-dir /absolute/library --offline --format json report generate --account ACCOUNT_ID --format json
```

Supply exactly one of `--run`/`--account`. The account option selects the latest saved
account analysis; prefer `--run` for an exact analysis. `--output` requires an existing
parent directory and a new file; it never overwrites, including symlinks. JSON stdout
is an envelope; the exported JSON file is its `data.content` document. Markdown stdout
and its exported file are the raw escaped document, not JSON. Its errors are still
JSON when root `--format json` is specified; branch on exit before parsing Markdown.
Reports are also stored as managed artifacts. Exported copies are outside automatic
retention/withdrawal cleanup: do not reuse them for new claims without re-resolving
citations. They may contain sensitive captions/comments; share only within scope.

Report paths/asset URIs are local, not portable hosted URLs. Markdown uses semantic
headings, readable text, descriptive asset links and escaped imported text; JSON
retains complete structured evidence. No HTML renderer or browser service is shipped.
For research results, `research report` has its own envelope containing a cited
research report rather than the media report format; preserve its returned revision.

The bounded `workflow` layer also supports URL comparisons and exact evidence audits
over independently permitted library observations. `workflow plan --mode compare
--url LEFT --against RIGHT` pins exact subjects; without `--comparison-spec` its
inventory is partial and numeric inference is withheld. `workflow plan --mode evidence
--from WORKFLOW` (or `--entity-revision`, or exact `--evidence-id`/`--evidence-revision`)
audits canonical records, with optional bounded graph/history context and no refit.
These modes do not acquire cold URL sources. `workflow report ID --format markdown`
always returns an envelope with the frozen Markdown in `data.content`; it differs
from the legacy raw-Markdown report command above. Source permissions and current
eligibility gate all reuse. New schemas: `url_comparison`, `evidence_audit` and
`recommendation`; the eight task bundles export independently.

## Inspect exact schemas

```text
socialdna --format json skill schema result
socialdna --format json skill schema capabilities
socialdna --format json skill schema comparison
socialdna --format json skill schema registration
socialdna --format json skill schema literature
socialdna --format json skill schema protocol
socialdna --format json skill schema evaluation
socialdna --format json skill schema experiment
```

These return engine-generated JSON Schema, not instructions to manufacture evidence.
Use subcommand `--help` for remaining CLI arguments and reject unknown schema versions.
The [tested command inventory](commands.json) is a validation contract, not an alternate engine.
