# slopstop

A Claude Code plugin that blocks installs of **hallucinated packages** before they run.

## The problem: slopsquatting

LLM coding agents hallucinate plausible-but-nonexistent package names at a high, predictable
rate — a 2025 USENIX Security study found this across 576,000 code samples from 16 models
(51% pure fabrications, 38% conflations of two real packages, 43% reproduced identically across
repeated runs of the same prompt).

Attackers watch for these predictable hallucinations and pre-register the fake names on real
registries (npm, PyPI) — a supply-chain attack known as **slopsquatting**. Confirmed 2026
incidents include `react-codeshift` and `unused-imports` on npm, and a hallucinated
`huggingface-cli` install command that was copy-pasted into public documentation and
accumulated 30,000+ downloads.

A human reviewing an AI's suggested `npm install <pkg>` before running it used to be an
implicit checkpoint. Autonomous coding agents increasingly run installers themselves — removing
that checkpoint entirely.

## What it does

`slopstop` adds two Claude Code hooks:

- **PreToolUse (Bash)** — before any `npm install`/`yarn add`/`pnpm add`/`pip install`/`uv add`
  (etc.) command runs, it extracts the package names and checks each one against the real
  registry (npmjs.org / pypi.org):
  - Package **doesn't exist** → the command is **blocked**, with a message naming the fake
    package(s) and flagging the slopsquatting risk.
  - Package **exists but was published very recently** (< 30 days) → the command is allowed,
    but you get a warning, since reactive same-day registration of a hallucinated name is a
    known slopsquatting pattern.
  - Any network error/timeout → **fails open** (allows the command silently) — it never blocks
    your work because a registry was slow or unreachable.

- **PostToolUse (Edit/Write/MultiEdit)** — catches the case where the agent edits
  `package.json`, `requirements.txt`, or `pyproject.toml` directly instead of running an
  installer, and warns (edits already happened, so this can't block) about any added dependency
  that doesn't exist or was published very recently.

Lookups are cached on disk for 24h (`~/.cache/slopstop/registry_cache.json`) so repeated checks
in a session don't re-hit the registry.

v1 covers **npm and PyPI** — the two highest-volume vibecoding ecosystems and the ones with the
most documented slopsquatting incidents. More ecosystems (Cargo, Go, RubyGems) can be added the
same way.

## Install

```
/plugin marketplace add Lasp10/slopstop
/plugin install slopstop
```

or, for local development:

```
claude plugin add /path/to/slopstop
```

## Try it

```
npm install this-package-does-not-exist-xyz123
```

should get blocked with an explanation, while:

```
npm install express
```

passes through untouched.

## How it's built

- `.claude-plugin/plugin.json` — plugin manifest.
- `hooks/hooks.json` — registers the PreToolUse and PostToolUse hooks.
- `hooks/check_install.py` — parses Bash install commands, extracts candidate package names
  (`hooks/lib/extract.py`), checks them against the registry (`hooks/lib/registries.py`), and
  emits a `permissionDecision: deny` to block.
- `hooks/check_manifest.py` — same registry check, applied to dependencies found in edited
  manifest files (`hooks/lib/manifest.py`).

No external dependencies — pure Python 3 standard library + `curl` (used instead of Python's
`urllib` directly to sidestep local SSL cert-store issues and rely on the OS trust store).

## License

MIT
