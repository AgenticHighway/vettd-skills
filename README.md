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

**Claude Code** — copy the skill directories you want into `~/.claude/skills/`:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git
cp -r vettd-skills/skills/* ~/.claude/skills/
```

**opencode** — copy into `~/.config/opencode/skills/`:

```bash
cp -r vettd-skills/skills/* ~/.config/opencode/skills/
```

Each skill directory is self-contained. Copy one, some, or all.

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

## Grading methodology

Grade thresholds and finding-severity definitions used throughout these
skills are not invented here — they follow Vettd's published methodology:
https://vettd.agentichighway.ai/methodology. If that page changes, these
skills need a matching update.

## CI

`.github/workflows/drift-check.yml` installs the latest released `vettd`
binary and runs every command documented across these skills
(`ci/documented-commands.jsonl`), failing if a documented output shape no
longer holds. This is how the skills stay honest as the CLI changes.

## License

MIT
