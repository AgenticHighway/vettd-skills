---
name: vet-before-install
description: "Use when about to install, adopt, or wire in a skill, MCP server, or agent config from an external source. WHEN: install this skill, add this MCP server, adopt this agent config, pull in this skill, before trusting a new integration. DO NOT USE FOR: artifacts already live (use audit-my-agent-environment), your own skill before publishing (use pre-publish-self-check), or findings you already have (use triage-a-flagged-finding)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---

# Vet a Skill, MCP Server, or Agent Before Installing It

## Overview

Stage a candidate skill, MCP server config, or agent config in an isolated
location and scan it before it is written into any live skills, config, or
agent directory. The artifact is never installed first and inspected later.

## When to Use

| Trigger | Example |
| --- | --- |
| Installing a skill from a repo or catalog | Cloning `SKILL.md` + assets from a GitHub repo |
| Adding an MCP server | Wiring a new `mcpServers` entry into an agent config |
| Adopting an agent config | Copying a colleague's or a downloaded agent definition |
| Vendoring a dependency that ships its own skill/agent files | Pulling in a package that bundles a `skills/` directory |

Do not use this skill for artifacts already installed and running — use
**audit-my-agent-environment** for that. Do not use it to check something you
authored yourself before sharing it — use **pre-publish-self-check** for
that.

## Command Contract

As of vettd 0.9.0:

- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

Additional contract notes for this skill:

- Always scan the **staging directory**, never the eventual install path.
- Use `scan folder <path> --deep --stdout` for skill/agent directory trees.
  `--deep` removes the directory depth limit and only exists on
  `scan folder`.
- Use `scan file <path> --stdout` when the candidate is a single config file
  (e.g. an MCP server entry in isolation).
- Redirect to a file with `--out <FILE>` when you need to re-read the same
  report across multiple steps instead of re-scanning.

## Workflow

1. **Do not touch the live install path yet.** Identify where the artifact
   would eventually live (a skills directory, an agent config file, an MCP
   servers block) but take no action against it.

2. **Stage the candidate in isolation.**

   ```bash
   staging_dir=$(mktemp -d /tmp/vettd-stage.XXXXXX)
   # Copy or clone the candidate artifact into $staging_dir, e.g.:
   git clone --depth 1 <source-repo-url> "$staging_dir/candidate"
   # or: cp -r <downloaded-path> "$staging_dir/candidate"
   ```

   The staging directory must be outside any directory an agent
   auto-loads skills, MCP servers, or configs from.

3. **Scan the staged copy.**

   ```bash
   vettd scan folder "$staging_dir/candidate" --deep --out "$staging_dir/report.json"
   ```

4. **Locate the relevant entry** in the report by artifact type:
   - Skill → `skills[]`, matched by `id` (`<abs-path>:<12-char-hash>`) or `name`
   - MCP server → `mcpServers[]`
   - Agent config → `agents[]`

5. **Read `overallGrade` and scan every finding's `severity`** for that
   entry's `externalScannerResults[].findings[]`. Apply the Decision Policy
   below.

6. **Only after the policy resolves to proceed**, copy the artifact from
   `$staging_dir` into its real install location.

7. **Clean up the staging directory unconditionally**, whether accepted or
   refused:

   ```bash
   rm -rf "$staging_dir"
   ```

## Decision Policy

`overallGrade` is computed from `structure` and `security` findings only,
using count-based thresholds evaluated F to A, first match wins:

| Grade | Threshold |
| --- | --- |
| F | 3+ highs, or any critical present |
| C | 3+ mediums, or 1-2 highs present |
| B | 4+ lows, or 1-2 mediums present |
| A | Fewer than 4 lows, no mediums/highs/criticals |

Because "any critical present" already forces `F`, a `B` or `A` grade
cannot structurally contain a critical finding. Checking severity directly
(row 1 below) is a fast-path, not a defense against a case that can
actually occur under normal grading.

A `pending` grade, a missing `overallGrade`, or a directory entry with
`scannerRunCount: 0` means the artifact has not actually been scanned. Per
Vettd's methodology, a scan with no findings is inconclusive, not a pass —
treat unscanned the same as untrusted: scan it yourself before proceeding.

Evaluate in this order. The first matching row wins.

| Condition | Action |
| --- | --- |
| Any finding with `severity: "critical"` | **REFUSE.** Do not install. Report the finding(s) verbatim to the human. |
| `overallGrade: "F"` | **REFUSE.** Do not install. Report why. |
| `overallGrade: "C"` | **STOP.** Ask the human, presenting the specific findings, before proceeding either way. |
| `overallGrade: "B"` | **Proceed with install**, but report the findings to the human afterward. |
| `overallGrade: "A"` | **Proceed with install.** |
| `overallGrade: "pending"`, missing, or no findings recorded at all | **Do not proceed.** Scan it yourself (this workflow) until a real grade is produced. |

If any finding needs deeper investigation before you can apply this table
(e.g. you don't understand why a rule fired):

⛔ **MANDATORY HAND-OFF** — invoke **triage-a-flagged-finding**.

## Common Mistakes

- Scanning the artifact *after* copying it into the live directory — this
  defeats the entire purpose of staging.
- Omitting `--deep` on nested skill directory trees, silently truncating
  what gets scanned.
- Branching on the scan command's exit code instead of reading
  `overallGrade` and `findings[].severity` from the JSON.
- Treating `description`/`best-practices`/`scripts`/`evals` category
  findings as if they change `overallGrade` — they don't; only `structure`
  and `security` findings drive the top-level grade, but a `critical`
  finding in *any* category still forces a REFUSE per the override rule.
- Skipping the direct severity check because the grade looked acceptable —
  it's a fast-path, and checking severity first catches a critical finding
  before you've even parsed `overallGrade`.
- Leaving the staging directory behind after the decision, especially after
  a REFUSE — always `rm -rf` it.
- Auto-approving a grade-C artifact because "the findings look minor" —
  grade C always requires a human decision, no exceptions.
- Treating a `pending` grade or an unscanned candidate as merely cautious
  rather than blocking — "no findings yet" is not the same as "clean."
