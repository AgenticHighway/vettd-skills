---
name: detect-supply-chain-drift
description: "Use when a previously-scanned artifact needs to be checked for changes since its last scan — before re-trusting an update, after a dependency bump, or on a schedule. WHEN: has this changed, did this skill change, re-scan after update, verify no drift, monitor for tampering. DO NOT USE FOR: scanning an artifact the first time (use vet-before-install) or triaging one finding (use triage-a-flagged-finding)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---

# Detect Supply Chain Drift

## Overview

Detects when a previously-clean artifact has changed since its last scan by diffing two `vettd` JSON reports. Surfaces new findings, resolved findings, and grade transitions that a single scan cannot show on its own. Grade semantics below follow Vettd's published methodology: https://vettd.agentichighway.ai/methodology

## Preflight

Run `vettd auth status --json`. If the binary is missing, `configured` is
false, or `reachable` is false:

⛔ **STOP** — invoke **setup-vettd**, then return here.

## When to Use

| Situation | Use this skill? |
|---|---|
| First-time scan of a new artifact | No — use **vet-before-install** |
| Recurring check that a trusted artifact is unmodified | Yes |
| Verifying an update after a dependency/version bump | Yes |
| A monitoring job needs a pass/fail signal on change | Yes |
| Investigating one specific finding already reported | No — use **triage-a-flagged-finding** |

`vettd` has no built-in baseline or diff feature. `scan_cache.rs` is a
performance stat-cache only — it does not track change history. All drift
detection in this skill is performed by the bundled script, not by `vettd`
itself.

## Command Contract

As of vettd 0.9.0:
- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

For this skill specifically, prefer `--out <FILE>` over `--stdout` for
both scans — you need two persisted JSON files to diff, not a single
stream to read once.

## Establishing a Baseline

Capture a baseline report for the artifact's root path and store it
somewhere durable (git, an artifact store, a monitoring bucket) — not a
temp directory that gets cleaned up before the next check.

```bash
vettd scan folder /path/to/artifact --deep --out baseline.json
```

| Flag | Why it matters here |
|---|---|
| `--deep` | Only valid on `scan folder`. Use it so baseline and future scans see the same file tree depth. |
| `--out` | Persists JSON to disk for later diffing. Do not use `--stdout` and redirect — `--out` is the supported contract. |

If checking host-wide drift instead of one artifact, use
`vettd scan default --out baseline.json` — note this caps depth at 5 and
is not equivalent to `scan folder --deep`. Do not mix the two scan modes
between baseline and re-scan; depth mismatches produce false-positive
"changes" that are really just newly-visible files.

## Detecting Drift

Re-scan the same path with the same flags used for the baseline:

```bash
vettd scan folder /path/to/artifact --deep --out current.json
```

Then diff:

```bash
python3 skills/detect-supply-chain-drift/scripts/diff-reports.py \
  baseline.json current.json
```

The script splits each artifact `id` (`<absolute-path>:<12-char-content-hash>`)
on the **last** `:` to separate path from hash — this is what actually
detects drift, not scan metadata or timestamps. Same path with a different
hash means the artifact's content changed since the baseline. Confirmed
against a real scan: mutating a skill's content in place (same path)
produces exactly one CHANGED entry with the old and new grade, the new
findings, and the findings that disappeared.

| Optional flag | Effect |
|---|---|
| `--json` | Machine-readable output for CI/automation |
| `--severity-threshold <level>` | Only report NEW findings at or above this severity (`critical`, `high`, `medium`, `low`, `info`) |

## Interpreting the Diff

| Classification | Meaning |
|---|---|
| ADDED | Path exists in current scan only — a new artifact appeared |
| REMOVED | Path existed in baseline only — an artifact disappeared |
| CHANGED | Same path, different content hash — the artifact was modified |
| UNCHANGED | Same path, same hash — no drift |

For CHANGED artifacts the script further reports:

- **NEW findings** — `ruleId`s present now that were absent in the baseline
- **RESOLVED findings** — `ruleId`s present in the baseline that are gone now
- **Grade transition** — e.g. `A → F`, when `overallGrade` differs between scans

Grade thresholds (https://vettd.agentichighway.ai/methodology) are hard
count cutoffs: `F` = 3+ highs or any critical; `C` = 3+ mediums or 1-2
highs; `B` = 4+ lows or 1-2 mediums; `A` = fewer than 4 lows, nothing
higher. A grade transition can happen from a single additional finding at
a threshold boundary (a second medium becoming a third pushes `B` → `C`)
just as easily as from a large change — treat every grade transition as
significant regardless of how small the underlying finding count change
looks.

Any NEW `critical` finding is the highest-priority signal this skill can
surface: critical means either adversarial intent was detected, or the
new pattern requires no exploitability preconditions at all. A previously
`A`/`B`-graded artifact that gains a single critical finding after an
update has, by definition, just dropped to `F`.

⛔ **MANDATORY HAND-OFF** — invoke **triage-a-flagged-finding** for any NEW
finding the diff surfaces. This skill detects and reports drift; it does
not adjudicate whether a new finding is acceptable.

The script's own exit code (0 = no drift, 1 = drift detected) is a
contract the script defines for itself, for scripting/CI convenience —
it is unrelated to `vettd`'s own exit code, which is always 0 regardless
of severity (see Command Contract above). Do not conflate the two.

## Common Mistakes

| Mistake | Consequence |
|---|---|
| Scanning a different root path for baseline vs. current | Artifact `id` paths won't match; everything reports as ADDED/REMOVED instead of CHANGED |
| Mixing `scan folder --deep` and `scan default` between the two scans | Depth mismatch produces spurious ADDED/REMOVED entries |
| Parsing `vettd`'s exit code as a drift signal | `vettd scan` always exits 0; only `diff-reports.py`'s exit code reflects drift |
| Using `--json` on the `scan` subcommand | Ignored on scan subcommands; you'll get human-readable text where JSON was expected |
| Discarding the baseline file after one comparison | The next check has nothing to diff against — persist baseline.json |
| Treating REMOVED as automatically safe | An artifact disappearing can itself be the drift signal worth investigating (e.g. silently swapped for a different path) |
| Ignoring severity-threshold interaction with exit code | `--severity-threshold` filters which NEW findings are *printed*; it does not change whether ADDED/REMOVED/CHANGED artifacts count as drift for the exit code |
