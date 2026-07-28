#!/usr/bin/env python3
"""Run every CLI invocation documented across vettd-skills against a real
`vettd` binary and fail if the claimed output shape no longer holds.

WHY this exists: skills document exact commands and exact JSON shapes. If a
future vettd release changes a flag, a key name, or a grading rule, the
skills silently become wrong. This script is the drift check for the
skills themselves — it is deliberately separate from
skills/detect-supply-chain-drift/scripts/diff-reports.py, which diffs two
*artifact* scans, not two *vettd releases*.

Usage:
    python3 ci/verify-commands.py ci/documented-commands.jsonl
                                   [--include-network]

Each line of the manifest is one JSON object:
    {"skill": "<skill-name>", "cmd": "<shell command>", "expect": "<kind>", ...}

Supported "expect" kinds:
    text        - stdout must match a regex ("match")
    json        - stdout must parse as JSON and contain each key in "keys"
                  at the top level
    skill-grade - stdout must parse as JSON; the skills[] entry whose `id`
                  contains "fixture" must have overallGrade == "grade"
    has-severity- stdout must parse as JSON; the skills[] entry whose `id`
                  contains "fixture" must have at least one finding across
                  externalScannerResults[].findings[] with the given
                  "severity"
    file        - after running cmd, "path" must exist and parse as JSON

Entries with "network": true are skipped unless --include-network is
passed, since they depend on a reachable public vettd directory endpoint
and would make this check flaky in environments without one (see
setup-vettd's Command Contract on the local-endpoint footgun).

Exit codes (this script's own contract):
    0 - every non-skipped entry passed
    1 - at least one entry failed
    2 - usage error (missing manifest, malformed manifest line)
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def load_manifest(path: str) -> list:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        print(f"error: manifest not found: {path}", file=sys.stderr)
        sys.exit(2)

    entries = []
    for lineno, raw_line in enumerate(manifest_path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"error: {path}:{lineno}: malformed JSON ({e})", file=sys.stderr)
            sys.exit(2)
    return entries


def run_cmd(cmd: str) -> subprocess.CompletedProcess:
    """Run a documented command and capture output.

    Commands in the manifest are trusted, repo-authored strings, not user
    input — shlex.split is used only to avoid a shell dependency, not as a
    security boundary.
    """
    return subprocess.run(
        shlex.split(cmd), capture_output=True, text=True, timeout=30
    )


def find_fixture_skill(payload: dict, fixture: str) -> dict:
    """Locate the skills[] entry whose id path contains the fixture name.

    id is shaped <absolute-path>:<content-hash>; matching on substring
    against the fixture directory name is enough here because fixture
    names are unique and controlled by this repo.
    """
    for skill in payload.get("skills", []):
        if fixture in skill.get("id", ""):
            return skill
    return {}


def check_text(result: subprocess.CompletedProcess, entry: dict) -> str:
    pattern = entry["match"]
    if not re.search(pattern, result.stdout):
        return f"stdout did not match /{pattern}/: {result.stdout[:200]!r}"
    return ""


def check_json(result: subprocess.CompletedProcess, entry: dict) -> str:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return f"stdout was not valid JSON ({e}): {result.stdout[:200]!r}"
    missing = [k for k in entry["keys"] if k not in payload]
    if missing:
        return f"missing top-level key(s): {missing}"
    return ""


def check_skill_grade(result: subprocess.CompletedProcess, entry: dict) -> str:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return f"stdout was not valid JSON ({e})"
    skill = find_fixture_skill(payload, entry["fixture"])
    if not skill:
        return f"no skills[] entry matched fixture {entry['fixture']!r}"
    actual = skill.get("overallGrade")
    if actual != entry["grade"]:
        return f"expected overallGrade {entry['grade']!r}, got {actual!r}"
    return ""


def check_has_severity(result: subprocess.CompletedProcess, entry: dict) -> str:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return f"stdout was not valid JSON ({e})"
    skill = find_fixture_skill(payload, entry["fixture"])
    if not skill:
        return f"no skills[] entry matched fixture {entry['fixture']!r}"
    severities = {
        f.get("severity")
        for r in skill.get("externalScannerResults", [])
        for f in r.get("findings", [])
    }
    if entry["severity"] not in severities:
        return f"expected a finding with severity {entry['severity']!r}, saw {sorted(severities)}"
    return ""


def check_file(result: subprocess.CompletedProcess, entry: dict) -> str:
    file_path = Path(entry["path"])
    if not file_path.is_file():
        return f"expected file not created: {entry['path']}"
    try:
        json.loads(file_path.read_text())
    except json.JSONDecodeError as e:
        return f"{entry['path']} is not valid JSON ({e})"
    return ""


CHECKERS = {
    "text": check_text,
    "json": check_json,
    "skill-grade": check_skill_grade,
    "has-severity": check_has_severity,
    "file": check_file,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Path to ci/documented-commands.jsonl")
    parser.add_argument(
        "--include-network",
        action="store_true",
        help="Also run entries marked network:true (requires a reachable "
        "public vettd directory endpoint)",
    )
    args = parser.parse_args()

    entries = load_manifest(args.manifest)
    failures = []
    skipped = 0

    for entry in entries:
        skill = entry.get("skill", "<unknown skill>")
        cmd = entry["cmd"]

        if entry.get("network") and not args.include_network:
            print(f"SKIP  [{skill}] {cmd}  (network:true, use --include-network)")
            skipped += 1
            continue

        try:
            result = run_cmd(cmd)
        except subprocess.TimeoutExpired:
            failures.append((skill, cmd, "command timed out after 30s"))
            print(f"FAIL  [{skill}] {cmd}")
            continue

        checker = CHECKERS[entry["expect"]]
        error = checker(result, entry)

        if error:
            failures.append((skill, cmd, error))
            print(f"FAIL  [{skill}] {cmd}\n      {error}")
        else:
            print(f"PASS  [{skill}] {cmd}")

    print()
    print(f"{len(entries) - skipped - len(failures)} passed, "
          f"{len(failures)} failed, {skipped} skipped")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
