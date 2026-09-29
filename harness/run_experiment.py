#!/usr/bin/env python3
"""
Experiment runner.

Executes (model x context variant x orchestration pattern x file x repetition)
and writes one JSON per run to results/. Resumable: a run whose result file
already exists is skipped, so a container restart mid-sweep costs nothing.

Usage:
  python3 harness/run_experiment.py --model claude-sonnet-5 --context zero_shot \\
      --pattern single --runs 5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import agents
import prompts
import providers
from score import RunScore, score_run, summarise

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "harness" / "results"
SCORED = ROOT / "harness" / "scored"
CORPUS_ROOT = {
    "terragoat": ROOT / "terragoat" / "terraform" / "aws",
    "terragoat_mut": ROOT / "terragoat_mut" / "terraform" / "aws",   # mutation control; see harness/mutate_corpus.py
}


def corpus_files(gt: dict, corpus: str) -> list[str]:
    return sorted({k.split("::", 1)[1] for k in gt["findings"] if k.startswith(corpus + "::")})


def read_source(corpus: str, filename: str) -> str:
    if corpus in CORPUS_ROOT:
        return (CORPUS_ROOT[corpus] / filename).read_text()
    # cloudgoat probe paths are scenario/file
    return (ROOT / "cloudgoat" / "cloudgoat" / "scenarios" / "aws" / filename).read_text()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def build_provenance(guidance: str | None, chunk_chars: int) -> dict:
    """
    Fingerprint the inputs that decide what a model actually saw.

    Section 2 commits to publishing exact prompts. Without this, an edit to
    prompts.py or the guidance corpus is invisible in the results, and there is
    no way to tell after the fact which version produced a given run.
    """
    here = Path(__file__).parent
    return {
        "prompts_sha": _sha((here / "prompts.py").read_text()),
        "schema_sha": _sha((here / "schema.py").read_text()),
        "agents_sha": _sha("".join(sorted(
            (p.read_text() for p in (here / "agents").glob("*.py")), key=len))),
        "guidance_sha": _sha(guidance) if guidance else None,
        "chunk_chars": chunk_chars,
        # added 2026-09-29: the provider code decides ceilings, endpoints, and
        # tool settings, so its version belongs in the record too
        "providers_sha": _sha((here / "providers.py").read_text()),
    }


def run_one(model: str, context: str, pattern: str, corpus: str, filename: str,
            rep: int, guidance: str | None, temperature: float | None,
            force: bool = False, reasoning: bool = False,
            chunk_chars: int = 2500, provenance: dict | None = None) -> dict:
    suffix = "__think" if reasoning else ""
    run_id = (f"{model}__{context}__{pattern}__{corpus}"
              f"{suffix}__{filename.replace('/', '_')}__r{rep}")
    out_path = RESULTS / f"{run_id}.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text())

    source = read_source(corpus, filename)
    result = agents.run_pattern(
        pattern, model=model, context=context, source=source, filename=filename,
        guidance=guidance, temperature=temperature, reasoning=reasoning,
        chunk_chars=chunk_chars)

    record = {
        "run_id": run_id,
        "model": model, "context": context, "pattern": pattern,
        "corpus": corpus, "file": filename, "repetition": rep,
        "temperature": temperature, "reasoning": reasoning,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provenance": provenance or {},
        **result.to_dict(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--context", default="zero_shot", choices=prompts.VARIANTS)
    ap.add_argument("--pattern", default="single", choices=agents.PATTERNS,
                    help="orchestration pattern; validated so a typo cannot "
                         "silently produce mislabelled single-agent runs")
    ap.add_argument("--chunk-chars", type=int, default=2500,
                    help="target chunk size for the chunked pattern; whole "
                         "top-level blocks are never split")
    ap.add_argument("--corpus", default="terragoat")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--temperature", type=float, default=None,
                    help="Left unset by default: sampling is not alignable across arms "
                         "(Claude 5 rejects the parameter). All arms run at provider default.")
    ap.add_argument("--ground-truth", type=Path, default=ROOT / "data" / "ground_truth.json")
    ap.add_argument("--guidance", type=Path, default=None,
                    help="RAG guidance text; required for the rag context variant")
    ap.add_argument("--reasoning", action="store_true",
                    help="enable the model's native reasoning; results are tagged __think")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    gt = json.loads(args.ground_truth.read_text())
    files = args.files or corpus_files(gt, args.corpus)
    guidance = args.guidance.read_text() if args.guidance else None
    provenance = build_provenance(guidance, args.chunk_chars)

    print(f"{args.model} | {args.context} | {args.pattern} | {args.corpus} | "
          f"{len(files)} files x {args.runs} runs")
    print(f"  prompts={provenance['prompts_sha']} agents={provenance['agents_sha']} "
          f"guidance={provenance['guidance_sha']}")

    per_file_runs: dict[str, list[RunScore]] = {}
    spend = 0.0
    for filename in files:
        truth = gt["findings"].get(f"{args.corpus}::{filename}", [])
        scores = []
        for rep in range(1, args.runs + 1):
            rec = run_one(args.model, args.context, args.pattern, args.corpus,
                          filename, rep, guidance, args.temperature, args.force,
                          reasoning=args.reasoning, chunk_chars=args.chunk_chars,
                          provenance=provenance)
            spend += rec.get("cost_usd", 0.0)
            if rec.get("error"):
                print(f"  {filename:14s} r{rep}  ERROR {rec['error'][:90]}")
                continue
            s = score_run(rec["run_id"], rec["findings"], truth)
            scores.append(s)
            flag = "!" if s.needs_adjudication else " "
            calls = rec.get("n_calls", 1)
            print(f"  {filename:14s} r{rep}  claims={len(rec['findings']):3d} "
                  f"TP={s.tp:2d} FP={s.fp:2d} FN={s.fn:2d} "
                  f"P={s.precision:.2f} R={s.recall:.2f} F1={s.f1:.2f} "
                  f"{rec['latency_s']:6.1f}s x{calls} {flag}")
        if scores:
            per_file_runs[filename] = scores

    all_runs = [s for v in per_file_runs.values() for s in v]
    if not all_runs:
        print("\nno successful runs")
        return

    overall = summarise(all_runs)
    SCORED.mkdir(parents=True, exist_ok=True)
    tag = (f"{args.model}__{args.context}__{args.pattern}__{args.corpus}"
           + ("__think" if args.reasoning else ""))
    (SCORED / f"{tag}.json").write_text(json.dumps({
        "config": {"model": args.model, "context": args.context,
                   "pattern": args.pattern, "corpus": args.corpus,
                   "runs": args.runs, "temperature": args.temperature,
                   "reasoning": args.reasoning,
                   "chunk_chars": args.chunk_chars},
        "provenance": provenance,
        "overall": overall,
        "per_file": {f: summarise(v) for f, v in per_file_runs.items()},
        "cost_usd": round(spend, 4),
    }, indent=2))

    ci = overall.get("ci") or {}
    print(f"\n  OVERALL  P={overall['precision']:.3f} R={overall['recall']:.3f} "
          f"F1={overall['f1']:.3f}")
    if ci:
        print(f"  95% CI   P={ci['precision']}  R={ci['recall']}  F1={ci['f1']}")
    t = overall["totals"]
    print(f"  totals   TP={t['tp']} FP={t['fp']} FN={t['fn']} "
          f"| lexical={t['lexical_matches']} pending_adjudication={t['pending_adjudication']}")
    print(f"  cost     ${spend:.4f}")
    print(f"  wrote    {SCORED / (tag + '.json')}")


if __name__ == "__main__":
    main()
