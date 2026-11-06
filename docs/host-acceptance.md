# Live host acceptance

Directory-layout, CLI and installed-wheel/sdist tests are not model conversations.
Do not claim host discovery, tool choice, or successful source access from them.
The same procedure applies again to new specialist bundles.

## Authorized procedure

1. Obtain permission for a temporary installation and model conversation. Explain
   possible subscription/provider cost. Do not configure new credentials or change
   global settings. Preserve host sandbox, hooks, approvals and user policies.
2. Build/test reviewed artifacts, install the wheel in an isolated environment, then
   run `python scripts/prepare_host_acceptance.py --engine /absolute/venv/bin/socialdna
   --host codex` (or `claude-code`/`opencode`). This only creates a temporary synthetic
   project and one skill. It does not launch a host or contact a provider.
3. Review `prompt.txt` and `fixture.json`. Only synthetic inputs and reviewed public
   instructions may be sent. Use the prepared project as the host's working directory;
   do not add repository/private directories. Use existing authorized model selection
   and access. Set a bounded process timeout; do not retry paid calls automatically.
4. Ask the host to use the named skill with the prompt. Record explicit selection
   separately from an independent automatic-discovery test. For Codex, the explicit
   invocation is `$social-dna-analyze`; Claude Code uses `/social-dna-analyze`;
   OpenCode can load the named skill. Do not install duplicate compatibility copies.
5. Inspect actual tool traces and engine artifacts, not the model's self-assessment:
   correct skill read, installed engine run, preserved original/canonical URL,
   actual workflow IDs, no source downloads or invented analytics, partial status
   retained, persisted report, exact evidence eligibility and independent re-open.
6. Record the installed engine/host version, observed model (or unknown), date/OS,
   permissions, selected skill/scope, commands, outputs, and acceptance result.
   Never commit authentication state, raw private logs, API keys or subscriptions.
   Delete only the exact task-owned temporary directory with permission when no
   longer needed. Reports outside the managed library are not automatically erased.

Official conventions checked 2026-11-06:
[Codex skills](https://learn.chatgpt.com/docs/build-skills),
[Claude Code skills](https://code.claude.com/docs/en/skills),
[OpenCode skills](https://opencode.ai/docs/skills/).
Documented compatibility is not a claim of observed host behavior.

## Acceptance matrix and release record

Every claimed host needs a real supported URL/prompt → engine → cited persisted
report conversation plus a denied/unavailable branch. Explicit selection alone
does not prove automatic routing. One analyze/photo check does not certify all
eight tasks, profile quality, video models, native APIs or all platforms.

Observed attempt on 2026-11-06 UTC (Linux, installed SocialDNA `0.0.26` wheel):

| Check | Observed result |
| --- | --- |
| Host | Codex CLI `0.162.0-alpha.17.2`; normal existing model/access selection |
| Installation | One `social-dna-analyze` bundle in an isolated temporary project; matching public resource hashes |
| Inputs | Generated owned geometric photo and synthetic recognized Instagram post identity; offline/no-AI engine |
| Invocation | Named skill requested in the prompt; `exec --sandbox workspace-write --skip-git-repo-check --ephemeral --json`, 180-second outer timeout |
| Runtime | Exit 1 before conversation: read-only normal Codex runtime directory; state database initialization/app-server client failed |
| Model and engine tools | No model selection/conversation or tool trace observed; no library/report produced by the host |
| Acceptance | **Blocked**, not a behavioral pass; no auth/home/policy bypass or paid retry attempted |

Claude Code and OpenCode live conversations are **not run**. Codex automatic
discovery and all eight tasks' complete behavioral matrix remain unverified. No
native social-platform or prepared-model live check was performed. The narrow
authorization was for synthetic-only existing-host use, not new credentials,
global settings changes or additional provider calls. A permitted terminal host
with writable normal runtime state is required to complete this gate. Missing
access/runtime is not a pass; DX5's all-host live acceptance remains open.
