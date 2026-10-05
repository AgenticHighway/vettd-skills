# vettd-skills

Agent-facing skills for [vettd](https://github.com/AgenticHighway/vettd-cli):
search and verify AI skills, MCP servers, and agent configs before you install
them, audit what is already running, and check your own work before publishing.

## Plugins

Two Claude Code plugins ship from this repo, in the `agentichighway` marketplace.
They do not overlap.

| Plugin | Skills | Needs |
|---|---|---|
| **vettd-directory** | `browse-directory-api` | HTTPS only. No binary, no API key. |
| **vettd** | the 7 CLI skills (`setup-vettd`, `vet-before-install`, `audit-my-agent-environment`, `pre-publish-self-check`, `find-a-safe-skill`, `triage-a-flagged-finding`, `detect-supply-chain-drift`) | The `vettd` binary on PATH. `setup-vettd` installs it. |

Install `vettd-directory` alone to search, inspect, and download. Install both
for the full workflow.

The `vettd` plugin does not bundle the binary. Install the CLI separately
(Homebrew or a signed GitHub release, as `setup-vettd` describes).

> **Status:** six of the seven CLI skills require `vettd` `>=0.10.0`, which is
> not yet released (the latest release is `0.9.3`). Until it ships, only
> `setup-vettd` works end to end. `browse-directory-api` works now.

## Install

Find your harness below. Each section covers install and update.

| Harness | Method | Skills |
|---|---|---|
| Claude Code | Plugin marketplace | `vettd-directory`, `vettd` |
| opencode | Copy into skills directory | all skills |
| Any other agent that reads `SKILL.md` | Copy into that agent's skills directory | all skills |

### Claude Code

Install (run in a terminal):

```bash
claude plugin marketplace add AgenticHighway/vettd-skills
claude plugin install vettd-directory@agentichighway   # browse, search, download; no CLI
claude plugin install vettd@agentichighway             # CLI skills; needs the vettd binary
```

Or inside a Claude Code session:

```
/plugin install vettd-directory --marketplace AgenticHighway/vettd-skills
```

Update:

```bash
claude plugin update vettd-directory@agentichighway
claude plugin update vettd@agentichighway
```

Updates arrive only when the plugin version in `.claude-plugin/marketplace.json`
is bumped. Auto-update is off by default for third-party marketplaces, so run
the update commands above to pick up new versions.

### opencode

opencode has no plugin system. Copy the skill directories in.

Install:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git
cp -r vettd-skills/skills/* ~/.config/opencode/skills/
```

Update:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git /tmp/vettd-skills-update
cp -r /tmp/vettd-skills-update/skills/. ~/.config/opencode/skills/
rm -rf /tmp/vettd-skills-update
```

opencode also reads `~/.agents/skills/` and `~/.claude/skills/`. Use either
path to share the same copy with other tools.

For a single project, copy into `<repo>/.opencode/skills/` instead. Commit that
directory only if the whole team should get these skills.

### Other harnesses

For any agent that loads `SKILL.md` directories, copy the skill directories
into that agent's skills directory. Each directory is usable on its own. The
cross-references between skills are by name only.

Install:

```bash
git clone https://github.com/AgenticHighway/vettd-skills.git
cp -r vettd-skills/skills/<skill-name> <your-agent-skills-dir>/
```

Update: re-clone to a temp directory and copy the same `skills/<skill-name>`
directories over the existing ones, as in the opencode update above.

Copying overwrites every installed skill from this repo. To update only some,
copy only those `skills/<name>` directories.

### Fast track (any agent)

Ask any agent to install from the repo:

> Please install skills from github.com/AgenticHighway/vettd-skills

## Known limitations

- **Directory downloads are not yet commit-pinned in production.**
  `browse-directory-api` tries the pinned download endpoint first and falls back
  to the unpinned source with a warning. Pinned downloads work once the vettd
  site's `dev` branch ships to production.

## Skills

| Skill | Use when |
|---|---|
| **browse-directory-api** | searching the public directory, checking a skill's grade, or downloading one, without the CLI |
| **setup-vettd** | vettd isn't installed, authenticated, or reachable |
| **vet-before-install** | about to install a skill, MCP server, or agent config |
| **audit-my-agent-environment** | checking what's currently installed and whether any of it is risky |
| **pre-publish-self-check** | about to publish or push a skill you authored |
| **find-a-safe-skill** | looking for an existing skill to do a task |
| **triage-a-flagged-finding** | handed a finding and deciding what to do about it |
| **detect-supply-chain-drift** | checking whether a previously-clean artifact has changed |

Run `vet-before-install` on any downloaded skill before you install it.

## Grading methodology

Grade thresholds and finding-severity definitions used throughout these
skills are not restated here. They follow Vettd's published methodology:
https://vettd.agentichighway.ai/methodology. If that page changes, these
skills need a matching update.

## CI

`.github/workflows/drift-check.yml` installs the latest released `vettd`
binary and runs every command documented across these skills
(`ci/documented-commands.jsonl`), failing if a documented output shape no
longer holds. `.github/workflows/plugin-validate.yml` runs
`claude plugin validate --strict .`.

## License

MIT
