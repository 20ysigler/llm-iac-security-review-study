"""
Output stability across repeated runs.

Temperature is not alignable across this study's five arms -- Claude 5 rejects
the parameter outright while the other three hosted arms accept it -- so
sampling cannot be held constant by configuration. Rather than claim a control
that does not exist, stability is measured and reported per arm.

Two distinct quantities, which the pilot showed are not the same thing:

  lexical stability  -- do repeated runs return the same SET of findings?
  score stability    -- do repeated runs produce the same F1?

The pilot found Sonnet 5 lexically unstable on every file (0/6 identical across
5 runs) while several files were perfectly score-stable, because the same
vulnerability gets described in different words each time. Reporting only one
of these would misrepresent the model's behaviour.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


def finding_signature(findings: list[dict]) -> tuple:
    """Set-like identity of a response: which (resource, category) pairs it claims."""
    return tuple(sorted(
        (f.get("resource", "").strip().lower(),
         (f.get("issue_category") or "").strip().lower())
        for f in findings))


def jaccard(a: tuple, b: tuple) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def stability_for_runs(records: list[dict], scores: list[float]) -> dict:
    """records: raw run dicts for one (config, file). scores: matching F1 per run."""
    sigs = [finding_signature(r["findings"]) for r in records]
    distinct = len(set(sigs))

    pairwise = [jaccard(sigs[i], sigs[j])
                for i in range(len(sigs)) for j in range(i + 1, len(sigs))]
    claim_counts = [len(r["findings"]) for r in records]

    return {
        "n_runs": len(records),
        "distinct_outputs": distinct,
        "identical_across_all_runs": distinct == 1,
        "mean_pairwise_jaccard": round(statistics.fmean(pairwise), 4) if pairwise else 1.0,
        "claims_min": min(claim_counts) if claim_counts else 0,
        "claims_max": max(claim_counts) if claim_counts else 0,
        "f1_min": round(min(scores), 4) if scores else 0.0,
        "f1_max": round(max(scores), 4) if scores else 0.0,
        "f1_spread": round(max(scores) - min(scores), 4) if scores else 0.0,
        "f1_stdev": round(statistics.stdev(scores), 4) if len(scores) > 1 else 0.0,
    }


def analyse(results_dir: Path, scored_dir: Path, config_tag: str) -> dict:
    """Aggregate stability for one configuration across all its files."""
    model, context, pattern, corpus = config_tag.split("__")
    byfile: dict[str, list[dict]] = defaultdict(list)
    for p in sorted(results_dir.glob(f"{model}__{context}__{pattern}__{corpus}__*.json")):
        rec = json.loads(p.read_text())
        if rec.get("error"):
            continue
        byfile[rec["file"]].append(rec)

    scored_path = scored_dir / f"{config_tag}.json"
    per_file_scores = {}
    if scored_path.exists():
        sc = json.loads(scored_path.read_text())
        per_file_scores = {f: [r["f1"] for r in v["per_run"]]
                           for f, v in sc.get("per_file", {}).items()}

    per_file = {}
    for f, recs in sorted(byfile.items()):
        recs.sort(key=lambda r: r["repetition"])
        per_file[f] = stability_for_runs(recs, per_file_scores.get(f, []))

    identical = sum(1 for v in per_file.values() if v["identical_across_all_runs"])
    jac = [v["mean_pairwise_jaccard"] for v in per_file.values()]
    spreads = [v["f1_spread"] for v in per_file.values()]

    return {
        "config": config_tag,
        "files": len(per_file),
        "files_fully_identical": identical,
        "mean_pairwise_jaccard": round(statistics.fmean(jac), 4) if jac else 0.0,
        "mean_f1_spread": round(statistics.fmean(spreads), 4) if spreads else 0.0,
        "max_f1_spread": round(max(spreads), 4) if spreads else 0.0,
        "per_file": per_file,
        "note": ("Sampling was left at each provider's default because temperature "
                 "is not settable on all arms. These figures report observed "
                 "stability rather than assuming it."),
    }


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parent.parent
    tag = sys.argv[1] if len(sys.argv) > 1 else "claude-sonnet-5__zero_shot__single__terragoat"
    out = analyse(root / "harness" / "results", root / "harness" / "scored", tag)
    dest = root / "harness" / "scored" / f"{tag}__stability.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"{out['config']}")
    print(f"  files fully identical across runs : {out['files_fully_identical']}/{out['files']}")
    print(f"  mean pairwise Jaccard             : {out['mean_pairwise_jaccard']}")
    print(f"  mean F1 spread across runs        : {out['mean_f1_spread']}")
    print(f"  max  F1 spread across runs        : {out['max_f1_spread']}")
    print()
    for f, v in out["per_file"].items():
        print(f"  {f:12s} distinct={v['distinct_outputs']}/{v['n_runs']} "
              f"jaccard={v['mean_pairwise_jaccard']:.3f} "
              f"claims={v['claims_min']}-{v['claims_max']} "
              f"F1 {v['f1_min']:.3f}-{v['f1_max']:.3f} (spread {v['f1_spread']:.3f})")
    print(f"\nwrote {dest}")
