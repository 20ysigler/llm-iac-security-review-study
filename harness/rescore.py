#!/usr/bin/env python3
"""
Regenerate harness/scored/<tag>.json for every configuration from the raw run
files, without any API call. Same scoring path as run_experiment.py (files
sorted, repetitions ascending, seeded bootstrap), so the output is identical to
what the runner would have written. The summaries carry six-decimal precision
so that the tables round once; the run files and their config and provenance
blocks are never touched.

    python3 harness/rescore.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import score_run, summarise           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES, SCORED = ROOT / "harness" / "results", ROOT / "harness" / "scored"
GT = json.loads((ROOT / "data" / "ground_truth_mut.json").read_text())["findings"]


def main() -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in RES.glob("*.json"):
        r = json.loads(p.read_text())
        tag = (f"{r['model']}__{r['context']}__{r['pattern']}__{r['corpus']}"
               + ("__think" if r.get("reasoning") else ""))
        groups[tag].append(r)
    for tag, rs in sorted(groups.items()):
        old = json.loads((SCORED / f"{tag}.json").read_text())
        rs.sort(key=lambda r: (r["file"], r["repetition"]))
        per_file: dict[str, list] = defaultdict(list)
        for r in rs:
            if r.get("error"):
                continue
            per_file[r["file"]].append(score_run(r["run_id"], r["findings"], GT.get(f"{r['corpus']}::{r['file']}", [])))
        all_runs = [s for v in per_file.values() for s in v]
        out = {
            "config": old["config"],
            "provenance": old["provenance"],
            "overall": summarise(all_runs),
            "per_file": {f: summarise(v) for f, v in per_file.items()},
            "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in rs), 4),
        }
        assert out["overall"]["totals"] == old["overall"]["totals"], tag
        assert abs(out["cost_usd"] - old["cost_usd"]) < 1e-9, tag
        (SCORED / f"{tag}.json").write_text(json.dumps(out, indent=2))
        print(f"{tag:60s} F1 {out['overall']['f1']:.6f} (was {old['overall']['f1']})")


if __name__ == "__main__":
    main()
