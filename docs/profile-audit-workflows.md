# Assisted profile audit proposals

This is the first implemented DX3-A lane, not completion of URL-only profile
collection or substantive semantic/aesthetic audit acceptance. No new infrastructure,
migration, dependency, hosted model or download is needed.

A host with a permitted source can record its actual observations without asking
the user to construct SocialDNA JSON:

```sh
socialdna workflow observe-profile https://www.instagram.com/example/ \
  --external-id ACTUAL_STABLE_ACCOUNT_ID --captured-at 2026-11-01T12:00:00Z \
  --permission-basis authorized_export --source-description 'Consented independent observation' \
  --username example --display-name 'Example Creator' --bio '' --links-empty
socialdna workflow plan --mode analyze --scope profile \
  --url https://www.instagram.com/example/ --profile-revision SNAPSHOT_REVISION \
  --audit-focus improvements --goal 'Identify observable weaknesses'
socialdna workflow run WORKFLOW_ID
socialdna workflow report WORKFLOW_ID --format markdown
```

Replace the example URL, identity and timestamps with real observations. Declarations
are not verified ownership or acquisition. Do not copy restricted native API fields
into this lane. URL-only input returns `profile_observation_required`, without network.
All three recognized platforms can associate independently supplied snapshots; this
does **not** implement three platform collection adapters.

Omitted text/assets are not collected. Explicit empty strings/empty inventory flags
retain observed emptiness. Existing C1-D validates pin ownership and dates, stores
supplied photo bytes, and separates public snapshots from genuine human reviews and
measured owner funnels. No external bio destination is visited. U1's bounded decoder
checks supplied photos; reported dimensions are not proof of branding quality.

The immutable `ProfileAuditProposal` is a new canonical producer using the existing
0019 workflow composition projection, ContentLocator, managed artifact store and
recursive evidence eligibility. It is always partial, `unreviewed_proposal`, with
deterministic `profile-field-checks-1`, never a counterfeit `ProfileReview`. It reports
literal field observations, favorable presence checks, empty-field improvement prompts,
unknowns and prioritized review prompts. It does not judge ambiguous positioning,
link destination consistency, pin alignment, inferred pillars or conversion effects.
The focus changes presentation, not evidence; account ownership/popularity is not
a biasing input.

Every read checks source eligibility and frozen integrity. A new observation and new
plan explicitly refresh; no previous output is rewritten. `workflow report` returns a
separate freshness hint if a later eligible snapshot of the same stable account exists.
Source withdrawal/confirmed erasure closes dependent proposals and managed derivatives;
external originals and exported copies remain outside automatic deletion.

Remaining DX3-A gates: permitted native profile adapters/alias resolution, genuinely
capable labeled semantic proposal producer, substantive strengths/weaknesses fixtures,
and consented real source/host checks. These are retained in PLAN, not marked complete.
