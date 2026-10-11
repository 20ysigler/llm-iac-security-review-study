#!/usr/bin/env python3
"""
Regenerate RESULTS.md and SUPPLEMENT.md from harness/results/ and harness/scored/.

    python3 harness/build_results.py            # rewrites both files at the repository root
    python3 harness/build_results.py /tmp/out   # writes them somewhere else, for a diff

RESULTS.md holds every table the paper reports, numbered as in the paper, plus
the study totals and the two supplementary tables the paper's text quotes.
SUPPLEMENT.md holds analyses computed from the same run files that the paper
does not report. harness/verify_paper.py re-derives every number in both files
independently and fails on any mismatch. The Table 5 section reads
harness/fp_review/set1_fp_adjudicated.json.
"""
from __future__ import annotations

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
SPLIT = {"db-app.tf", "ec2.tf"}
CEIL = {"claude-opus-5": 8000, "claude-sonnet-5": 8000, "gpt-5.6-terra": 8000, "deepseek-v4-flash": 16000}
A, B, C, D = ("Real issue, not in answer key", "Real but excluded by our criteria",
              "Model was wrong", "Same issue reported twice")
BASE = "__system_enriched__single__terragoat_mut"


def S(tag): return json.loads((SCORED / f"{tag}.json").read_text())
def runs(tag):
    think = tag.endswith("__think")
    return [json.loads(p.read_text()) for p in RES.glob(f"{tag}__*.json") if ("__think__" in p.name) == think]
def ci(o): return f"[{o['ci']['f1'][0]:.3f}, {o['ci']['f1'][1]:.3f}]"
def pfmt(p): return "<0.001" if p < 0.001 else (f"{p:.2f}" if p >= 0.01 else f"{p:.3f}")
def perf(tag):
    o = S(tag)["overall"]; t = o["totals"]
    return f"{o['precision']:.3f} | {o['recall']:.3f} | {o['f1']:.3f} | {ci(o)} | {t['tp']} | {t['fp']} | {t['fn']}"
def f1_of(tp, fp, fn):
    p_ = tp / (tp + fp) if tp + fp else 0; r_ = tp / (tp + fn) if tp + fn else 0
    return 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
def strict(tag):
    """(tp, single-cue tp, cwe-level tp, fp, fn) for a configuration under the matcher as scored."""
    tp = one = cwe = fp = fn = 0
    for r in runs(tag):
        m, uc, ug = match_findings(r["findings"], GT.get(f"terragoat_mut::{r['file']}", []))
        tp += len(m); one += sum(1 for x in m if x.level == "resource_issue" and x.score < 3.0)
        cwe += sum(1 for x in m if x.level == "cwe"); fp += len(uc); fn += len(ug)
    return tp, one, cwe, fp, fn


# Every paired test, computed once: label -> (family, display label, result).
PAIRED: dict[str, tuple[str, str, dict]] = {}
def paired(family, label, tag_a, tag_b):
    r = compare(tag_a, tag_b); PAIRED[f"{family}:{label}"] = (family, label, r); return r
def paired_cells(r):
    return f"{r['observed_f1_difference']:+.3f} | [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] | {pfmt(r['p_value'])} | {'yes' if r['excludes_zero'] else 'no'}"


def results_md() -> str:
    L: list[str] = []
    out = L.append
    out("# Results\n")
    out("Every table the paper reports, numbered as in the paper, computed from `harness/results/` (1,080 runs on `terragoat_mut`: 36 configurations x 6 files x 5 repetitions) and `harness/scored/`. "
        "Precision, recall, and F1 are pooled over a configuration's 30 runs; the 95% confidence interval is a percentile bootstrap over the 30 runs (10,000 draws). "
        "Paired comparisons (`harness/compare.py`) resample the 30 file-and-repetition units two configurations share (20,000 draws); `p` is the raw two-sided bootstrap p-value. "
        "The paper draws its conclusions at p ≤ 0.01 without correction for the 35 paired tests; Holm-adjusted values for all 35 are in `SUPPLEMENT.md`. "
        "Reasoning is off unless stated (Claude: forced tool call; GPT: reasoning_effort none; DeepSeek: thinking disabled). Values are rounded once from six-decimal summaries. "
        "Regenerate with `python3 harness/build_results.py`; check with `python3 harness/verify_paper.py`.\n")

    # ---- Table 2
    out("## Table 2. Detection performance by model (system-prompt enrichment, single agent; 30 runs each)\n")
    out("| Model | Served as | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Cost (USD, 30 runs) |\n|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        tag = f"{m}{BASE}"
        out(f"| {NAME[m]} | {runs(tag)[0]['resolved_model']} | {perf(tag)} | {S(tag)['cost_usd']:.2f} |")

    # ---- Table 3
    out("\n## Table 3. Paired F1 difference against Claude Opus 5\n")
    out("| Model | F1 difference | 95% CI | p | Excludes zero |\n|---|---|---|---|---|")
    for m in MODELS[1:]:
        out(f"| {NAME[m]} | {paired_cells(paired('model comparison', NAME[m], f'{m}{BASE}', f'claude-opus-5{BASE}'))} |")

    # ---- Table 4
    out("\n## Table 4. Per-file F1 by model (system-prompt enrichment, single agent)\n")
    out("| Model | db-app.tf | ec2.tf | iam.tf | kms.tf | lambda.tf | s3.tf |\n|---|---|---|---|---|---|---|")
    for m in MODELS:
        pf = S(f"{m}{BASE}")["per_file"]
        out(f"| {NAME[m]} | " + " | ".join(f"{pf[f]['f1']:.2f}" for f in FILES) + " |")

    # ---- Table 5
    adj = json.loads((ROOT / "harness/fp_review/set1_fp_adjudicated.json").read_text()); rows = adj["rows"]
    out("\n## Table 5. Classification of rejected claims and adjusted precision (model comparison)\n")
    out(f"Every claim the scorer rejected in the four model-comparison configurations ({len(rows)}: "
        + ", ".join(f"{NAME[m]} {sum(1 for r in rows if r['model'] == m)}" for m in ["claude-opus-5", "deepseek-v4-flash", "claude-sonnet-5", "gpt-5.6-terra"])
        + ") was read against the Terraform and placed in one of four groups: **A** a real vulnerability the Checkov-derived ground truth has no rule for; "
        "**B** a true observation the study's criterion excludes (recovery controls, passive logging, tags, hardening without an attack path, design facts); "
        "**C** a model error; **D** a duplicate of a finding the same run was already credited for. "
        f"First pass by an AI model, then every row reviewed by the author, whose verdict governs ({adj['review']['rows']} of {adj['review']['rows']} first-pass verdicts accepted). "
        "Rows: `harness/fp_review/set1_fp_adjudicated.json`; workbook: `harness/fp_review/set1_fp_review.xlsx`. "
        "Adjusted precision = (TP + A) / (TP + FP); the A+D column also credits the duplicates. Recall is unaffected.\n")
    out("| Model | A real | B excluded | C wrong | D duplicate | FP | Raw P | Adjusted P (A) | Adjusted P (A+D) | Recall | Raw F1 | Adjusted F1 (A) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-terra", "deepseek-v4-flash"]:
        t = S(f"{m}{BASE}")["overall"]["totals"]; tp, fp, fn = t["tp"], t["fp"], t["fn"]
        cnt = {k: sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == k) for k in (A, B, C, D)}
        rec = tp / (tp + fn); rawp = tp / (tp + fp); adjp = (tp + cnt[A]) / (tp + fp)
        out(f"| {NAME[m]} | {cnt[A]} | {cnt[B]} | {cnt[C]} | {cnt[D]} | {fp} | {rawp:.3f} | {adjp:.3f} | {(tp + cnt[A] + cnt[D]) / (tp + fp):.3f} | {rec:.3f} | {2 * rawp * rec / (rawp + rec):.3f} | {2 * adjp * rec / (adjp + rec):.3f} |")
    out("\nConservative bound. Some group-A claims on iam.tf attribute the access-key exposure to the Terraform output; without `pgp_key` the `encrypted_secret` attribute that output references is empty, so the output exposes nothing while the plaintext `secret` in state does. Withholding the A credit from every iam.tf claim whose description names the output gives:\n")
    out("| Model | A credits withheld | Adjusted P (A) | Adjusted P without output-pathway credits |\n|---|---|---|---|")
    for m in ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-terra", "deepseek-v4-flash"]:
        t = S(f"{m}{BASE}")["overall"]["totals"]; tp, fp = t["tp"], t["fp"]
        a_all = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A)
        a_out = sum(1 for r in rows if r["model"] == m and r["reviewer_verdict"] == A and r["file"] == "iam.tf" and "output" in r["description"].lower())
        out(f"| {NAME[m]} | {a_out} | {(tp + a_all) / (tp + fp):.3f} | {(tp + a_all - a_out) / (tp + fp):.3f} |")

    # ---- Table 6
    out("\n## Table 6. Effect of native reasoning mode (system-prompt enrichment, single agent)\n")
    out("| Model | Reasoning | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Latency (s) | Output tokens | Cost (USD, 30 runs) | Empty-list runs | No-content runs |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        for th in ("", "__think"):
            tag = f"{m}{BASE}{th}"; rs = runs(tag)
            z = sum(len(r["findings"]) == 0 for r in rs)
            nj = sum(bool((r.get("raw_text") or "").strip()) and not (r["raw_text"] or "").lstrip().startswith("{") for r in rs)
            out(f"| {NAME[m]} | {'on' if th else 'off'} | {perf(tag)} | {statistics.mean(r['latency_s'] for r in rs):.1f} | "
                f"{statistics.mean(r['output_tokens'] for r in rs):,.0f} | {S(tag)['cost_usd']:.2f} | {z} | {nj} |")
    out("\nPaired F1 difference, reasoning on minus off:\n\n| Model | F1 difference | 95% CI | p | Excludes zero |\n|---|---|---|---|---|")
    for m in MODELS:
        out(f"| {NAME[m]} | {paired_cells(paired('reasoning', NAME[m], f'{m}{BASE}__think', f'{m}{BASE}'))} |")
    out("\nTable 7 in the paper (public benchmark standing against observed rank) is compiled from the leaderboards the paper cites, not from the run data, and is not reproduced here.")

    # ---- Table 8
    out("\n## Table 8. F1 by model and context variant (single agent; 30 runs per cell)\n")
    out("| Model | zero_shot | few_shot | system_enriched | rag (guidance injection) | chain_of_thought |\n|---|---|---|---|---|---|")
    for m in MODELS:
        out(f"| {NAME[m]} | " + " | ".join(f"{S(f'{m}__{c}__single__terragoat_mut')['overall']['f1']:.3f}" for c in VARIANTS) + " |")
    out("\nDetail behind Table 8:\n\n| Model | Variant | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Cost (USD, 30 runs) |\n|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        for c in VARIANTS:
            tag = f"{m}__{c}__single__terragoat_mut"
            out(f"| {NAME[m]} | {VNAME[c]} | {perf(tag)} | {S(tag)['cost_usd']:.2f} |")

    # ---- Table 9
    out("\n## Table 9. Paired F1 difference against the same model's zero-shot run\n")
    out("| Model | Variant | F1 difference | 95% CI | p | Excludes zero |\n|---|---|---|---|---|---|")
    for m in MODELS:
        for c in ["few_shot", "system_enriched", "rag", "chain_of_thought"]:
            out(f"| {NAME[m]} | {VNAME[c]} | {paired_cells(paired('context', f'{NAME[m]} | {VNAME[c]}', f'{m}__{c}__single__terragoat_mut', f'{m}__zero_shot__single__terragoat_mut'))} |")

    # ---- Table 10
    out("\n## Table 10. Detection performance and cost by orchestration pattern (system-prompt enrichment)\n")
    out("| Model | Pattern | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Calls per run | Latency (s) | Cost per review (USD) | Cost multiple |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    steps = lambda r: {s["step"]: s for s in r["steps"]}   # noqa: E731
    man = json.loads((ROOT / "data" / "terragoat_resources.json").read_text())["resources"]
    ren = json.loads((ROOT / "data" / "rename_map.json").read_text())["renames"]
    valid = {f: {normalise_resource(ren.get(x, x)) for x in v} for f, v in man.items()}
    mech, fab = [], []
    for m in MODELS:
        base = S(f"{m}{BASE}")["cost_usd"] / 30
        for p in PATTERNS:
            tag = f"{m}__system_enriched__{p}__terragoat_mut"; rs = runs(tag); d = S(tag)
            out(f"| {NAME[m]} | {p} | {perf(tag)} | {statistics.mean(r.get('n_calls', 1) for r in rs):.1f} | "
                f"{statistics.mean(r['latency_s'] for r in rs):.1f} | {d['cost_usd'] / 30:.4f} | {(d['cost_usd'] / 30) / base:.1f} |")
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
    out("\nCost per review is the 30-run cost divided by 30; the cost multiple is relative to the same model's single call. Latency was measured from one cloud container and is comparable within this table only. "
        "Debate samples the same model twice and reconciles with a third call.")
    out("\nMechanism counts used in Section 3.3.3: " + "; ".join(mech) + ". Fabricated resource addresses (claims naming a resource not in the file): " + "; ".join(fab) + ".")

    # ---- Table 11
    out("\n## Table 11. Paired F1 difference against the same model's single-agent configuration\n")
    out("| Model | Pattern | F1 difference | 95% CI | p | Excludes zero |\n|---|---|---|---|---|---|")
    for m in MODELS:
        for p in ["critic", "debate", "chunked"]:
            out(f"| {NAME[m]} | {p} | {paired_cells(paired('orchestration', f'{NAME[m]} | {p}', f'{m}__system_enriched__{p}__terragoat_mut', f'{m}{BASE}'))} |")

    # ---- Study totals
    allr = [json.loads(p.read_text()) for p in RES.glob("*.json")]
    n_cfg = len(list(SCORED.glob("*.json"))); n_runs = len(allr)
    calls = {}
    for r in allr: calls[r["pattern"]] = calls.get(r["pattern"], 0) + r["n_calls"]
    ncfg = {"prompt": len(list(SCORED.glob("*__single__terragoat_mut.json"))),
            "pattern": len([p for p in SCORED.glob("*.json") if "__single__" not in p.name]),
            "reasoning": len(list(SCORED.glob("*__think.json")))}
    tpfn = sorted({S(p.stem)["overall"]["totals"]["tp"] + S(p.stem)["overall"]["totals"]["fn"] for p in SCORED.glob("*.json")})
    nocontent = sorted(r["run_id"] for r in allr if not r["findings"] and not (r.get("raw_text") or "").strip().startswith("{"))
    tot = sum(S(p.stem)["cost_usd"] for p in SCORED.glob("*.json"))
    out("\n## Study totals\n")
    out(f"{n_cfg} configurations and {n_runs:,} runs: {ncfg['prompt']} model-and-prompt configurations (single call, reasoning off), {ncfg['pattern']} model-and-pattern configurations beyond the single call, and {ncfg['reasoning']} reasoning-on configurations, "
        f"with the system_enriched single call as the baseline for the last two groups. A run is one review of one file; API calls per run: single {calls['single'] // 720}, critic {calls['critic'] // 120}, debate {calls['debate'] // 120}, "
        f"chunked {calls['chunked'] / 120:.2f} on average ({calls['chunked']} calls over 120 runs); {sum(calls.values()):,} calls in all. "
        f"Every configuration scores 52 findings x 5 repetitions, so TP + FN = {tpfn[0] if len(tpfn) == 1 else tpfn} in every configuration. "
        f"No run ended in an API error; {len(nocontent)} run returned no content and is scored as an empty findings list ({', '.join(nocontent)}). "
        f"Every accepted match is at the resource-plus-category or CWE level. Total API spend ≈ ${tot:.2f} at the August 2026 list prices in `providers.py`. "
        "Prompt provenance is identical across every run (`prompts=8a683cfec1c99d66`).")

    # ---- Supplementary tables the paper's text quotes
    out("\n## Strict-matcher F1 for the model comparison\n")
    out("A resource-plus-category match needs the resource address plus at least one category cue; a CWE-level match needs the resource plus the same CWE. `F1 strict` treats every single-cue and CWE-level match as a false positive and its finding as missed: a bound on what a stricter matcher could report, not a corrected score (Section 3.1.3). All 36 configurations are in `SUPPLEMENT.md`.\n")
    out("| Model | TP | Single-cue TP | CWE-level TP | F1 | F1 strict |\n|---|---|---|---|---|---|")
    for m in MODELS:
        tp, one, cwe, fp, fn = strict(f"{m}{BASE}")
        out(f"| {NAME[m]} | {tp} | {one} | {cwe} | {f1_of(tp, fp, fn):.3f} | {f1_of(tp - one - cwe, fp + one + cwe, fn + one + cwe):.3f} |")

    out("\n## Chunking by file\n")
    out("The chunked pattern packs whole top-level blocks into chunks of at most 2,500 characters (`agents/hcl.py`). A file under the budget is sent whole in one call under `prompts.CHUNK_HEADER`, which presents the text as an excerpt of a larger file and forbids findings on resources not shown (Section 3.3.3).\n")
    sizes = {f: len((ROOT / "terragoat_mut/terraform/aws" / f).read_text()) for f in FILES}
    chunks = {}
    for r in allr:
        if r["pattern"] == "chunked": chunks.setdefault(r["file"], set()).add(r["chunks"])
    out("| File | Characters | Chunks |\n|---|---|---|")
    for f in FILES: out(f"| {f} | {sizes[f]:,} | {', '.join(str(c) for c in sorted(chunks[f]))} |")
    out("\nSingle call versus chunked, pooled over the split files (db-app.tf, ec2.tf) and the unsplit files (iam.tf, kms.tf, lambda.tf, s3.tf):\n\n| Model | Files | TP single → chunked | FP single → chunked | F1 single → chunked | ΔF1 |\n|---|---|---|---|---|---|")
    for m in MODELS:
        a = S(f"{m}{BASE}")["per_file"]; b = S(f"{m}__system_enriched__chunked__terragoat_mut")["per_file"]
        for lab, sel in (("split", SPLIT), ("unsplit", set(FILES) - SPLIT)):
            ta = [sum(a[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]; tb = [sum(b[f]["totals"][k] for f in sel) for k in ("tp", "fp", "fn")]
            out(f"| {NAME[m]} | {lab} | {ta[0]} → {tb[0]} | {ta[1]} → {tb[1]} | {f1_of(*ta):.3f} → {f1_of(*tb):.3f} | {f1_of(*tb) - f1_of(*ta):+.3f} |")
    cnt = {}
    for pat in ("single", "chunked"):
        for r in runs(f"claude-opus-5__system_enriched__{pat}__terragoat_mut"):
            if r["file"] != "s3.tf": continue
            for x in match_findings(r["findings"], GT["terragoat_mut::s3.tf"])[0]: cnt[(pat, x.gt_id)] = cnt.get((pat, x.gt_id), 0) + 1
    s3 = [g for g in GT["terragoat_mut::s3.tf"] if g["checkov_id"] == "CKV2_AWS_6"]
    out("\nClaude Opus 5 on s3.tf (one chunk, sent whole under the chunk header), CKV2_AWS_6 public-access-block findings matched in five runs, single → chunked: "
        + "; ".join(f"{g['resource']} {cnt.get(('single', g['id']), 0)} → {cnt.get(('chunked', g['id']), 0)}" for g in s3) + ".")
    return "\n".join(L) + "\n"


def supplement_md() -> str:
    L: list[str] = []
    out = L.append
    out("# Supplement\n")
    out("Analyses computed from the same run files as `RESULTS.md` that the paper does not report. Regenerated by `python3 harness/build_results.py`; checked by `python3 harness/verify_paper.py`.\n")

    # ---- Holm
    out("## Holm-adjusted p-values for all 35 paired tests\n")
    out("The paper runs 35 paired comparisons in four families (3 model contrasts, 4 reasoning contrasts, 16 context contrasts, 12 orchestration contrasts) and draws conclusions at a raw p ≤ 0.01. "
        "This table adds Holm step-down adjusted p-values, within each family and across all 35 tests at once. Adjusted p = max over the step-down sequence of (m − i) × p(i), capped at 1.\n")
    fam_adj = {}
    for fam in ("model comparison", "reasoning", "context", "orchestration"):
        fam_adj.update(holm({k: v[2]["p_value"] for k, v in PAIRED.items() if v[0] == fam}))
    glob_adj = holm({k: v[2]["p_value"] for k, v in PAIRED.items()})
    out("| Family | Contrast | F1 difference | p | Holm p (family) | Holm p (all 35) |\n|---|---|---|---|---|---|")
    for k, (fam, label, r) in PAIRED.items():
        out(f"| {fam} | {label.replace(' | ', ' / ')} | {r['observed_f1_difference']:+.3f} | {pfmt(r['p_value'])} | {pfmt(fam_adj[k])} | {pfmt(glob_adj[k])} |")
    sig = [k for k, v in glob_adj.items() if v <= 0.01]
    out(f"\nContrasts with Holm p ≤ 0.01 across all 35 tests: " + "; ".join(f"{PAIRED[k][1].replace(' | ', ' / ')} ({pfmt(glob_adj[k])})" for k in sig) + ".")

    # ---- matcher sensitivity, all configurations
    out("\n## Matcher sensitivity, all 36 configurations\n")
    out("Same definition as the strict-matcher table in `RESULTS.md`: `F1 strict` treats every single-cue and CWE-level match as a false positive and its finding as missed.\n")
    out("| Model | Configuration | TP | Single-cue TP | CWE-level TP | F1 | F1 strict |\n|---|---|---|---|---|---|---|")
    T = O = Cw = 0
    for p in sorted(SCORED.glob("*.json")):
        tag = p.stem; tp, one, cwe, fp, fn = strict(tag)
        cfg = tag.split("__"); label = f"{cfg[1]} / {cfg[2]}" + (" / reasoning on" if tag.endswith("__think") else "")
        out(f"| {NAME[cfg[0]]} | {label} | {tp} | {one} | {cwe} | {f1_of(tp, fp, fn):.3f} | {f1_of(tp - one - cwe, fp + one + cwe, fn + one + cwe):.3f} |")
        T += tp; O += one; Cw += cwe
    out(f"\nAcross all 36 configurations: {T} accepted matches, {O} single-cue ({100 * O / T:.1f}%), {Cw} CWE-level ({100 * Cw / T:.1f}%).")

    # ---- output ceilings
    out("\n## Reasoning-on output ceilings\n")
    out("`max_tokens` is 4,096 on every reasoning-off call. With reasoning on, `providers.py` raises the ceiling to 8,000 for the Claude and GPT calls and to 16,000 for the DeepSeek call, chosen so that no ceiling binds.\n")
    out("| Model | Ceiling | Reasoning-on runs at the ceiling | Of which empty findings | Longest response (output tokens) |\n|---|---|---|---|---|")
    for m in MODELS:
        rr = runs(f"{m}{BASE}__think")
        at = [r for r in rr if r["output_tokens"] >= CEIL[m]]
        out(f"| {NAME[m]} | {CEIL[m]:,} | {len(at)} | {sum(1 for r in at if not r['findings'])} | {max(r['output_tokens'] for r in rr):,} |")
    lines = []
    for lab, ceil in (("4096", 4096), ("8000", 8000)):
        d = ROOT / f"harness/results_superseded/deepseek-v4-flash__system_enriched__single__terragoat_mut__think_{lab}"
        rr = [json.loads(p.read_text()) for p in d.glob("deepseek-*.json")]
        s = json.loads((d / "scored_summary.json").read_text())
        lines.append(f"at {ceil:,}: F1 {s['overall']['f1']:.3f}, {sum(1 for r in rr if r['output_tokens'] >= ceil)} of {len(rr)} runs at the ceiling, {sum(1 for r in rr if not r['findings'])} scored as empty")
    ds = runs(f"deepseek-v4-flash{BASE}__think")
    out(f"\nThe DeepSeek reasoning-on configuration was run at three ceilings. The reported arm is the 16,000-token run (F1 {S(f'deepseek-v4-flash{BASE}__think')['overall']['f1']:.3f}, longest response {max(r['output_tokens'] for r in ds):,} tokens). "
        f"The two earlier arms are kept in `harness/results_superseded/` with their scored summaries: " + "; ".join(lines) + ".")
    return "\n".join(L) + "\n"


def main() -> None:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "RESULTS.md").write_text(results_md(), encoding="utf-8")
    (outdir / "SUPPLEMENT.md").write_text(supplement_md(), encoding="utf-8")
    print(f"wrote {outdir / 'RESULTS.md'} and {outdir / 'SUPPLEMENT.md'}")


if __name__ == "__main__":
    main()
