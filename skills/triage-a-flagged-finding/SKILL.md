---
name: triage-a-flagged-finding
description: "Use when handed one or more specific scan findings and needing to decide whether to remediate, remove, or accept-with-justification. WHEN: triage this finding, what do I do about this flagged rule, decide on this security finding, handed a finding from vettd, resolve this flagged rule ID. DO NOT USE FOR: running the initial scan that produces findings (use vet-before-install or audit-my-agent-environment), or searching for a new skill to install (use find-a-safe-skill)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---

# Triage a Flagged Finding

## Overview

Given one or more findings from a vettd scan report, locate the underlying
evidence and decide whether to remediate, remove, or accept the finding with
a documented justification.

## Preflight

Run `vettd auth status --json`. If the binary is missing, `configured` is
false, or `reachable` is false:

⛔ **STOP** — invoke **setup-vettd**, then return here.

## When to Use

Use this skill whenever you are handed a specific finding (or a short list
of findings) and need to decide what to do about it — typically as a
hand-off from another skill's Decision Policy, such as:

- **vet-before-install** stopping on `overallGrade: "C"`
- **audit-my-agent-environment** surfacing findings on already-live artifacts
- **detect-supply-chain-drift** flagging a changed dependency or source

Do not use this skill to run a scan from scratch — it consumes findings,
it doesn't produce them. Do not use it to search a catalog for a
replacement artifact — use **find-a-safe-skill** for that.

## Command Contract

As of vettd 0.9.0:

- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

## Workflow

1. **Re-establish the full report** if you were only handed a `ruleId` or a
   summary, not the raw JSON:

   ```bash
   vettd scan folder <path-to-artifact> --deep --out /tmp/vettd-triage-report.json
   ```

2. **Locate the artifact's entry** in the appropriate array
   (`skills[]`, `mcpServers[]`, `agents[]`, `agenticApps[]`) by matching
   `id` (`<abs-path>:<12-char-hash>`) or `name`.

3. **Locate the specific finding** inside that entry's
   `externalScannerResults[].findings[]` by `ruleId`. Read every field:
   `category`, `severity`, `label`, and — most importantly — `detail`.
   `detail` is the evidence; do not guess at remediation from `label` alone.

   Example finding:

   ```json
   {
     "ruleId": "VTD-0088",
     "category": "security",
     "severity": "medium",
     "label": "References external URL — review for indirect prompt injection risk",
     "detail": "External URL(s) detected in SKILL.md — referenced content can change after audit"
   }
   ```

4. **Classify by `category` and `severity`** using the Decision Policy
   below to choose one of: **remediate**, **remove**, or
   **accept-with-justification**.

5. **Remediate:**
   - Edit the source artifact directly to address the `detail`.
   - Re-scan the corrected copy and confirm the same `ruleId` no longer
     appears for that entry.
   - If the artifact was mid-install via **vet-before-install**, return to
     that skill's staging step with the corrected copy rather than
     installing the unfixed version.

6. **Remove:**
   - Delete or uninstall the artifact (skill directory, MCP server entry,
     agent config block).
   - Re-scan the parent directory/config and confirm the entry is gone
     entirely, not just the one finding.

7. **Accept-with-justification:**
   - Only valid for non-critical findings, and only after documenting the
     specific reason the risk is acceptable (e.g. "external URL is our own
     pinned CDN asset, content is immutable by hash").
   - Never use this path silently — the justification must be recorded
     wherever the calling skill or human tracks accepted risk, not just
     held in memory.

## Decision Policy

Evaluate `severity` first, then `category`.

| Severity | Category | Action |
| --- | --- | --- |
| `critical` | any | **Remediate or remove immediately.** Never accept-with-justification. |
| `high` | `security` | **Remediate.** If not fixable in the source, **remove.** |
| `medium` / `low` | `security` | **Remediate** if the fix is straightforward; otherwise **accept-with-justification** with explicit human sign-off. |
| any | `structure` | **Remediate** — structure findings are typically a quick, mechanical fix (missing metadata, malformed manifest). |
| any | `description` / `best-practices` / `scripts` / `evals` | Lower priority. **Accept-with-justification** is normally acceptable after a brief human review, since these categories affect internal score and `trustLevel` but do not drive `overallGrade` directly. |

If remediation was performed as part of an install decision that originally
stopped in **vet-before-install**:

⛔ **MANDATORY HAND-OFF** — invoke **vet-before-install** to re-stage and
re-scan the corrected artifact before it is installed.

## Common Mistakes

- Accepting a `critical` finding because the artifact's overall grade
  looked acceptable — grade and severity are independent; critical always
  wins.
- Deciding a remediation from the `label` field alone without reading
  `detail`, and then fixing the wrong thing.
- Fixing the source but never re-scanning, so the same `ruleId` resurfaces
  on the next audit.
- Confusing `trustLevel` with `overallGrade` — they are related but not the
  same field, and a triage decision should be based on the specific
  finding's `severity`/`category`, not a single summary label.
- Using accept-with-justification as a silent default for anything that's
  inconvenient to fix, rather than reserving it for genuinely low-risk,
  non-critical findings with a recorded reason.
- Removing the artifact but not re-scanning the parent directory/config to
  confirm the entry is actually gone (stale references, duplicate copies).
