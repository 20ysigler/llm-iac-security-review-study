#!/usr/bin/env python3
"""
Regenerate RESULTS.md from harness/results/ and harness/scored/.

    python3 harness/build_results.py > RESULTS.md

Every table the paper quotes is produced here; harness/verify_paper.py then
re-derives each number independently and fails on any mismatch. The
adjudication section reads harness/fp_review/set1_fp_adjudicated.json.
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare import compare, holm              # noqa: E402
from match import match_findings               # noqa: E402
from match import normalise_resource           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES, SCORED = ROOT / "harness" / "results", ROOT / "harness" / "scored"
GT = json.loads((ROOT / "data" / "ground_truth_mut.json").read_text())["findings"]
MODELS = ["claude-opus-5", "claude-sonnet-5", "deepseek-v4-flash", "gpt-5.6-terra"]
NAME = {"claude-opus-5": "Claude Opus 5", "claude-sonnet-5": "Claude Sonnet 5",
        "gpt-5.6-terra": "GPT-5.6 Terra", "deepseek-v4-flash": "DeepSeek Flash"}
VARIANTS = ["zero_shot", "few_shot", "system_enriched", "rag", "chain_of_thought"]
VNAME = {"zero_shot": "zero_shot", "few_shot": "few_shot", "system_enriched": "system_enriched",
         "rag": "rag (guidance injection)", "chain_of_thought": "chain_of_thought"}
PATTERNS = ["single", "critic", "debate", "chunked"]
FILES = ["db-app.tf", "ec2.tf", "iam.tf", "kms.tf", "lambda.tf", "s3.tf"]
A, B, C, D = ("Real issue, not in answer key", "Real but excluded by our criteria",
              "Model was wrong", "Same issue reported twice")


def S(tag): return json.loads((SCORED / f"{tag}.json").read_text())
def runs(tag):
    think = tag.endswith("__think")
    return [json.loads(p.read_text()) for p in RES.glob(f"{tag}__*.json") if ("__think__" in p.name) == think]
def ci(o): return f"[{o['ci']['f1'][0]:.3f}, {o['ci']['f1'][1]:.3f}]"
def pfmt(p): return "<0.001" if p < 0.001 else (f"{p:.2f}" if p >= 0.01 else f"{p:.3f}")
def paired_family(pairs):
    """pairs: list of (label, tag_a, tag_b). Returns rows with raw and Holm-adjusted p (family-wise)."""
    res = [(label, compare(a, b)) for label, a, b in pairs]
    adj = holm({label: r["p_value"] for label, r in res})
    return [(label, r, adj[label]) for label, r in res]
def paired_row(label, r, hp):
    return (f"| {label} | {r['observed_f1_difference']:+.3f} | [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] | "
            f"{pfmt(r['p_value'])} | {pfmt(hp)} | {'yes' if r['excludes_zero'] else 'no'} |")
ALL_P = {}   # every paired test, for the global Holm line
def perf(tag):
    o = S(tag)["overall"]; t = o["totals"]
    return f"{o['precision']:.3f} | {o['recall']:.3f} | {o['f1']:.3f} | {ci(o)} | {t['tp']} | {t['fp']} | {t['fn']}"
def out(*a): print(*a)


out("# Results\n")
out("All runs on `terragoat_mut` (corpus regenerated 2026-09-22 after a mutator fix; see Corpus note), 5 repetitions per file, 6 files, 30 runs per configuration. Micro-averaged P/R/F1; 95% percentile bootstrap CI (10,000 iterations). Paired comparisons via `harness/compare.py` on shared (file, repetition) units, 20,000 iterations; `p` is the raw two-sided bootstrap p, `Holm p` is Holm-adjusted within the table's family of tests (3 model contrasts, 4 reasoning contrasts, 16 context contrasts, 12 orchestration contrasts). Reasoning off unless stated (Claude: forced tool call; GPT: reasoning_effort none; DeepSeek: thinking disabled). Values are rounded once, from six-decimal summaries (revised 2026-09-27). Regenerate this file with `python3 harness/build_results.py > RESULTS.md`; check it with `python3 harness/verify_paper.py`.\n")

# ---------------------------------------------------------------- Set 1
out("## Set 1 — Model selection (system_enriched, single)\n")
out("| Model | Served as | P | R | F1 | F1 95% CI | TP | FP | FN | Cost (USD) |\n|---|---|---|---|---|---|---|---|---|---|")
for m in MODELS:
    tag = f"{m}__system_enriched__single__terragoat_mut"
    out(f"| {NAME[m]} | {runs(tag)[0]['resolved_model']} | {perf(tag)} | {S(tag)['cost_usd']:.2f} |")
out("\nPaired F1 difference vs Claude Opus 5 (30 shared units):\n\n| Model | F1 diff | 95% CI | p | Holm p | Excludes zero |\n|---|---|---|---|---|---|")
for label, r, hp in paired_family([(NAME[m], f"{m}__system_enriched__single__terragoat_mut", "claude-opus-5__system_enriched__single__terragoat_mut") for m in MODELS[1:]]):
    out(paired_row(label, r, hp)); ALL_P[f"set1:{label}"] = r["p_value"]
out("\nPer-file F1 (system_enriched, single):\n\n| Model | db-app.tf | ec2.tf | iam.tf | kms.tf | lambda.tf | s3.tf |\n|---|---|---|---|---|---|---|")
for m in MODELS:
    pf = S(f"{m}__system_enriched__single__terragoat_mut")["per_file"]
    out(f"| {NAME[m]} | " + " | ".join(f"{pf[f]['f1']:.2f}" for f in FILES) + " |")

out("\n### Native reasoning on vs off (Set 1 configurations; added after Sets 1–3)\n")
out("| Model | Reasoning | P | R | F1 | F1 95% CI | TP | FP | FN | Latency (s) | Out tokens | Cost (USD) | Zero-finding runs | Non-JSON runs |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for m in MODELS:
    for th in ("", "__think"):
        tag = f"{m}__system_enriched__single__terragoat_mut{th}"; rs = runs(tag)
        z = sum(len(r["findings"]) == 0 for r in rs)
        nj = sum(bool((r.get("raw_text") or "").strip()) and not (r["raw_text"] or "").lstrip().startswith("{") for r in rs)
        out(f"| {NAME[m]} | {'on' if th else 'off'} | {perf(tag)} | {statistics.mean(r['latency_s'] for r in rs):.1f} | "
            f"{statistics.mean(r['output_tokens'] for r in rs):,.0f} | {S(tag)['cost_usd']:.2f} | {z} | {nj} |")
out("\nPaired F1 difference, reasoning on − off:\n\n| Model | F1 diff | 95% CI | p | Holm p | Excludes zero |\n|---|---|---|---|---|---|")
for label, r, hp in paired_family([(NAME[m], f"{m}__system_enriched__single__terragoat_mut__think", f"{m}__system_enriched__single__terragoat_mut") for m in MODELS]):
    out(paired_row(label, r, hp)); ALL_P[f"reasoning:{label}"] = r["p_value"]

# ---------------------------------------------------------------- Set 2
out("\n## Set 2 — Context engineering (all four models, single)\n")
out("| Model | Variant | P | R | F1 | F1 95% CI | TP | FP | FN | Cost (USD) |\n|---|---|---|---|---|---|---|---|---|---|")
for m in MODELS:
    for c in VARIANTS:
        tag = f"{m}__{c}__single__terragoat_mut"
        out(f"| {NAME[m]} | {VNAME[c]} | {perf(tag)} | {S(tag)['cost_usd']:.2f} |")
out("\nPaired F1 difference vs the same model's zero_shot:\n\n| Model | Variant | F1 diff | 95% CI | p | Holm p | Excludes zero |\n|---|---|---|---|---|---|---|")
for label, r, hp in paired_family([(f"{NAME[m]} | {VNAME[c]}", f"{m}__{c}__single__terragoat_mut", f"{m}__zero_shot__single__terragoat_mut")
                                   for m in MODELS for c in ["few_shot", "system_enriched", "rag", "chain_of_thought"]]):
    out(paired_row(label, r, hp)); ALL_P[f"context:{label}"] = r["p_value"]
out("\nF1 by model and variant (compact):\n\n| Model | zero_shot | few_shot | system_enriched | rag | chain_of_thought |\n|---|---|---|---|---|---|")
for m in MODELS:
    out(f"| {NAME[m]} | " + " | ".join(f"{S(f'{m}__{c}__single__terragoat_mut')['overall']['f1']:.3f}" for c in VARIANTS) + " |")

# ---------------------------------------------------------------- Set 3
out("\n## Set 3 — Orchestration (all four models, system_enriched)\n")
out("| Model | Pattern | P | R | F1 | F1 95% CI | TP | FP | FN | Calls | Latency (s) | Cost/review (USD) | Cost × |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
mech, fab = [], []
man = json.loads((ROOT / "data" / "terragoat_resources.json").read_text())["resources"]
ren = json.loads((ROOT / "data" / "rename_map.json").read_text())["renames"]
valid = {f: {normalise_resource(ren.get(x, x)) for x in v} for f, v in man.items()}
steps = lambda r: {s["step"]: s for s in r["steps"]}   # noqa: E731
for m in MODELS:
    base = S(f"{m}__system_enriched__single__terragoat_mut")["cost_usd"] / 30
    for p in PATTERNS:
        tag = f"{m}__system_enriched__{p}__terragoat_mut"; rs = runs(tag); d = S(tag)
        out(f"| {NAME[m]} | {p} | {perf(tag)} | {statistics.mean(r.get('n_calls', 1) for r in rs):.1f} | "
            f"{statistics.mean(r['latency_s'] for r in rs):.1f} | {d['cost_usd']/30:.4f} | {(d['cost_usd']/30)/base:.1f} |")
    rs = runs(f"{m}__system_enriched__critic__terragoat_mut")
    mech.append(f"{NAME[m]} critic: {sum(steps(r)['review']['n_findings'] for r in rs)} → {sum(steps(r)['critique']['n_findings'] for r in rs)} findings, "
                f"shrank in {sum(steps(r)['critique']['n_findings'] < steps(r)['review']['n_findings'] for r in rs)}/30 runs")
    rs = runs(f"{m}__system_enriched__debate__terragoat_mut")
    mech.append(f"{NAME[m]} debate: reviewers {sum(steps(r)['reviewer_a']['n_findings'] for r in rs)}/{sum(steps(r)['reviewer_b']['n_findings'] for r in rs)} → reconciled {sum(steps(r)['reconciler']['n_findings'] for r in rs)}")
    for p in ("single", "chunked"):
        tot = bad = 0
        for r in runs(f"{m}__system_enriched__{p}__terragoat_mut"):
            for c in r["findings"]:
                tot += 1; bad += normalise_resource(c.get("resource", "")) not in valid[r["file"]]
        fab.append(f"{NAME[m]} {p} {bad}/{tot}")
out("\nPaired F1 difference vs same-model single:\n\n| Model | Pattern | F1 diff | 95% CI | p | Holm p | Excludes zero |\n|---|---|---|---|---|---|---|")
for label, r, hp in paired_family([(f"{NAME[m]} | {p}", f"{m}__system_enriched__{p}__terragoat_mut", f"{m}__system_enriched__single__terragoat_mut")
                                   for m in MODELS for p in ["critic", "debate", "chunked"]]):
    out(paired_row(label, r, hp)); ALL_P[f"orchestration:{label}"] = r["p_value"]
out("\nF1 by model and pattern (compact):\n\n| Model | single | critic | debate | chunked |\n|---|---|---|---|---|")
for m in MODELS:
    out(f"| {NAME[m]} | " + " | ".join(f"{S(f'{m}__system_enriched__{p}__terragoat_mut')['overall']['f1']:.3f}" for p in PATTERNS) + " |")
out("\nMechanism: " + "; ".join(mech) + ". Fabricated resource addresses (claim address not present in the file): " + "; ".join(fab) +
    ". Debate samples the same model twice (self-consistency), not two different models. Latency measured from one cloud container; comparable within this table only.")

# ---------------------------------------------------------------- totals
n_cfg = len(list(SCORED.glob("*.json"))); n_runs = len(list(RES.glob("*.json")))
_all_runs_for_totals = [json.loads(p.read_text()) for p in RES.glob("*.json")]
tot = sum(S(p.stem)["cost_usd"] for p in SCORED.glob("*.json"))
_nocontent = sorted(r["run_id"] for r in _all_runs_for_totals if not r["findings"] and not (r.get("raw_text") or "").strip().startswith("{"))
out(f"\n## Study totals\n\n{n_cfg} configurations, {n_runs} runs, zero error runs in the reported data ({len(_nocontent)} run returned no parsable content and is scored as an empty findings list: {', '.join(_nocontent)}), zero lexical-level matches (the lexical level cannot fire: category scores take only the values 0, 0.5 and 1, so no score falls in its [0.25, 0.5) window), zero findings pending adjudication. "
    f"Total API spend for the reported runs ≈ ${tot:.2f} at the August 2026 list prices in `providers.py` (plus ≈ $6 for 180 superseded runs on the pre-fix corpus, retained in the repository history at fdb7d76). "
    "Prompt provenance identical across every run (`prompts=8a683cfec1c99d66`).")

# ---------------------------------------------------------------- multiplicity (global)
gh = holm(ALL_P)
sig = sorted(k for k, v in gh.items() if v <= 0.01)
out(f"\n## Multiplicity across all {len(ALL_P)} paired tests\n\nHolm-adjusted across all {len(ALL_P)} tests at once, the contrasts with adjusted p ≤ 0.01 are: " + "; ".join(f"{k.split(':',1)[1].replace(' | ', ' / ')} ({pfmt(gh[k])})" for k in sig) + ". Every other contrast, including the three positive orchestration differences (DeepSeek debate, GPT debate, GPT chunked), does not reach 0.01 after correction within its own family or globally.")

# ---------------------------------------------------------------- matcher sensitivity
out("\n## Matcher sensitivity (added 2026-09-27)\n\nA level-1 match needs the resource address plus at least one category cue (score 0.5); a CWE-level match needs the resource plus the same CWE. Single-cue and CWE-level matches are the ones most exposed to wrong-target credit. `F1 strict` treats every such match as a false positive and its finding as missed: a lower bound on what a stricter matcher could report, not a corrected score.\n")
out("| Model | Configuration | TP | single-cue TP | CWE-level TP | F1 | F1 strict |\n|---|---|---|---|---|---|---|")
strict_rows = []
for p in sorted(SCORED.glob("*.json")):
    tag = p.stem; rs = runs(tag); tp = one = cwe = fp = fn = 0
    for r in rs:
        truth = GT.get(f"terragoat_mut::{r['file']}", [])
        m, uc, ug = match_findings(r["findings"], truth)
        tp += len(m); one += sum(1 for x in m if x.level == "resource_issue" and x.score < 3.0)
        cwe += sum(1 for x in m if x.level == "cwe"); fp += len(uc); fn += len(ug)
    f1 = lambda a, b, c: (2*a/(2*a+b+c)) if a else 0.0
    st = tp - one - cwe
    cfg = tag.split("__"); label = f"{cfg[1]} / {cfg[2]}" + (" / reasoning on" if tag.endswith("__think") else "")
    out(f"| {NAME[cfg[0]]} | {label} | {tp} | {one} | {cwe} | {f1(tp, fp, fn):.3f} | {f1(st, fp+one+cwe, fn+one+cwe):.3f} |")
    strict_rows.append((tag, tp, one, cwe))
T1 = sum(r[1] for r in strict_rows); O1 = sum(r[2] for r in strict_rows); C1 = sum(r[3] for r in strict_rows)
out(f"\nAcross all 36 configurations: {T1} accepted matches, {O1} single-cue ({100*O1/T1:.1f}%), {C1} CWE-level ({100*C1/T1:.1f}%).")

# ---------------------------------------------------------------- DeepSeek repricing
import datetime
def _peak(ts):
    t = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"); return t.weekday() < 5 and (1 <= t.hour < 4 or 6 <= t.hour < 10)
def _cur(inp, outp, hit, pk):
    return inp/1e6*((0.006 if pk else 0.003) if hit else (0.30 if pk else 0.15)) + outp/1e6*(1.2 if pk else 0.6)
ds = runs("deepseek-v4-flash__system_enriched__single__terragoat_mut"); hit = miss = 0.0
for r in ds:
    pk = _peak(r["timestamp"])
    for st_ in (r.get("steps") or [{"input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"]}]):
        hit += _cur(st_.get("input_tokens", 0), st_.get("output_tokens", 0), True, pk); miss += _cur(st_.get("input_tokens", 0), st_.get("output_tokens", 0), False, pk)
out(f"\n## DeepSeek tariff note (added 2026-09-27)\n\nEvery cost figure uses the August 2026 list prices hard-coded in `providers.py` (DeepSeek $0.14 / $0.28 per million input / output tokens). DeepSeek's schedule for `deepseek-flash` on 2026-09-27 is cache-aware and time-of-day dependent ($0.15 / $0.30 per million input tokens on a cache miss, $0.003 / $0.006 on a cache hit, $0.60 / $1.20 output, off-peak / peak UTC). Repricing the 30 baseline DeepSeek runs by their timestamps and token counts gives ${hit:.4f} (every input token a cache hit) to ${miss:.4f} (every input token a cache miss) against ${S('deepseek-v4-flash__system_enriched__single__terragoat_mut')['cost_usd']:.4f} at the constant tariff. Cache statistics and invoices were not retained; the constant-tariff figures remain the study's cost basis.")


# ---------------------------------------------------------------- run accounting, chunking, ceiling (2026-09-28)
_all = [json.loads(p.read_text()) for p in RES.glob("*.json")]
_calls = {}
for r in _all: _calls[r["pattern"]] = _calls.get(r["pattern"], 0) + r["n_calls"]
_ncfg = {"prompt": len([p for p in SCORED.glob("*__single__terragoat_mut.json")]),
         "pattern": len([p for p in SCORED.glob("*.json") if "__single__" not in p.name]),
         "reasoning": len([p for p in SCORED.glob("*__think.json")])}
_tpfn = sorted({S(p.stem)["overall"]["totals"]["tp"] + S(p.stem)["overall"]["totals"]["fn"] for p in SCORED.glob("*.json")})
out(f"\n## Run accounting (added 2026-09-28)\n\n{_ncfg['prompt']} model-and-prompt configurations (single call, reasoning off), {_ncfg['pattern']} model-and-pattern configurations beyond the single call, and {_ncfg['reasoning']} reasoning-on configurations share the system_enriched single call as baseline: {_ncfg['prompt'] + _ncfg['pattern'] + _ncfg['reasoning']} configurations. "
    f"A run is one review of one file. API calls per run: single {_calls['single'] // 720}, critic {_calls['critic'] // 120}, debate {_calls['debate'] // 120}, chunked {_calls['chunked'] / 120:.2f} on average ({_calls['chunked']} calls over 120 runs); {sum(_calls.values()):,} calls in all. "
    f"Every configuration scores 52 findings x 5 repetitions, so TP + FN = {_tpfn[0] if len(_tpfn) == 1 else _tpfn} in every configuration.")

_sizes = {f: len((ROOT / "terragoat_mut/terraform/aws" / f).read_text()) for f in FILES}
_chunks = {}
for r in _all:
    if r["pattern"] == "chunked": _chunks.setdefault(r["file"], set()).add(r["chunks"])
out("\n## Chunking by file (added 2026-09-28)\n\nThe chunked pattern packs whole top-level blocks into chunks of at most 2,500 characters (`agents/hcl.py`), so a file under the budget is sent whole in one call, under `prompts.CHUNK_HEADER`, which presents the text as an excerpt and forbids findings on resources not shown.\n\n| File | Characters | Chunks |\n|---|---|---|")
for f in FILES: out(f"| {f} | {_sizes[f]:,} | {', '.join(str(c) for c in sorted(_chunks[f]))} |")
def _f1(tp, fp, fn):
    p_ = tp / (tp + fp) if tp + fp else 0; r_ = tp / (tp + fn) if tp + fn else 0
    return 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
_split = {"db-app.tf", "ec2.tf"}
out("\nSingle-call versus chunked, pooled over the split files (db-app.tf, ec2.tf) and the unsplit files (iam.tf, kms.tf, lambda.tf, s3.tf):\n\n| Model | Files | TP single → chunked | FP single → chunked | F1 single → chunked | ΔF1 |\n|---|---|---|---|---|---|")
for m in MODELS:
    a = S(f"{m}__system_enriched__single__terragoat_mut")["per_file"]; b = S(f"{m}__system_enriched__chunked__terragoat_mut")["per_file"]
    for lab, sel in (("split", _split), ("unsplit", set(FILES) - _split)):
        ta = [sum(a[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]; tb = [sum(b[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]
        out(f"| {NAME[m]} | {lab} | {ta[0]} → {tb[0]} | {ta[1]} → {tb[1]} | {_f1(*ta):.3f} → {_f1(*tb):.3f} | {_f1(*tb) - _f1(*ta):+.3f} |")
from match import match_findings as _mf
_cnt = {}
for pat in ("single", "chunked"):
    for r in runs(f"claude-opus-5__system_enriched__{pat}__terragoat_mut"):
        if r["file"] != "s3.tf": continue
        for x in _mf(r["findings"], GT["terragoat_mut::s3.tf"])[0]: _cnt[(pat, x.gt_id)] = _cnt.get((pat, x.gt_id), 0) + 1
_s3 = [g for g in GT["terragoat_mut::s3.tf"] if g["checkov_id"] == "CKV2_AWS_6"]
out("\nClaude Opus 5 on s3.tf (one chunk; sent whole under the chunk header), CKV2_AWS_6 public-access-block findings matched in 5 runs, single → chunked: " + "; ".join(f"{g['resource']} {_cnt.get(('single', g['id']), 0)} → {_cnt.get(('chunked', g['id']), 0)}" for g in _s3) + ".")

CEIL = {"claude-opus-5": 8000, "claude-sonnet-5": 8000, "gpt-5.6-terra": 8000, "deepseek-v4-flash": 16000}
out("\n## Reasoning-on output ceiling (added 2026-09-28; DeepSeek arm rerun 2026-09-29)\n\n`max_tokens` is 4,096 on every reasoning-off call. With reasoning on, `providers.py` raises the ceiling to 8,000 for the Claude (`max_tokens`) and GPT (`max_output_tokens`, /v1/responses) calls and to 16,000 for the DeepSeek chat/completions call. The DeepSeek ceiling was raised twice: the September 20-22 runs kept 4,096 and eight of 30 stopped at exactly that ceiling before returning a findings list (six with no content, two with prose); a rerun on 2026-09-29 at 8,000 still stopped one of 30 at the ceiling. The reported arm is the 2026-09-29 rerun at 16,000, chosen so that the ceiling does not bind; no run reached it. Both superseded arms are retained with their scored summaries in `harness/results_superseded/` (`..._think_4096/`, `..._think_8000/`); every rerun response was served as `deepseek-flash`, the identifier the September runs recorded, and `providers_sha` in each rerun file records the provider code.\n\n| Model | Ceiling | Reasoning-on runs at the ceiling | Of which empty findings | Max output tokens seen |\n|---|---|---|---|---|")
for m in MODELS:
    rr = runs(f"{m}__system_enriched__single__terragoat_mut__think")
    at = [r for r in rr if r["output_tokens"] >= CEIL[m]]
    out(f"| {NAME[m]} | {CEIL[m]:,} | {len(at)} | {sum(1 for r in at if not r['findings'])} | {max(r['output_tokens'] for r in rr):,} |")
for _lab, _ceil in (("4096", 4096), ("8000", 8000)):
    _d = ROOT / f"harness/results_superseded/deepseek-v4-flash__system_enriched__single__terragoat_mut__think_{_lab}"
    _r = [json.loads(p.read_text()) for p in _d.glob("deepseek-*.json")]
    _s = json.loads((_d / "scored_summary.json").read_text())
    out(f"\nSuperseded DeepSeek reasoning-on arm at {_ceil:,} ({len(_r)} runs, {min(r['timestamp'] for r in _r)[:10]} to {max(r['timestamp'] for r in _r)[:10]}): F1 {_s['overall']['f1']:.3f}, {sum(1 for r in _r if r['output_tokens'] >= _ceil)} runs at the ceiling, {sum(1 for r in _r if not r['findings'])} scored as empty.")
out(f"\nReported DeepSeek reasoning-on arm at 16,000 ({min(r['timestamp'] for r in runs('deepseek-v4-flash__system_enriched__single__terragoat_mut__think'))[:10]}): F1 {S('deepseek-v4-flash__system_enriched__single__terragoat_mut__think')['overall']['f1']:.3f}, longest response {max(r['output_tokens'] for r in runs('deepseek-v4-flash__system_enriched__single__terragoat_mut__think')):,} tokens.")

out("""
## Corpus note (2026-09-22)

The first mutated corpus (used for runs on 2026-09-20) carried a defect: the string-fragment rule `og-` → `catalogopts-` matched inside `log-delivery-write`, turning the `audit_trail` bucket's ACL into the invalid value `lcatalogopts-delivery-write`, and sequential replacement double-substituted several identifier strings in db-app.tf (`catalcatalogopts-`). Neither touched a ground-truth attribute, and Checkov's 95/95 result held, but two models flagged the invalid ACL as a finding. `mutate_corpus.py` was fixed (single-pass, boundary-anchored replacement), the corpus regenerated, Checkov re-validated (95/95, zero drift), and every run on the two affected files (s3.tf, db-app.tf; 180 runs across the 18 configurations then existing) was redone. The other four files were byte-identical before and after and their runs stand. One DeepSeek reasoning run failed on a dropped connection (IncompleteRead) and was redone; that exception is now retryable in `providers.py`. The 18 configurations added on 2026-09-26 (context variants on Opus, GPT and DeepSeek; orchestration on GPT and DeepSeek) ran on the corrected corpus only.
""")

# ---------------------------------------------------------------- adjudication
adj = json.loads((ROOT / "harness/fp_review/set1_fp_adjudicated.json").read_text()); rows = adj["rows"]
out("## Unmatched-claim (false-positive) adjudication — Set 1, reasoning off\n")
SHORT = {"claude-opus-5": "Opus", "deepseek-v4-flash": "DeepSeek", "claude-sonnet-5": "Sonnet", "gpt-5.6-terra": "GPT"}
out(f"Every unmatched claim ({len(rows)}: " + ", ".join(f"{SHORT[m]} {sum(1 for r in rows if r['model']==m)}" for m in ["claude-opus-5","deepseek-v4-flash","claude-sonnet-5","gpt-5.6-terra"]) +
    ") was classified into one of four buckets. First pass by Claude (an Anthropic model; disclosed), then reviewed row by row by the author, whose verdict governs. Sheet: `harness/fp_review/set1_fp_review.xlsx`.\n")
out("Buckets: **A** real vulnerability outside the oracle's rule coverage; **B** true observation excluded by the study criteria (recovery controls, passive logging, tags, hardening without an attack path, design facts); **C** model error; **D** duplicate of a finding credited elsewhere in the same run (including matcher attribution).\n")
out("Adjusted precision = (TP + A) / (TP + FP); a second figure also credits D. Recall is unaffected.\n")
out("| Model | A real | B excluded | C wrong | D duplicate | FP | Raw P | Adjusted P (A) | Adjusted P (A+D) | Recall | Raw F1 | Adjusted F1 (A) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
for m in ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-terra", "deepseek-v4-flash"]:
    t = S(f"{m}__system_enriched__single__terragoat_mut")["overall"]["totals"]; tp, fp, fn = t["tp"], t["fp"], t["fn"]
    cnt = {k: sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == k) for k in (A, B, C, D)}
    rec = tp/(tp+fn); rawp = tp/(tp+fp); adjp = (tp+cnt[A])/(tp+fp)
    out(f"| {NAME[m]} | {cnt[A]} | {cnt[B]} | {cnt[C]} | {cnt[D]} | {fp} | {rawp:.3f} | {adjp:.3f} | {(tp+cnt[A]+cnt[D])/(tp+fp):.3f} | {rec:.3f} | {2*rawp*rec/(rawp+rec):.3f} | {2*adjp*rec/(adjp+rec):.3f} |")
out("\nOutput-pathway sensitivity (added 2026-09-27): some bucket-A claims on iam.tf attribute the access-key exposure to the Terraform output. Without `pgp_key` the `encrypted_secret` attribute that the output references is empty, so the output pathway exposes nothing; the plaintext `secret` in state does. Withholding the A credit from every iam.tf claim whose description names the output gives:\n")
out("| Model | A credits withheld | Adjusted P (A) | Adjusted P without output-pathway credits |\n|---|---|---|---|")
for m in ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-terra", "deepseek-v4-flash"]:
    t = S(f"{m}__system_enriched__single__terragoat_mut")["overall"]["totals"]; tp, fp = t["tp"], t["fp"]
    a_all = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A)
    a_out = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A and r["file"] == "iam.tf" and "output" in r["description"].lower())
    out(f"| {NAME[m]} | {a_out} | {(tp+a_all)/(tp+fp):.3f} | {(tp+a_all-a_out)/(tp+fp):.3f} |")
out(f"\nReviewed row by row by the author on {adj['review']['date']}; all {adj['review']['rows']} first-pass verdicts accepted (agreement {adj['review']['rows']}/{adj['review']['rows']}). "
    "Outright model errors are rare (5 of 177). The largest single source of unmatched claims is bucket B on S3 buckets (versioning, access logging, `force_destroy`), which Opus and DeepSeek report on nearly every bucket in every run. "
    "The most common bucket-A findings: database credentials interpolated into EC2 `user_data` (all four models), the IAM access-key secret in state and in an output (all four), MySQL ingress scoped to the whole VPC rather than the application security group, snapshots of unencrypted volumes, and missing TLS-only bucket policies.")
