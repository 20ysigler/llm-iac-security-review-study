# Results

All runs on `terragoat_mut` (corpus regenerated 2026-09-22 after a mutator fix; see Corpus note), 5 repetitions per file, 6 files, 30 runs per configuration. Micro-averaged P/R/F1; 95% percentile bootstrap CI (10,000 iterations). Paired comparisons via `harness/compare.py` on shared (file, repetition) units, 20,000 iterations; `p` is the raw two-sided bootstrap p, `Holm p` is Holm-adjusted within the table's family of tests (3 model contrasts, 4 reasoning contrasts, 16 context contrasts, 12 orchestration contrasts). Reasoning off unless stated (Claude: forced tool call; GPT: reasoning_effort none; DeepSeek: thinking disabled). Values are rounded once, from six-decimal summaries (revised 2026-09-27). Regenerate this file with `python3 harness/build_results.py > RESULTS.md`; check it with `python3 harness/verify_paper.py`.

## Set 1 — Model selection (system_enriched, single)

| Model | Served as | P | R | F1 | F1 95% CI | TP | FP | FN | Cost (USD) |
|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | claude-opus-5 | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | 1.41 |
| Claude Sonnet 5 | claude-sonnet-5 | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | 0.43 |
| DeepSeek Flash | deepseek-flash | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | 0.01 |
| GPT-5.6 Terra | gpt-5.6-terra | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | 0.18 |

Paired F1 difference vs Claude Opus 5 (30 shared units):

| Model | F1 diff | 95% CI | p | Holm p | Excludes zero |
|---|---|---|---|---|---|
| Claude Sonnet 5 | -0.057 | [-0.082, -0.034] | <0.001 | <0.001 | yes |
| DeepSeek Flash | -0.112 | [-0.152, -0.071] | <0.001 | <0.001 | yes |
| GPT-5.6 Terra | -0.229 | [-0.277, -0.185] | <0.001 | <0.001 | yes |

Per-file F1 (system_enriched, single):

| Model | db-app.tf | ec2.tf | iam.tf | kms.tf | lambda.tf | s3.tf |
|---|---|---|---|---|---|---|
| Claude Opus 5 | 0.60 | 0.73 | 0.34 | 1.00 | 0.87 | 0.76 |
| Claude Sonnet 5 | 0.56 | 0.69 | 0.33 | 0.89 | 0.75 | 0.72 |
| DeepSeek Flash | 0.50 | 0.63 | 0.27 | 0.75 | 0.58 | 0.73 |
| GPT-5.6 Terra | 0.44 | 0.42 | 0.22 | 0.17 | 0.57 | 0.67 |

### Native reasoning on vs off (Set 1 configurations; added after Sets 1–3)

| Model | Reasoning | P | R | F1 | F1 95% CI | TP | FP | FN | Latency (s) | Out tokens | Cost (USD) | Zero-finding runs | Non-JSON runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | off | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | 14.8 | 1,267 | 1.41 | 0 | 0 |
| Claude Opus 5 | on | 0.732 | 0.642 | 0.684 | [0.617, 0.745] | 167 | 61 | 93 | 25.6 | 2,059 | 1.98 | 0 | 0 |
| Claude Sonnet 5 | off | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | 7.6 | 816 | 0.43 | 0 | 0 |
| Claude Sonnet 5 | on | 0.869 | 0.435 | 0.579 | [0.512, 0.650] | 113 | 17 | 147 | 15.1 | 1,522 | 0.64 | 0 | 0 |
| DeepSeek Flash | off | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | 3.6 | 640 | 0.01 | 1 | 0 |
| DeepSeek Flash | on | 0.815 | 0.408 | 0.544 | [0.471, 0.619] | 106 | 24 | 154 | 14.2 | 2,981 | 0.03 | 0 | 0 |
| GPT-5.6 Terra | off | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | 4.4 | 257 | 0.18 | 3 | 0 |
| GPT-5.6 Terra | on | 0.917 | 0.338 | 0.494 | [0.446, 0.541] | 88 | 8 | 172 | 8.7 | 570 | 0.29 | 2 | 0 |

Paired F1 difference, reasoning on − off:

| Model | F1 diff | 95% CI | p | Holm p | Excludes zero |
|---|---|---|---|---|---|
| Claude Opus 5 | -0.004 | [-0.042, +0.030] | 0.83 | 0.83 | no |
| Claude Sonnet 5 | -0.052 | [-0.102, +0.007] | 0.08 | 0.32 | no |
| DeepSeek Flash | -0.033 | [-0.091, +0.029] | 0.29 | 0.59 | no |
| GPT-5.6 Terra | +0.035 | [-0.014, +0.089] | 0.18 | 0.54 | no |

## Set 2 — Context engineering (all four models, single)

| Model | Variant | P | R | F1 | F1 95% CI | TP | FP | FN | Cost (USD) |
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

Paired F1 difference vs the same model's zero_shot:

| Model | Variant | F1 diff | 95% CI | p | Holm p | Excludes zero |
|---|---|---|---|---|---|---|
| Claude Opus 5 | few_shot | -0.033 | [-0.068, -0.003] | 0.03 | 0.38 | yes |
| Claude Opus 5 | system_enriched | +0.003 | [-0.018, +0.023] | 0.81 | 1.00 | no |
| Claude Opus 5 | rag (guidance injection) | -0.001 | [-0.028, +0.024] | 0.94 | 1.00 | no |
| Claude Opus 5 | chain_of_thought | -0.022 | [-0.045, -0.002] | 0.03 | 0.38 | yes |
| Claude Sonnet 5 | few_shot | -0.072 | [-0.107, -0.036] | <0.001 | 0.003 | yes |
| Claude Sonnet 5 | system_enriched | -0.032 | [-0.087, +0.021] | 0.25 | 1.00 | no |
| Claude Sonnet 5 | rag (guidance injection) | -0.026 | [-0.078, +0.025] | 0.34 | 1.00 | no |
| Claude Sonnet 5 | chain_of_thought | -0.059 | [-0.101, -0.020] | 0.002 | 0.03 | yes |
| DeepSeek Flash | few_shot | +0.004 | [-0.049, +0.060] | 0.89 | 1.00 | no |
| DeepSeek Flash | system_enriched | +0.011 | [-0.039, +0.059] | 0.68 | 1.00 | no |
| DeepSeek Flash | rag (guidance injection) | -0.001 | [-0.037, +0.041] | 0.92 | 1.00 | no |
| DeepSeek Flash | chain_of_thought | -0.035 | [-0.089, +0.009] | 0.12 | 1.00 | no |
| GPT-5.6 Terra | few_shot | +0.043 | [-0.017, +0.103] | 0.16 | 1.00 | no |
| GPT-5.6 Terra | system_enriched | +0.005 | [-0.033, +0.038] | 0.77 | 1.00 | no |
| GPT-5.6 Terra | rag (guidance injection) | +0.073 | [+0.029, +0.115] | <0.001 | 0.007 | yes |
| GPT-5.6 Terra | chain_of_thought | -0.008 | [-0.042, +0.024] | 0.64 | 1.00 | no |

F1 by model and variant (compact):

| Model | zero_shot | few_shot | system_enriched | rag | chain_of_thought |
|---|---|---|---|---|---|
| Claude Opus 5 | 0.685 | 0.652 | 0.688 | 0.684 | 0.663 |
| Claude Sonnet 5 | 0.664 | 0.592 | 0.632 | 0.638 | 0.605 |
| DeepSeek Flash | 0.566 | 0.570 | 0.577 | 0.565 | 0.531 |
| GPT-5.6 Terra | 0.454 | 0.497 | 0.459 | 0.527 | 0.446 |

## Set 3 — Orchestration (all four models, system_enriched)

| Model | Pattern | P | R | F1 | F1 95% CI | TP | FP | FN | Calls | Latency (s) | Cost/review (USD) | Cost × |
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

Paired F1 difference vs same-model single:

| Model | Pattern | F1 diff | 95% CI | p | Holm p | Excludes zero |
|---|---|---|---|---|---|---|
| Claude Opus 5 | critic | -0.024 | [-0.058, +0.007] | 0.12 | 0.86 | no |
| Claude Opus 5 | debate | -0.007 | [-0.030, +0.013] | 0.58 | 1.00 | no |
| Claude Opus 5 | chunked | -0.078 | [-0.124, -0.034] | <0.001 | <0.001 | yes |
| Claude Sonnet 5 | critic | -0.073 | [-0.128, -0.012] | 0.02 | 0.20 | yes |
| Claude Sonnet 5 | debate | +0.015 | [-0.020, +0.050] | 0.42 | 1.00 | no |
| Claude Sonnet 5 | chunked | -0.019 | [-0.053, +0.020] | 0.34 | 1.00 | no |
| DeepSeek Flash | critic | -0.030 | [-0.097, +0.030] | 0.34 | 1.00 | no |
| DeepSeek Flash | debate | +0.048 | [+0.012, +0.083] | 0.01 | 0.13 | yes |
| DeepSeek Flash | chunked | -0.007 | [-0.046, +0.030] | 0.72 | 1.00 | no |
| GPT-5.6 Terra | critic | +0.024 | [-0.036, +0.076] | 0.40 | 1.00 | no |
| GPT-5.6 Terra | debate | +0.064 | [+0.009, +0.118] | 0.02 | 0.20 | yes |
| GPT-5.6 Terra | chunked | +0.075 | [+0.019, +0.126] | 0.006 | 0.07 | yes |

F1 by model and pattern (compact):

| Model | single | critic | debate | chunked |
|---|---|---|---|---|
| Claude Opus 5 | 0.688 | 0.664 | 0.682 | 0.610 |
| Claude Sonnet 5 | 0.632 | 0.558 | 0.646 | 0.613 |
| DeepSeek Flash | 0.577 | 0.546 | 0.625 | 0.570 |
| GPT-5.6 Terra | 0.459 | 0.483 | 0.523 | 0.534 |

Mechanism: Claude Opus 5 critic: 260 → 243 findings, shrank in 18/30 runs; Claude Opus 5 debate: reviewers 263/257 → reconciled 268; Claude Sonnet 5 critic: 164 → 127 findings, shrank in 24/30 runs; Claude Sonnet 5 debate: reviewers 159/158 → reconciled 161; DeepSeek Flash critic: 191 → 139 findings, shrank in 17/30 runs; DeepSeek Flash debate: reviewers 179/195 → reconciled 188; GPT-5.6 Terra critic: 109 → 100 findings, shrank in 11/30 runs; GPT-5.6 Terra debate: reviewers 113/111 → reconciled 111. Fabricated resource addresses (claim address not present in the file): Claude Opus 5 single 0/263; Claude Opus 5 chunked 5/245; Claude Sonnet 5 single 0/158; Claude Sonnet 5 chunked 5/174; DeepSeek Flash single 5/184; DeepSeek Flash chunked 9/186; GPT-5.6 Terra single 3/93; GPT-5.6 Terra chunked 5/126. Debate samples the same model twice (self-consistency), not two different models. Latency measured from one cloud container; comparable within this table only.

## Study totals

36 configurations, 1080 runs, zero error runs in the reported data (1 run returned no parsable content and is scored as an empty findings list: deepseek-v4-flash__chain_of_thought__single__terragoat_mut__lambda.tf__r3), zero lexical-level matches (the lexical level cannot fire: category scores take only the values 0, 0.5 and 1, so no score falls in its [0.25, 0.5) window), zero findings pending adjudication. Total API spend for the reported runs ≈ $26.88 at the August 2026 list prices in `providers.py` (plus ≈ $6 for 180 superseded runs on the pre-fix corpus, retained in the repository history at fdb7d76). Prompt provenance identical across every run (`prompts=8a683cfec1c99d66`).

## Multiplicity across all 35 paired tests

Holm-adjusted across all 35 tests at once, the contrasts with adjusted p ≤ 0.01 are: Claude Sonnet 5 / few_shot (0.006); Claude Opus 5 / chunked (<0.001); Claude Sonnet 5 (<0.001); DeepSeek Flash (<0.001); GPT-5.6 Terra (<0.001). Every other contrast, including the three positive orchestration differences (DeepSeek debate, GPT debate, GPT chunked), does not reach 0.01 after correction within its own family or globally.

## Matcher sensitivity (added 2026-09-27)

A level-1 match needs the resource address plus at least one category cue (score 0.5); a CWE-level match needs the resource plus the same CWE. Single-cue and CWE-level matches are the ones most exposed to wrong-target credit. `F1 strict` treats every such match as a false positive and its finding as missed: a lower bound on what a stricter matcher could report, not a corrected score.

| Model | Configuration | TP | single-cue TP | CWE-level TP | F1 | F1 strict |
|---|---|---|---|---|---|---|
| Claude Opus 5 | chain_of_thought / single | 181 | 29 | 1 | 0.663 | 0.553 |
| Claude Opus 5 | few_shot / single | 165 | 35 | 2 | 0.652 | 0.506 |
| Claude Opus 5 | rag / single | 182 | 27 | 0 | 0.684 | 0.583 |
| Claude Opus 5 | system_enriched / chunked | 154 | 27 | 1 | 0.610 | 0.499 |
| Claude Opus 5 | system_enriched / critic | 167 | 39 | 1 | 0.664 | 0.505 |
| Claude Opus 5 | system_enriched / debate | 180 | 39 | 1 | 0.682 | 0.530 |
| Claude Opus 5 | system_enriched / single | 180 | 31 | 0 | 0.688 | 0.570 |
| Claude Opus 5 | system_enriched / single / reasoning on | 167 | 28 | 0 | 0.684 | 0.570 |
| Claude Opus 5 | zero_shot / single | 182 | 29 | 2 | 0.685 | 0.569 |
| Claude Sonnet 5 | chain_of_thought / single | 130 | 25 | 0 | 0.605 | 0.488 |
| Claude Sonnet 5 | few_shot / single | 124 | 20 | 0 | 0.592 | 0.496 |
| Claude Sonnet 5 | rag / single | 141 | 26 | 0 | 0.638 | 0.520 |
| Claude Sonnet 5 | system_enriched / chunked | 133 | 23 | 1 | 0.613 | 0.502 |
| Claude Sonnet 5 | system_enriched / critic | 108 | 12 | 5 | 0.558 | 0.470 |
| Claude Sonnet 5 | system_enriched / debate | 136 | 20 | 1 | 0.646 | 0.546 |
| Claude Sonnet 5 | system_enriched / single | 132 | 20 | 0 | 0.632 | 0.536 |
| Claude Sonnet 5 | system_enriched / single / reasoning on | 113 | 18 | 0 | 0.579 | 0.487 |
| Claude Sonnet 5 | zero_shot / single | 144 | 19 | 0 | 0.664 | 0.576 |
| DeepSeek Flash | chain_of_thought / single | 121 | 25 | 0 | 0.531 | 0.421 |
| DeepSeek Flash | few_shot / single | 128 | 31 | 1 | 0.570 | 0.428 |
| DeepSeek Flash | rag / single | 135 | 31 | 1 | 0.565 | 0.431 |
| DeepSeek Flash | system_enriched / chunked | 127 | 30 | 1 | 0.570 | 0.430 |
| DeepSeek Flash | system_enriched / critic | 109 | 22 | 1 | 0.546 | 0.431 |
| DeepSeek Flash | system_enriched / debate | 140 | 50 | 1 | 0.625 | 0.397 |
| DeepSeek Flash | system_enriched / single | 128 | 24 | 2 | 0.577 | 0.459 |
| DeepSeek Flash | system_enriched / single / reasoning on | 106 | 18 | 0 | 0.544 | 0.451 |
| DeepSeek Flash | zero_shot / single | 131 | 29 | 0 | 0.566 | 0.441 |
| GPT-5.6 Terra | chain_of_thought / single | 79 | 35 | 2 | 0.446 | 0.237 |
| GPT-5.6 Terra | few_shot / single | 90 | 27 | 5 | 0.497 | 0.320 |
| GPT-5.6 Terra | rag / single | 98 | 22 | 0 | 0.527 | 0.409 |
| GPT-5.6 Terra | system_enriched / chunked | 103 | 38 | 0 | 0.534 | 0.337 |
| GPT-5.6 Terra | system_enriched / critic | 87 | 33 | 0 | 0.483 | 0.300 |
| GPT-5.6 Terra | system_enriched / debate | 97 | 33 | 0 | 0.523 | 0.345 |
| GPT-5.6 Terra | system_enriched / single | 81 | 31 | 0 | 0.459 | 0.283 |
| GPT-5.6 Terra | system_enriched / single / reasoning on | 88 | 25 | 2 | 0.494 | 0.343 |
| GPT-5.6 Terra | zero_shot / single | 82 | 35 | 2 | 0.454 | 0.249 |

Across all 36 configurations: 4649 accepted matches, 1006 single-cue (21.6%), 33 CWE-level (0.7%).

## DeepSeek tariff note (added 2026-09-27)

Every cost figure uses the August 2026 list prices hard-coded in `providers.py` (DeepSeek $0.14 / $0.28 per million input / output tokens). DeepSeek's schedule for `deepseek-flash` on 2026-09-27 is cache-aware and time-of-day dependent ($0.15 / $0.30 per million input tokens on a cache miss, $0.003 / $0.006 on a cache hit, $0.60 / $1.20 output, off-peak / peak UTC). Repricing the 30 baseline DeepSeek runs by their timestamps and token counts gives $0.0178 (every input token a cache hit) to $0.0299 (every input token a cache miss) against $0.0133 at the constant tariff. Cache statistics and invoices were not retained; the constant-tariff figures remain the study's cost basis.

## Run accounting (added 2026-09-28)

20 model-and-prompt configurations (single call, reasoning off), 12 model-and-pattern configurations beyond the single call, and 4 reasoning-on configurations share the system_enriched single call as baseline: 36 configurations. A run is one review of one file. API calls per run: single 1, critic 2, debate 3, chunked 1.83 on average (220 calls over 120 runs); 1,540 calls in all. Every configuration scores 52 findings x 5 repetitions, so TP + FN = 260 in every configuration.

## Chunking by file (added 2026-09-28)

The chunked pattern packs whole top-level blocks into chunks of at most 2,500 characters (`agents/hcl.py`), so a file under the budget is sent whole in one call, under `prompts.CHUNK_HEADER`, which presents the text as an excerpt and forbids findings on resources not shown.

| File | Characters | Chunks |
|---|---|---|
| db-app.tf | 8,951 | 4 |
| ec2.tf | 4,768 | 3 |
| iam.tf | 864 | 1 |
| kms.tf | 333 | 1 |
| lambda.tf | 894 | 1 |
| s3.tf | 1,892 | 1 |

Single-call versus chunked, pooled over the split files (db-app.tf, ec2.tf) and the unsplit files (iam.tf, kms.tf, lambda.tf, s3.tf):

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

Claude Opus 5 on s3.tf (one chunk; sent whole under the chunk header), CKV2_AWS_6 public-access-block findings matched in 5 runs, single → chunked: aws_s3_bucket.reports_archive 5 → 5; aws_s3_bucket.model_artifacts 5 → 0; aws_s3_bucket.ledger_exports 5 → 0; aws_s3_bucket.audit_trail 5 → 1; aws_s3_bucket.ops_runbooks 5 → 0.

## Reasoning-on output ceiling (added 2026-09-28; DeepSeek arm rerun 2026-09-29)

`max_tokens` is 4,096 on every reasoning-off call. With reasoning on, `providers.py` raises the ceiling to 8,000 for the Claude (`max_tokens`) and GPT (`max_output_tokens`, /v1/responses) calls and to 16,000 for the DeepSeek chat/completions call. The DeepSeek ceiling was raised twice: the September 20-22 runs kept 4,096 and eight of 30 stopped at exactly that ceiling before returning a findings list (six with no content, two with prose); a rerun on 2026-09-29 at 8,000 still stopped one of 30 at the ceiling. The reported arm is the 2026-09-29 rerun at 16,000, chosen so that the ceiling does not bind; no run reached it. Both superseded arms are retained with their scored summaries in `harness/results_superseded/` (`..._think_4096/`, `..._think_8000/`); every rerun response was served as `deepseek-flash`, the identifier the September runs recorded, and `providers_sha` in each rerun file records the provider code.

| Model | Ceiling | Reasoning-on runs at the ceiling | Of which empty findings | Max output tokens seen |
|---|---|---|---|---|
| Claude Opus 5 | 8,000 | 0 | 0 | 3,734 |
| Claude Sonnet 5 | 8,000 | 0 | 0 | 2,943 |
| DeepSeek Flash | 16,000 | 0 | 0 | 8,314 |
| GPT-5.6 Terra | 8,000 | 0 | 0 | 1,437 |

Superseded DeepSeek reasoning-on arm at 4,096 (30 runs, 2026-09-20 to 2026-09-22): F1 0.424, 8 runs at the ceiling, 8 scored as empty.

Superseded DeepSeek reasoning-on arm at 8,000 (30 runs, 2026-09-29 to 2026-09-29): F1 0.528, 1 runs at the ceiling, 1 scored as empty.

Reported DeepSeek reasoning-on arm at 16,000 (2026-09-29): F1 0.544, longest response 8,314 tokens.

## Corpus note (2026-09-22)

The first mutated corpus (used for runs on 2026-09-20) carried a defect: the string-fragment rule `og-` → `catalogopts-` matched inside `log-delivery-write`, turning the `audit_trail` bucket's ACL into the invalid value `lcatalogopts-delivery-write`, and sequential replacement double-substituted several identifier strings in db-app.tf (`catalcatalogopts-`). Neither touched a ground-truth attribute, and Checkov's 95/95 result held, but two models flagged the invalid ACL as a finding. `mutate_corpus.py` was fixed (single-pass, boundary-anchored replacement), the corpus regenerated, Checkov re-validated (95/95, zero drift), and every run on the two affected files (s3.tf, db-app.tf; 180 runs across the 18 configurations then existing) was redone. The other four files were byte-identical before and after and their runs stand. One DeepSeek reasoning run failed on a dropped connection (IncompleteRead) and was redone; that exception is now retryable in `providers.py`. The 18 configurations added on 2026-09-26 (context variants on Opus, GPT and DeepSeek; orchestration on GPT and DeepSeek) ran on the corrected corpus only.

## Unmatched-claim (false-positive) adjudication — Set 1, reasoning off

Every unmatched claim (177: Opus 83, DeepSeek 56, Sonnet 26, GPT 12) was classified into one of four buckets. First pass by Claude (an Anthropic model; disclosed), then reviewed row by row by the author, whose verdict governs. Sheet: `harness/fp_review/set1_fp_review.xlsx`.

Buckets: **A** real vulnerability outside the oracle's rule coverage; **B** true observation excluded by the study criteria (recovery controls, passive logging, tags, hardening without an attack path, design facts); **C** model error; **D** duplicate of a finding credited elsewhere in the same run (including matcher attribution).

Adjusted precision = (TP + A) / (TP + FP); a second figure also credits D. Recall is unaffected.

| Model | A real | B excluded | C wrong | D duplicate | FP | Raw P | Adjusted P (A) | Adjusted P (A+D) | Recall | Raw F1 | Adjusted F1 (A) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | 29 | 37 | 1 | 16 | 83 | 0.684 | 0.795 | 0.856 | 0.692 | 0.688 | 0.740 |
| Claude Sonnet 5 | 13 | 7 | 1 | 5 | 26 | 0.835 | 0.918 | 0.949 | 0.508 | 0.632 | 0.654 |
| GPT-5.6 Terra | 8 | 1 | 0 | 3 | 12 | 0.871 | 0.957 | 0.989 | 0.312 | 0.459 | 0.470 |
| DeepSeek Flash | 14 | 29 | 3 | 10 | 56 | 0.696 | 0.772 | 0.826 | 0.492 | 0.577 | 0.601 |

Output-pathway sensitivity (added 2026-09-27): some bucket-A claims on iam.tf attribute the access-key exposure to the Terraform output. Without `pgp_key` the `encrypted_secret` attribute that the output references is empty, so the output pathway exposes nothing; the plaintext `secret` in state does. Withholding the A credit from every iam.tf claim whose description names the output gives:

| Model | A credits withheld | Adjusted P (A) | Adjusted P without output-pathway credits |
|---|---|---|---|
| Claude Opus 5 | 7 | 0.795 | 0.768 |
| Claude Sonnet 5 | 5 | 0.918 | 0.886 |
| GPT-5.6 Terra | 3 | 0.957 | 0.925 |
| DeepSeek Flash | 4 | 0.772 | 0.750 |

Reviewed row by row by the author on 2026-09-22; all 177 first-pass verdicts accepted (agreement 177/177). Outright model errors are rare (5 of 177). The largest single source of unmatched claims is bucket B on S3 buckets (versioning, access logging, `force_destroy`), which Opus and DeepSeek report on nearly every bucket in every run. The most common bucket-A findings: database credentials interpolated into EC2 `user_data` (all four models), the IAM access-key secret in state and in an output (all four), MySQL ingress scoped to the whole VPC rather than the application security group, snapshots of unencrypted volumes, and missing TLS-only bucket policies.
