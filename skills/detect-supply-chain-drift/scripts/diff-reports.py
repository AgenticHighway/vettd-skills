#!/usr/bin/env python3
"""Diff two vettd JSON scan reports to detect supply-chain drift.

WHY this script exists: vettd has no built-in baseline/diff capability.
scan_cache.rs is a performance stat-cache, not a change-tracking feature,
and there is no --baseline flag. This script is the only place drift
detection logic lives for the detect-supply-chain-drift skill.

Core insight: every artifact in a vettd report has an `id` shaped like
    <absolute-path>:<12-char-content-hash>
Same path + different hash means the artifact's content changed between
the two scans. Same path + same hash means it did not. Paths can contain
colons on some systems, so we split on the LAST colon (rsplit), not the
first.

Usage:
    python3 diff-reports.py <baseline.json> <current.json> [--json]
                             [--severity-threshold LEVEL]

Exit codes (this script's own contract, NOT vettd's — vettd scan always
exits 0 regardless of severity; do not conflate the two):
    0 - no drift detected (no ADDED, REMOVED, or CHANGED artifacts)
    1 - drift detected
    2 - usage / file error (missing file, malformed JSON, etc.)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# The five top-level artifact arrays a vettd report can contain.
ARTIFACT_KEYS = ["prompts", "skills", "mcpServers", "agents", "agenticApps"]

# Higher number = more severe. Used only for --severity-threshold filtering
# of NEW findings; it does not affect ADDED/REMOVED/CHANGED classification.
SEVERITY_ORDER = {"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}


@dataclass
class ArtifactRecord:
    """One artifact's identity + findings, indexed by (category, path)."""

    category: str
    path: str
    content_hash: str
    name: str
    artifact_type: str
    overall_grade: str
    # ruleId -> finding dict, so NEW/RESOLVED can be computed as set ops
    # over dict keys while still letting us print severity/label/detail.
    findings: Dict[str, dict] = field(default_factory=dict)


def load_report(path: str) -> dict:
    """Load a vettd JSON report, failing with a clear message, not a traceback.

    Malformed input is a user-facing error (wrong file, truncated write,
    vettd crash mid-scan) — it should never surface as a raw exception.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"error: report file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"error: {path} is not valid JSON ({e})", file=sys.stderr)
        sys.exit(2)

    if not isinstance(data, dict) or "scanMeta" not in data:
        print(
            f"error: {path} does not look like a vettd scan report "
            "(missing top-level 'scanMeta')",
            file=sys.stderr,
        )
        sys.exit(2)

    return data


def parse_id(artifact_id: str) -> Optional[Tuple[str, str]]:
    """Split '<path>:<hash>' on the LAST ':' — paths may contain colons.

    Returns None (and lets the caller warn + skip) if the id has no colon
    at all, since that means it doesn't match the documented id format and
    we cannot safely separate path from hash.
    """
    if ":" not in artifact_id:
        return None
    path, content_hash = artifact_id.rsplit(":", 1)
    return path, content_hash


def collect_findings(artifact: dict) -> Dict[str, dict]:
    """Flatten externalScannerResults[].findings[] into ruleId -> finding.

    Multiple scanner results can exist per artifact (first-party +
    third-party scanners); we flatten across all of them since drift
    detection cares about the union of what was found, not which scanner
    found it.
    """
    findings: Dict[str, dict] = {}
    for result in artifact.get("externalScannerResults", []) or []:
        for finding in result.get("findings", []) or []:
            rule_id = finding.get("ruleId")
            if rule_id:
                findings[rule_id] = finding
    return findings


def index_report(data: dict, source_label: str) -> Dict[Tuple[str, str], ArtifactRecord]:
    """Build a (category, path) -> ArtifactRecord index for one report.

    Keyed by category as well as path (not path alone) because two
    different artifact types could theoretically share a filesystem path
    (e.g. a directory scanned as both a skill and an agent bundle), and we
    don't want that to look like a single artifact changing type.
    """
    index: Dict[Tuple[str, str], ArtifactRecord] = {}
    skipped = 0

    for category in ARTIFACT_KEYS:
        for artifact in data.get(category, []) or []:
            parsed = parse_id(artifact.get("id", ""))
            if parsed is None:
                skipped += 1
                continue
            path, content_hash = parsed
            index[(category, path)] = ArtifactRecord(
                category=category,
                path=path,
                content_hash=content_hash,
                name=artifact.get("name", "<unknown>"),
                artifact_type=artifact.get("type", category),
                overall_grade=artifact.get("overallGrade", "pending"),
                findings=collect_findings(artifact),
            )

    if skipped:
        print(
            f"warning: {source_label}: skipped {skipped} artifact(s) with "
            "an id that did not match '<path>:<hash>'",
            file=sys.stderr,
        )

    return index


@dataclass
class ChangedArtifact:
    key: Tuple[str, str]
    baseline: ArtifactRecord
    current: ArtifactRecord
    new_findings: List[dict]
    resolved_findings: List[dict]
    grade_transition: Optional[Tuple[str, str]]


def diff_indexes(
    baseline_idx: Dict[Tuple[str, str], ArtifactRecord],
    current_idx: Dict[Tuple[str, str], ArtifactRecord],
) -> Tuple[List[ArtifactRecord], List[ArtifactRecord], List[ChangedArtifact], List[Tuple[str, str]]]:
    """Classify every artifact as ADDED, REMOVED, CHANGED, or UNCHANGED."""
    baseline_keys = set(baseline_idx)
    current_keys = set(current_idx)

    added = [current_idx[k] for k in current_keys - baseline_keys]
    removed = [baseline_idx[k] for k in baseline_keys - current_keys]

    changed: List[ChangedArtifact] = []
    unchanged: List[Tuple[str, str]] = []

    for key in baseline_keys & current_keys:
        before = baseline_idx[key]
        after = current_idx[key]

        if before.content_hash == after.content_hash:
            unchanged.append(key)
            continue

        # Content hash differs -> the artifact itself changed. Diff its
        # findings as sets of ruleIds so NEW/RESOLVED are order-independent.
        new_rule_ids = set(after.findings) - set(before.findings)
        resolved_rule_ids = set(before.findings) - set(after.findings)

        grade_transition = None
        if before.overall_grade != after.overall_grade:
            grade_transition = (before.overall_grade, after.overall_grade)

        changed.append(
            ChangedArtifact(
                key=key,
                baseline=before,
                current=after,
                new_findings=[after.findings[r] for r in new_rule_ids],
                resolved_findings=[before.findings[r] for r in resolved_rule_ids],
                grade_transition=grade_transition,
            )
        )

    return added, removed, changed, unchanged


def severity_at_or_above(finding: dict, threshold: Optional[str]) -> bool:
    """True if a finding meets --severity-threshold (or no threshold set)."""
    if threshold is None:
        return True
    finding_rank = SEVERITY_ORDER.get(finding.get("severity", "info"), 1)
    threshold_rank = SEVERITY_ORDER.get(threshold, 1)
    return finding_rank >= threshold_rank


def build_result(
    baseline_meta: dict,
    current_meta: dict,
    added: List[ArtifactRecord],
    removed: List[ArtifactRecord],
    changed: List[ChangedArtifact],
    unchanged: List[Tuple[str, str]],
    severity_threshold: Optional[str],
) -> dict:
    """Assemble the machine-readable result shape shared by text and JSON output."""

    def artifact_summary(rec: ArtifactRecord) -> dict:
        return {
            "category": rec.category,
            "path": rec.path,
            "name": rec.name,
            "type": rec.artifact_type,
            "overallGrade": rec.overall_grade,
        }

    def changed_summary(c: ChangedArtifact) -> dict:
        filtered_new = [
            f for f in c.new_findings if severity_at_or_above(f, severity_threshold)
        ]
        return {
            "category": c.current.category,
            "path": c.current.path,
            "name": c.current.name,
            "type": c.current.artifact_type,
            "gradeTransition": (
                {"from": c.grade_transition[0], "to": c.grade_transition[1]}
                if c.grade_transition
                else None
            ),
            "newFindings": [
                {
                    "ruleId": f.get("ruleId"),
                    "severity": f.get("severity"),
                    "label": f.get("label"),
                    "detail": f.get("detail"),
                }
                for f in filtered_new
            ],
            "resolvedFindings": [
                {"ruleId": f.get("ruleId"), "severity": f.get("severity")}
                for f in c.resolved_findings
            ],
        }

    return {
        "baseline": {
            "scanId": baseline_meta.get("scanId"),
            "scannedAt": baseline_meta.get("scannedAt"),
        },
        "current": {
            "scanId": current_meta.get("scanId"),
            "scannedAt": current_meta.get("scannedAt"),
        },
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
        "added": [artifact_summary(a) for a in added],
        "removed": [artifact_summary(r) for r in removed],
        "changed": [changed_summary(c) for c in changed],
        "driftDetected": bool(added or removed or changed),
    }


def print_human_readable(result: dict) -> None:
    print(f"Baseline scan: {result['baseline']['scanId']} ({result['baseline']['scannedAt']})")
    print(f"Current scan:  {result['current']['scanId']} ({result['current']['scannedAt']})")
    print()
    s = result["summary"]
    print(
        f"Summary: {s['added']} added, {s['removed']} removed, "
        f"{s['changed']} changed, {s['unchanged']} unchanged"
    )

    if result["added"]:
        print("\nADDED:")
        for a in result["added"]:
            print(f"  + [{a['category']}] {a['path']} ({a['name']}, grade {a['overallGrade']})")

    if result["removed"]:
        print("\nREMOVED:")
        for r in result["removed"]:
            print(f"  - [{r['category']}] {r['path']} ({r['name']}, last grade {r['overallGrade']})")

    if result["changed"]:
        print("\nCHANGED:")
        for c in result["changed"]:
            print(f"  ~ [{c['category']}] {c['path']} ({c['name']})")
            if c["gradeTransition"]:
                print(f"      grade: {c['gradeTransition']['from']} -> {c['gradeTransition']['to']}")
            for f in c["newFindings"]:
                print(f"      NEW      [{f['severity']}] {f['ruleId']} - {f['label']}")
            for f in c["resolvedFindings"]:
                print(f"      RESOLVED [{f['severity']}] {f['ruleId']}")

    if not result["driftDetected"]:
        print("\nNo drift detected.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diff two vettd JSON scan reports to detect supply-chain drift."
    )
    parser.add_argument("baseline", help="Path to the baseline vettd JSON report")
    parser.add_argument("current", help="Path to the current vettd JSON report")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--severity-threshold",
        choices=list(SEVERITY_ORDER.keys()),
        default=None,
        help="Only report NEW findings at or above this severity",
    )
    args = parser.parse_args()

    baseline_data = load_report(args.baseline)
    current_data = load_report(args.current)

    baseline_idx = index_report(baseline_data, args.baseline)
    current_idx = index_report(current_data, args.current)

    added, removed, changed, unchanged = diff_indexes(baseline_idx, current_idx)

    result = build_result(
        baseline_data.get("scanMeta", {}),
        current_data.get("scanMeta", {}),
        added,
        removed,
        changed,
        unchanged,
        args.severity_threshold,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human_readable(result)

    # This exit code is diff-reports.py's own contract, not vettd's — vettd
    # scan always exits 0 regardless of severity. 0 = no drift, 1 = drift.
    sys.exit(1 if result["driftDetected"] else 0)


if __name__ == "__main__":
    main()
