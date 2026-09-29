#!/usr/bin/env python3
"""
Recompute every number in RESULTS.md from the raw result files and fail on any
mismatch. RESULTS.md is the single source the paper's tables are copied from,
so if this passes, every figure in the paper traces back to harness/results/.

    python3 harness/verify_paper.py

Needs only the repository: harness/results/, harness/scored/, data/, RESULTS.md,
harness/fp_review/set1_fp_adjudicated.json. No API key, no network.

Checks, in order:
  1. inventory      1080 runs, 36 configurations, zero error runs, one prompt hash,
                    ground truth 52/6, Checkov diff recorded and empty
  2. re-derivation  every scored/*.json re-computes from its raw runs
  3. tables         every row of every table in RESULTS.md re-computes from raw
                    runs, using the same rounding the tables use
  4. adjudication   the FP table matches the reviewer's verdicts in the JSON
  5. audit additions (2026-09-27) Holm-adjusted p-values per family and globally, the
                    matcher sensitivity table, the output-pathway sensitivity, the DeepSeek
                    tariff range
"""
from __future__ import annotations

import glob
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare import compare, holm                # noqa: E402
from match import normalise_resource             # noqa: E402
from score import score_run, summarise           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES, SCORED = ROOT / "harness" / "results", ROOT / "harness" / "scored"
GT = json.loads((ROOT / "data" / "ground_truth_mut.json").read_text())["findings"]
DOC = (ROOT / "RESULTS.md").read_text()
FAIL: list[str] = []

MODEL = {"Claude Opus 5": "claude-opus-5", "Claude Sonnet 5": "claude-sonnet-5",
         "GPT-5.6 Terra": "gpt-5.6-terra", "DeepSeek Flash": "deepseek-v4-flash"}
VARIANT = {"zero_shot": "zero_shot", "few_shot": "few_shot", "system_enriched": "system_enriched",
           "rag (guidance injection)": "rag", "chain_of_thought": "chain_of_thought"}
FILES = ["db-app.tf", "ec2.tf", "iam.tf", "kms.tf", "lambda.tf", "s3.tf"]
A, B, C, D = ("Real issue, not in answer key", "Real but excluded by our criteria",
              "Model was wrong", "Same issue reported twice")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  -- ' + detail) if (detail and not ok) else ''}")
    if not ok:
        FAIL.append(name)


def runs(tag: str) -> list[dict]:
    think = tag.endswith("__think")
    return [json.loads(p.read_text()) for p in RES.glob(f"{tag}__*.json")
            if ("__think__" in p.name) == think]


def scored(tag: str) -> dict:
    return json.loads((SCORED / f"{tag}.json").read_text())


def table(after: str) -> list[list[str]]:
    """Rows of the first markdown table that follows the given heading text."""
    i = DOC.index(after)
    rows, started = [], False
    for line in DOC[i:].splitlines()[1:]:
        if line.startswith("|"):
            started = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append(cells)
        elif started:
            break
    return rows[1:]                              # drop header


def pfmt(p: float) -> str:
    return "<0.001" if p < 0.001 else (f"{p:.2f}" if p >= 0.01 else f"{p:.3f}")


def num(s: str) -> float:
    return float(s.replace(",", "").replace("+", "").replace("**", ""))


def ci_str(o: dict) -> str:
    return f"[{o['ci']['f1'][0]:.3f}, {o['ci']['f1'][1]:.3f}]"


def perf_row_ok(tag: str, cells: list[str], offset: int) -> tuple[bool, str]:
    """P R F1 CI TP FP FN starting at cells[offset]."""
    o = scored(tag)["overall"]; t = o["totals"]
    want = [f"{o['precision']:.3f}", f"{o['recall']:.3f}", f"{o['f1']:.3f}", ci_str(o),
            str(t["tp"]), str(t["fp"]), str(t["fn"])]
    got = cells[offset:offset + 7]
    return want == got, f"want {want} got {got}"


ALL_P: dict[str, float] = {}


def paired_table_ok(heading: str, keyfn) -> None:
    """Check every row of a paired table: F1 diff | 95% CI | p | Holm p | Excludes zero (last five cells).
    keyfn(cells) -> (label, tag_a, tag_b). Holm is computed over the table's own rows (its family)."""
    rows = table(heading)
    res = [(keyfn(c), c) for c in rows]
    adj = holm({label: compare(a, b)["p_value"] for (label, a, b), _ in res})
    for (label, a, b), cells in res:
        r = compare(a, b)
        want = [f"{r['observed_f1_difference']:+.3f}", f"[{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]",
                pfmt(r["p_value"]), pfmt(adj[label]), "yes" if r["excludes_zero"] else "no"]
        got = cells[-5:]
        ALL_P[f"{heading}:{label}"] = r["p_value"]
        check(label, want == got, f"want {want} got {got}")


# ------------------------------------------------------------------ 1. inventory
print("\n== inventory ==")
allruns = [json.loads(p.read_text()) for p in RES.glob("*.json")]
check("1080 result files", len(allruns) == 1080, f"found {len(allruns)}")
check("36 scored configurations", len(list(SCORED.glob("*.json"))) == 36)
check("zero error runs", not any(r.get("error") for r in allruns))
hashes = {r["provenance"]["prompts_sha"] for r in allruns}
check("one prompt hash across every run (8a683cfec1c99d66)", hashes == {"8a683cfec1c99d66"}, str(hashes))
check("ground truth: 52 findings across 6 files",
      sum(len(v) for v in GT.values()) == 52 and len(GT) == 6)
diff = (ROOT / "data" / "mutation_checkov_diff.txt").read_text()
check("Checkov diff recorded: identical 95 / no differences",
      "identical pairs : 95" in diff and "No differences" in diff)
check("s3.tf carries the corrected ACL",
      'acl    = "log-delivery-write"' in (ROOT / "terragoat_mut/terraform/aws/s3.tf").read_text())

# ------------------------------------------------------------ 2. re-derivation
print("\n== every scored configuration re-derives from raw runs ==")
for p in sorted(SCORED.glob("*.json")):
    tag = p.stem; d = json.loads(p.read_text()); s = d["overall"]
    # Same order the runner scored in (files sorted, reps ascending): the
    # bootstrap is seeded, so resample indices must map to the same runs.
    ordered = sorted(runs(tag), key=lambda r: (r["file"], r["repetition"]))
    rs = [score_run(r["run_id"], r["findings"], GT.get(f"terragoat_mut::{r['file']}", []))
          for r in ordered]
    o = summarise(rs)
    ok = (o["n_runs"] == s["n_runs"] == 30 and o["totals"] == {k: s["totals"][k] for k in o["totals"]}
          and all(abs(o[k] - s[k]) < 5e-4 for k in ("precision", "recall", "f1"))
          and o["ci"] == s["ci"])
    check(tag, ok, f"recomputed F1={o['f1']:.4f} n={o['n_runs']} stored F1={s['f1']:.4f} n={s['n_runs']}")

# ------------------------------------------------------------------- 3. tables
print("\n== Set 1 table ==")
for cells in table("## Set 1"):
    m = MODEL[cells[0]]; tag = f"{m}__system_enriched__single__terragoat_mut"
    ok, det = perf_row_ok(tag, cells, 2)
    served = runs(tag)[0]["resolved_model"]
    cost = f"{scored(tag)['cost_usd']:.2f}"
    check(f"{cells[0]}", ok and cells[1] == served and cells[9] == cost,
          det + f"; served {served} vs {cells[1]}; cost {cost} vs {cells[9]}")

print("\n== Set 1 paired vs Opus ==")
paired_table_ok("Paired F1 difference vs Claude Opus 5",
                lambda c: (c[0], f"{MODEL[c[0]]}__system_enriched__single__terragoat_mut", "claude-opus-5__system_enriched__single__terragoat_mut"))

print("\n== per-file F1 ==")
for cells in table("Per-file F1"):
    m = MODEL[cells[0]]; pf = scored(f"{m}__system_enriched__single__terragoat_mut")["per_file"]
    want = [f"{pf[f]['f1']:.2f}" for f in FILES]
    check(cells[0], want == cells[1:7], f"want {want} got {cells[1:7]}")

print("\n== reasoning on/off table ==")
for cells in table("### Native reasoning"):
    m = MODEL[cells[0]]; tag = f"{m}__system_enriched__single__terragoat_mut" + ("__think" if cells[1] == "on" else "")
    ok, det = perf_row_ok(tag, cells, 2)
    rs = runs(tag); d = scored(tag)
    lat = f"{statistics.mean(r['latency_s'] for r in rs):.1f}"
    tok = f"{statistics.mean(r['output_tokens'] for r in rs):,.0f}"
    zero = str(sum(len(r["findings"]) == 0 for r in rs))
    nonjson = str(sum(bool((r.get("raw_text") or "").strip())
                      and not (r["raw_text"] or "").lstrip().startswith("{") for r in rs))
    extra = [lat, tok, f"{d['cost_usd']:.2f}", zero, nonjson]
    check(f"{cells[0]} reasoning {cells[1]}", ok and cells[9:14] == extra, det + f"; extra want {extra} got {cells[9:14]}")

print("\n== reasoning paired on−off ==")
paired_table_ok("Paired F1 difference, reasoning on",
                lambda c: (c[0], f"{MODEL[c[0]]}__system_enriched__single__terragoat_mut__think", f"{MODEL[c[0]]}__system_enriched__single__terragoat_mut"))

print("\n== Set 2 table ==")
for cells in table("## Set 2"):
    m = MODEL[cells[0]]; tag = f"{m}__{VARIANT[cells[1]]}__single__terragoat_mut"
    ok, det = perf_row_ok(tag, cells, 2)
    check(f"{cells[0]} {cells[1]}", ok and cells[9] == f"{scored(tag)['cost_usd']:.2f}", det)

print("\n== Set 2 paired vs zero_shot ==")
paired_table_ok("Paired F1 difference vs the same model's zero_shot",
                lambda c: (f"{c[0]} {c[1]}", f"{MODEL[c[0]]}__{VARIANT[c[1]]}__single__terragoat_mut", f"{MODEL[c[0]]}__zero_shot__single__terragoat_mut"))

print("\n== Set 2 compact ==")
for cells in table("F1 by model and variant"):
    m = MODEL[cells[0]]
    want = [f"{scored(f'{m}__{c}__single__terragoat_mut')['overall']['f1']:.3f}"
            for c in ["zero_shot", "few_shot", "system_enriched", "rag", "chain_of_thought"]]
    check(cells[0], want == cells[1:6], f"want {want} got {cells[1:6]}")

print("\n== Set 3 table ==")
for cells in table("## Set 3"):
    m = MODEL[cells[0]]; tag = f"{m}__system_enriched__{cells[1]}__terragoat_mut"
    ok, det = perf_row_ok(tag, cells, 2)
    rs = runs(tag); d = scored(tag); base = scored(f"{m}__system_enriched__single__terragoat_mut")["cost_usd"] / 30
    extra = [f"{statistics.mean(r.get('n_calls', 1) for r in rs):.1f}",
             f"{statistics.mean(r['latency_s'] for r in rs):.1f}",
             f"{d['cost_usd'] / 30:.4f}", f"{(d['cost_usd'] / 30) / base:.1f}"]
    check(f"{cells[0]} {cells[1]}", ok and cells[9:13] == extra, det + f"; extra want {extra} got {cells[9:13]}")

print("\n== Set 3 paired vs single ==")
paired_table_ok("Paired F1 difference vs same-model single",
                lambda c: (f"{c[0]} {c[1]}", f"{MODEL[c[0]]}__system_enriched__{c[1]}__terragoat_mut", f"{MODEL[c[0]]}__system_enriched__single__terragoat_mut"))

print("\n== Set 3 compact ==")
for cells in table("F1 by model and pattern"):
    m = MODEL[cells[0]]
    want = [f"{scored(f'{m}__system_enriched__{p}__terragoat_mut')['overall']['f1']:.3f}"
            for p in ["single", "critic", "debate", "chunked"]]
    check(cells[0], want == cells[1:5], f"want {want} got {cells[1:5]}")

print("\n== mechanism sentence ==")
mech = DOC[DOC.index("Mechanism:"):].split("\n", 1)[0]
steps = lambda r: {s["step"]: s for s in r["steps"]}                     # noqa: E731
for m, name in ((k, v) for v, k in MODEL.items()):
    rs = runs(f"{m}__system_enriched__critic__terragoat_mut")
    want = (f"{name} critic: {sum(steps(r)['review']['n_findings'] for r in rs)} → "
            f"{sum(steps(r)['critique']['n_findings'] for r in rs)} findings, shrank in "
            f"{sum(steps(r)['critique']['n_findings'] < steps(r)['review']['n_findings'] for r in rs)}/30 runs")
    check(want, want in mech)
    rs = runs(f"{m}__system_enriched__debate__terragoat_mut")
    want = (f"{name} debate: reviewers {sum(steps(r)['reviewer_a']['n_findings'] for r in rs)}/"
            f"{sum(steps(r)['reviewer_b']['n_findings'] for r in rs)} → reconciled "
            f"{sum(steps(r)['reconciler']['n_findings'] for r in rs)}")
    check(want, want in mech)
man = json.loads((ROOT / "data" / "terragoat_resources.json").read_text())["resources"]
ren = json.loads((ROOT / "data" / "rename_map.json").read_text())["renames"]
valid = {f: {normalise_resource(ren.get(x, x)) for x in v} for f, v in man.items()}
for m, name in ((k, v) for v, k in MODEL.items()):
    for pat in ("single", "chunked"):
        tot = bad = 0
        for r in runs(f"{m}__system_enriched__{pat}__terragoat_mut"):
            for c in r["findings"]:
                tot += 1; bad += normalise_resource(c.get("resource", "")) not in valid[r["file"]]
        want = f"{name} {pat} {bad}/{tot}"
        check(f"fabricated addresses: {want}", want in mech)

print("\n== study totals ==")
tot = sum(scored(p.stem)["cost_usd"] for p in SCORED.glob("*.json"))
check("36 configurations, 1080 runs stated", "36 configurations, 1080 runs" in DOC)
check(f"total spend ≈ ${tot:.2f} stated", f"≈ ${tot:.2f}" in DOC)

print("\n== global Holm sentence ==")
gh = holm(ALL_P)
check("35 paired tests collected", len(ALL_P) == 35, str(len(ALL_P)))
sig = sorted(k for k, v in gh.items() if v <= 0.01)
mult = DOC[DOC.index("## Multiplicity"):].split("\n\n", 2)[1]
for k in sig:
    label = k.split(":", 1)[1]
    check(f"global Holm ≤ 0.01: {label} ({pfmt(gh[k])})", f"({pfmt(gh[k])})" in mult and label.split(" ")[0] in mult)
check("global Holm: exactly the listed contrasts", mult.count("(") == len(sig) + 1, f"{mult.count('(')} vs {len(sig)}")

print("\n== matcher sensitivity table ==")
from match import match_findings                 # noqa: E402
f1x = lambda a, b, c: (2 * a / (2 * a + b + c)) if a else 0.0   # noqa: E731
CFGNAME = {v: k for k, v in MODEL.items()}
tot_tp = tot_one = tot_cwe = 0
for cells in table("## Matcher sensitivity"):
    m = MODEL[cells[0]]; parts = cells[1].split(" / ")
    tag = f"{m}__{parts[0]}__{parts[1]}__terragoat_mut" + ("__think" if len(parts) == 3 else "")
    tp = one = cwe = fp = fn = 0
    for r in runs(tag):
        mt, uc, ug = match_findings(r["findings"], GT.get(f"terragoat_mut::{r['file']}", []))
        tp += len(mt); one += sum(1 for x in mt if x.level == "resource_issue" and x.score < 3.0)
        cwe += sum(1 for x in mt if x.level == "cwe"); fp += len(uc); fn += len(ug)
    tot_tp += tp; tot_one += one; tot_cwe += cwe
    want = [str(tp), str(one), str(cwe), f"{f1x(tp, fp, fn):.3f}", f"{f1x(tp - one - cwe, fp + one + cwe, fn + one + cwe):.3f}"]
    check(f"{cells[0]} {cells[1]}", want == cells[2:7], f"want {want} got {cells[2:7]}")
check(f"matcher totals {tot_tp}/{tot_one}/{tot_cwe}",
      f"{tot_tp} accepted matches, {tot_one} single-cue ({100*tot_one/tot_tp:.1f}%), {tot_cwe} CWE-level ({100*tot_cwe/tot_tp:.1f}%)" in DOC)

print("\n== DeepSeek tariff note ==")
import datetime                                  # noqa: E402
def _peak(ts):
    t = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"); return t.weekday() < 5 and (1 <= t.hour < 4 or 6 <= t.hour < 10)
def _cur(i, o, hit, pk):
    return i / 1e6 * ((0.006 if pk else 0.003) if hit else (0.30 if pk else 0.15)) + o / 1e6 * (1.2 if pk else 0.6)
hit = miss = 0.0
for r in runs("deepseek-v4-flash__system_enriched__single__terragoat_mut"):
    pk = _peak(r["timestamp"])
    for st in (r.get("steps") or [{"input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"]}]):
        hit += _cur(st.get("input_tokens", 0), st.get("output_tokens", 0), True, pk); miss += _cur(st.get("input_tokens", 0), st.get("output_tokens", 0), False, pk)
check(f"repriced range ${hit:.4f} to ${miss:.4f} stated", f"gives ${hit:.4f} (every input token a cache hit) to ${miss:.4f}" in DOC)

# ------------------------------------------------------------- 4. adjudication
print("\n== run accounting, chunking, ceiling (2026-09-28) ==")
_all = [json.loads(p.read_text()) for p in RES.glob("*.json")]
_calls = {}
for r in _all: _calls[r["pattern"]] = _calls.get(r["pattern"], 0) + r["n_calls"]
check("1,540 API calls (720 single, 240 critic, 360 debate, 220 chunked) stated",
      _calls == {"single": 720, "critic": 240, "debate": 360, "chunked": 220} and "1,540 calls in all" in DOC, str(_calls))
check("20 + 12 + 4 configurations stated", "20 model-and-prompt configurations" in DOC and "12 model-and-pattern" in DOC and "4 reasoning-on" in DOC)
check("TP + FN = 260 in every configuration", all(scored(p.stem)["overall"]["totals"]["tp"] + scored(p.stem)["overall"]["totals"]["fn"] == 260 for p in SCORED.glob("*.json")) and "TP + FN = 260" in DOC)
_chunks = {}
for r in _all:
    if r["pattern"] == "chunked": _chunks.setdefault(r["file"], set()).add(r["chunks"])
check("chunk counts db-app 4, ec2 3, others 1", {f: sorted(v) for f, v in _chunks.items()} == {"db-app.tf": [4], "ec2.tf": [3], "iam.tf": [1], "kms.tf": [1], "lambda.tf": [1], "s3.tf": [1]}, str(_chunks))
for f in FILES:
    check(f"chunking table row {f}", f"| {f} | {len((ROOT / 'terragoat_mut/terraform/aws' / f).read_text()):,} | {sorted(_chunks[f])[0]} |" in DOC)
def _f1(tp, fp, fn):
    p_ = tp / (tp + fp) if tp + fp else 0; r_ = tp / (tp + fn) if tp + fn else 0
    return 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
for cells in table("Single-call versus chunked"):
    m = MODEL[cells[0]]; sel = {"db-app.tf", "ec2.tf"} if cells[1] == "split" else set(FILES) - {"db-app.tf", "ec2.tf"}
    a = scored(f"{m}__system_enriched__single__terragoat_mut")["per_file"]; b = scored(f"{m}__system_enriched__chunked__terragoat_mut")["per_file"]
    ta = [sum(a[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]; tb = [sum(b[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]
    want = [f"{ta[0]} → {tb[0]}", f"{ta[1]} → {tb[1]}", f"{_f1(*ta):.3f} → {_f1(*tb):.3f}", f"{_f1(*tb) - _f1(*ta):+.3f}"]
    check(f"{cells[0]} {cells[1]} chunking row", want == cells[2:6], f"want {want} got {cells[2:6]}")
_cnt = {}
for pat in ("single", "chunked"):
    for r in runs(f"claude-opus-5__system_enriched__{pat}__terragoat_mut"):
        if r["file"] == "s3.tf":
            for x in match_findings(r["findings"], GT["terragoat_mut::s3.tf"])[0]: _cnt[(pat, x.gt_id)] = _cnt.get((pat, x.gt_id), 0) + 1
_s3 = [g for g in GT["terragoat_mut::s3.tf"] if g["checkov_id"] == "CKV2_AWS_6"]
check("Opus s3.tf CKV2_AWS_6 per-bucket counts stated", "; ".join(f"{g['resource']} {_cnt.get(('single', g['id']), 0)} → {_cnt.get(('chunked', g['id']), 0)}" for g in _s3) in DOC)
CEIL = {"claude-opus-5": 8000, "claude-sonnet-5": 8000, "gpt-5.6-terra": 8000, "deepseek-v4-flash": 16000}
for cells in table("## Reasoning-on output ceiling"):
    m = MODEL[cells[0]]; rr = runs(f"{m}__system_enriched__single__terragoat_mut__think")
    at = [r for r in rr if r["output_tokens"] >= CEIL[m]]
    want = [f"{CEIL[m]:,}", str(len(at)), str(sum(1 for r in at if not r["findings"])), f"{max(r['output_tokens'] for r in rr):,}"]
    check(f"{cells[0]} ceiling row", want == cells[1:5], f"want {want} got {cells[1:5]}")
_ds = runs("deepseek-v4-flash__system_enriched__single__terragoat_mut__think")
check("DeepSeek reasoning arm: 30 runs dated 2026-09-29, all served as deepseek-flash, providers_sha recorded, none at 16,000, none empty",
      len(_ds) == 30 and all(r["timestamp"].startswith("2026-09-29") for r in _ds)
      and all(r["resolved_model"] == "deepseek-flash" for r in _ds) and all(r["provenance"].get("providers_sha") for r in _ds)
      and all(r["output_tokens"] < 16000 and r["findings"] for r in _ds))
_nc = sorted(r["run_id"] for r in _all if not r["findings"] and not (r.get("raw_text") or "").strip().startswith("{"))
check("exactly one run in the reported data returned no parsable content (DeepSeek chain_of_thought lambda.tf r3), stated in Study totals",
      _nc == ["deepseek-v4-flash__chain_of_thought__single__terragoat_mut__lambda.tf__r3"] and f"1 run returned no parsable content and is scored as an empty findings list: {_nc[0]}" in DOC)
check("no reasoning-on run of any model reached its ceiling",
      all(r["output_tokens"] < CEIL[m] for m in MODEL.values() for r in runs(f"{m}__system_enriched__single__terragoat_mut__think")))
for _lab, _ceil, _at, _empty in (("4096", 4096, 8, 8), ("8000", 8000, 1, 1)):
    _d = ROOT / f"harness/results_superseded/deepseek-v4-flash__system_enriched__single__terragoat_mut__think_{_lab}"
    _r = [json.loads(p.read_text()) for p in _d.glob("deepseek-*.json")]
    _s = json.loads((_d / "scored_summary.json").read_text())
    check(f"superseded DeepSeek arm at {_ceil} retained: 30 runs, {_at} at the ceiling, {_empty} empty, F1 stated",
          len(_r) == 30 and sum(1 for r in _r if r["output_tokens"] >= _ceil) == _at and sum(1 for r in _r if not r["findings"]) == _empty
          and f"Superseded DeepSeek reasoning-on arm at {_ceil:,} (30 runs" in DOC and f"F1 {_s['overall']['f1']:.3f}, {_at} runs at the ceiling, {_empty} scored as empty." in DOC)
check("reported DeepSeek arm F1 stated", f"Reported DeepSeek reasoning-on arm at 16,000 (2026-09-29): F1 {scored('deepseek-v4-flash__system_enriched__single__terragoat_mut__think')['overall']['f1']:.3f}" in DOC)

print("\n== false-positive adjudication ==")
adj = json.loads((ROOT / "harness/fp_review/set1_fp_adjudicated.json").read_text())
rows = adj["rows"]
check("177 unmatched claims adjudicated, none reasoning-on",
      len(rows) == 177 and not any("__think__" in r["run_id"] for r in rows))
check("every row carries a reviewer verdict", all(r.get("reviewer_verdict") in (A, B, C, D) for r in rows))
# the unmatched set itself re-derives from the raw runs
from match import match_findings                 # noqa: E402
rederived = 0
for r in runs("claude-opus-5__system_enriched__single__terragoat_mut") + \
         runs("claude-sonnet-5__system_enriched__single__terragoat_mut") + \
         runs("gpt-5.6-terra__system_enriched__single__terragoat_mut") + \
         runs("deepseek-v4-flash__system_enriched__single__terragoat_mut"):
    _, unmatched, _ = match_findings(r["findings"], GT.get(f"terragoat_mut::{r['file']}", []))
    rederived += len(unmatched)
check("unmatched-claim count re-derives (177)", rederived == 177, str(rederived))
for cells in table("## Unmatched-claim"):
    m = MODEL[cells[0]]; t = scored(f"{m}__system_enriched__single__terragoat_mut")["overall"]["totals"]
    tp, fp, fn = t["tp"], t["fp"], t["fn"]
    cnt = {k: sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == k) for k in (A, B, C, D)}
    rec = tp / (tp + fn); rawp = tp / (tp + fp); adjp = (tp + cnt[A]) / (tp + fp)
    want = [str(cnt[A]), str(cnt[B]), str(cnt[C]), str(cnt[D]), str(fp), f"{rawp:.3f}", f"{adjp:.3f}",
            f"{(tp + cnt[A] + cnt[D]) / (tp + fp):.3f}", f"{rec:.3f}",
            f"{2 * rawp * rec / (rawp + rec):.3f}", f"{2 * adjp * rec / (adjp + rec):.3f}"]
    check(f"{cells[0]} adjudication row", want == cells[1:12], f"want {want} got {cells[1:12]}")
for cells in table("Output-pathway sensitivity"):
    m = MODEL[cells[0]]; t = scored(f"{m}__system_enriched__single__terragoat_mut")["overall"]["totals"]; tp, fp = t["tp"], t["fp"]
    a_all = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A)
    a_out = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A and r["file"] == "iam.tf" and "output" in r["description"].lower())
    want = [str(a_out), f"{(tp + a_all) / (tp + fp):.3f}", f"{(tp + a_all - a_out) / (tp + fp):.3f}"]
    check(f"{cells[0]} output-pathway sensitivity", want == cells[1:4], f"want {want} got {cells[1:4]}")

print()
if FAIL:
    print(f"{len(FAIL)} CHECK(S) FAILED"); sys.exit(1)
print("every figure in RESULTS.md reproduces from harness/results/")
