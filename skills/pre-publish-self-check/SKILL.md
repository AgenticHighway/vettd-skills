---
name: pre-publish-self-check
description: "Use when a skill author has finished writing or editing a skill and wants to check it before pushing to GitHub, opening a PR, or sharing it. WHEN: before publishing a skill, before pushing to GitHub, self-review of a skill I wrote, checking my own skill directory. DO NOT USE FOR: scanning someone else's skill before installing (use vet-before-install), or an environment sweep (use audit-my-agent-environment)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---

# Self-Check a Skill Before Publishing

## Overview

Scan your own skill directory before you push, open a PR, or share it, then fix and rescan until security and structure findings are clean. Treat vettd as a linter you run on your own work, not a gate someone else runs on you.

## Preflight

Run `vettd auth status --json`. If the binary is missing, `configured` is
false, or `reachable` is false:

⛔ **STOP** — invoke **setup-vettd**, then return here.

## When to Use

| Situation | Action |
|---|---|
| You wrote or edited a skill directory and want to publish it | Use this skill |
| You are about to open a PR that adds or changes a skill | Use this skill |
| You want to double-check a skill before sharing it with a teammate | Use this skill |
| You are about to install a skill someone else wrote | Use `vet-before-install` instead |
| You want a sweep of every skill already installed across an environment | Use `audit-my-agent-environment` instead |
| A specific finding's meaning or severity is unclear | Finish this skill, then invoke `triage-a-flagged-finding` |

## Command Contract

As of vettd 0.9.0:
- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

Scan the skill directory you are authoring:

```bash
vettd scan folder ./skills/my-skill --stdout --deep
```

`--deep` has no depth limit and only exists on `scan folder`. Use it here — reference files nested a few levels deep (scripts/, references/, examples/) are exactly what a real reviewer or installer will read, so scan them too. A scan of a small skill directory takes roughly 100-300ms, so rescanning after every fix is cheap. Treat the loop as free.

## Workflow

1. Run the Preflight check.
2. Scan: `vettd scan folder <path-to-your-skill> --stdout --deep`.
3. Parse the JSON. Find your skill's entry in `skills[]` by matching the path portion of `id` (`<abs-path>:<12-char-content-hash>`) against your directory — do not match on `name` alone, since multiple scans can produce entries with the same name.
4. Read `overallGrade` and `trustLevel` for that entry.
5. Read every entry in `externalScannerResults[].findings[]`. Group by `category`: `security`, `structure`, `description`, `best-practices`, `scripts`, `evals`.
6. Fix `security` and `structure` findings first, ordered by `severity` (`critical` > `high` > `medium` > `low` > `info`) — these two categories are what determine `overallGrade` and `trustLevel`.
7. Rescan with the same command. Confirm each fixed `ruleId` no longer appears, and confirm no new `security`/`structure` finding was introduced by the fix.
8. Repeat steps 6-7 until `security` and `structure` are free of `critical`/`high` findings and `overallGrade` reaches the level you're targeting (A or B, `Trusted` or `Conditional`).
9. Only after that: address `description`, `best-practices`, `scripts`, and `evals` findings. These do not move `overallGrade`, but they're real quality signal — fix them because the skill is genuinely better, not to chase a letter.
10. If a finding's cause or severity doesn't make sense for your skill:

⛔ **MANDATORY HAND-OFF** — invoke **triage-a-flagged-finding**.

11. Stop when `security`/`structure` are clean at your target grade and you've made a deliberate call (fix or accept) on every remaining `description`/`best-practices`/`scripts`/`evals` finding.

## Grade Thresholds

`overallGrade` is computed from `structure` and `security` findings only,
using thresholds evaluated F to A, first match wins. Full methodology:
https://vettd.agentichighway.ai/methodology

| Grade | Threshold |
| --- | --- |
| F | 3+ highs, or any critical present |
| C | 3+ mediums, or 1-2 highs present |
| B | 4+ lows, or 1-2 mediums present |
| A | Fewer than 4 lows, no mediums/highs/criticals |

Use this to know your exact headroom. Two mediums is still a `B`; a third
medium drops you to `C`. One high is `C` regardless of how clean
everything else is; three highs is `F` even with zero criticals. A single
`critical` finding is always `F` — critical means adversarial intent, or a
pattern that fires unconditionally with no exploitability preconditions.
There is no threshold to stay under; fix it or the grade cannot move.

Reaching grade `A` means no `structure`/`security` findings of note in
what was scanned — it is not a guarantee of safety in every environment,
and a scan that returns very few findings overall is a weaker signal than
one that returns many `info`-level findings showing real coverage.

## Fixing Common Findings

| Cause | Example ruleId | Category | Fix |
|---|---|---|---|
| External URL referenced in SKILL.md | VTD-0088 | security | Inline the needed content instead of linking out, or pin to a specific commit/version so referenced content can't change after audit |
| Missing SKILL.md | VTD-0095 (absence) | structure | Add the required SKILL.md with correct frontmatter |
| Cloud instance metadata endpoint probed | VTD-0029 | security | Remove the probe entirely — a skill has no legitimate reason to read cloud metadata endpoints; this is a known credential-theft vector and fires as `critical` |
| Shell + network + filesystem access declared together | dangerous-keyword-combo rules | security | Split into narrower steps, drop any tool declaration you don't actually invoke, or document in the skill why the combination is required |
| Base64 decode-and-use patterns | encoding/obfuscation rules | security | Avoid decode-then-execute flows; if decoding is legitimate, keep the decoded content as inert data, never pipe it to a shell or interpreter |
| Remote content piped straight to a shell (`curl \| sh`) | remote-exec rules | security | Replace with a pinned, checksum-verified install step; never pipe unreviewed remote output directly into execution |
| Credential-shaped strings, or scripts reading known credential paths (cloud provider creds, SSH private keys, container registry configs) | secret-pattern rules | security | Remove real-looking keys/tokens from examples; never read credential file paths from a skill script; read real credentials from environment variables instead |
| Skill name suspiciously close to a known popular skill | typosquatting rules | security | Rename to something clearly distinct — name-proximity to a popular skill is a recognized supply-chain attack pattern, not a style nitpick |
| A chain of otherwise-ordinary signals (credential access, then encoding, then outbound transmission; or remote fetch piped straight to a shell) | chained-signal rules | security | Vettd weighs sequences, not just individual signals — the difference between careless code and an intentional attack is often visible in the chain. Break the chain: don't decode-then-transmit, don't fetch-then-execute, in a single flow. |
| Overly broad tool/permission declarations | broad-permission rules | structure/security | Declare the narrowest explicit tool list your skill actually uses instead of a wildcard or "all tools" |
| Prose describing what your skill does *not* do (e.g. "no network access") | keyword-detection false positive | — | Vettd's keyword matching does not understand negation — mentioning "network access" or "shell execution" in prose, even to disclaim it, can add that permission to your skill's declared surface. Omit the negated mention rather than stating it. |

## Common Mistakes

| Mistake | Why it's wrong |
|---|---|
| Treating a `description`/`best-practices`/`scripts`/`evals` finding as blocking publication | Only `security` and `structure` findings affect `overallGrade` and `trustLevel` |
| Assuming a fix worked without rescanning | The only proof a finding is resolved is its absence from the next `--stdout --deep` scan |
| Reading the human-readable terminal output instead of `--stdout` JSON | ANSI escapes are emitted regardless of TTY state and will corrupt any parsing |
| Branching logic on the scan's exit code | Scans always exit 0; severity lives only in the JSON, never in the exit status |
| Scanning without `--deep` | Findings in nested `scripts/`/`references/` files won't be included, giving a false sense of a clean skill |
| Matching your skill by `name` instead of the path portion of `id` | Multiple scan runs or similarly-named skills can collide on `name` alone |
| Treating `Conditional` trustLevel as always a failure | Some skills legitimately need elevated permissions; `Conditional` can be the correct, expected outcome — check the underlying findings, not just the label |
| Disclaiming capabilities in prose ("this skill does not use the network") | Keyword matching has no concept of negation and may still flag the mentioned capability |
