#!/usr/bin/env python3
"""
Paired bootstrap comparison between two configurations.

Overlapping confidence intervals are a conservative test: non-overlap implies a
difference, but overlap does not imply its absence. The correct test is to
bootstrap the DIFFERENCE directly, resampling the shared units (file, repetition)
so the two configurations are compared on the same draws.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORED = ROOT / "harness" / "scored"


def runs_by_unit(tag: str) -> dict:
    """Map (file, repetition) -> (tp, fp, fn) for one configuration."""
    d = json.loads((SCORED / f"{tag}.json").read_text())
    out = {}
    for f, v in d["per_file"].items():
        for r in v["per_run"]:
            rep = r["run_id"].rsplit("__r", 1)[-1]
            out[(f, rep)] = (r["tp"], r["fp"], r["fn"])
    return out


def micro(units: list[tuple]) -> float:
    tp = sum(u[0] for u in units)
    fp = sum(u[1] for u in units)
    fn = sum(u[2] for u in units)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def compare(tag_a: str, tag_b: str, iterations: int = 20000,
            seed: int = 20260816) -> dict:
    a, b = runs_by_unit(tag_a), runs_by_unit(tag_b)
    shared = sorted(set(a) & set(b))
    if not shared:
        raise SystemExit("no shared (file, repetition) units to pair on")

    obs = micro([a[k] for k in shared]) - micro([b[k] for k in shared])
    rng = random.Random(seed)
    diffs = []
    for _ in range(iterations):
        draw = [rng.choice(shared) for _ in shared]
        diffs.append(micro([a[k] for k in draw]) - micro([b[k] for k in draw]))
    diffs.sort()
    lo = diffs[int(iterations * 0.025)]
    hi = diffs[int(iterations * 0.975) - 1]
    # two-sided p: proportion of resamples on the other side of zero, doubled
    side = min(sum(1 for d in diffs if d <= 0), sum(1 for d in diffs if d >= 0))
    p_value = min(1.0, 2 * side / iterations)

    return {
        "a": tag_a, "b": tag_b, "paired_units": len(shared),
        "observed_f1_difference": round(obs, 6),
        "ci95": [round(lo, 6), round(hi, 6)],
        "excludes_zero": lo > 0 or hi < 0,
        "p_value": round(p_value, 6),
        "iterations": iterations,
    }


def holm(pvals: dict) -> dict:
    """Holm step-down adjusted p-values for a family of tests {name: p}.

    Added 2026-09-27 after the independent audit: the paper runs 35 paired
    tests in four families (model comparison, reasoning, context, orchestration)
    and reported raw bootstrap p-values only. Adjusted p = max over the
    step-down sequence of (m - i) * p_(i), capped at 1.
    """
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[name] = running
    return out


if __name__ == "__main__":
    res = compare(sys.argv[1], sys.argv[2])
    print(f"{res['a']}\n  vs {res['b']}")
    print(f"  paired units      : {res['paired_units']}")
    print(f"  F1 difference     : {res['observed_f1_difference']:+.4f}")
    print(f"  95% CI on diff    : {res['ci95']}")
    print(f"  excludes zero     : {res['excludes_zero']}")
    print(f"  two-sided p       : {res['p_value']}")
