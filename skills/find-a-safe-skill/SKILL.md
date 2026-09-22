---
name: find-a-safe-skill
description: "Use when a user or agent needs to find an existing skill that performs a task, before writing one from scratch or grabbing the first search result. WHEN: find a skill for X, is there a skill that does X, search the skill directory, which skill should I use, compare candidate skills for safety. DO NOT USE FOR: scanning a skill you already downloaded or chose (use vet-before-install), auditing your own local agent environment (use audit-my-agent-environment)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.2.0"
  requires-vettd: ">=0.10.0"
---

# Find a Safe Skill

## Overview

Search the public vettd directory for skills that perform a given task, then compare candidates by grade and findings to choose the safest fit — not the first or most popular result.

## When to Use

| Trigger | Example |
|---|---|
| Need a skill for a task, none installed yet | "Is there a skill that formats invoices?" |
| Multiple candidates exist for the same task | Two search hits both claim to do PDF parsing |
| Choosing the safer of several similar skills | Deciding between two "git-commit-helper" skills |
| Sanity-checking a skill someone else recommended | A teammate links a skill slug |

Do not use for:

- Scanning a skill you have already chosen and are about to install — hand off to **vet-before-install**.
- Auditing skills already installed in your local environment — use **audit-my-agent-environment**.

## Command Contract

As of vettd 0.9.0:
- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

This distinction only applies to `scan`. `--json` works correctly on every
`directory` subcommand — `search`, `list`, `view`, `findings`, `signals`,
`compare`, and `random` all emit clean JSON with `--json`, with no ANSI
escapes and no scan-style caveat. All `directory` reads work anonymously;
no auth is required to search, view, compare, or read signals.

Available `directory` subcommands:

```bash
vettd directory search <QUERY>... --json [--page N] [--sort newest|rating|alpha] [-r/--reverse]
vettd directory list --json [--page N] [--sort newest|rating|alpha] [-r/--reverse]
vettd directory view <SLUG> --json
vettd directory findings <SLUG> --json [--min-severity critical|high|medium|low|info]
vettd directory signals <SLUG> --json    # vettd 0.10.0+
vettd directory compare <SLUG_A> <SLUG_B> --json
vettd directory random --json
```

There is no `--category`, `--grade`, or `--tag` filter flag. Filter by
grade and category client-side after fetching results.

`vettd directory signals <SLUG>` (vettd 0.10.0+) renders the published
signal record for a skill — seven categories (safety, reliability,
performance, cost, compatibility, Popularity, characteristics), each with
its verdict form and row count, then the signal rows; `--json` returns the
raw envelope. Cards from `search`/`list` may also carry a compact
`signalCategories` summary (omitted when the card has no signal data).

## Workflow

1. **Search broadly.** Use the task description as the query, not a guessed skill name:

   ```bash
   vettd directory search "invoice pdf parsing" --json
   ```

   Response shape:

   ```json
   {"skills":[{"slug":"...","name":"...","description":"...","version":"...",
   "author":"...","category":"...","badgeStatus":null,"overallGrade":"A",
   "sourceType":"scan","scannerRunCount":3}],"total":142,"page":1,"totalPages":8}
   ```

2. **Filter client-side.** Drop anything below your acceptable grade
   threshold (default: reject `F`, treat `C` with caution). Page through
   `--page N` if the first page has no strong match. Re-sort with
   `--sort rating` or `--sort newest` if relevance is unclear.

3. **Shortlist 2–4 candidates.** Do not stop at the first `A`-graded hit —
   grade alone does not tell you if the skill actually fits the task or is
   well-built.

4. **Pull details for each candidate:**

   ```bash
   vettd directory view <slug> --json
   ```

   This adds `license`, `sourceUrl`, `hasSkillMd`, `hasScripts`, `hasEvals`,
   `fileCount`, `completedAt`, `findings[]`, and `scannerRuns[]`.

5. **Pull findings for each candidate**, filtered to what matters:

   ```bash
   vettd directory findings <slug> --json --min-severity medium
   ```

   Each entry has `severity`, `label`, `category`, `detail`, `source`,
   `filepath`. Read `category` on every finding — a `security` finding at
   `medium` severity is a different decision than a `best-practices`
   finding at the same severity.

6. **Read the signal record for human context (optional).**

   ```bash
   vettd directory signals <slug>
   ```

   This shows the seven signal categories with their verdict form and row
   count. Signals are evidence/context, not findings — they never change
   `overallGrade`, so they are not a go/no-go axis. Weigh grade and
   `findings[]` first; use signals to understand a candidate's character
   (maturity, sizing, popularity) after the safety decision is made.

7. **Head-to-head on the top two:**

   ```bash
   vettd directory compare <slugA> <slugB> --json
   ```

8. Pick a winner using **Choosing Between Candidates** below.

9. ⛔ **MANDATORY HAND-OFF** — invoke **vet-before-install**.

   A well-graded directory entry describes what was scanned when the
   directory record was made. It is not a substitute for scanning the
   actual files you are about to download and run.

## Choosing Between Candidates

Compare in this order. Do not stop at the first differentiator if two
candidates tie.

| Priority | Signal | Rule |
|---|---|---|
| 0 | `overallGrade: "pending"`, `scannerRunCount: 0`, or any `scannerRuns[].verdict: null` | **Reject outright**, don't just deprioritize. An unscanned candidate has no usable result and is not a safer default than a scanned `B`. A `null` verdict means a scan ran but produced no usable result — treat it the same as unscanned. |
| 1 | `overallGrade` | Prefer `A` > `B` > `C`. Reject `F` unless the user explicitly overrides. |
| 2 | `findings[]` at same grade | Read `category` + `severity`, don't just count. A `security` finding at a given severity is a stronger safety concern than a `best-practices` finding at the same severity. |
| 3 | `scannerRunCount` / `scannerRuns[]` | More runs, and more scanners with matching `verdict`, means more scrutiny has already been applied. Prefer the more-scanned candidate when grades tie. |
| 4 | `sourceType` | `scan` (verified pipeline) outranks unverified or manually-entered sources, all else equal. |
| 5 | Quality tiebreakers only | `hasEvals`, `hasScripts`, description clarity, `fileCount` matching expected scope. Use these only to break ties — they do not change the grade and should never override a worse grade or worse findings. |

**Key trap:** `overallGrade` counts findings from **every** category
(`structure`, `security`, `best-practices`, `description`, `scripts`,
`evals`), only `info` excluded, evaluated F to A: `F` = any `critical` or
3+ `high`; `C` = any `high` or 3+ `medium`; `B` = any `medium` or 4+
`low`; `A` = otherwise, including zero findings. A single letter hides the
category mix — two `A`-graded skills can differ significantly in
real-world quality — so always read `findings[]` for both candidates
before picking, even when grades match. Signals are context for a human,
not a go/no-go: they never change the grade.

**Framework labels are not certifications.** If a candidate displays a
compliance/framework tag (OWASP, NIST 800-53, CMMC, ISO 42001, EU AI Act,
CISA), treat it as reference context the submitter or reviewer is using,
not an automated compliance guarantee — Vettd does not perform a formal
audit against any of these frameworks today. Never use a framework label
as a tiebreaker in place of an actual grade or finding comparison.

## Common Mistakes

| Mistake | Why it's wrong | Fix |
|---|---|---|
| Picking the first search hit | Search relevance ≠ safety or fit | Shortlist and compare at least 2–3 candidates |
| Trusting `overallGrade` alone | The letter hides which categories and severities produced it | Always pull `findings[]` before deciding |
| Treating signals as a go/no-go | Signals are evidence/context and never change the grade | Decide on grade + `findings[]`; use `directory signals` only for human context |
| Assuming this skill installs anything | This is discovery-only | Hand off to **vet-before-install** before use |
| Passing `--category`, `--grade`, or `--tag` to `search`/`list` | These flags don't exist | Filter the returned JSON client-side |
| Treating `directory` like `scan` for JSON output | `scan --json` is broken and ignored; `directory --json` is not | Use `--json` on `directory` freely; use `--stdout` only for `scan` |
| Getting `Connection refused` on any `directory` command | `directory` reuses the configured *ingest* endpoint. If that was pointed at a local test server (e.g. `http://localhost:3000`), every `directory` call fails — there is no `--endpoint` override | Invoke **setup-vettd** to reconfigure the endpoint back to the public directory, then retry |
| Comparing candidates only by name/popularity | Not a safety signal | Compare by grade, then findings, then scanner coverage |
| Treating an unscanned (`pending`/`scannerRunCount: 0`/null `verdict`) candidate as a neutral or safe default | No scan result recorded means not yet evaluated, not evaluated-and-clean | Reject outright per priority 0 above, or hand off to **vet-before-install** to scan it yourself |
| Treating a displayed framework tag (OWASP/NIST/CMMC/ISO 42001/EU AI Act/CISA) as a safety certification | These are reference context, not automated audits | Weigh grade and findings; ignore framework tags as a decision signal |
