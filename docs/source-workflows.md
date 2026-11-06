# Source-only URL workflows

Implemented in `0.0.21` / migration `0018_workflows`. Automated synthetic transports are
not live API acceptance. The supplied real URL awaits a locally configured key,
active retention maintenance and a separate real host/skill conversation.

## What ships

One YouTube video/Short URL can yield a durable, cited native metadata report through
the official `videos.list` endpoint. YouTube aliases normalize to the same stable ID;
Instagram/TikTok post/account URLs are recognized, not acquired. No accounts are
enumerated. No video, audio, thumbnails, captions or comments are downloaded.

Native title/description/duration/count strings stay in a source-qualified capture.
Omitted fields are unknown, not zero; retrieval time is not a historical metric
measurement timestamp. No rates, scores, psychological or audiovisual findings are
computed. Generic statistics and semantic/graph research indexing are blocked for
these sources; API counts are not silently turned into engine metric observations.
An arbitrary unsupported research goal produces partial coverage and a next action,
not a claim that the question was answered. The default task requests native metadata;
`--question-scope native_metadata` is an explicit caller declaration of that scope.

## Start without access

```text
socialdna --offline --no-ai --format json capabilities
socialdna --offline --no-ai --format json workflow plan --url https://www.youtube.com/shorts/EaYRjrQuxEk --dry-run
```

Both are non-initializing, with no request or model inference. A normal plan persists
only the safe target and immutable budgets. Unsupported URL shapes/credentials and
ambiguous IDs are refused; user URLs are never direct HTTP destinations.

## Explicit operator setup

Enable YouTube Data API v3 for an appropriate project and configure the API key
locally in `SOCIALDNA_YOUTUBE_API_KEY`, or a secret environment variable named by
`youtube_api_key_env` in settings. Never paste the key in chat, arguments, a plan or
an export. A key configured in another terminal may not reach the agent's process.
This first adapter does not implement OAuth, discover credentials or store keys.
Google recommends header-based API key transmission; the client uses `X-Goog-Api-Key`.
[Google guidance](https://cloud.google.com/docs/authentication/api-keys-use).

Live retention is supported only with a matching active **Linux systemd user timer**.
Inspect/export its exact configuration using:

```text
socialdna --data-dir /absolute/library --format json workflow maintenance --output-dir /absolute/new-units
```

This creates files only in the explicit new directory. It does not install, enable,
start or change host settings. Separately review the generated service/interpreter
and library paths; an authorized operator must install the files in the appropriate
systemd user unit directory, reload units and enable/start the named timer. User
session scheduling/linger is an operator decision; never enable it silently. Retention
checks exact loaded units, no drop-ins/reload pending, the timer's active state and
service binding. Moving the interpreter/library requires explicit reconfiguration.
Other scheduler adapters are deferred. A machine that is off cannot guarantee
wall-clock deletion; external exports/backups remain the operator's responsibility.

The timer runs the no-network/no-AI `workflow maintain` command hourly (persistent
catch-up), applying default 7-day expiry. Configuration can shorten/change this to
1–29 days, never remove the bound. Startup also denies expired data before normal
access and resumes cleanup. This is an operational safeguard, not a legal certification.
Review the applicable [YouTube policies](https://developers.google.com/youtube/terms/developer-policies)
and any [conditional additional analytics approval](https://developers.google.com/youtube/terms/derived-metrics-policy)
before expanding permitted use.

## Capture and reopen

```text
socialdna --data-dir /absolute/library --format json workflow plan --url https://www.youtube.com/shorts/EaYRjrQuxEk
socialdna --data-dir /absolute/library --format json workflow run WORKFLOW_ID
socialdna --data-dir /absolute/library --offline --no-ai --format json workflow show WORKFLOW_ID
socialdna --data-dir /absolute/library --offline --no-ai workflow report WORKFLOW_ID --format markdown --output /absolute/new-report.md
```

Use the returned ID. Run with a native-compatible goal; audiovisual URL analysis is
future DX2 work. Missing credentials/offline/maintenance returns partial5 and a
required action, without consuming an HTTP attempt. Unimplemented platform/target
routes return unavailable3. Permission errors return4. HTTP429/5xx checkpoints
bounded retry-after, not a hidden retry loop. A successful resume reuses the capture;
a deliberate refresh is a new explicit plan. Deleted/private/unavailable responses
are not interpreted as zero performance. API errors never echo bodies/keys.

Plans pin 20-second request time and 1MiB response limits by default, one page/one post,
and at most 3 lifetime attempts. Requests use a fixed official HTTPS endpoint, public
DNS checks, no redirects/proxy inheritance, bounded identity-encoded JSON and TLS.
DNS resolution follows OS resolver behavior; the request budget is not an OS-wide
hard execution deadline. No key is put in a query string or durable audit.
The endpoint and fields follow [videos.list](https://developers.google.com/youtube/data/reference/rest/v3/videos/list).

`workflow report` **always returns a JSON envelope**; Markdown is `data.content`.
`--output` writes just the frozen document and refuses overwrite. This is additive:
legacy `report generate --format markdown` keeps its original raw-Markdown output.
Saved-result tasks can use `workflow plan --mode report --from WORKFLOW_ID`, then
run the new ID offline. This never fetches or refits anything.

## Persistence and recovery

`workflow_sessions` pins request/plan/hash/state; `workflow_targets` records one
safe identity; `workflow_attempts` records claims/deadlines/cooldowns;
`acquisition_captures` binds source/policy/expiry to an exact canonical revision;
`workflow_bindings` links output roles to those revisions. Existing account/post
identity/publication import is atomic with capture/source rows. Actual native fields
use existing typed ContextLocator evidence, not a new parallel citation system.
JSON/Markdown artifacts are frozen, checksummed and checked on every read.

The directory writer lock is closed before HTTP. A short claim transaction precedes
the request; commit rechecks attempt token/deadline, identity, expiry and maintenance.
An import failure rolls back canonical rows. A committed capture survives report
interruption and resumes without another request. Stale/concurrent workers cannot
overwrite a newer reservation. Policy changes require a new plan.

Withdrawal withholds dependent reports without claiming byte erasure. Existing
confirmed source-erasure journals scrub API snapshots/artifacts and restore prior
independently sourced current metadata when possible. Expiry uses that deny-first
journal; restart resumes interruption. Backup restoration keeps existing restricted
recovery/withdrawal reconciliation, then reapplies source expiry before access.
Managed erasure does not erase user exports or old external backups automatically.
Qdrant/NetworkX need no new collections or graph structures for this native-only path.

## Export task skills

```text
socialdna --format json skill export /absolute/project/.agents/skills/social-dna-ingest --name social-dna-ingest
socialdna --format json skill export /absolute/project/.agents/skills/social-dna-report --name social-dna-report
```

Use the corresponding host's chosen parent; no host settings are edited. Both work
independently: ingest explicitly captures, report reads saved outputs only. The
maintained shared reference in `skills/shared` is assembled into each exported
bundle, including wheel/sdist installations; export rather than copying the source
fragment alone. Existing `socialdna` export remains backward-compatible. Available
schemas add `workflow_request`, `workflow_plan`, `capture` and `workflow_report`.
The remaining 12 task skills are planned, not directories advertised as working tools.
