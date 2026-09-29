#!/bin/bash
# Publication note: this line originally sourced a private key file. ANTHROPIC_API_KEY, OPENAI_API_KEY, and DEEPSEEK_HOST_KEY must be in the environment.
cd "$(dirname "$0")"
R="--context system_enriched --pattern single --corpus terragoat_mut --ground-truth data/ground_truth_mut.json --runs 5 --reasoning"
for M in claude-opus-5 claude-sonnet-5 gpt-5.6-terra deepseek-v4-flash; do
  ( echo "### START $M reasoning $(date -u +%H:%M:%S)"; python3 harness/run_experiment.py --model $M $R; echo "### DONE $M $(date -u +%H:%M:%S)" ) > logs/think_$M.log 2>&1 &
done
wait
echo "ALL DONE $(date -u +%H:%M:%S)" > logs/think_driver.log
