---
name: audit-my-agent-environment
description: "Use when an agent needs to inventory and audit its own runtime environment for dangerous or untrusted artifacts. WHEN: audit my environment, what's installed, check my MCP servers, is my setup safe, self-audit. DO NOT USE FOR: vetting one skill before installing (use vet-before-install), publishing checks (use pre-publish-self-check), one finding (use triage-a-flagged-finding), or drift over time (use detect-supply-chain-drift)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---

# Audit My Agent Environment

## Overview

This skill turns an agent's own runtime — skills directories, MCP configs, AGENTS.md/CLAUDE.md files, and rule files — into a scanned inventory with flagged findings, using `vettd scan default` as the primary tool. It answers "what am I actually running right now, and is any of it dangerous?" for the agent's own environment, not a third-party artifact under consideration.

## Preflight

Run `vettd auth status --json`. If the binary is missing, `configured` is
false, or `reachable` is false:

⛔ **STOP** — invoke **setup-vettd**, then return here.

## When to Use

| Situation | Use this skill? |
|---|---|
| "What's actually running in my environment right now?" | Yes |
| Periodic self-check of skills/MCP/rules hygiene | Yes |
| Someone asks you to audit your own setup for danger | Yes |
| Deciding whether to install a specific new skill | No — use **vet-before-install** |
| Checking a skill you authored before publishing it | No — use **pre-publish-self-check** |
| Investigating one finding already surfaced by a prior scan | No — use **triage-a-flagged-finding** |
| Comparing this environment's scan to a prior baseline over time | No — use **detect-supply-chain-drift** |

## Command Contract

As of vettd 0.9.0:
- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

Additional command facts specific to self-audit:

| Command | Purpose | Notes |
|---|---|---|
| `vettd scan default --stdout` | Broad sweep: critical host roots + bounded user-space/project roots | Depth hard-capped at 5; watch stderr for `scan depth capped at 5` |
| `vettd scan quick --stdout` | OS-aware agent-config areas only (fast) | Also depth-capped; use for a quick recheck, not full coverage |
| `vettd scan folder <path> --stdout --deep` | Full-depth scan of one directory | Only place `--deep` exists; required to close gaps `scan default`/`quick` leave |
| `vettd scan file <path> --stdout` | Scan a single file (e.g. one MCP config) | Use for known MCP config paths — see Known Gap below |
| `vettd scan full` | Whole filesystem | **Never use in automation** — exceeds 60s and times out |

**Known gap:** `scan default --stdout` returns an empty `mcpServers` array
even when the human-readable output lists MCP configs it found. Do not
trust the JSON `mcpServers` field alone for MCP inventory — explicitly
`scan folder`/`scan file` each MCP config path (see Workflow step 3).

## Workflow

1. **Preflight.** Confirm `vettd auth status --json` passes (see above).

2. **Broad sweep.** Run:
   ```
   vettd scan default --stdout
   ```
   Capture stdout as the primary JSON payload (`scanMeta`, `prompts`,
   `skills`, `mcpServers`, `agents`, `agenticApps`). Capture stderr
   separately — if it contains `scan depth capped at 5`, note which
   `scanRoots` were likely truncated; you will need step 4 for those.

3. **Explicitly cover MCP configs (mandatory, do not skip).** Because
   `mcpServers` in the JSON payload is unreliable (see Known Gap), scan
   known MCP config locations directly, e.g.:
   ```
   vettd scan file ~/.config/Code/User/mcp.json --stdout
   vettd scan folder ~/.config/opencode --stdout --deep
   ```
   Adjust paths to whatever MCP configs actually exist on this host —
   check IDE/editor config directories, not just the ones listed here.

4. **Fill depth-cap gaps.** For any root flagged as truncated in step 2
   (or any location you know holds many nested agent artifacts, such as a
   large skills library), rescan it fully:
   ```
   vettd scan folder ~/.claude/skills --stdout --deep
   vettd scan folder ~/.cursor --stdout --deep
   ```
   Also explicitly scan flat-file artifacts that live outside a
   directory-scan sweep root if unsure they were covered: `.cursorrules`,
   `AGENTS.md`, `CLAUDE.md`.

5. **Build the inventory.** Merge all JSON payloads into one list per
   top-level key:
   - `skills[]` — `id` (`<abs-path>:<12-char-hash>`), `name`, `type`,
     `trustLevel`, `overallGrade`, `executionEnvironment`
   - `mcpServers[]`, `agents[]`, `agenticApps[]`, `prompts[]` — same
     pattern, from whichever scan actually populated them
   - `scanMeta` — record `scanRoots`, `scannedAt`, and `hostNetwork`
     (firewall state) per scan run, since multiple scans in this
     workflow each carry their own `scanMeta`

6. **Flag anything risky.** Anything with `overallGrade` of `C` or `F`, or
   any `externalScannerResults[].findings[]` entry with `severity` of
   `critical` or `high`, is flagged. Do not re-derive or soften severity —
   report it as-is.

   Grade thresholds, per Vettd's methodology
   (https://vettd.agentichighway.ai/methodology): `F` = 3+ highs or any
   critical; `C` = 3+ mediums or 1-2 highs; `B` = 4+ lows or 1-2 mediums;
   `A` = fewer than 4 lows, nothing higher. A single `critical` finding
   forces `F`; a single `high` finding already forces at least `C` — an
   `A`/`B` grade cannot structurally contain a `high` or `critical`
   finding, so if you see `overallGrade: "high"`-severity findings on
   something graded `A`/`B`, treat it as a scan/grade inconsistency
   worth flagging, not a normal case.

7. **Hand off flagged items.**

   ⛔ **MANDATORY HAND-OFF** — invoke **triage-a-flagged-finding**.

   Do this for every flagged skill, MCP server, agent, or agentic app
   found in steps 2–4, before concluding the audit.

8. **Report the inventory.** Present a full inventory (not just flagged
   items) so the user can see what is currently installed, even where
   nothing was flagged.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Trusting `mcpServers: []` from `scan default --stdout` as "no MCP servers found" | Explicitly scan known MCP config paths with `scan file`/`scan folder --deep` |
| Running `vettd scan full` for a "complete" audit | Never automate `scan full` — it exceeds 60s and times out. Use `scan default` + targeted `scan folder --deep` instead |
| Ignoring the depth-cap warning on stderr | Treat it as a signal to rerun the affected root with `scan folder <path> --stdout --deep` |
| Branching on the scan process exit code to detect problems | Exit code is always 0 regardless of findings — read the JSON, not the exit status |
| Parsing the human-readable scan output for automation | Human output carries ANSI escapes even off a TTY — always use `--stdout` and parse JSON |
| Treating `overallGrade: C` as merely a quality nitpick | Grade derives only from `structure`/`security` findings — a `C` or `F` is a trust signal, not a style comment |
| Concluding the audit without invoking triage on flagged items | Hand-off to **triage-a-flagged-finding** is mandatory for every flagged artifact, not optional follow-up |
| Skipping flat-file artifacts (`.cursorrules`, `AGENTS.md`, `CLAUDE.md`) because they aren't under a scanned directory root | Explicitly include them in step 4 if unsure a sweep covered them |
| Treating a location your scans never actually covered as "nothing found there" | Absence of findings from a gap in coverage is not the same as a clean result — per Vettd's methodology, no findings is inconclusive, not a pass; confirm every intended root was actually scanned (watch stderr depth-cap warnings) before reporting it clean |
