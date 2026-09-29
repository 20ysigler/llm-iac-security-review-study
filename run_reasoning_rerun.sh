#!/usr/bin/env bash
# 2026-09-29: rerun of the DeepSeek reasoning-on arm. Run twice: first with the
# 8,000-token output ceiling (one run still truncated), then with 16,000, which
# is the reported arm (providers.py). Before each run the previous arm's files
# were moved to harness/results_superseded/ so run_experiment.py did not skip them.
set -euo pipefail
cd "$(dirname "$0")"
python3 harness/run_experiment.py --model deepseek-v4-flash --context system_enriched \
  --pattern single --corpus terragoat_mut --ground-truth data/ground_truth_mut.json \
  --reasoning --runs 5
