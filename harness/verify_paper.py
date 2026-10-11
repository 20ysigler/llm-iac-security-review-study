#!/usr/bin/env python3
"""
Recompute every number in RESULTS.md and SUPPLEMENT.md from the raw run files
and fail on any mismatch. RESULTS.md is the single source the paper's tables
are copied from, so if this passes, every figure in the paper traces back to
harness/results/.

    python3 harness/verify_paper.py

Needs only the repository: harness/results/, harness/scored/, data/,
harness/fp_review/set1_fp_adjudicated.json, RESULTS.md, SUPPLEMENT.md. No API
key, no network.

Checks, in order:
  1. inventory      1,080 runs, 36 configurations, zero error runs, one prompt
                    hash, ground truth 52 findings in 6 files, Checkov diff
                    recorded and empty, corpus carries the corrected ACL
  2. re-derivation  every scored/*.json re-computes from its raw runs
  3. tables         every row of every table in RESULTS.md re-computes from the
                    raw runs, with the same rounding the tables use
  4. adjudication   Table 5 matches the reviewer's verdicts in the JSON and the
                    unmatched-claim set re-derives from the raw runs
  5. supplement     the Holm table (family-wise and across all 35 tests), the
                    36-configuration matcher-sensitivity table, and the
                    output-ceiling table re-compute
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare import compare, holm                # noqa: E402
from match import match_findings                 # noqa: E402
from match import normalise_resource             # noqa: E402
from score import score_run, summarise           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES, SCORED = ROOT / "harness" / "results", ROOT / "harness" / "scored"
GT = json.loads((ROOT / "data" / "ground_truth_mut.json").read_text())["findings"]
DOC = (ROOT / "RESULTS.md").read_text()
SUP = (ROOT / "SUPPLEMENT.md").read_text()
FAIL: list[str] = []

MODEL = {"Claude Opus 5": "claude-opus-5", "Claude Sonnet 5": "claude-sonnet-5",
         "GPT-5.6 Terra": "gpt-5.6-terra", "DeepSeek Flash": "deepseek-v4-flash"}
VARIANT = {"zero_shot": "zero_shot", "few_shot": "few_shot", "system_enriched": "system_enriched",
           "rag (guidance injection)": "rag", "chain_of_thought": "chain_of_thought"}
FILES = ["db-app.tf", "ec2.tf", "iam.tf", "kms.tf", "lambda.tf", "s3.tf"]
CEIL = {"claude-opus-5": 8000, "claude-sonnet-5": 8000, "gpt-5.6-terra": 8000, "deepseek-v4-flash": 16000}
A, B, C, D = ("Real issue, not in answer key", "Real but excluded by our criteria",
              "Model was wrong", "Same issue reported twice")
BASE = "__system_enriched__single__terragoat_mut"


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


def table(after: str, doc: str = DOC) -> list[list[str]]:
    """Rows of the first markdown table that follows the given heading text."""
    i = doc.index(after)
    rows, started = [], False
    for line in doc[i:].splitlines()[1:]:
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


def ci_str(o: dict) -> str:
    return f"[{o['ci']['f1'][0]:.3f}, {o['ci']['f1'][1]:.3f}]"


def f1_of(tp: int, fp: int, fn: int) -> float:
    p_ = tp / (tp + fp) if tp + fp else 0; r_ = tp / (tp + fn) if tp + fn else 0
    return 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0


def perf_row_ok(tag: str, cells: list[str], offset: int) -> tuple[bool, str]:
    """Precision, recall, F1, CI, TP, FP, FN starting at cells[offset]."""
    o = scored(tag)["overall"]; t = o["totals"]
    want = [f"{o['precision']:.3f}", f"{o['recall']:.3f}", f"{o['f1']:.3f}", ci_str(o),
            str(t["tp"]), str(t["fp"]), str(t["fn"])]
    got = cells[offset:offset + 7]
    return want == got, f"want {want} got {got}"


def strict(tag: str) -> tuple[int, int, int, int, int]:
    tp = one = cwe = fp = fn = 0
    for r in runs(tag):
        mt, uc, ug = match_findings(r["findings"], GT.get(f"terragoat_mut::{r['file']}", []))
        tp += len(mt); one += sum(1 for x in mt if x.level == "resource_issue" and x.score < 3.0)
        cwe += sum(1 for x in mt if x.level == "cwe"); fp += len(uc); fn += len(ug)
    return tp, one, cwe, fp, fn


PAIRED: dict[str, tuple[str, str, dict]] = {}      # key -> (family, label, result)


def paired_table_ok(heading: str, family: str, keyfn) -> None:
    """Check every row of a paired table: F1 difference | 95% CI | p | Excludes zero (last four cells).
    keyfn(cells) -> (label, tag_a, tag_b)."""
    for cells in table(heading):
        label, a, b = keyfn(cells)
        r = compare(a, b)
        PAIRED[f"{family}:{label}"] = (family, label, r)
        want = [f"{r['observed_f1_difference']:+.3f}", f"[{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]",
                pfmt(r["p_value"]), "yes" if r["excludes_zero"] else "no"]
        got = cells[-4:]
        check(label, want == got, f"want {want} got {got}")


# ------------------------------------------------------------------ 1. inventory
print("\n== inventory ==")
allruns = [json.loads(p.read_text()) for p in RES.glob("*.json")]
check("1,080 result files", len(allruns) == 1080, f"found {len(allruns)}")
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
    # Same order the runner scored in (files sorted, repetitions ascending): the
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
print("\n== Table 2 ==")
for cells in table("## Table 2."):
    m = MODEL[cells[0]]; tag = f"{m}{BASE}"
    ok, det = perf_row_ok(tag, cells, 2)
    served = runs(tag)[0]["resolved_model"]
    cost = f"{scored(tag)['cost_usd']:.2f}"
    check(f"{cells[0]}", ok and cells[1] == served and cells[9] == cost,
          det + f"; served {served} vs {cells[1]}; cost {cost} vs {cells[9]}")

print("\n== Table 3 ==")
paired_table_ok("## Table 3.", "model comparison",
                lambda c: (c[0], f"{MODEL[c[0]]}{BASE}", f"claude-opus-5{BASE}"))

print("\n== Table 4 ==")
for cells in table("## Table 4."):
    m = MODEL[cells[0]]; pf = scored(f"{m}{BASE}")["per_file"]
    want = [f"{pf[f]['f1']:.2f}" for f in FILES]
    check(cells[0], want == cells[1:7], f"want {want} got {cells[1:7]}")

print("\n== Table 6 ==")
for cells in table("## Table 6."):
    m = MODEL[cells[0]]; tag = f"{m}{BASE}" + ("__think" if cells[1] == "on" else "")
    ok, det = perf_row_ok(tag, cells, 2)
    rs = runs(tag); d = scored(tag)
    lat = f"{statistics.mean(r['latency_s'] for r in rs):.1f}"
    tok = f"{statistics.mean(r['output_tokens'] for r in rs):,.0f}"
    zero = str(sum(len(r["findings"]) == 0 for r in rs))
    nonjson = str(sum(bool((r.get("raw_text") or "").strip())
                      and not (r["raw_text"] or "").lstrip().startswith("{") for r in rs))
    extra = [lat, tok, f"{d['cost_usd']:.2f}", zero, nonjson]
    check(f"{cells[0]} reasoning {cells[1]}", ok and cells[9:14] == extra, det + f"; extra want {extra} got {cells[9:14]}")
paired_table_ok("Paired F1 difference, reasoning on minus off", "reasoning",
                lambda c: (c[0], f"{MODEL[c[0]]}{BASE}__think", f"{MODEL[c[0]]}{BASE}"))

print("\n== Table 8 ==")
for cells in table("## Table 8."):
    m = MODEL[cells[0]]
    want = [f"{scored(f'{m}__{c}__single__terragoat_mut')['overall']['f1']:.3f}"
            for c in ["zero_shot", "few_shot", "system_enriched", "rag", "chain_of_thought"]]
    check(cells[0], want == cells[1:6], f"want {want} got {cells[1:6]}")
for cells in table("Detail behind Table 8"):
    m = MODEL[cells[0]]; tag = f"{m}__{VARIANT[cells[1]]}__single__terragoat_mut"
    ok, det = perf_row_ok(tag, cells, 2)
    check(f"{cells[0]} {cells[1]}", ok and cells[9] == f"{scored(tag)['cost_usd']:.2f}", det)

print("\n== Table 9 ==")
paired_table_ok("## Table 9.", "context",
                lambda c: (f"{c[0]} | {c[1]}", f"{MODEL[c[0]]}__{VARIANT[c[1]]}__single__terragoat_mut", f"{MODEL[c[0]]}__zero_shot__single__terragoat_mut"))

print("\n== Table 10 ==")
for cells in table("## Table 10."):
    m = MODEL[cells[0]]; tag = f"{m}__system_enriched__{cells[1]}__terragoat_mut"
    ok, det = perf_row_ok(tag, cells, 2)
    rs = runs(tag); d = scored(tag); base = scored(f"{m}{BASE}")["cost_usd"] / 30
    extra = [f"{statistics.mean(r.get('n_calls', 1) for r in rs):.1f}",
             f"{statistics.mean(r['latency_s'] for r in rs):.1f}",
             f"{d['cost_usd'] / 30:.4f}", f"{(d['cost_usd'] / 30) / base:.1f}"]
    check(f"{cells[0]} {cells[1]}", ok and cells[9:13] == extra, det + f"; extra want {extra} got {cells[9:13]}")
mech = DOC[DOC.index("Mechanism counts"):].split("\n", 1)[0]
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

print("\n== Table 11 ==")
paired_table_ok("## Table 11.", "orchestration",
                lambda c: (f"{c[0]} | {c[1]}", f"{MODEL[c[0]]}__system_enriched__{c[1]}__terragoat_mut", f"{MODEL[c[0]]}{BASE}"))

print("\n== study totals ==")
tot = sum(scored(p.stem)["cost_usd"] for p in SCORED.glob("*.json"))
totals = DOC[DOC.index("## Study totals"):].split("## ", 2)[1]
check("36 configurations and 1,080 runs stated", "36 configurations and 1,080 runs" in totals)
calls = {}
for r in allruns: calls[r["pattern"]] = calls.get(r["pattern"], 0) + r["n_calls"]
check("1,540 API calls (720 single, 240 critic, 360 debate, 220 chunked) stated",
      calls == {"single": 720, "critic": 240, "debate": 360, "chunked": 220} and "1,540 calls in all" in totals, str(calls))
check("20 + 12 + 4 configurations stated", "20 model-and-prompt" in totals and "12 model-and-pattern" in totals and "4 reasoning-on" in totals)
check("TP + FN = 260 in every configuration",
      all(scored(p.stem)["overall"]["totals"]["tp"] + scored(p.stem)["overall"]["totals"]["fn"] == 260 for p in SCORED.glob("*.json")) and "TP + FN = 260" in totals)
nc = sorted(r["run_id"] for r in allruns if not r["findings"] and not (r.get("raw_text") or "").strip().startswith("{"))
check("exactly one run returned no content (DeepSeek chain_of_thought lambda.tf r3), stated",
      nc == ["deepseek-v4-flash__chain_of_thought__single__terragoat_mut__lambda.tf__r3"] and f"1 run returned no content and is scored as an empty findings list ({nc[0]})" in totals)
check(f"total spend ≈ ${tot:.2f} stated", f"≈ ${tot:.2f}" in totals)

print("\n== strict-matcher table (model comparison) ==")
for cells in table("## Strict-matcher F1"):
    m = MODEL[cells[0]]; tp, one, cwe, fp, fn = strict(f"{m}{BASE}")
    want = [str(tp), str(one), str(cwe), f"{f1_of(tp, fp, fn):.3f}", f"{f1_of(tp - one - cwe, fp + one + cwe, fn + one + cwe):.3f}"]
    check(cells[0], want == cells[1:6], f"want {want} got {cells[1:6]}")

print("\n== chunking by file ==")
chunks = {}
for r in allruns:
    if r["pattern"] == "chunked": chunks.setdefault(r["file"], set()).add(r["chunks"])
check("chunk counts db-app 4, ec2 3, others 1", {f: sorted(v) for f, v in chunks.items()} == {"db-app.tf": [4], "ec2.tf": [3], "iam.tf": [1], "kms.tf": [1], "lambda.tf": [1], "s3.tf": [1]}, str(chunks))
for f in FILES:
    check(f"chunking table row {f}", f"| {f} | {len((ROOT / 'terragoat_mut/terraform/aws' / f).read_text()):,} | {sorted(chunks[f])[0]} |" in DOC)
for cells in table("Single call versus chunked"):
    m = MODEL[cells[0]]; sel = {"db-app.tf", "ec2.tf"} if cells[1] == "split" else set(FILES) - {"db-app.tf", "ec2.tf"}
    a = scored(f"{m}{BASE}")["per_file"]; b = scored(f"{m}__system_enriched__chunked__terragoat_mut")["per_file"]
    ta = [sum(a[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]; tb = [sum(b[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]
    want = [f"{ta[0]} → {tb[0]}", f"{ta[1]} → {tb[1]}", f"{f1_of(*ta):.3f} → {f1_of(*tb):.3f}", f"{f1_of(*tb) - f1_of(*ta):+.3f}"]
    check(f"{cells[0]} {cells[1]} chunking row", want == cells[2:6], f"want {want} got {cells[2:6]}")
cnt = {}
for pat in ("single", "chunked"):
    for r in runs(f"claude-opus-5__system_enriched__{pat}__terragoat_mut"):
        if r["file"] == "s3.tf":
            for x in match_findings(r["findings"], GT["terragoat_mut::s3.tf"])[0]: cnt[(pat, x.gt_id)] = cnt.get((pat, x.gt_id), 0) + 1
s3 = [g for g in GT["terragoat_mut::s3.tf"] if g["checkov_id"] == "CKV2_AWS_6"]
check("Opus s3.tf CKV2_AWS_6 per-bucket counts stated", "; ".join(f"{g['resource']} {cnt.get(('single', g['id']), 0)} → {cnt.get(('chunked', g['id']), 0)}" for g in s3) in DOC)

# ------------------------------------------------------------- 4. adjudication
print("\n== Table 5 (adjudication) ==")
adj = json.loads((ROOT / "harness/fp_review/set1_fp_adjudicated.json").read_text())
rows = adj["rows"]
check("177 unmatched claims adjudicated, none reasoning-on",
      len(rows) == 177 and not any("__think__" in r["run_id"] for r in rows))
check("every row carries a reviewer verdict", all(r.get("reviewer_verdict") in (A, B, C, D) for r in rows))
rederived = 0
for m in MODEL.values():
    for r in runs(f"{m}{BASE}"):
        _, unmatched, _ = match_findings(r["findings"], GT.get(f"terragoat_mut::{r['file']}", []))
        rederived += len(unmatched)
check("unmatched-claim count re-derives (177)", rederived == 177, str(rederived))
for cells in table("## Table 5."):
    m = MODEL[cells[0]]; t = scored(f"{m}{BASE}")["overall"]["totals"]
    tp, fp, fn = t["tp"], t["fp"], t["fn"]
    cnt = {k: sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == k) for k in (A, B, C, D)}
    rec = tp / (tp + fn); rawp = tp / (tp + fp); adjp = (tp + cnt[A]) / (tp + fp)
    want = [str(cnt[A]), str(cnt[B]), str(cnt[C]), str(cnt[D]), str(fp), f"{rawp:.3f}", f"{adjp:.3f}",
            f"{(tp + cnt[A] + cnt[D]) / (tp + fp):.3f}", f"{rec:.3f}",
            f"{2 * rawp * rec / (rawp + rec):.3f}", f"{2 * adjp * rec / (adjp + rec):.3f}"]
    check(f"{cells[0]} adjudication row", want == cells[1:12], f"want {want} got {cells[1:12]}")
for cells in table("Conservative bound."):
    m = MODEL[cells[0]]; t = scored(f"{m}{BASE}")["overall"]["totals"]; tp, fp = t["tp"], t["fp"]
    a_all = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A)
    a_out = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A and r["file"] == "iam.tf" and "output" in r["description"].lower())
    want = [str(a_out), f"{(tp + a_all) / (tp + fp):.3f}", f"{(tp + a_all - a_out) / (tp + fp):.3f}"]
    check(f"{cells[0]} conservative bound", want == cells[1:4], f"want {want} got {cells[1:4]}")

# --------------------------------------------------------------- 5. supplement
print("\n== supplement: Holm table ==")
check("35 paired tests collected from the RESULTS.md tables", len(PAIRED) == 35, str(len(PAIRED)))
fam_adj = {}
for fam in ("model comparison", "reasoning", "context", "orchestration"):
    fam_adj.update(holm({k: v[2]["p_value"] for k, v in PAIRED.items() if v[0] == fam}))
glob_adj = holm({k: v[2]["p_value"] for k, v in PAIRED.items()})
by_label = {(v[0], v[1].replace(" | ", " / ")): k for k, v in PAIRED.items()}
hrows = table("## Holm-adjusted", SUP)
check("Holm table has 35 rows", len(hrows) == 35, str(len(hrows)))
for cells in hrows:
    k = by_label.get((cells[0], cells[1]))
    if k is None:
        check(f"Holm row {cells[0]} / {cells[1]} matches a paired test", False); continue
    r = PAIRED[k][2]
    want = [f"{r['observed_f1_difference']:+.3f}", pfmt(r["p_value"]), pfmt(fam_adj[k]), pfmt(glob_adj[k])]
    check(f"Holm row {cells[1]}", want == cells[2:6], f"want {want} got {cells[2:6]}")
sig = [k for k, v in glob_adj.items() if v <= 0.01]
sent = SUP[SUP.index("Contrasts with Holm p ≤ 0.01 across all 35 tests:"):].split("\n", 1)[0]
check("global Holm sentence lists exactly the contrasts at ≤ 0.01",
      all(f"{PAIRED[k][1].replace(' | ', ' / ')} ({pfmt(glob_adj[k])})" in sent for k in sig) and sent.count("(") == len(sig), sent)

print("\n== supplement: matcher sensitivity, all configurations ==")
T = O = Cw = 0
for cells in table("## Matcher sensitivity", SUP):
    m = MODEL[cells[0]]; parts = cells[1].split(" / ")
    tag = f"{m}__{parts[0]}__{parts[1]}__terragoat_mut" + ("__think" if len(parts) == 3 else "")
    tp, one, cwe, fp, fn = strict(tag); T += tp; O += one; Cw += cwe
    want = [str(tp), str(one), str(cwe), f"{f1_of(tp, fp, fn):.3f}", f"{f1_of(tp - one - cwe, fp + one + cwe, fn + one + cwe):.3f}"]
    check(f"{cells[0]} {cells[1]}", want == cells[2:7], f"want {want} got {cells[2:7]}")
check(f"matcher totals {T}/{O}/{Cw}",
      f"{T} accepted matches, {O} single-cue ({100 * O / T:.1f}%), {Cw} CWE-level ({100 * Cw / T:.1f}%)" in SUP)

print("\n== supplement: output ceilings ==")
for cells in table("## Reasoning-on output ceilings", SUP):
    m = MODEL[cells[0]]; rr = runs(f"{m}{BASE}__think")
    at = [r for r in rr if r["output_tokens"] >= CEIL[m]]
    want = [f"{CEIL[m]:,}", str(len(at)), str(sum(1 for r in at if not r["findings"])), f"{max(r['output_tokens'] for r in rr):,}"]
    check(f"{cells[0]} ceiling row", want == cells[1:5], f"want {want} got {cells[1:5]}")
check("no reasoning-on run of any model reached its ceiling",
      all(r["output_tokens"] < CEIL[m] for m in MODEL.values() for r in runs(f"{m}{BASE}__think")))
ds = runs(f"deepseek-v4-flash{BASE}__think")
check("reported DeepSeek reasoning arm: 30 runs, all served as deepseek-flash, none empty, F1 and longest response stated",
      len(ds) == 30 and all(r["resolved_model"] == "deepseek-flash" for r in ds) and all(r["findings"] for r in ds)
      and f"(F1 {scored(f'deepseek-v4-flash{BASE}__think')['overall']['f1']:.3f}, longest response {max(r['output_tokens'] for r in ds):,} tokens)" in SUP)
for lab, ceil, at_n, empty_n in (("4096", 4096, 8, 8), ("8000", 8000, 1, 1)):
    d = ROOT / f"harness/results_superseded/deepseek-v4-flash__system_enriched__single__terragoat_mut__think_{lab}"
    rr = [json.loads(p.read_text()) for p in d.glob("deepseek-*.json")]
    s = json.loads((d / "scored_summary.json").read_text())
    check(f"superseded DeepSeek arm at {ceil}: 30 runs retained, {at_n} at the ceiling, {empty_n} empty, F1 stated",
          len(rr) == 30 and sum(1 for r in rr if r["output_tokens"] >= ceil) == at_n and sum(1 for r in rr if not r["findings"]) == empty_n
          and f"at {ceil:,}: F1 {s['overall']['f1']:.3f}, {at_n} of 30 runs at the ceiling, {empty_n} scored as empty" in SUP)

print()
if FAIL:
    print(f"{len(FAIL)} CHECK(S) FAILED"); sys.exit(1)
print("every figure in RESULTS.md and SUPPLEMENT.md reproduces from harness/results/")
