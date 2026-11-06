# URL-first workflows and task skills

Status: **proposed design; not implemented**. Reviewed 2026-11-06 against package
`0.0.20` / database `0017_images`. Implementation requires separate approval.
The delivery sequence and milestone-specific acceptance tests are in
[PLAN.md §20](../PLAN.md#20-url-first-dx-and-task-skills--proposed).

## 1. Product contract and existing gap

The intended interaction is **skill + account/post URL(s) + a normal-language
request → a useful, evidence-qualified report**. The user should not have to
prepare SocialDNA JSON, choose statistical formulas or manually connect engine IDs.
Initial installation and source authorization may require setup; ordinary subsequent
requests should reuse that setup within its valid scope.

The engine already imports supplied exports, analyzes local video/images/carousels,
compares eligible populations, maintains research memory and exports reports. U2
delivered one portable `socialdna` instruction bundle. It did **not** deliver URL
collection, account enumeration, durable multi-stage conversational tasks or the
three task-specific skills below. Stored `Post.url` / `Media.uri` values are
references, not implemented download instructions.

This design adds an intake/coordinator layer before existing producers. It does
not replace the engine, weaken research contracts or reopen completed milestones.
Source access can limit the requested question: a polished metadata summary is
not evidence that video content, distribution or conversion was analyzed.

**Instagram, TikTok and YouTube are all required product targets**, following the
user's platform preference. Connectors are delivered serially to keep changes
testable, not to reduce the product to YouTube. The three-platform goal is unfinished
until each has a genuinely working, accurately scoped route and its own acceptance
record. No route may be called complete merely because a URL shape is recognized.

## 2. User-facing skills and examples

| Skill | Primary job | Expected inputs and boundaries |
|---|---|---|
| `social-dna-report` | Study an account or assemble a readable report about supplied subjects | One or more account/post URLs, goal, optional supplied evidence. Route to content, publishing, audience, distribution and profile sections only where evidence permits. |
| `social-dna-analyze` | Inspect particular content in depth | One or more post URLs; dispatch actual available video/photo/carousel media and metadata. Never describe unobserved footage as watched. |
| `social-dna-compare` | Compare accounts or posts under a declared question | At least two compatible subjects; explain unequal coverage and withhold invalid numerical comparisons. |
| Existing `socialdna` | Backward-compatible umbrella and local/export/research entrypoint | Keep its name, installed behavior and existing commands. It can route to the same workflows when those ship. |

Illustrative **future** Codex requests:

```text
$social-dna-report https://www.youtube.com/@example
Study the available recent posts. What is distinctive about the account,
what performance evidence supports the patterns, and what should I test?

$social-dna-analyze https://www.instagram.com/reel/EXAMPLE/
Explain the opening, pacing, subtitles and sound design. Separate what
you measured from interpretation and tell me what you could not access.

$social-dna-compare https://www.tiktok.com/@example_a https://www.tiktok.com/@example_b
Compare their content approaches, including ordinary posts, not just hits.
Focus on what I could test for an Arabic-language cooking account.
```

These examples are not claims that the URLs, connectors or commands work today.
Claude Code uses its native `/skill-name` invocation; OpenCode uses native skill
loading. The host may also discover the appropriate skill from normal language.
The Python executable remains `socialdna`, not any of these skill names.

The agent groups missing information into a focused question only when needed:
ambiguous account identity, incompatible comparison goal, unavailable authorization,
material scope/cost increase or an evidence branch requiring supplied originals.
Do not ask the user to invent schemas, fabricate reviewer attestations or run each
internal command. Account access, media copying and model-transfer consent are
different permissions.

## 3. Additive architecture and communication

```text
Host task skill + URLs + user goal
              │ typed request, no executable page instructions
              ▼
URL intake → persisted bounded plan → source/access checks
                                      │
                     permitted acquisition / supplied input binding
                                      │ normalized captures + coverage
                                      ▼
                   existing atomic imports and media registration
                                      │ exact IDs/revisions/hashes
                                      ▼
                   existing analysis/comparison/research services
                                      │ qualified outputs + citations
                                      ▼
                   workflow report + host interpretation (labeled)
```

| Boundary | Proposed implementation files | Existing integration |
|---|---|---|
| Typed requests, plans, targets and coverage | `domain/workflows.py`, `domain/acquisition.py` | ResultEnvelope 1.0, existing IDs/settings/evidence contracts |
| Offline URL classification and safe resolution policy | `ingestion/urls.py` | Platform/external-ID account and post identities, supplied local bindings |
| Source collection | `ingestion/connectors/base.py`, then individual connector files | Existing source provenance, account/tabular imports, separate C1 import contracts |
| Durable coordination | `application/workflow_service.py`, `storage/workflow_repository.py` | Existing media/account/analysis/performance/research services and task cache |
| Source policy enforcement | `ingestion/access_policy.py` | Existing permission/consent, source-capability and retention rules; no second scientific eligibility system |
| Composite output | `application/workflow_report_service.py`, `reporting/workflow.py` | Existing evidence resolver, report documents and safe export helper |
| Agent interface | `cli/workflow_commands.py`, additive skill export/schema support | Existing CLI/envelope/exit families and non-initializing capabilities |
| Task skills | Future `skills/social-dna-{report,analyze,compare}/` | One maintained shared reference source, packaged independently into each bundle |

These are responsibility boundaries, not permission to scaffold unused modules.
Introduce each file only with its first tested consumer. Start synchronous and
single-machine: no agent framework, MCP server, background scheduler, queue server,
headless browser dependency or new database service is required.

The coordinator executes a validated plan; it does not invent research designs.
Basic inspection dispatches directly to existing deterministic services. Optional
research reuses R2–R10's actual registration, timing, sampling, review and evidence
gates. The host can propose interpretations and questions, not silently certify
scientific reviews or auto-create human approval records.

## 4. Contracts, commands and resumability

All interfaces below are **proposed**, not part of the current command inventory.

### Typed objects

- `WorkflowRequest` 1.0: mode (`report`, `analyze`, `compare`), sanitized user goal,
  ordered URLs/local attachments, requested platform/language/niche/audience/objective,
  declared scope and library. No embedded credentials or executable expressions.
- `WorkflowPlan` 1.0: request hash, typed unresolved/resolved targets, exact planned
  operations, connector/policy versions, scope, resource ceilings, reuse/freshness
  rules and required actions. Approval binds the plan hash; changing its access,
  destinations, comparison purpose or budget invalidates affected grants.
- `CaptureManifest` 1.0: provider route/version, original sanitized URL and stable
  source ID, collection times, source-defined measurement times/definitions, pages,
  cursors, returned/omitted/excluded counts, selection frame, errors, availability,
  field provenance, allowed uses and retention/refresh deadlines. A fetch time is
  not automatically a metric's observation time.
- `WorkflowReport` 1.0: exact subject/plan/run/evidence references, coverage, explicit
  claim lanes, results and unavailable branches. Keep this composition versioned
  separately from existing video/account/research report schemas.

Expose these through the existing `skill schema` registry when implemented. Models
and cross-field validation are authoritative; bundled schemas derive from them.
Source/host capture packets, if later supported, must validate against the same
capture contract. Pasted AI prose or a search snippet is not a numeric API response.

### Minimal engine surface

```text
socialdna workflow plan --mode report --url URL --goal "QUESTION"
socialdna workflow run WORKFLOW_ID
socialdna workflow show WORKFLOW_ID
socialdna workflow report WORKFLOW_ID --format markdown --output NEW_FILE
```

`plan` persists local intent/limits but performs no network acquisition; the plan
can contain identity-resolution steps. A dry-run variant must be non-writing.
`run` executes or resumes the same plan; `show` exposes progress, coverage and
required actions; `report` composes saved eligible results without fetching again.
Multiple `--url` / attachment arguments and a typed request-file option serve the
agent, not a requirement for ordinary users to author JSON. Credentials are
configured outside arguments/prompts; expose only redacted prerequisite state.
An explicit refresh creates a new capture/plan revision, not an accidental retry.

Lifecycle: `planned → running → completed | partial | awaiting_action | failed |
cancelled`. Resuming an eligible interrupted/awaiting workflow returns to running;
completed plans reuse validated results unless refresh is explicitly requested.
Cancellation checkpoints current work and stops future steps; no persistent worker
needs a new cancellation daemon. Process termination must remain recoverable.

Keep ResultEnvelope **1.0** and existing exit codes. Workflow ID/state/structured
action codes live in `data`; do not put a workflow ID in `run_id` unless an actual
engine run exists. `run` returns partial/exit 5 for useful incomplete work or a
recoverable required action, error/exit 2 for invalid requests, 3 for wholly
unavailable functionality, 4 for denied permission and 7 for unrecoverable provider
failure, consistent with existing error mapping. `show` succeeding at retrieval
can return success while describing a failed workflow. Report exports preserve
partial status and never overwrite existing files/symlinks.

### Locking and execution

`open_application()` currently holds the data-directory writer lock throughout its
context. Do not put new acquisition/OAuth/browser waits under that context. Existing
media/provider task lifecycles remain unchanged; this is not a redesign of their
lock granularity. Claim a collection step and reserve its remaining budget under a
short lock; close it; acquire into a bounded staging area; reopen,
recheck plan/permission/withdrawal/generation tokens and atomically import/bind.
Never nest existing lock-owning import entrypoints. Refactor shared transaction
helpers only if required, preserving their public behavior.

Use per-step attempt tokens and compare-and-swap publication to reject obsolete
workers. Concurrent runs must not both own a step or exceed the reserved budget.
An interrupted acquisition can leave a failed attempt, but not a completed capture
or half-imported account. Retry idempotency covers the capture/import/binding
boundary, not just HTTP request deduplication. A deliberate later observation is
new dated evidence; retrying the same capture is not an independent observation.

## 5. Minimal persistent state and research memory

Use the existing SQLite/artifact store. Proposed first-use projections:

| Projection | Required fields/invariants |
|---|---|
| `workflow_session` | ID, schema/version, mode, sanitized request, immutable plan/hash, state, resource reservations/usage, settings/version pins, timestamps and required-action codes. No secrets. |
| `workflow_target` | FK session, ordered target key, sanitized supplied URL, platform/kind, resolution state, stable external ID, canonical account/post binding and supplied-media linkage. Aliases are not permanent identity. |
| `workflow_step` | FK session/target, logical step/input hash, attempt number/token, state, bounded checkpoint, timing, consumed budget, error category and sanitized provenance. Unique attempt identity; no successful step without committed outputs. |
| `acquisition_capture` | Canonical capture revision, source/target/attempt binding, capture manifest/hash, retained-artifact reference, policy/permission snapshot and current expiry/revocation eligibility. Minimized field-level locators. |
| `workflow_binding` | FK session/step, role, exact canonical entity/revision/evidence/run/report reference. Validate via existing typed resolvers and real FKs where the target table is fixed. No mutable “latest” citations. |

Implement only projections the first slice actually writes/reads. Operational state
is not an alternative source of performance metrics. Normalized Account/Post/Media,
metric snapshots, comments and C1 records remain in their existing canonical stores.
The acquisition adapter emits v1 imports or the relevant dedicated C1 contract;
do not add arbitrary fields to strict v1 JSON or invent metric definitions.

Any new canonical capture/report producer needs a real resolver/typed locator,
source dependency, withdrawal path and retention traversal in its first migration.
Add the next migration from the actual released head; never modify `0001`–`0017`
or pre-create every future platform table. Upgrade populated libraries, verify
checksums/backup/restore and document rollback limits.

Research memory consumes eligible canonical evidence, not whole session prompts,
OAuth traffic, HTML dumps or unsourced host summaries. No new Qdrant collection or
embedding space is required. Reuse R6 projection/outbox rules if an actually useful
capture locator needs SQL/FTS/graph retrieval. A structural “workflow used post”
relationship is not a causal/psychological finding. SQL population manifests, not
nearest-neighbor retrieval, determine quantitative comparison samples.

Policy expiry is a first-use requirement: recheck eligibility on run/resume/report/
query, reconcile overdue managed material on library access and expose due cleanup.
Integrate capture fields, temporary files, normalized copies, reports, indexes and
backups with the existing erasure/recovery machinery. A local CLI not running cannot
promise continuous deadline enforcement; routes needing unattended maintenance stay
disabled unless an approved maintenance mechanism is actually configured. Do not
claim indefinite immutable history where deletion or refresh is required. External
exports remain explicitly outside automatic cleanup; warn before exporting
restricted data and refuse an export when its source policy disallows it.

## 6. Acquisition and source-policy design

### Routing and capability checks

Parse known Instagram/TikTok/YouTube account/post shapes offline. Distinguish URL
shape recognition from an implemented connector and from authorized access. Preserve
an unresolved target when a handle needs permitted lookup. Resolve stable IDs before
merging identities; renamed handles and duplicate aliases must not split/join accounts
incorrectly. Never infer a missing account from a similar display name.

Connector operations are small and purpose-specific: resolve target, enumerate a
bounded collection, capture selected native fields, and acquire media **only when
that route explicitly permits it**. Each reports configured/access/operation state,
field availability, expected quota units, supported pagination and freshness policy.
`capabilities` remains offline, non-initializing and free of authentication probes;
connection tests/fetches are separate explicit operations. Configuration is not
proof of authentication, permission or successful collection.

Evaluate permitted **acquisition, storage, transformation, cross-subject comparison,
media access, export, refresh and deletion** separately. Connector profiles are
versioned, cite dated official documents and record applicable app/use-case approval.
The operator must actually obtain provider approval where required; neither a user
checkbox, an API key nor an agent-written permission string proves it. Do not export
platform-restricted data and reimport it as supposedly independent evidence.

### Platform routes and research findings

Default planning order is **YouTube first, subject to access/use-case review**, then
Instagram and TikTok independently. All three are required deliveries; this is an
engineering sequence, not a platform-exclusion decision or a claim that YouTube is
an unrestricted intelligence source. Revalidate at implementation. If feasibility
changes the sequence materially, report it before changing scope.

| Route | Feasible initial scope | Explicit gate / fallback |
|---|---|---|
| YouTube Data API | Resolve channels/posts and retrieve permitted native metadata/counts; account enumeration via uploads playlist | Restrictive baseline policies apply. Derived analytics need an applicable approved use case. Downloading audiovisual content is not the default route. Independently supplied creator originals can support media work subject to their own rights. |
| Instagram professional-account routes | Authorized professional-account data; eligible business/creator discovery under the documented Facebook Login route | Consumer-account access is not generally supplied by that route. Instagram Login and Facebook Login have different capabilities; do not treat them interchangeably. Owner insights and media require their own current permissions/use-case review. |
| TikTok Display API | An approved app and authorizing user's supported profile/video fields | It is not arbitrary-competitor access or automatic permission for downstream analytics/media copying. Review allowed purpose before enabling a producer. |
| TikTok Research Tools | Only qualifying approved research projects | Not a default commercial/creator connector. Return an access limitation rather than borrowing unrelated credentials. |
| Supplied originals / permitted exports | Existing offline imports bound to resolved URLs and source provenance | Clearly label this assisted workflow; do not count URL recognition plus user files as proof of cold URL-only acquisition. |

YouTube's baseline policies restrict media copying, aggregation, derived uses and
stored data. A separate analytics amendment is conditional on the applicable
approval process; it permits specified additional metrics/storage, not unrestricted
use. Therefore derived analysis is disabled unless its actual approval scope is
recorded; baseline metadata cannot silently enter R2/R9 comparisons. Resolve policy
ambiguity before enabling an operation. See the official
[developer policies](https://developers.google.com/youtube/terms/developer-policies),
[compliance guide](https://developers.google.com/youtube/terms/developer-policies-guide)
and [additional analytics policies](https://developers.google.com/youtube/terms/derived-metrics-policy).

The API's [channel lookup](https://developers.google.com/youtube/data/reference/rest/v3/channels/list)
and [playlist pagination](https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list)
are the proposed bounded enumeration route, rather than broad search as a sampling
frame. Request costs and quotas must come from current endpoint documentation.

Do not collect audience comments by default. Any enabled comment branch needs a
bounded R4 collection frame, source permission, personal-data minimization and
qualified reaction annotations; visible comments are not a representative audience
survey or evidence of individual viewers' hidden mental states.

Meta documents professional-account capabilities and Facebook Login limitations in
its [official Instagram collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).
TikTok documents app/user authorization for its
[Display API](https://developers.tiktok.com/docs/en/display-api-get-started);
its [Research FAQ](https://developers.tiktok.com/docs/en/research-api-faq) excludes
creator/advertiser/commercial users from Research Tools and explains archive lag.
These are source-access findings, not a legal certification of the proposed product.

### Budgets, failure and security

Provisional product defaults: one post for a post request; at most 20 recent
observable posts per account and 40 total per workflow; at most 100 HTTP requests
including retries and 10 minutes acquisition wall time. Enforce response/total byte
limits and timeouts as well; choose tested byte limits with the first adapter.
Existing configured ceilings always win. No automatic paid request, model download,
remote model transfer or media download merely because a URL was supplied.
Prepared model work also needs its existing resource policy. Extra scope is visible
before execution, not an unlimited “study everything” loop.

Persist request/page attempts and retry-after checkpoints; bounded retry/backoff,
not long waits under a lock. Record private/deleted/unavailable/region-limited items,
quota exhaustion, disabled comments and pagination truncation. Return useful partial
results where possible. A newest-first sample cannot establish complete historical
cadence, lifetime success rates or publication-time covariates.

Allow only known HTTPS source/redirect hosts and supported URL shapes. Reject
credentials in URLs, arbitrary ports, local/private/link-local destinations, spoofed
hosts and unsafe schemes. Revalidate DNS/redirect destinations and every downloaded
resource, not just the first URL; cap redirects, bytes and media decoding. Provider
CDNs need explicit rules. Do not follow links extracted from biographies/captions
as implicit authorization for general crawling.

Use injected HTTP clients for deterministic tests and central request accounting.
Keep access tokens in supported secret storage/environment references, not SQLite,
shell arguments, capture bodies, reports or prompts. Redact errors and signed URLs.
No password collection, cookie harvesting, CAPTCHA bypass, proxy/account rotation,
undocumented API reverse engineering or scraper fallback after a denied API.
Host browser capture is optional later work only with supported host tooling,
permitted purpose and validated provenance; browsing a page does not authorize
extracting its media or guessing private metrics. Platform text/comments/model
output remain untrusted data, never instructions to run tools or change policy.

## 7. Reports, comparisons and honest completion

Every workflow report contains:

1. Subjects, user question, actual route/access level, observation dates, sample
   selection, coverage and missing capabilities.
2. Source-native observations with exact capture/canonical citations.
3. Actual engine measurements and eligible comparisons, separated from model/host
   interpretation and reviewed research findings.
4. Counterexamples, competing explanations, unavailable evidence and uncertainty.
5. Evidence-qualified actions to test; no promised lift, hidden ranking weights,
   automatic publishing or asserted psychological cause.

Use three explicit coverage levels: **source-only**, **media-enriched**, and
**research-qualified**. These describe evidence supplied, not a universal quality
score. Report-only metadata work may complete a metadata question; it remains
partial for a requested editing/psychological/performance explanation. An assisted
path requiring originals/exports is identified separately from cold URL-only use.

`social-dna-compare` freezes the question, source permissions, subject kinds, sampling
frame, metric definitions, observation windows, maturity and available feature timing
before analysis. Unequal access is disclosed. No cross-platform leaderboard from
incompatible views, retention or engagement denominators; narrative comparisons are
possible when quantitative comparability is absent. Two creators do not establish
general cross-creator effects. Public current counts do not recover historical
seven-day performance, unseen impressions, saves, retention or conversions.

The host can add a cited narrative to the engine-backed report. Validate its
structure, existing evidence IDs and claim-lane labels; do not claim that this
automatically verifies semantic entailment or scientific truth. Unsupported prose
must not be persisted as a measured/statistical result. An offline/no-model report
must still be useful, even if it is less interpretive.

## 8. Portable packaging and verification

Task bundles have small frontmatter/entrypoints and focused references. Maintain
shared workflow/evidence instructions once, then include them in each exported
bundle so each skill works without a sibling skill or source checkout. Do not ship
symlinks or relative links escaping a skill directory. Tests detect shared-reference
drift. No duplicated statistics, alternate acquisition engine or host-specific SDK.

Preserve `skill export DEST/socialdna`. Proposed additive selection is
`skill export --name social-dna-report DEST/social-dna-report`; destinations remain
explicit, new and non-overwriting. The same bundle uses project-local
`.agents/skills` (Codex), `.claude/skills` (Claude Code) or `.opencode/skills`
(OpenCode). Installation, dependency preparation, model consent and source connection
remain separate explicit actions; planning authorizes none of them.

Host conventions were checked against official
[Codex skills](https://developers.openai.com/codex/skills),
[Claude Code skills](https://code.claude.com/docs/en/skills) and
[OpenCode skills](https://opencode.ai/docs/skills) documentation on 2026-11-06.
Do not rely on host-specific argument substitution or slash commands in shared
instructions. The engine contract, not assumed identical host behavior, is portable.

Verification has distinct gates: deterministic unit/contract/integration fixtures;
installed wheel/sdist end-to-end tests; consented live source smoke; actual live
host conversations. A fixture HTTP server proves connector behavior, not production
access. Directory-layout tests prove packaging, not skill invocation/tool choice.
Each provider/skill release records which gates ran and with what version/access;
an unavailable live check stays open, never relabeled passing. Never use real tokens
or private creator data in fixtures or distribution archives.

## 9. Decisions for review

- Proceed additively with three task skills and one shared workflow coordinator.
- Deliver one cold post-URL/source-only report first, then genuine permitted media,
  account studies, comparisons, release hardening and independent platform additions.
- Include all three platforms as required targets, with YouTube provisionally first
  in delivery order and source-policy feasibility reviewed for each connector. Public
  API data does not necessarily permit every requested goal.
- Keep direct offline inputs first-class and support assisted workflows honestly.
- Reuse the existing storage, scientific contracts and memory; add only first-use
  workflow/capture persistence and no required infrastructure.
- Keep live source and live host acceptance explicit. A public claim of complete
  URL-first account intelligence requires the account/comparison and applicable
  source/media gates, not just the first metadata report or three skill directories.
  A claim of three-platform support additionally requires DX6-A and DX6-B's actual
  routes and source-access checks; they are not optional product commitments.

Deferred: unattended monitoring, universal browser collection, paid data vendors,
automatic literature collection, a GUI, hosting/report sharing, publishing/account
edits, general arbitrary-URL crawling and distributed workers. They are not implied
by “URL-first.”
