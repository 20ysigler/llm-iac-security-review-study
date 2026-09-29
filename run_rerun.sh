#!/bin/bash
# Re-run s3.tf and db-app.tf for all 18 configurations after the mutator fix.
# The runner skips the 4 unchanged files' existing results and re-scores every config.
# Publication note: this line originally sourced a private key file. ANTHROPIC_API_KEY, OPENAI_API_KEY, and DEEPSEEK_HOST_KEY must be in the environment.
cd "$(dirname "$0")"
R="--corpus terragoat_mut --ground-truth data/ground_truth_mut.json --runs 5"
claude () {
  for M in claude-opus-5 claude-sonnet-5; do
    python3 harness/run_experiment.py --model $M --context system_enriched --pattern single $R
    python3 harness/run_experiment.py --model $M --context system_enriched --pattern single $R --reasoning
    for P in critic chunked debate; do python3 harness/run_experiment.py --model $M --context system_enriched --pattern $P $R; done
  done
  for C in zero_shot few_shot chain_of_thought; do python3 harness/run_experiment.py --model claude-sonnet-5 --context $C --pattern single $R; done
  python3 harness/run_experiment.py --model claude-sonnet-5 --context rag --pattern single $R --guidance data/rag_guidance.md
  echo "### CLAUDE DONE $(date -u +%H:%M:%S)"
}
others () {
  for M in gpt-5.6-terra deepseek-v4-flash; do
    python3 harness/run_experiment.py --model $M --context system_enriched --pattern single $R
    python3 harness/run_experiment.py --model $M --context system_enriched --pattern single $R --reasoning
  done
  echo "### OTHERS DONE $(date -u +%H:%M:%S)"
}
claude > logs/rerun_claude.log 2>&1 &
others > logs/rerun_others.log 2>&1 &
wait
echo "ALL DONE $(date -u +%H:%M:%S)" > logs/rerun_driver.log
