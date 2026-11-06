# Engine and host setup

## First-use diagnosis

Run `socialdna --format json setup --task analyze --host codex --input-kind image`
for an owned local photo, or add `--url URL` for a URL workflow (omit input-kind
unless supplying a local original). Choose `--scope profile` for profile analysis;
`--host` accepts `codex`, `claude-code` or `opencode`. `--project-dir PATH` selects
the suggested project installation path without creating it.

Setup returns diagnostics and argument-array next-step templates. It never opens
or migrates a library, probes a connection, starts a model, installs a bundle or
changes host settings. Exit 5 means action is needed, not a failed installation.
Resolve template bindings from actual previous results. An agent handles workflow
IDs; the user should normally supply a URL, question and any missing authorization
or original file, not normalized JSON or hand-crafted engine IDs.

`skill list` separates eight delivered task bundles from six planned specialists.
`skill inspect --name social-dna-analyze` validates bundled public files and returns
their SHA-256 hashes without writing. Each task export includes this setup guide
and the shared workflow reference; no sibling skill installation is necessary.
For a task bundle, append `--name social-dna-analyze` to `skill export` and name the
destination `social-dna-analyze` rather than `socialdna` in the examples below.

## Source connections and explicit actions

Local photo/video analysis requires no platform key. FFmpeg/ffprobe are required
only for video; local ASR/OCR and other prepared models remain optional. No models
are downloaded or selected automatically by setup.

The delivered native connection is one YouTube post's official public metadata,
not its media, captions, comments or account enumeration. Configure the key in the
engine's local `SOCIALDNA_YOUTUBE_API_KEY` environment variable (or the locally
configured variable), never in a prompt, URL, JSON export or command argument.
Presence is not validity or permission. `workflow maintenance` inspects the
required retention scheduler; it does not install or enable one. Review the
returned platform/OS requirements and obtain explicit permission before setup.
`workflow plan --url URL` persists intent only; `workflow run RETURNED_ID` is the
explicit network action and checks actual access, budgets and retention readiness.
It can return denied/unavailable/partial. Do not bypass these gates or relabel API
metadata as independently observed creative/research evidence.

Instagram/TikTok and profile/account URLs are recognized identities, not delivered
native collectors. Use actual permitted observations, existing eligible library
records or authorized originals. No key can unlock a collector that is not built.
Never infer retention, audience analytics, filming details or conversion from URL
metadata. Offline mode prohibits native acquisition but supports local analysis,
saved eligible reports, exports and source qualification.

The entire `socialdna` skill directory is portable. There are no host-specific SDKs,
hooks, tool allowlists, dynamic shell substitutions or alternate analysis services.
Use a terminal-enabled local session. Remote/cloud sessions need their own engine,
authorized inputs and skill installation; a local subscription does not supply these.

Install a reviewed SocialDNA wheel in an isolated Python 3.11+ environment, or use the
repository's locked environment (`uv sync --locked`, then `uv run socialdna`). Core
installation needs no model extras. Video additionally needs FFmpeg and FFprobe on
PATH. Photos do not. Package installation may need network access: obtain approval
and use a prepared offline wheel cache when required. No runtime model download is automatic.

Use an explicit invocation prefix throughout the session: `socialdna`, an absolute
environment executable, or `uv run --project /absolute/checkout socialdna`. Do not
assume the shell's current directory equals the skill directory.

## Install the skill only when requested

Create the intended parent skills directory, then export to a **new** directory:

```text
socialdna --format json skill export /absolute/project/.agents/skills/socialdna
socialdna --format json skill export /absolute/project/.claude/skills/socialdna
socialdna --format json skill export /absolute/project/.opencode/skills/socialdna
```

Choose one line for the intended host. Existing destinations are refused, including
symlinks. Move aside an old installation yourself after reviewing it; export never
overwrites it. The engine writes only the explicit destination, not host settings.
Do not install duplicate copies for OpenCode, which also discovers compatible paths.

| Local host | Project skill directory | Explicit selection |
|---|---|---|
| Codex | `.agents/skills/socialdna` | Ask to use `$socialdna` |
| Claude Code | `.claude/skills/socialdna` | `/socialdna` |
| OpenCode | `.opencode/skills/socialdna` | Ask to load the `socialdna` skill |

Reopen or refresh the host's skill list after copying. Global equivalents are
`~/.agents/skills`, `~/.claude/skills`, and `~/.config/opencode/skills`; do not write
these unless the user requests a global install. On Windows pass a native absolute
path as one argument (quote paths with spaces). All three hosts run the same engine.

Compatibility guidance was checked 2026-11-06 against official
[Codex](https://developers.openai.com/codex/skills),
[Claude Code](https://code.claude.com/docs/en/skills), and
[OpenCode 1](https://opencode.ai/docs/skills)/[OpenCode 2](https://opencode.ai/v2/docs/skills)
documentation. Host policies can disable
discovery or terminal execution; do not bypass them. Documented discovery is not a
live host behavioral test.

## Diagnose

```text
socialdna --version
socialdna --data-dir /absolute/library --offline --format json capabilities
socialdna --data-dir /absolute/library --offline --format json doctor
```

Capabilities reads settings/model metadata and checks prepared checksums, but does
not open SQLite/Qdrant or contact endpoints. `doctor` is a deeper library check and
can initialize/migrate/reconcile local storage. Run it on the intended local data
directory, not an arbitrary legacy library. Back up valuable existing data before
upgrading; do not edit migration histories or reuse a library on network storage.

Check JSON `checks`, warnings and exit status; exit 0 may still contain optional-model
warnings. Missing FFmpeg blocks video, not photos/account analytics. Missing prepared
models does not block deterministic analysis. For corruption, lock conflicts or
permission errors, explain the exact error rather than creating another library
silently. Restore/withdraw/erase operations require separately confirmed exact scope.
