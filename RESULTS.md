# Results

Every table the paper reports, numbered as in the paper, computed from `harness/results/` (1,080 runs on `terragoat_mut`: 36 configurations x 6 files x 5 repetitions) and `harness/scored/`. Precision, recall, and F1 are pooled over a configuration's 30 runs; the 95% confidence interval is a percentile bootstrap over the 30 runs (10,000 draws). Paired comparisons (`harness/compare.py`) resample the 30 file-and-repetition units two configurations share (20,000 draws); `p` is the raw two-sided bootstrap p-value. The paper draws its conclusions at p ≤ 0.01 without correction for the 35 paired tests; Holm-adjusted values for all 35 are in `SUPPLEMENT.md`. Reasoning is off unless stated (Claude: forced tool call; GPT: reasoning_effort none; DeepSeek: thinking disabled). Values are rounded once from six-decimal summaries. Regenerate with `python3 harness/build_results.py`; check with `python3 harness/verify_paper.py`.

## Table 2. Detection performance by model (system-prompt enrichment, single agent; 30 runs each)

| Model | Served as | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Cost (USD, 30 runs) |
|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | claude-opus-5 | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | 1.41 |
| Claude Sonnet 5 | claude-sonnet-5 | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | 0.43 |
| DeepSeek Flash | deepseek-flash | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | 0.01 |
| GPT-5.6 Terra | gpt-5.6-terra | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | 0.18 |

## Table 3. Paired F1 difference against Claude Opus 5

| Model | F1 difference | 95% CI | p | Excludes zero |
|---|---|---|---|---|
| Claude Sonnet 5 | -0.057 | [-0.082, -0.034] | <0.001 | yes |
| DeepSeek Flash | -0.112 | [-0.152, -0.071] | <0.001 | yes |
| GPT-5.6 Terra | -0.229 | [-0.277, -0.185] | <0.001 | yes |

## Table 4. Per-file F1 by model (system-prompt enrichment, single agent)

| Model | db-app.tf | ec2.tf | iam.tf | kms.tf | lambda.tf | s3.tf |
|---|---|---|---|---|---|---|
| Claude Opus 5 | 0.60 | 0.73 | 0.34 | 1.00 | 0.87 | 0.76 |
| Claude Sonnet 5 | 0.56 | 0.69 | 0.33 | 0.89 | 0.75 | 0.72 |
| DeepSeek Flash | 0.50 | 0.63 | 0.27 | 0.75 | 0.58 | 0.73 |
| GPT-5.6 Terra | 0.44 | 0.42 | 0.22 | 0.17 | 0.57 | 0.67 |

## Table 5. Classification of rejected claims and adjusted precision (model comparison)

Every claim the scorer rejected in the four model-comparison configurations (177: Claude Opus 5 83, DeepSeek Flash 56, Claude Sonnet 5 26, GPT-5.6 Terra 12) was read against the Terraform and placed in one of four groups: **A** a real vulnerability the Checkov-derived ground truth has no rule for; **B** a true observation the study's criterion excludes (recovery controls, passive logging, tags, hardening without an attack path, design facts); **C** a model error; **D** a duplicate of a finding the same run was already credited for. First pass by an AI model, then every row reviewed by the author, whose verdict governs (177 of 177 first-pass verdicts accepted). Rows: `harness/fp_review/set1_fp_adjudicated.json`; workbook: `harness/fp_review/set1_fp_review.xlsx`. Adjusted precision = (TP + A) / (TP + FP); the A+D column also credits the duplicates. Recall is unaffected.

| Model | A real | B excluded | C wrong | D duplicate | FP | Raw P | Adjusted P (A) | Adjusted P (A+D) | Recall | Raw F1 | Adjusted F1 (A) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | 29 | 37 | 1 | 16 | 83 | 0.684 | 0.795 | 0.856 | 0.692 | 0.688 | 0.740 |
| Claude Sonnet 5 | 13 | 7 | 1 | 5 | 26 | 0.835 | 0.918 | 0.949 | 0.508 | 0.632 | 0.654 |
| GPT-5.6 Terra | 8 | 1 | 0 | 3 | 12 | 0.871 | 0.957 | 0.989 | 0.312 | 0.459 | 0.470 |
| DeepSeek Flash | 14 | 29 | 3 | 10 | 56 | 0.696 | 0.772 | 0.826 | 0.492 | 0.577 | 0.601 |

Conservative bound. Some group-A claims on iam.tf attribute the access-key exposure to the Terraform output; without `pgp_key` the `encrypted_secret` attribute that output references is empty, so the output exposes nothing while the plaintext `secret` in state does. Withholding the A credit from every iam.tf claim whose description names the output gives:

| Model | A credits withheld | Adjusted P (A) | Adjusted P without output-pathway credits |
|---|---|---|---|
| Claude Opus 5 | 7 | 0.795 | 0.768 |
| Claude Sonnet 5 | 5 | 0.918 | 0.886 |
| GPT-5.6 Terra | 3 | 0.957 | 0.925 |
| DeepSeek Flash | 4 | 0.772 | 0.750 |

## Table 6. Effect of native reasoning mode (system-prompt enrichment, single agent)

| Model | Reasoning | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Latency (s) | Output tokens | Cost (USD, 30 runs) | Empty-list runs | No-content runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | off | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | 14.8 | 1,267 | 1.41 | 0 | 0 |
| Claude Opus 5 | on | 0.732 | 0.642 | 0.684 | [0.617, 0.745] | 167 | 61 | 93 | 25.6 | 2,059 | 1.98 | 0 | 0 |
| Claude Sonnet 5 | off | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | 7.6 | 816 | 0.43 | 0 | 0 |
| Claude Sonnet 5 | on | 0.869 | 0.435 | 0.579 | [0.512, 0.650] | 113 | 17 | 147 | 15.1 | 1,522 | 0.64 | 0 | 0 |
| DeepSeek Flash | off | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | 3.6 | 640 | 0.01 | 1 | 0 |
| DeepSeek Flash | on | 0.815 | 0.408 | 0.544 | [0.471, 0.619] | 106 | 24 | 154 | 14.2 | 2,981 | 0.03 | 0 | 0 |
| GPT-5.6 Terra | off | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | 4.4 | 257 | 0.18 | 3 | 0 |
| GPT-5.6 Terra | on | 0.917 | 0.338 | 0.494 | [0.446, 0.541] | 88 | 8 | 172 | 8.7 | 570 | 0.29 | 2 | 0 |

Paired F1 difference, reasoning on minus off:

| Model | F1 difference | 95% CI | p | Excludes zero |
|---|---|---|---|---|
| Claude Opus 5 | -0.004 | [-0.042, +0.030] | 0.83 | no |
| Claude Sonnet 5 | -0.052 | [-0.102, +0.007] | 0.08 | no |
| DeepSeek Flash | -0.033 | [-0.091, +0.029] | 0.29 | no |
| GPT-5.6 Terra | +0.035 | [-0.014, +0.089] | 0.18 | no |

Table 7 in the paper (public benchmark standing against observed rank) is compiled from the leaderboards the paper cites, not from the run data, and is not reproduced here.

## Table 8. F1 by model and context variant (single agent; 30 runs per cell)

| Model | zero_shot | few_shot | system_enriched | rag (guidance injection) | chain_of_thought |
|---|---|---|---|---|---|
| Claude Opus 5 | 0.685 | 0.652 | 0.688 | 0.684 | 0.663 |
| Claude Sonnet 5 | 0.664 | 0.592 | 0.632 | 0.638 | 0.605 |
| DeepSeek Flash | 0.566 | 0.570 | 0.577 | 0.565 | 0.531 |
| GPT-5.6 Terra | 0.454 | 0.497 | 0.459 | 0.527 | 0.446 |

Detail behind Table 8:

| Model | Variant | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Cost (USD, 30 runs) |
|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | zero_shot | 0.672 | 0.700 | 0.685 | [0.631, 0.738] | 182 | 89 | 78 | 1.30 |
| Claude Opus 5 | few_shot | 0.671 | 0.635 | 0.652 | [0.599, 0.704] | 165 | 81 | 95 | 1.33 |
| Claude Opus 5 | system_enriched | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | 1.41 |
| Claude Opus 5 | rag (guidance injection) | 0.669 | 0.700 | 0.684 | [0.620, 0.746] | 182 | 90 | 78 | 1.58 |
| Claude Opus 5 | chain_of_thought | 0.633 | 0.696 | 0.663 | [0.612, 0.710] | 181 | 105 | 79 | 1.40 |
| Claude Sonnet 5 | zero_shot | 0.828 | 0.554 | 0.664 | [0.594, 0.731] | 144 | 30 | 116 | 0.42 |
| Claude Sonnet 5 | few_shot | 0.780 | 0.477 | 0.592 | [0.538, 0.642] | 124 | 35 | 136 | 0.44 |
| Claude Sonnet 5 | system_enriched | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | 0.43 |
| Claude Sonnet 5 | rag (guidance injection) | 0.775 | 0.542 | 0.638 | [0.564, 0.705] | 141 | 41 | 119 | 0.53 |
| Claude Sonnet 5 | chain_of_thought | 0.765 | 0.500 | 0.605 | [0.533, 0.676] | 130 | 40 | 130 | 0.44 |
| DeepSeek Flash | zero_shot | 0.645 | 0.504 | 0.566 | [0.502, 0.626] | 131 | 72 | 129 | 0.01 |
| DeepSeek Flash | few_shot | 0.677 | 0.492 | 0.570 | [0.509, 0.628] | 128 | 61 | 132 | 0.01 |
| DeepSeek Flash | system_enriched | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | 0.01 |
| DeepSeek Flash | rag (guidance injection) | 0.619 | 0.519 | 0.565 | [0.504, 0.626] | 135 | 83 | 125 | 0.02 |
| DeepSeek Flash | chain_of_thought | 0.617 | 0.465 | 0.531 | [0.456, 0.597] | 121 | 75 | 139 | 0.01 |
| GPT-5.6 Terra | zero_shot | 0.812 | 0.315 | 0.454 | [0.404, 0.503] | 82 | 19 | 178 | 0.17 |
| GPT-5.6 Terra | few_shot | 0.882 | 0.346 | 0.497 | [0.431, 0.565] | 90 | 12 | 170 | 0.20 |
| GPT-5.6 Terra | system_enriched | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | 0.18 |
| GPT-5.6 Terra | rag (guidance injection) | 0.875 | 0.377 | 0.527 | [0.479, 0.568] | 98 | 14 | 162 | 0.25 |
| GPT-5.6 Terra | chain_of_thought | 0.840 | 0.304 | 0.446 | [0.396, 0.496] | 79 | 15 | 181 | 0.18 |

## Table 9. Paired F1 difference against the same model's zero-shot run

| Model | Variant | F1 difference | 95% CI | p | Excludes zero |
|---|---|---|---|---|---|
| Claude Opus 5 | few_shot | -0.033 | [-0.068, -0.003] | 0.03 | yes |
| Claude Opus 5 | system_enriched | +0.003 | [-0.018, +0.023] | 0.81 | no |
| Claude Opus 5 | rag (guidance injection) | -0.001 | [-0.028, +0.024] | 0.94 | no |
| Claude Opus 5 | chain_of_thought | -0.022 | [-0.045, -0.002] | 0.03 | yes |
| Claude Sonnet 5 | few_shot | -0.072 | [-0.107, -0.036] | <0.001 | yes |
| Claude Sonnet 5 | system_enriched | -0.032 | [-0.087, +0.021] | 0.25 | no |
| Claude Sonnet 5 | rag (guidance injection) | -0.026 | [-0.078, +0.025] | 0.34 | no |
| Claude Sonnet 5 | chain_of_thought | -0.059 | [-0.101, -0.020] | 0.002 | yes |
| DeepSeek Flash | few_shot | +0.004 | [-0.049, +0.060] | 0.89 | no |
| DeepSeek Flash | system_enriched | +0.011 | [-0.039, +0.059] | 0.68 | no |
| DeepSeek Flash | rag (guidance injection) | -0.001 | [-0.037, +0.041] | 0.92 | no |
| DeepSeek Flash | chain_of_thought | -0.035 | [-0.089, +0.009] | 0.12 | no |
| GPT-5.6 Terra | few_shot | +0.043 | [-0.017, +0.103] | 0.16 | no |
| GPT-5.6 Terra | system_enriched | +0.005 | [-0.033, +0.038] | 0.77 | no |
| GPT-5.6 Terra | rag (guidance injection) | +0.073 | [+0.029, +0.115] | <0.001 | yes |
| GPT-5.6 Terra | chain_of_thought | -0.008 | [-0.042, +0.024] | 0.64 | no |

## Table 10. Detection performance and cost by orchestration pattern (system-prompt enrichment)

| Model | Pattern | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Calls per run | Latency (s) | Cost per review (USD) | Cost multiple |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | single | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | 1.0 | 14.8 | 0.0468 | 1.0 |
| Claude Opus 5 | critic | 0.687 | 0.642 | 0.664 | [0.606, 0.716] | 167 | 76 | 93 | 2.0 | 27.2 | 0.0988 | 2.1 |
| Claude Opus 5 | debate | 0.672 | 0.692 | 0.682 | [0.625, 0.731] | 180 | 88 | 80 | 3.0 | 42.2 | 0.1549 | 3.3 |
| Claude Opus 5 | chunked | 0.629 | 0.592 | 0.610 | [0.559, 0.661] | 154 | 91 | 106 | 1.8 | 16.2 | 0.0557 | 1.2 |
| Claude Sonnet 5 | single | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | 1.0 | 7.6 | 0.0144 | 1.0 |
| Claude Sonnet 5 | critic | 0.850 | 0.415 | 0.558 | [0.485, 0.629] | 108 | 19 | 152 | 2.0 | 13.1 | 0.0295 | 2.1 |
| Claude Sonnet 5 | debate | 0.845 | 0.523 | 0.646 | [0.593, 0.695] | 136 | 25 | 124 | 3.0 | 22.0 | 0.0474 | 3.3 |
| Claude Sonnet 5 | chunked | 0.764 | 0.512 | 0.613 | [0.559, 0.670] | 133 | 41 | 127 | 1.8 | 9.8 | 0.0196 | 1.4 |
| DeepSeek Flash | single | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | 1.0 | 3.6 | 0.0004 | 1.0 |
| DeepSeek Flash | critic | 0.784 | 0.419 | 0.546 | [0.473, 0.617] | 109 | 30 | 151 | 2.0 | 6.3 | 0.0010 | 2.2 |
| DeepSeek Flash | debate | 0.745 | 0.538 | 0.625 | [0.555, 0.687] | 140 | 48 | 120 | 3.0 | 10.0 | 0.0016 | 3.5 |
| DeepSeek Flash | chunked | 0.683 | 0.488 | 0.570 | [0.513, 0.622] | 127 | 59 | 133 | 1.8 | 4.6 | 0.0006 | 1.4 |
| GPT-5.6 Terra | single | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | 1.0 | 4.4 | 0.0062 | 1.0 |
| GPT-5.6 Terra | critic | 0.870 | 0.335 | 0.483 | [0.426, 0.531] | 87 | 13 | 173 | 2.0 | 7.3 | 0.0139 | 2.3 |
| GPT-5.6 Terra | debate | 0.874 | 0.373 | 0.523 | [0.463, 0.574] | 97 | 14 | 163 | 3.0 | 11.0 | 0.0219 | 3.6 |
| GPT-5.6 Terra | chunked | 0.817 | 0.396 | 0.534 | [0.472, 0.585] | 103 | 23 | 157 | 1.8 | 5.6 | 0.0092 | 1.5 |

Cost per review is the 30-run cost divided by 30; the cost multiple is relative to the same model's single call. Latency was measured from one cloud container and is comparable within this table only. Debate samples the same model twice and reconciles with a third call.

Mechanism counts used in Section 3.3.3: Claude Opus 5 critic: 260 → 243 findings, shrank in 18/30 runs; Claude Opus 5 debate: reviewers 263/257 → reconciled 268; Claude Sonnet 5 critic: 164 → 127 findings, shrank in 24/30 runs; Claude Sonnet 5 debate: reviewers 159/158 → reconciled 161; DeepSeek Flash critic: 191 → 139 findings, shrank in 17/30 runs; DeepSeek Flash debate: reviewers 179/195 → reconciled 188; GPT-5.6 Terra critic: 109 → 100 findings, shrank in 11/30 runs; GPT-5.6 Terra debate: reviewers 113/111 → reconciled 111. Fabricated resource addresses (claims naming a resource not in the file): Claude Opus 5 single 0/263; Claude Opus 5 chunked 5/245; Claude Sonnet 5 single 0/158; Claude Sonnet 5 chunked 5/174; DeepSeek Flash single 5/184; DeepSeek Flash chunked 9/186; GPT-5.6 Terra single 3/93; GPT-5.6 Terra chunked 5/126.

## Table 11. Paired F1 difference against the same model's single-agent configuration

| Model | Pattern | F1 difference | 95% CI | p | Excludes zero |
|---|---|---|---|---|---|
| Claude Opus 5 | critic | -0.024 | [-0.058, +0.007] | 0.12 | no |
| Claude Opus 5 | debate | -0.007 | [-0.030, +0.013] | 0.58 | no |
| Claude Opus 5 | chunked | -0.078 | [-0.124, -0.034] | <0.001 | yes |
| Claude Sonnet 5 | critic | -0.073 | [-0.128, -0.012] | 0.02 | yes |
| Claude Sonnet 5 | debate | +0.015 | [-0.020, +0.050] | 0.42 | no |
| Claude Sonnet 5 | chunked | -0.019 | [-0.053, +0.020] | 0.34 | no |
| DeepSeek Flash | critic | -0.030 | [-0.097, +0.030] | 0.34 | no |
| DeepSeek Flash | debate | +0.048 | [+0.012, +0.083] | 0.01 | yes |
| DeepSeek Flash | chunked | -0.007 | [-0.046, +0.030] | 0.72 | no |
| GPT-5.6 Terra | critic | +0.024 | [-0.036, +0.076] | 0.40 | no |
| GPT-5.6 Terra | debate | +0.064 | [+0.009, +0.118] | 0.02 | yes |
| GPT-5.6 Terra | chunked | +0.075 | [+0.019, +0.126] | 0.006 | yes |

## Study totals

36 configurations and 1,080 runs: 20 model-and-prompt configurations (single call, reasoning off), 12 model-and-pattern configurations beyond the single call, and 4 reasoning-on configurations, with the system_enriched single call as the baseline for the last two groups. A run is one review of one file; API calls per run: single 1, critic 2, debate 3, chunked 1.83 on average (220 calls over 120 runs); 1,540 calls in all. Every configuration scores 52 findings x 5 repetitions, so TP + FN = 260 in every configuration. No run ended in an API error; 1 run returned no content and is scored as an empty findings list (deepseek-v4-flash__chain_of_thought__single__terragoat_mut__lambda.tf__r3). Every accepted match is at the resource-plus-category or CWE level. Total API spend ≈ $26.88 at the August 2026 list prices in `providers.py`. Prompt provenance is identical across every run (`prompts=8a683cfec1c99d66`).

## Strict-matcher F1 for the model comparison

A resource-plus-category match needs the resource address plus at least one category cue; a CWE-level match needs the resource plus the same CWE. `F1 strict` treats every single-cue and CWE-level match as a false positive and its finding as missed: a bound on what a stricter matcher could report, not a corrected score (Section 3.1.3). All 36 configurations are in `SUPPLEMENT.md`.

| Model | TP | Single-cue TP | CWE-level TP | F1 | F1 strict |
|---|---|---|---|---|---|
| Claude Opus 5 | 180 | 31 | 0 | 0.688 | 0.570 |
| Claude Sonnet 5 | 132 | 20 | 0 | 0.632 | 0.536 |
| DeepSeek Flash | 128 | 24 | 2 | 0.577 | 0.459 |
| GPT-5.6 Terra | 81 | 31 | 0 | 0.459 | 0.283 |

## Chunking by file

The chunked pattern packs whole top-level blocks into chunks of at most 2,500 characters (`agents/hcl.py`). A file under the budget is sent whole in one call under `prompts.CHUNK_HEADER`, which presents the text as an excerpt of a larger file and forbids findings on resources not shown (Section 3.3.3).

| File | Characters | Chunks |
|---|---|---|
| db-app.tf | 8,951 | 4 |
| ec2.tf | 4,768 | 3 |
| iam.tf | 864 | 1 |
| kms.tf | 333 | 1 |
| lambda.tf | 894 | 1 |
| s3.tf | 1,892 | 1 |

Single call versus chunked, pooled over the split files (db-app.tf, ec2.tf) and the unsplit files (iam.tf, kms.tf, lambda.tf, s3.tf):

| Model | Files | TP single → chunked | FP single → chunked | F1 single → chunked | ΔF1 |
|---|---|---|---|---|---|
| Claude Opus 5 | split | 90 → 88 | 37 → 47 | 0.674 → 0.640 | -0.034 |
| Claude Opus 5 | unsplit | 90 → 66 | 46 → 44 | 0.703 → 0.574 | -0.129 |
| Claude Sonnet 5 | split | 69 → 66 | 10 → 30 | 0.630 → 0.559 | -0.071 |
| Claude Sonnet 5 | unsplit | 63 → 67 | 16 → 11 | 0.633 → 0.677 | +0.044 |
| DeepSeek Flash | split | 67 → 68 | 30 → 29 | 0.565 → 0.574 | +0.008 |
| DeepSeek Flash | unsplit | 61 → 59 | 26 → 30 | 0.589 → 0.565 | -0.025 |
| GPT-5.6 Terra | split | 40 → 63 | 6 → 15 | 0.430 → 0.578 | +0.148 |
| GPT-5.6 Terra | unsplit | 41 → 40 | 6 → 8 | 0.491 → 0.476 | -0.015 |

Claude Opus 5 on s3.tf (one chunk, sent whole under the chunk header), CKV2_AWS_6 public-access-block findings matched in five runs, single → chunked: aws_s3_bucket.reports_archive 5 → 5; aws_s3_bucket.model_artifacts 5 → 0; aws_s3_bucket.ledger_exports 5 → 0; aws_s3_bucket.audit_trail 5 → 1; aws_s3_bucket.ops_runbooks 5 → 0.
