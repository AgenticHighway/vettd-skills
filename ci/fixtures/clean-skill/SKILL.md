---
name: clean-skill
description: "Use when running vettd-skills CI to verify a scan of a well-formed, low-risk skill still yields a clean result. This is a fixture, not a real skill."
license: MIT
---

# Clean Skill (CI Fixture)

## Overview

This is a deliberately unremarkable skill used only to give the drift-check
and command-verification CI something clean to scan. It performs no actions.

## When to Use

Never. This is a fixture for `vettd-skills` CI, not a skill for agents to
invoke.

## Workflow

1. Read a local file.
2. Summarize its contents.
3. Report the summary back to the user.
