# Pilot runs on the original TerraGoat files

1,050 runs made in August and early September 2026 on the original, unmutated TerraGoat AWS files (corpus `terragoat`), before the mutated corpus existed. The paper uses them in two places only: to choose system-prompt enrichment as the fixed prompt for the model comparison and the orchestration leg (Section 3.2.1: paired on the shared runs, it was the only variant to beat zero-shot), and to note that the pilot's top-of-ranking, Opus then Sonnet, was reproduced on the mutated corpus (Section 3.4.1).

The pilot ran up to fifteen repetitions on five configurations and five on the rest, with an earlier revision of the harness (the pilot harness is archived in the study's validation package). Score them against `data/ground_truth.json` (the same 52 findings on the original resource names) with `harness/score.py`; the file format is the one described in `harness/results/README.md`. These runs are not part of the 1,080 reported in the paper.
