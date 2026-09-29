"""
Scoring: TP/FP/FN per run, aggregated to precision, recall, and F1 with 95%
bootstrap confidence intervals.

Bootstrap rather than a normal approximation because n is 5 runs per
configuration; the bootstrap makes no distributional assumption and the method
section commits to it (Efron & Tibshirani, 1993).

Resampling is over RUNS, not over findings. The run is the independent
replicate -- findings within one run are not independent of each other, since
they come from a single model response.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path

from match import match_findings


@dataclass
class RunScore:
    run_id: str
    tp: int
    fp: int
    fn: int
    lexical_matches: int          # matched only at the weakest level
    needs_adjudication: list      # (gt_id, claim_index) pairs a human should check

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(precision=round(self.precision, 4),
                 recall=round(self.recall, 4),
                 f1=round(self.f1, 4))
        return d


def score_run(run_id: str, claims: list[dict], truth: list[dict]) -> RunScore:
    matches, unmatched_claims, unmatched_gt = match_findings(claims, truth)
    adjudicate = [(m.gt_id, m.claim_index) for m in matches if m.needs_adjudication]
    return RunScore(
        run_id=run_id,
        tp=len(matches),
        fp=len(unmatched_claims),
        fn=len(unmatched_gt),
        lexical_matches=sum(1 for m in matches if m.level == "lexical"),
        needs_adjudication=adjudicate,
    )


def _micro(runs: list[RunScore]) -> tuple[float, float, float]:
    """Pooled counts across runs, then the metrics. Avoids small-sample bias."""
    tp = sum(r.tp for r in runs)
    fp = sum(r.fp for r in runs)
    fn = sum(r.fn for r in runs)
    p = tp / (tp + fp) if tp + fp else 0.0
    r_ = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r_ / (p + r_) if p + r_ else 0.0
    return p, r_, f


def bootstrap_ci(runs: list[RunScore], iterations: int = 10000,
                 alpha: float = 0.05, seed: int = 20260816) -> dict:
    """
    Percentile bootstrap over runs.

    With n=5 there are only 5**5 distinct resamples, so the interval is coarse.
    That coarseness is real and is the honest reason the method section calls
    for 10-20 runs on close comparisons; it is not smoothed over here.
    """
    rng = random.Random(seed)
    point = _micro(runs)
    if len(runs) < 2:
        return {"precision": point[0], "recall": point[1], "f1": point[2],
                "ci": None, "n_runs": len(runs),
                "note": "confidence interval undefined for a single run"}

    draws = {"precision": [], "recall": [], "f1": []}
    for _ in range(iterations):
        sample = [rng.choice(runs) for _ in runs]
        p, r, f = _micro(sample)
        draws["precision"].append(p)
        draws["recall"].append(r)
        draws["f1"].append(f)

    lo_i = int(iterations * alpha / 2)
    hi_i = int(iterations * (1 - alpha / 2)) - 1
    ci = {}
    for k, v in draws.items():
        v.sort()
        # Six decimals: the tables print three, and rounding twice (4 then 3)
        # misplaced the last digit of seven cells in the first draft.
        ci[k] = [round(v[lo_i], 6), round(v[hi_i], 6)]
    return {"precision": round(point[0], 6), "recall": round(point[1], 6),
            "f1": round(point[2], 6), "ci": ci, "n_runs": len(runs),
            "iterations": iterations}


def load_ground_truth(path: Path, corpus: str, file: str) -> list[dict]:
    data = json.loads(Path(path).read_text())
    return data["findings"].get(f"{corpus}::{file}", [])


def summarise(runs: list[RunScore]) -> dict:
    stats = bootstrap_ci(runs)
    stats["totals"] = {
        "tp": sum(r.tp for r in runs),
        "fp": sum(r.fp for r in runs),
        "fn": sum(r.fn for r in runs),
        "lexical_matches": sum(r.lexical_matches for r in runs),
        "pending_adjudication": sum(len(r.needs_adjudication) for r in runs),
    }
    stats["per_run"] = [r.to_dict() for r in runs]
    return stats
