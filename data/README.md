# Data files

| File | What it is |
|---|---|
| `../terragoat_mut/terraform/aws/*.tf` | the mutated corpus the models reviewed (six files scored: s3.tf, ec2.tf, db-app.tf, iam.tf, kms.tf, lambda.tf); see NOTICE |
| `ground_truth_mut.json` | the 52 findings, keyed `terragoat_mut::<file>`, each with resource, category, CWE, severity, and originating Checkov check; `meta.criteria` states the inclusion criterion |
| `ground_truth.json` | the same 52 findings on the original resource names (`terragoat::<file>`), used to score the pilot runs |
| `checkov_raw.json` | Checkov 3.3.11 output on the original TerraGoat AWS directory: 215 failed checks, 95 of them in the six files reviewed |
| `ground_truth_construction/` | how 95 checks became 52 findings: `ground_truth_scaffold.json` (pretriage of every failed check into security / operational / ambiguous; it also lists an early CloudGoat probe that was not pursued, so only the `terragoat` entries matter), `verdicts_roy.json` (the author's rulings on the 13 ambiguous checks), `ground_truth_review.xlsx` (the review workbook), `rag_guidance_provenance.md` (sources of the guidance text) |
| `rename_map.json` | original -> mutated resource names, produced by `harness/mutate_corpus.py` (seed 20260908) |
| `rag_guidance.md` | the guidance text prepended by the guidance-injection prompt variant (CIS, AWS Well-Architected, OWASP excerpts; no Checkov rule text) |
| `mutation_checkov_diff.txt` | the equivalence check: Checkov's 95 failed checks on the original and mutated files, mapped back by resource name |
| `terragoat_commit.txt` | the TerraGoat commit the corpus was built from |
| `terragoat_resources.json` | the 40 resources in the six original files, by file |
