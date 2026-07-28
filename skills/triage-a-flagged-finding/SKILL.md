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
a documented justification. Severity and grade definitions below follow
Vettd's published methodology: https://vettd.agentichighway.ai/methodology

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

### Severity Semantics

Severity is not an arbitrary ranking. Each level has a specific meaning:

| Severity | Meaning |
| --- | --- |
| `critical` | Adversarial intent, or no exploitability preconditions required — fires unconditionally wherever the pattern appears. A finding tagged with malicious intent is always elevated to critical regardless of its base assignment. |
| `high` | Serious harm, conditional on one additional factor: caller-controlled input reaching the operation, a specific execution environment, or a permissive configuration. Reflects negligent intent, not malicious intent. |
| `medium` | A known weakness class with conditional exploitability, limited impact in isolation, or meaningful false-positive risk. Warrants review; not confirmed exploitable. |
| `low` | Heuristic match only. High false-positive rate, no confirmed data flow to a vulnerability. |
| `info` | Observation only. No direct harm path. Never counts toward `overallGrade`. |

This distinction changes how you triage: a `high` finding usually means the
author wrote something careless, not something hostile — the fix is a code
change, not an incident. A `critical` finding means the pattern is
adversarial by design, or it needs zero conditions to fire. Treat it as a
stop-the-line event, not a backlog item.

### Action Table

Evaluate `severity` first, then `category`.

| Severity | Category | Action |
| --- | --- | --- |
| `critical` | any | **Remediate or remove immediately.** Never accept-with-justification. This finding alone already forces `overallGrade` to `F` by policy. |
| `high` | `security` | **Remediate.** If not fixable in the source, **remove.** Three or more highs also forces `F`; even one high forces at least `C`. |
| `medium` / `low` | `security` | **Remediate** if the fix is straightforward; otherwise **accept-with-justification** with explicit human sign-off. Three or more mediums forces `C`; four or more lows forces at least `B`. |
| any | `structure` | **Remediate** — structure findings are typically a quick, mechanical fix (missing metadata, malformed manifest). |
| any | `description` / `best-practices` / `scripts` / `evals` | Lower priority. **Accept-with-justification** is normally acceptable after a brief human review, since these categories affect internal score and `trustLevel` but never drive `overallGrade`. |

If remediation was performed as part of an install decision that originally
stopped in **vet-before-install**:

⛔ **MANDATORY HAND-OFF** — invoke **vet-before-install** to re-stage and
re-scan the corrected artifact before it is installed.

## Common Mistakes

- Waiting to check `overallGrade` before reacting to a `critical` finding —
  a single critical finding always forces the grade to `F` by policy, so a
  `B` or `A` grade cannot structurally coexist with one. Act on severity
  directly; don't wait to cross-check the grade.
- Treating a scan that returned no findings, or an artifact with
  `overallGrade: "pending"`, as equivalent to a clean result. Per Vettd's
  methodology, the absence of findings is inconclusive, not a pass — an
  unscanned or not-yet-analyzed artifact still needs a real scan before
  any triage decision.
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
