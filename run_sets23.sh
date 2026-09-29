#!/bin/bash
# Sets 2 and 3 on terragoat_mut, 5 reps. Three sequential streams run concurrently.
# Publication note: this line originally sourced a private key file. ANTHROPIC_API_KEY, OPENAI_API_KEY, and DEEPSEEK_HOST_KEY must be in the environment.
cd "$(dirname "$0")"
R="--corpus terragoat_mut --ground-truth data/ground_truth_mut.json --runs 5"
set2 () {
  for C in zero_shot few_shot chain_of_thought; do
    echo "### START sonnet $C $(date -u +%H:%M:%S)"
    python3 harness/run_experiment.py --model claude-sonnet-5 --context $C --pattern single $R
  done
  echo "### START sonnet rag $(date -u +%H:%M:%S)"
  python3 harness/run_experiment.py --model claude-sonnet-5 --context rag --pattern single $R --guidance data/rag_guidance.md
  echo "### SET2 DONE $(date -u +%H:%M:%S)"
}
set3 () {
  local M=$1
  for P in critic chunked debate; do
    echo "### START $M $P $(date -u +%H:%M:%S)"
    python3 harness/run_experiment.py --model $M --context system_enriched --pattern $P $R
  done
  echo "### SET3 $M DONE $(date -u +%H:%M:%S)"
}
set2                 > logs/set2_sonnet.log 2>&1 &
set3 claude-opus-5   > logs/set3_opus.log   2>&1 &
set3 claude-sonnet-5 > logs/set3_sonnet.log 2>&1 &
wait
echo "ALL DONE $(date -u +%H:%M:%S)" >> logs/set2_sonnet.log
