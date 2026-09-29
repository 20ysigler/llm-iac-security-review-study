#!/bin/bash
# Publication note: this line originally sourced a private key file. ANTHROPIC_API_KEY, OPENAI_API_KEY, and DEEPSEEK_HOST_KEY must be in the environment.
cd "$(dirname "$0")"
R="--corpus terragoat_mut --ground-truth data/ground_truth_mut.json --runs 5"
sonnet () {
  M=claude-sonnet-5
  python3 harness/run_experiment.py --model $M --context system_enriched --pattern single $R
  python3 harness/run_experiment.py --model $M --context system_enriched --pattern single $R --reasoning
  for P in critic chunked debate; do python3 harness/run_experiment.py --model $M --context system_enriched --pattern $P $R; done
  echo "### SONNET DONE $(date -u +%H:%M:%S)"
}
set2 () {
  for C in zero_shot few_shot chain_of_thought; do python3 harness/run_experiment.py --model claude-sonnet-5 --context $C --pattern single $R; done
  python3 harness/run_experiment.py --model claude-sonnet-5 --context rag --pattern single $R --guidance data/rag_guidance.md
  echo "### SET2 DONE $(date -u +%H:%M:%S)"
}
sonnet > logs/rerun_sonnet.log 2>&1 &
set2   > logs/rerun_set2.log 2>&1 &
wait
