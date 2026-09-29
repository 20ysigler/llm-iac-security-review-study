#!/bin/bash
# Fill the grid: context variants on Opus/GPT/DeepSeek; orchestration on GPT/DeepSeek. 5 reps, terragoat_mut.
# Publication note: this line originally sourced a private key file. ANTHROPIC_API_KEY, OPENAI_API_KEY, and DEEPSEEK_HOST_KEY must be in the environment.
cd "$(dirname "$0")"
R="--corpus terragoat_mut --ground-truth data/ground_truth_mut.json --runs 5"
ctx () {  # $1 = model
  for C in zero_shot few_shot chain_of_thought; do
    echo "### START $1 $C $(date -u +%H:%M:%S)"; python3 harness/run_experiment.py --model $1 --context $C --pattern single $R
  done
  echo "### START $1 rag $(date -u +%H:%M:%S)"; python3 harness/run_experiment.py --model $1 --context rag --pattern single $R --guidance data/rag_guidance.md
  echo "### CTX $1 DONE $(date -u +%H:%M:%S)"
}
orch () {  # $1 = model
  for P in critic chunked debate; do
    echo "### START $1 $P $(date -u +%H:%M:%S)"; python3 harness/run_experiment.py --model $1 --context system_enriched --pattern $P $R
  done
  echo "### ORCH $1 DONE $(date -u +%H:%M:%S)"
}
ctx  claude-opus-5       > logs/grid_ctx_opus.log     2>&1 &
ctx  gpt-5.6-terra       > logs/grid_ctx_gpt.log      2>&1 &
ctx  deepseek-v4-flash   > logs/grid_ctx_deepseek.log 2>&1 &
orch gpt-5.6-terra       > logs/grid_orch_gpt.log     2>&1 &
orch deepseek-v4-flash   > logs/grid_orch_deepseek.log 2>&1 &
wait
echo "ALL DONE $(date -u +%H:%M:%S)" > logs/grid_driver.log
