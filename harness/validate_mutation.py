#!/usr/bin/env python3
"""
Prove the mutated corpus has the same flaws as the original.

Scans both corpora with the pinned Checkov, maps every failed check in the
mutated scan back to its original resource address through data/rename_map.json,
and compares the (check_id, file, resource) sets restricted to the six files
under review. Also checks that today's scan of the ORIGINAL matches the scan
saved in August (data/checkov_raw.json), which guards against Checkov ruleset
drift. Writes data/mutation_checkov_diff.txt. Exits non-zero on any difference.

    pip install checkov==3.3.11
    python3 harness/validate_mutation.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {"s3.tf", "ec2.tf", "db-app.tf", "iam.tf", "kms.tf", "lambda.tf"}
CHECKOV_VERSION = "3.3.11"


def scan(directory: Path) -> set[tuple[str, str, str]]:
    out = subprocess.run(
        ["checkov", "-d", str(directory), "--framework", "terraform", "--skip-download",
         "-o", "json", "--quiet", "--compact"],
        capture_output=True, text=True)
    data = json.loads(out.stdout)
    return failed_set(data)


def failed_set(data) -> set[tuple[str, str, str]]:
    reports = data if isinstance(data, list) else [data]
    found = set()
    for rep in reports:
        for r in rep.get("results", {}).get("failed_checks", []):
            f = r["file_path"].lstrip("/").split("/")[-1]
            if f in FILES:
                found.add((r["check_id"], f, r["resource"]))
    return found


def main() -> None:
    ver = subprocess.run(["checkov", "--version"], capture_output=True, text=True).stdout.strip()
    if ver != CHECKOV_VERSION:
        raise SystemExit(f"checkov {ver} found; the study pins {CHECKOV_VERSION}")
    renames = json.loads((ROOT / "data" / "rename_map.json").read_text())["renames"]
    back = {v: k for k, v in renames.items() if not k.startswith("local.")}

    orig = scan(ROOT / "terragoat" / "terraform" / "aws")
    mut_raw = scan(ROOT / "terragoat_mut" / "terraform" / "aws")
    unmapped = sorted({r for _, _, r in mut_raw if r not in back})
    mut = {(c, f, back.get(r, r)) for c, f, r in mut_raw}
    saved = failed_set(json.loads((ROOT / "data" / "checkov_raw.json").read_text()))

    only_o, only_m = sorted(orig - mut), sorted(mut - orig)
    drift = sorted(saved ^ orig)

    lines = [
        "Mutation control: semantic-preservation check",
        f"Checkov {ver}, --skip-download, --framework terraform; full terraform/aws directory scanned "
        "both times; comparison restricted to the six corpus files. Mutated resource addresses are "
        "mapped back to originals via data/rename_map.json.",
        "",
        f"original corpus : {len(orig)} failed checks",
        f"mutated corpus  : {len(mut_raw)} failed checks",
        f"identical pairs : {len(orig & mut)}",
        f"in original only: {len(only_o)}",
        f"in mutated only : {len(only_m)}",
        f"unmapped mutated resources: {unmapped or 'none'}",
        "",
        f"Drift check (today's scan of the ORIGINAL vs data/checkov_raw.json saved in August): "
        f"symmetric difference = {len(drift)}",
    ]
    if only_o or only_m or unmapped or drift:
        lines.append("\nDIFFERENCES:")
        lines += [f"  - {c} {f} {r}" for c, f, r in only_o]
        lines += [f"  + {c} {f} {r}" for c, f, r in only_m]
        lines += [f"  ~ drift {c} {f} {r}" for c, f, r in drift]
    else:
        lines.append("\nNo differences. Every vulnerability Checkov detects in the original is detected "
                     "at the corresponding resource in the mutated corpus.")
    text = "\n".join(lines) + "\n"
    (ROOT / "data" / "mutation_checkov_diff.txt").write_text(text)
    print(text)
    sys.exit(1 if (only_o or only_m or unmapped or drift) else 0)


if __name__ == "__main__":
    main()
