# AGENTS.md — vettd-skills

Conventions for anyone (human or agent) adding or editing a skill here.

## Layout

Flat. One directory per skill: `skills/<skill-name>/SKILL.md`. Never nest by
category. Supporting files (`scripts/`, `references/`) live inside the skill
directory that uses them.

## No cross-skill file references

A skill directory must be copyable on its own. Never reference another
skill's files by relative path (`../other-skill/thing.md`). Refer to other
skills **by name only**, in bold: `invoke **triage-a-flagged-finding**`.

## Frontmatter

```yaml
---
name: <kebab-case, matches directory name>
description: "Use when <triggers>. WHEN: <phrases>. DO NOT USE FOR: <negatives> (use <other-skill>)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---
```

`description` must be under 500 characters, third person, and describe
**only when to use the skill** — never how it works. A description that
summarizes the workflow becomes a shortcut agents take instead of reading
the skill body.

`requires-vettd` must reflect the oldest version on which every command in
the skill actually works. Do not inflate it.

## Required sections

`# Title` → `## Overview` (≤2 sentences) → `## When to Use`
→ `## Command Contract` → `## Workflow` → `## Common Mistakes`.
Add `## Decision Policy` if the skill makes a go/no-go call.

Do not add a dedicated preflight/setup-check step to a skill's `## Workflow`.
If a skill's commands can fail because vettd itself isn't installed,
authenticated, or reachable, cover that as a row in `## Common Mistakes`
pointing at **setup-vettd**, not as a mandatory first step every skill
repeats verbatim.

## Grading methodology is not invented here

Grade thresholds (A/B/C/F) and finding severities (critical/high/medium/
low/info) referenced by any skill must match
https://vettd.agentichighway.ai/methodology exactly — do not restate them
from memory or from a prior skill edit. If the published methodology
changes, treat every skill referencing grades or severities as needing
review, not just the one being edited.

## Documented commands must be registered

Every CLI invocation a skill documents must have a line in
`ci/documented-commands.jsonl`. CI runs them against a real binary and fails
if the output shape changes. An unregistered command is an untested claim.

## Style

150-250 lines. Imperative mood. Tables over bullet lists for structured
data. No narrative ("in session X we found..."). Code blocks complete and
runnable.
