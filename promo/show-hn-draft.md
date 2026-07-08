TITLE (80 char limit):
Show HN: Slopstop, blocks AI agents from installing hallucinated packages

URL: https://github.com/Lasp10/slopstop

TEXT (post as a comment on your own submission, HN convention):

I built this after digging into "slopsquatting." LLMs hallucinate plausible-but-nonexistent
package names at a surprisingly high, predictable rate. A 2025 USENIX study found this across
576k code samples from 16 models. About 43% of hallucinated names were reproduced identically
across 10 repeated runs of the same prompt. Attackers watch for this and pre-register the exact
fake names models suggest, so `npm install <hallucinated-name>` pulls down an
attacker-controlled package. There have been a few confirmed 2026 incidents already
(react-codeshift, unused-imports on npm, and a hallucinated huggingface-cli install command
that got copy-pasted into Alibaba's public docs and picked up 30k+ downloads).

The part that makes this worse now: a human used to eyeball the AI's suggested install command
before running it, an implicit checkpoint. Autonomous coding agents (Claude Code, Cursor agent
mode, etc.) increasingly run the installer themselves, removing that checkpoint.

slopstop is a Claude Code plugin that hooks into PreToolUse on Bash. Before an install command
runs, it checks every package name against the real npm/PyPI registry and hard-blocks the
command if the package doesn't exist, with the reasoning surfaced back to the agent/user. It
also warns on packages that exist but were published under 30 days ago, a common reactive
slopsquat pattern. It fails open on any network error so it never blocks legitimate work. No
external dependencies, pure Python stdlib plus curl.

Feedback welcome, especially on other install-time signals worth checking (typosquat distance
to popular package names, maintainer/repo link checks, etc).
