# vettd-skills

Agent-facing skills for [vettd](https://github.com/AgenticHighway/vettd-cli) —
detect, analyze, and report AI execution artifacts.

These skills let an agent vet a skill, MCP server, or agent config **before**
installing it; audit what it is already running; and check its own work
before publishing.

## Requirements

The `vettd` binary must be on PATH. Every skill declares its minimum version
in `metadata.requires-vettd`. Start with **setup-vettd** — every other skill
hands off to it when the environment isn't ready.

## Install

**Fast Track (any agent)** — simply ask any agent to install vettd-skills:

> Please install skills from github.com/AgenticHighway/vettd-skills

**Claude Code** — copy the skill directories you want into `~/.claude/skills/`:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git
cp -r vettd-skills/skills/* ~/.claude/skills/
```

**opencode** — copy into `~/.config/opencode/skills/`:

```bash
cp -r vettd-skills/skills/* ~/.config/opencode/skills/
```

Skill directories contain cross-references, but each is still usable as a standalone 
skill. Copy one, some, or all.

## Updating

The current path is to re-clone to a temp directory and copy the updated files over
your existing install:

**Claude Code**:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git /tmp/vettd-skills-update
cp -r /tmp/vettd-skills-update/skills/. ~/.claude/skills/
rm -rf /tmp/vettd-skills-update
```

**opencode**:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git /tmp/vettd-skills-update
cp -r /tmp/vettd-skills-update/skills/. ~/.config/opencode/skills/
rm -rf /tmp/vettd-skills-update
```

This overwrites every skill you've installed from this repo with the
current version. If you only installed some, copy the specific
`skills/<name>` directories instead of the whole tree.

## Skills

| Skill | Use when |
|---|---|
| **setup-vettd** | vettd isn't installed, authenticated, or reachable |
| **vet-before-install** | about to install a skill, MCP server, or agent config |
| **audit-my-agent-environment** | checking what's currently installed and whether any of it is risky |
| **pre-publish-self-check** | about to publish or push a skill you authored |
| **find-a-safe-skill** | looking for an existing skill to do a task |
| **triage-a-flagged-finding** | handed a finding and deciding what to do about it |
| **detect-supply-chain-drift** | checking whether a previously-clean artifact has changed |

Skills that read scan or directory data also cover vettd's non-finding
signals — evidence/context that never becomes findings and never changes
the grade (see the Grading methodology section).

## Grading methodology

`overallGrade` is computed from every finding across all six categories
(`structure`, `security`, `best-practices`, `description`, `scripts`,
`evals`), with only `info` severity excluded, evaluated F → A: `F` = any
`critical` or 3+ `high`; `C` = any `high` or 3+ `medium`; `B` = any
`medium` or 4+ `low`; `A` = otherwise, including zero findings.
`trustLevel` derives from the grade: `A` → Trusted, `B` → Conditional,
`C`/`F` → Untrusted.

Signals are a separate store: seven categories (safety, reliability,
performance, cost, compatibility, Popularity, characteristics) with three
verdict forms (`graded`, `measured`, `unjudged`). They are evidence/context,
not findings, and never affect `overallGrade`. See `vettd directory
signals <slug>` (vettd 0.10.0+) for a skill's published signal record.

## CI

`.github/workflows/drift-check.yml` installs the latest released `vettd`
binary and runs every command documented across these skills
(`ci/documented-commands.jsonl`), failing if a documented output shape no
longer holds. This is how the skills stay honest as the CLI changes.

## License

MIT
