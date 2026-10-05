#!/usr/bin/env python3
"""Fail if .claude-plugin/marketplace.json and skills/ disagree.

WHY this exists: plugins list their skills explicitly, so a new skills/<name>/
directory that nobody adds to the marketplace silently never ships to plugin
users, and a listed path that was renamed breaks the install. `claude plugin
validate` checks the manifest's shape; this checks it against the repo.

Usage: python3 ci/verify-marketplace.py

Exit codes: 0 consistent, 1 mismatch.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def main() -> None:
    marketplace = json.loads(MARKETPLACE.read_text())
    on_disk = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}

    listed = Counter()
    errors = []
    for plugin in marketplace["plugins"]:
        for path in plugin.get("skills", []):
            name = Path(path).name
            listed[name] += 1
            if not (ROOT / path / "SKILL.md").is_file():
                errors.append(f"{plugin['name']}: {path} has no SKILL.md")

    for name in sorted(on_disk - set(listed)):
        errors.append(f"skills/{name} is not listed in any plugin")
    for name, count in sorted(listed.items()):
        if count > 1:
            errors.append(f"skills/{name} is listed in {count} plugins; expected 1")

    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        sys.exit(1)
    print(f"OK    {len(on_disk)} skills across {len(marketplace['plugins'])} plugins")


if __name__ == "__main__":
    main()
