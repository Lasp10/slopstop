# Slopsquatting is a real supply-chain risk now. A Claude Code plugin that closes the gap

If you've spent time vibecoding with an autonomous agent, you've probably watched it run
`npm install` or `pip install` on its own, without asking. That's convenient, until the package
it installs doesn't actually exist and never did.

## The bug that becomes an attack

LLMs hallucinate package names. This isn't rare: a 2025 USENIX Security study tested 16 models
across 576,000 code-generation samples and found a meaningful fraction of referenced packages
were hallucinated: 51% pure fabrications, 38% "conflations" (mashing two real package names
together, e.g. `express-mongoose`), 13% typo variants. The alarming part is that when
researchers re-ran the same prompt 10 times, 43% of hallucinated names came back identical
every single time.

That predictability is what turns a model quirk into an attack surface. If an attacker can
predict which fake name a popular model will suggest for a popular task, they just register
that name on the real registry ahead of time and wait. This is called slopsquatting, and it's
already happened:

- `react-codeshift` on npm: a hallucinated name a security researcher found circulating through
  real agent traffic, registered by nobody in particular, just there.
- `unused-imports`: flagged and security-held by npm, but still pulling about 233 weekly
  downloads months later.
- A hallucinated `huggingface-cli` install command got copy-pasted into Alibaba's own public
  documentation without verification, and the resulting package picked up 30,000+ downloads.

## Why this is getting worse, not better

The traditional mitigation was implicit: a developer reads the AI's suggested command before
running it. That's a real checkpoint, even if an informal one. But the entire premise of
"vibecoding" with an autonomous agent is that it runs commands for you. Claude Code, Cursor's
agent mode, Replit's agent: the industry direction is fewer confirmations, not more. The
checkpoint that used to catch this is being designed out of the workflow at the exact moment
the underlying hallucination problem hasn't gone away.

## What I built

[slopstop](https://github.com/Lasp10/slopstop) is a small Claude Code plugin that puts a
machine-checkable version of that old human checkpoint back in place, at the one point where
it's cheap to check: right before the install command executes.

It hooks `PreToolUse` on `Bash`. When it sees an install command (`npm install`, `pip install`,
`uv add`, etc.), it pulls out the package names being installed and checks each one against the
real registry, npmjs.org or pypi.org, before letting the command run.

- Package doesn't exist: the install is blocked outright, with the exact fake name(s) called
  out and a note that this matches the slopsquatting pattern.
- Package exists but was published in the last 30 days: allowed, but flagged, since a same-week
  registration of a name is consistent with someone reactively slopsquatting a known
  hallucination.
- Registry unreachable or times out: fails open, silently. It should never be the reason your
  build breaks.

A second hook covers the case where the agent edits `package.json` or `requirements.txt`
directly instead of running an installer. Same registry check, applied to newly-declared
dependencies, surfaced as a warning since the edit's already happened by the time it runs.

It's pure Python standard library plus `curl`. No dependencies to audit, ships as a normal
Claude Code plugin, and results are cached for 24h so it doesn't hammer the registries.

## Try it

```
/plugin marketplace add Lasp10/slopstop
/plugin install slopstop
```

Then ask your agent to `npm install this-package-does-not-exist-xyz123` and watch it get
blocked, while `npm install express` passes straight through.

Repo: https://github.com/Lasp10/slopstop
