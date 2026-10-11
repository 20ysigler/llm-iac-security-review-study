# Superseded runs

Runs that were replaced before the reported data set was fixed. None of them is part of the 1,080 runs in `harness/results/`, and `harness/verify_paper.py` reads them only to confirm the figures quoted in `SUPPLEMENT.md`.

- `deepseek-v4-flash__system_enriched__single__terragoat_mut__think_4096/` and `..._think_8000/`: the DeepSeek reasoning-on configuration at output ceilings of 4,096 and 8,000 tokens, each with its `scored_summary.json`. The reported arm, at 16,000 tokens, is in `harness/results/` (`SUPPLEMENT.md`, "Reasoning-on output ceilings").
- `pre_mutator_fix_snapshot_fdb7d76/`: the 180 runs on s3.tf and db-app.tf made before a defect in `mutate_corpus.py` was corrected, with the two pre-fix corpus files (paper, Section 3.4.1).
