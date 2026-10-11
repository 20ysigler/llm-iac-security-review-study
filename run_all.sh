#!/usr/bin/env bash
# Re-run the whole study: 36 configurations x 6 files x 5 repetitions on the
# mutated corpus, about $27 at August 2026 list prices. Needs ANTHROPIC_API_KEY,
# OPENAI_API_KEY, and DEEPSEEK_HOST_KEY in the environment. run_experiment.py
# skips any run whose result file already exists, so the script can be
# interrupted and restarted; it writes to harness/results/ and harness/scored/.
set -euo pipefail
cd "$(dirname "$0")"
COMMON="--corpus terragoat_mut --ground-truth data/ground_truth_mut.json --runs 5"
MODELS="claude-opus-5 claude-sonnet-5 gpt-5.6-terra deepseek-v4-flash"

for M in $MODELS; do
  # Context variants, single call (20 configurations).
  for C in zero_shot few_shot system_enriched chain_of_thought; do
    python3 harness/run_experiment.py --model "$M" --context "$C" --pattern single $COMMON
  done
  python3 harness/run_experiment.py --model "$M" --context rag --pattern single $COMMON --guidance data/rag_guidance.md
  # Orchestration patterns on the enriched prompt (12 configurations).
  for P in critic debate chunked; do
    python3 harness/run_experiment.py --model "$M" --context system_enriched --pattern "$P" $COMMON
  done
  # Native reasoning on, enriched prompt, single call (4 configurations).
  python3 harness/run_experiment.py --model "$M" --context system_enriched --pattern single $COMMON --reasoning
done

python3 harness/rescore.py
python3 harness/build_results.py
python3 harness/verify_paper.py
