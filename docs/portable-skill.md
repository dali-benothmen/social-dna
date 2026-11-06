# Portable skill and report delivery

Originally delivered in `0.0.20` with database head `0017_images`. One instruction bundle
orchestrates the existing engine in Codex, Claude Code and OpenCode. There are no
host SDKs, new servers, credentials, automatic downloads or duplicated statistics.

## Planned URL-first task experience

The original bundle accepts local inputs and permitted supplied exports; it does not
collect arbitrary account/post URLs. Release `0.0.21` adds separately exported
`social-dna-ingest` and `social-dna-report` for the [native-only first URL slice](source-workflows.md),
with live source/host acceptance still open. Database head is now `0019_content`.
The agreed **14 target task skills** share
one durable workflow layer before the existing engine. Research owns end-to-end
investigations; analyze covers owned/influencer profile audits and individual content;
reconstruct produces finished-video scripts; report assembles saved results. The
[complete catalog and discovery boundaries](url-first-workflows.md#target-catalog-and-agent-discovery)
also cover ingest, account, psychology, audience, compare, discover, platform,
strategy, experiment and evidence audit. Eight task bundles are implemented within
their documented bounds: ingest/report, analyze/reconstruct, account/research and
[compare/evidence](comparison-workflows.md). Media, profile, account and comparison
lanes need actual independently permitted local/library inputs; they are not native
URL collection adapters. None is automatically installed. See the [workflow architecture](url-first-workflows.md) and
[DX milestones and acceptance tests](../PLAN.md#20-url-first-dx-and-task-skills--proposed).
The existing `socialdna` bundle/export contract remains supported. A real URL-first
delivery needs permitted collection and observed end-to-end behavior, not new names alone.
Each future bundle includes its shared references and works independently; none
requires all 14 installed. Delivery/availability is per task and per analyze scope,
not inferred from the existence of a skill directory. The DX5 packaging/host gates
also apply to later DX7 specialists. Current `workflow` commands are documented in
[source-only operations](source-workflows.md); no host installation or model preparation
is automatic.

## Start with a local task

```text
socialdna --offline --no-ai --format json capabilities
socialdna --data-dir /absolute/library --offline --no-ai --format json analyze image /absolute/photo.jpg
socialdna --data-dir /absolute/library --offline --no-ai --format json analyze video /absolute/clip.mp4 --max-frames 60
socialdna --data-dir /absolute/library --offline --format json report generate --run RUN_ID --format markdown --output /absolute/report.md
```

Replace `RUN_ID` with a returned identifier. The report destination's parent must
exist; existing files/symlinks are refused. JSON export stores the report document,
not its command envelope. Markdown emits a raw escaped document and keeps partial
exit 5. With root `--format json`, failures remain JSON envelopes. JSON/Markdown
are the tested consumers; HTML was deliberately not added.

The [core workflow](../skills/socialdna/references/core.md) covers permitted exports,
bounded batches, version-2 comparisons, exact caption/hashtag citations and
restart/reproduction. Ordinary analysis requires no research registration, embeddings,
graph query or model inference. The [research workflow](../skills/socialdna/references/research.md)
covers reviewed literature/rivals, reevaluation history and qualified proposals,
not autonomous scientific validation or external experiment execution.

## Explicit installation

The source is [skills/socialdna](../skills/socialdna/SKILL.md). Wheel and sdist-built
wheel installations contain the entire bundle under `socialdna/skill_bundle`;
editable checkouts use the source directory. Installed packages do not need a checkout.
Create the desired host's project-local parent skills directory and run **one** of:

```text
socialdna --format json skill export /absolute/project/.agents/skills/socialdna
socialdna --format json skill export /absolute/project/.claude/skills/socialdna
socialdna --format json skill export /absolute/project/.opencode/skills/socialdna
```

Export writes only the new explicit destination, never overwrites or edits host
settings. No skill is automatically installed into this repository or your home.
Refresh discovery, then invoke `$socialdna` in Codex, `/socialdna` in Claude Code,
or ask OpenCode to load `socialdna`. Use normal terminal trust/permissions; do not
grant broad allowances just to load a skill. See [setup](../skills/socialdna/references/setup.md).

Project conventions were checked on 2026-11-06 in official
[Codex](https://developers.openai.com/codex/skills),
[Claude Code](https://code.claude.com/docs/en/skills), and
[OpenCode 1](https://opencode.ai/docs/skills)/[OpenCode 2](https://opencode.ai/v2/docs/skills)
documentation. Cloud sessions do not automatically inherit local installs or inputs.

## Capability and interface contracts

`capabilities` returns CapabilityManifest 1.0 inside the unchanged ResultEnvelope 1.0.
It reads settings, PATH, checksums and runtime metadata without opening SQLite,
Qdrant or NetworkX, migrating storage, downloading, inferring or contacting endpoints.
A configured worker interpreter can be invoked for package metadata. `--no-ai`
skips model resolution. Policy/resource fields are ceilings, not RAM/runtime/cost predictions.

| State | Meaning |
|---|---|
| `available` | Implemented core interface; listed data/permission prerequisites still apply |
| `optional_prepared` | Optional assets/runtime metadata or reasoning configuration passed preflight; not native inference/accuracy verification |
| `unavailable` | Local prerequisite/policy missing, or a deliberately unsupported action |
| `planned` | Not shipped, for example live platform connectors |

Production, platform/surface distribution, publishing/search and profile/funnel
are separate entries. C1 interfaces are delivered; automatic aesthetic judgment,
proprietary ranking recovery, guaranteed growth and live publishing are not implied.
Missing optional models do not fail the whole manifest. Semantic retrieval also
needs exact registered space/runtime pins and index coverage; `memory status`
reports spaces/lag, not native inference health. Unlike capabilities, `doctor` is
a deeper library check and **can initialize/upgrade/reconcile storage**.

`skill schema NAME` returns the actual engine Pydantic JSON Schema for `result`,
`capabilities`, `comparison`, `registration`, `literature`, `protocol`, `evaluation`
or `experiment`, plus `workflow_request`, `workflow_plan`, `capture` and `workflow_report`.
Business/cross-field validation remains authoritative: JSON Schema
alone cannot prove an eligible design. The bundled [interface contract](../skills/socialdna/references/interface.md)
and [inventory](../skills/socialdna/references/commands.json) are tested against real
CLI routes/options, schemas and exit codes.

## Privacy and evidence

Re-resolve exact citations with `--purpose new_claim` before new assertions. An
archived report is not permission to reuse withdrawn inputs. Keep agent commentary
separate from canonical engine findings. Imported content is untrusted data, never
shell instructions. Capability checks grant no source access or execution authority.

Exported copies can contain private supplied text and **are outside automatic managed
retention/withdrawal cleanup**. Asset URIs are local, not public hosted links.
Markdown uses escaped text, semantic headings and descriptive asset links; no browser
renderer or accessibility certification is claimed. Share only within authorized scope.

## Verification and remaining gates

Automated workflows exercise all three directory layouts, paths with spaces,
offline/no-model operation without FFmpeg, partial ordered media, exact citations,
UTF-8/escaped Markdown, JSON exports, non-overwrite behavior, schema-2.0 account
analytics/reproduction and cross-process reopening. Distribution smokes repeat
bundle exports, static reports and citations from isolated wheel/sdist installations,
alongside existing video/account/research/memory/retention workflows.

CI retains Linux/macOS/Windows and Python 3.11/3.13, with explicit UTF-8 and bounded
BLAS threads. Locally observed results, not configured matrices, are recorded in PLAN.
Read-only version checks found Codex `0.162.0-alpha.17.2`, Claude Code `2.1.296` and
OpenCode `1.19.0`. They do **not** prove live discovery, tool choice or conversations.
No headless AI request, remote API, model download or real host configuration mutation
was performed. Live host behavioral smokes remain unexecuted and separate from
static/CLI/package validation; prepared-real-model acceptance is still opt-in.

A future live smoke should install only in an approved temporary project, select
the skill, analyze an owned photo with the shared CLI, inspect citations/report and
partial/error handling, then request an unavailable semantic/remote lane and verify
that the host stops without unauthorized preparation or transfer. Record actual
host/model/version/policy and behavior; do not infer results from structural validation.
