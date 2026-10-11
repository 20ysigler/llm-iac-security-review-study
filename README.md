# LLM security review of Terraform: model, prompt, agent pattern, and reasoning

Data and code for **AI-Facilitated IaC Security Review: The Effects of Model Selection, Context Engineering, and Agent Orchestration on Vulnerability Detection** (Clifton Sigler, SANS Technology Institute, 2026).

## The question and the answer

Can a large language model take on part of the security review of Terraform, and how much do the model, the prompt, the agent pattern, and native reasoning each matter?

Four models (Claude Opus 5, Claude Sonnet 5, GPT-5.6 Terra, and a DeepSeek Flash endpoint) reviewed six files of a mutated TerraGoat corpus, rewritten to reduce recall from training data, across five prompt variants and four orchestration patterns, five repetitions each: 36 configurations, 1,080 scored runs, 1,540 API calls, about $27 at list prices. Every claim a model made was scored against 52 Checkov-derived findings.

**Model choice mattered most, and what it changed was recall.** With the same prompt and a single call:

| Model | Precision | Recall | F1 | F1 95% CI | TP | FP | FN | Paired F1 difference vs Opus (p) |
|---|---|---|---|---|---|---|---|---|
| Claude Opus 5 | 0.684 | 0.692 | 0.688 | [0.636, 0.735] | 180 | 83 | 80 | — |
| Claude Sonnet 5 | 0.835 | 0.508 | 0.632 | [0.576, 0.682] | 132 | 26 | 128 | −0.057 (<0.001) |
| DeepSeek Flash | 0.696 | 0.492 | 0.577 | [0.517, 0.633] | 128 | 56 | 132 | −0.112 (<0.001) |
| GPT-5.6 Terra | 0.871 | 0.312 | 0.459 | [0.405, 0.512] | 81 | 12 | 179 | −0.229 (<0.001) |

The cheaper models were not wrong more often; they found less. Prompt design and multi-agent patterns helped only the two weakest models, by five to eight F1 points, lowered the two strongest, and cost up to 3.6 times as much. Native reasoning helped no model. A review of the 177 claims the scorer rejected in the model comparison found that a third were real weaknesses the Checkov-derived ground truth could not see and two-fifths were true observations outside the study's criterion; adjusted precision ranged from 0.77 to 0.96 and the ranking did not change.

Every table in the paper is in [`RESULTS.md`](RESULTS.md), numbered as in the paper, and every number in it recomputes from the raw run files. Analyses the paper does not report (Holm-adjusted p-values for all 35 paired tests, matcher sensitivity for every configuration, output ceilings) are in [`SUPPLEMENT.md`](SUPPLEMENT.md).

## Reproduce the tables without an API key

```bash
git clone https://github.com/20ysigler/llm-iac-security-review-study.git
cd llm-iac-security-review-study
python3 harness/verify_paper.py                 # re-derives every number in RESULTS.md and SUPPLEMENT.md from harness/results/ (270 checks)
python3 harness/build_results.py /tmp/out       # regenerates both files; then diff /tmp/out/RESULTS.md RESULTS.md
python3 harness/rescore.py                      # rebuilds harness/scored/ from the raw runs
```

The harness is Python 3.11 standard library only. `requirements.txt` lists Checkov 3.3.11, needed only to re-validate the corpus:

```bash
pip install -r requirements.txt
python3 harness/validate_mutation.py            # Checkov on the mutated corpus: 95 failed checks, identical to the original
```

Re-running the models needs `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `DEEPSEEK_HOST_KEY` in the environment and about $27 at August 2026 list prices: `./run_all.sh` runs the 36 configurations, rescores, rebuilds the tables, and verifies them. `run_experiment.py` skips a run whose result file already exists, so a partial rerun is safe.

## What is here

```
RESULTS.md                   every table in the paper (Tables 2 to 11), the study totals, and the two supplementary tables the paper's text quotes
SUPPLEMENT.md                analyses the paper does not report: Holm-adjusted p-values, matcher sensitivity for all 36 configurations, output ceilings
run_all.sh                   re-runs the whole study
harness/                     the code
  run_experiment.py            runner: one configuration, six files, n repetitions
  prompts.py                   the five prompt variants and the critic, reconciler, and chunk instructions (hash 8a683cfec1c99d66 in every run)
  schema.py                    the JSON response schema the models answer through
  providers.py                 Anthropic, OpenAI, and DeepSeek calls: endpoints, tool forcing, reasoning settings, output ceilings, retries
  agents/patterns.py, hcl.py   single, critic, debate, and chunked patterns; whole-block chunking with a resource manifest
  match.py                     the matcher: resource + category cues, then CWE; greedy, one-to-one
  score.py, compare.py         pooled precision/recall/F1, percentile bootstrap (10,000 draws), paired bootstrap on shared file-and-repetition units (20,000 draws), Holm adjustment
  build_results.py             writes RESULTS.md and SUPPLEMENT.md
  verify_paper.py              recomputes every number in both files from the run files and fails on any mismatch
  rescore.py                   regenerates harness/scored/ from harness/results/
  mutate_corpus.py             the corpus rewrite (seed 20260908); validate_mutation.py checks it against Checkov
  test_agents.py               offline tests of the four patterns against a stub provider
  results/                     the 1,080 raw run files, one per model x context x pattern x file x repetition (README.md describes the fields)
  scored/                      the 36 per-configuration summaries (pooled counts, per-run counts, bootstrap intervals)
  fp_review/                   the 177 rejected claims of the model comparison with the first-pass classification and the author's verdicts
  results_pilot_original/      the 1,050 pilot runs on the original, unmutated TerraGoat files (README.md inside)
  results_superseded/          runs replaced before the data set was fixed: two earlier DeepSeek reasoning arms and the 180 pre-fix corpus runs (README.md inside)
terragoat_mut/               the mutated corpus the models reviewed; NOTICE for the TerraGoat licence
data/
  ground_truth_mut.json        the 52 findings, each with resource, category, CWE, severity, and originating Checkov check
  checkov_raw.json             Checkov 3.3.11 output on the original TerraGoat AWS files (215 failed checks; 95 in the six files reviewed)
  ground_truth_construction/   how the 95 checks became 52 findings: pretriage, the author's rulings on the 13 ambiguous checks, review workbook
  ground_truth.json            the same 52 findings on the original resource names, used to score the pilot runs
  rename_map.json              original -> mutated resource names
  rag_guidance.md              the guidance text injected by the guidance-injection variant
  mutation_checkov_diff.txt    the Checkov equivalence check between original and mutated files
  terragoat_commit.txt         the TerraGoat commit the corpus was built from (729f8da, 2023-04-27)
paper/                       the paper will be added here once SANS has accepted it
```

## How a run is scored

A run is one review of one file. The model answers through a fixed JSON schema (resource, issue category, description, severity, CWE). A claim matches a ground-truth finding when it names the same resource and its category or description contains at least one cue from the finding's category vocabulary, or when it carries the same CWE on the same resource; matching is greedy and one-to-one. Unmatched claims are false positives, unmatched findings are false negatives. Precision, recall, and F1 are computed from counts pooled over a configuration's 30 runs; confidence intervals resample the 30 runs; paired comparisons between two configurations resample the 30 file-and-repetition units they share. Section 2 of the paper and `harness/match.py` have the details, and `harness/fp_review/` shows what the 177 rejected claims of the model comparison were.

## Limitations

The ground truth is what Checkov can see, and one rater classified both the 95 Checkov checks and the 177 rejected claims; precision as scored is therefore a floor, and the adjusted figures in Table 5 are bounds, not corrected scores. About 22% of accepted matches rest on a single vocabulary cue; the strict-matcher tables bound the effect but no sample of matches was independently verified. Thirty-five paired tests were run without correction, and the paper draws conclusions at p ≤ 0.01; the Holm-adjusted values in `SUPPLEMENT.md` show which results survive correction. The mutated corpus carries two defects (an unresolved `local.env_prefix` reference and an AMI filter that matches no image) that Checkov does not see and the models could. In the chunked pattern, four of the six files were short enough to be sent whole under the chunk header, so for those files the pattern differs from the single call only by that header. The debate pattern's reviewer overlap was not recorded, so the union-plus-pruning reading of its results is an inference. Memorization of the public corpus was reduced by the mutation, not measured.

## Licence and citation

Code: MIT (`LICENSE`). Model outputs, scored data, and tables: CC BY 4.0 (`LICENSE-DATA`). The mutated corpus is a derivative of Bridgecrew's TerraGoat, Apache License 2.0 (`NOTICE`). Cite with `CITATION.cff`, or:

> Sigler, C. (2026). *llm-iac-security-review-study: Harness, corpus, and results for AI-facilitated IaC security review* (Version v1.1) [Computer software and data]. GitHub. https://github.com/20ysigler/llm-iac-security-review-study

Contact: Clifton Sigler, clifton@collusion.org.
