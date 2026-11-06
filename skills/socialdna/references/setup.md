# Engine and host setup

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
