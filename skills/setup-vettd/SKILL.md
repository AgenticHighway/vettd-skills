---
name: setup-vettd
description: "Use when the vettd binary is missing, unauthenticated, or unreachable, or when a command from another vettd skill fails because vettd itself isn't set up. WHEN: vettd not found, command not found vettd, install vettd, configure vettd, vettd auth, connection refused from vettd, vettd endpoint wrong. DO NOT USE FOR: scanning anything (use vet-before-install or audit-my-agent-environment)."
license: MIT
metadata:
  author: Agentic Highway
  version: "0.1.0"
  requires-vettd: ">=0.9.0"
---

# Set Up vettd

## Overview

Bring the local `vettd` installation to a working state: binary present,
credentials configured, and endpoint reachable. This is the only skill that
modifies vettd configuration. Credential entry (Step 5) is always run by the
user in their own terminal — never by the agent.

## When to Use

| Symptom | Cause |
|---|---|
| `command not found: vettd` | Binary not installed |
| A command from another skill failed with a setup-related error | One of the three states below is bad |
| `Connection refused` from `directory` commands | Endpoint misconfigured — see Step 4 |
| `not authenticated` on submit or inventory | No API key configured |

## Command Contract

As of vettd 0.9.0:
- Use `--stdout` for JSON from `scan`. The `--json` flag is accepted but
  ignored on scan subcommands and emits human-readable text.
- Do not branch on exit code. Scans exit 0 regardless of severity.
- Never parse human-readable output. ANSI escapes are emitted even when
  stdout is not a TTY.

`--json` works correctly on `auth`, `directory`, and `contract`. The caveat
above applies only to `scan`.

There is **no** `VETTD_API_KEY` environment variable. Credentials come from
`~/.config/vettd/config.json` or the `--api-key` flag. Prefer the config
file: `--api-key` is visible in process listings and CI logs.

`vettd auth status` (with or without `--json`) exits non-zero (observed: 5)
whenever the endpoint is unreachable, even though `configured` and
`api_key_set` can both be `true`. Do not treat that exit code as "not
configured" — read the JSON fields instead.

## Workflow

### Step 1 — Is the binary present?

```bash
vettd --version
```

If this fails, install (Step 2). Otherwise go to Step 3.

### Step 2 — Install

| Platform | Method |
|---|---|
| macOS | Homebrew (recommended) or release binary |
| Linux | Release binary |
| Windows | Release binary |

**macOS — Homebrew:**

```bash
brew tap AgenticHighway/tap
brew install vettd
```

**macOS — release binary** (swap `arm64`/`amd64` for your chip; macOS has no
`sha256sum` by default, so use `shasum`):

```bash
curl -fsSLO https://github.com/AgenticHighway/vettd-cli/releases/latest/download/vettd-darwin-arm64.tar.gz
curl -fsSLO https://github.com/AgenticHighway/vettd-cli/releases/latest/download/checksums.txt
shasum -a 256 --check --ignore-missing checksums.txt
tar xzf vettd-darwin-arm64.tar.gz
install -m 0755 vettd ~/.local/bin/vettd
```

**Linux — release binary** (swap `arm64`/`amd64` for your architecture):

```bash
curl -fsSLO https://github.com/AgenticHighway/vettd-cli/releases/latest/download/vettd-linux-amd64.tar.gz
curl -fsSLO https://github.com/AgenticHighway/vettd-cli/releases/latest/download/checksums.txt
sha256sum --check --ignore-missing checksums.txt
tar xzf vettd-linux-amd64.tar.gz
install -m 0755 vettd ~/.local/bin/vettd
```

**Windows — release binary:**

```powershell
Invoke-WebRequest -Uri https://github.com/AgenticHighway/vettd-cli/releases/latest/download/vettd-windows-amd64.exe -OutFile vettd.exe
Invoke-WebRequest -Uri https://github.com/AgenticHighway/vettd-cli/releases/latest/download/checksums.txt -OutFile checksums.txt
# Confirm the sha256 for vettd-windows-amd64.exe in checksums.txt matches:
Get-FileHash vettd.exe -Algorithm SHA256
Move-Item vettd.exe "$env:LOCALAPPDATA\Microsoft\WindowsApps\vettd.exe"   # or any directory already on PATH
```

Valid platform/arch pairs: `darwin-arm64`, `darwin-amd64`, `linux-arm64`,
`linux-amd64`, `windows-amd64`.

Verify: `vettd --version`.

### Step 3 — Read current state

```bash
vettd auth status --json
```

```json
{"configured":true,"endpoint":"https://vettd.agentichighway.ai/api/scans/ingest",
 "api_key_set":true,"scanner_uuid":"...","account_uuid":null,
 "reachable":true,"account":null}
```

| Field | Healthy value |
|---|---|
| `configured` | `true` |
| `api_key_set` | `true` (only needed for submission and inventory) |
| `reachable` | `true` |
| `endpoint` | a public vettd endpoint, **not** localhost — see Step 4 |

Scanning works fully offline. Only submission, `directory`, and `inventory`
need a reachable endpoint.

### Step 4 — Check the endpoint is not local

The most common broken state. `directory` derives its base URL from the
configured *ingest* endpoint. If `endpoint` points at `localhost` or a
private address, **every `directory` command fails with `Connection
refused`** — there is no `--endpoint` override on `directory` itself.

If `endpoint` contains `localhost`, `127.0.0.1`, or a private range, and the
user is not deliberately testing against a local server, repoint it:

```bash
vettd auth --endpoint https://vettd.agentichighway.ai/api/scans/ingest \
           --allow-public-endpoint
```

`--allow-public-endpoint` is required for any non-local endpoint and lives
on `vettd auth`, not on `vettd auth status`. Public endpoints must be HTTPS.

### Step 5 — Have the user configure credentials (only if needed)

Skip if the user only intends to scan locally.

**Do not run this command yourself.** It prompts interactively for the API
key, and an agent has no way to satisfy that prompt without the key passing
through its own process, logs, or context — the same risk this skill already
avoids by rejecting `--api-key` on the command line.

Ask the user to run the following in their own terminal, then wait for them
to confirm it's done:

```bash
vettd auth --allow-public-endpoint
```

API keys start with `ah_`. Never accept a key typed into chat, never type or
paste one into a command yourself, and never echo a key into a shell
command, a log, or a commit.

### Step 6 — Confirm

```bash
vettd auth status --json
```

Report the resulting state, then return to the skill that handed off.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Assuming the Homebrew tap is broken | Fixed as of the `0.9.0` formula update — `brew tap AgenticHighway/tap && brew install vettd` now carries real checksums and tracks the current release. |
| Treating `reachable: false` as fatal | Scanning is local-first and works offline. Only submission, `directory`, and `inventory` need the network. |
| Passing `--api-key` on the command line | Visible in process listings and CI logs. Use the config file. |
| Setting a public endpoint without `--allow-public-endpoint` | The command is rejected by design. |
| Leaving a `localhost` endpoint configured after local testing | Silently breaks every `directory` command. |
| Passing `--allow-public-endpoint` to `auth status` | That flag exists on `auth`, not `auth status`; `auth status` rejects it as an unexpected argument. |
| Echoing the API key to confirm it was set | Use `vettd auth status --json` and check `api_key_set`. |
| Running `vettd auth --allow-public-endpoint` yourself instead of asking the user | The key must never pass through the agent's process or context; hand off to the user's own terminal and wait for confirmation. |
