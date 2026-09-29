# Known limitations and open items

What a reviewer of the paper should weigh, with what would settle each item and what it would cost. Numbers reproduce from `RESULTS.md` in this repository (`harness/verify_paper.py`, 241 checks). Items are grouped by when they were identified; none was repaired beyond disclosure in the paper.

## Identified during the final revision (September 2026)

1. **Chunked pattern: header effect versus split effect.** The 2,500-character chunk budget split only db-app.tf (4 chunks) and ec2.tf (3). The other four files were sent whole under `CHUNK_HEADER`, which tells the model it is reading an excerpt and forbids findings on resources not shown. Opus lost 24 of its 26 chunked true positives on the unsplit files (22 on s3.tf, where CKV2_AWS_6 public-access-block matches fell from 5/5 to 0/5 on three buckets and 1/5 on a fourth); GPT's net gain of 22 true positives was 23 on the two split files and one fewer on the unsplit ones. The paper now reports these counts (Sections 3.3.1, 3.3.3, 4.3.2) and attributes the Opus loss to the header "most plausibly". Settling it needs a header-only arm (whole file plus `CHUNK_HEADER`) or a chunked arm without the header on the four unsplit files: 4 models x 4 files x 5 repetitions = 80 runs, about $2 at list prices. Not run.

2. **DeepSeek reasoning-on results were confounded by the output ceiling (resolved 2026-09-29).** The arm was rerun twice: at 8,000 tokens (the Claude and GPT reasoning ceiling) one run of 30 still truncated; at 16,000 no run reached the ceiling (longest response 8,314 tokens). The reported arm is the 16,000 run: F1 0.544 against 0.577 with reasoning off, difference −0.033, 95% CI [−0.091, +0.029], p = 0.29, the same pattern as the other three models (more precise, less thorough, no measurable change). Both superseded arms are retained with their scored summaries in `harness/results_superseded/`. Residual: the DeepSeek reasoning arm was run nine days after the rest of the study, under the same served identifier (`deepseek-flash`); no Claude or GPT reasoning response came within half of its own 8,000-token ceiling, so those arms were not rerun.

3. **Mutation defects left in the corpus.** The six reviewed files reference `local.env_prefix` while consts.tf defines `resource_prefix`, so the corpus does not validate as Terraform, and the AMI filter in db-app.tf matches no image (Section 3.4.1). Checkov's result was unaffected; whether the invalid reference changed what the models reported is unmeasured. Settling it needs a corrected corpus and a full rerun: 1,080 runs, about $27 at list prices (the reported study's total spend). Not run.

4. **Multiplicity and the results between p = 0.01 and p = 0.05.** Opus few-shot (p = 0.03), Opus chain-of-thought (p = 0.03), Sonnet critic (p = 0.02), GPT debate (p = 0.023), and DeepSeek debate (p = 0.013) are now all labelled "short of the study's threshold" in the paper. Thirty-five paired tests were run without correction (Section 2.6). `RESULTS.md` carries Holm-adjusted p-values per family and globally; the author chose not to report them in the paper. Settling any one of these contrasts needs more repetitions (the harness's own note calls for 10 to 20 on close comparisons).

## Carried from the first audit

5. **Accepted matches were not independently verified.** 999 of 4,616 accepted matches (21.6%) rest on one vocabulary cue and 33 on the CWE level. The strict-rule sensitivity (Section 3.1.3; `RESULTS.md`, Matcher sensitivity) discounts them all, which is a bound, not a measurement. A blinded human check of a random sample of accepted matches (200 would give a false-credit rate to within about +/-5 points) has not been done. Until it is, "precision as scored is a lower bound" (Section 2.4) holds only with respect to ground-truth coverage.

6. **Single rater.** All 95 Checkov checks were classified by one rater (13 ambiguous checks ruled by the author; `verdicts_roy.json`), and the 177 rejected claims were classified by an AI first pass that the author reviewed and accepted without change (177/177). No second rater, no agreement statistic. The paper discloses both.

7. **Memorization was defended against, not measured.** The original corpus was not run alongside the mutated one; the pilot on the original corpus used a different repetition count and an earlier harness, so it is not a paired comparison. Settling it needs the 36 configurations rerun on the original TerraGoat files: about $27.

8. **Debate mechanism.** Section 3.3.3 reads the reconciled counts as consistent with union-plus-pruning; the overlap between reviewer A and reviewer B was not measured, and the run files store only the reconciled findings and the two reviewers' counts, so it cannot be computed after the fact. Settling it needs the debate arms rerun with both reviewers' findings retained: 360 calls, about $9.

## Sources and disclosure

9. **Verdet et al. (2025).** The introduction's "commonly exploited attack vector" claim was removed in v4 because the accessible text (abstract; Springer landing page) does not contain it; the full text could not be retrieved. The remaining citation in Section 4.1.2 (a missed misconfiguration reaches production) rests on the abstract's premise. If the full text supports the original claim, it can be restored.

10. **Center for Internet Security (2026).** The benchmark's version (7.0.0) is confirmed; its publication year is not shown on the cited page. The v4 wording ("the resource categories that the CIS AWS Foundations Benchmark addresses") is supported by the benchmark's section structure, not by the landing page, which carries no content.

11. **Crosley (2026)** is a vendor blog whose productivity figures are largely unsourced within the post. v4 attributes the claim ("report increases") rather than asserting it.

12. **Repository publication.** Resolved: this repository, tagged `v1.0-submission`, is what the paper cites.

## Items considered and left as they are

13. Adjusted precision remains in the abstract (0.77 to 0.96); the conservative bound with output-pathway credits withheld (0.75 to 0.93) is in Table 5.
14. The FP-minutes / FN-production argument (Section 4.1.2) is an argument, cited to Verdet et al. for the premise, not a measured cost.
15. Costs are token counts at August 2026 list prices, not billed amounts; the DeepSeek tariff changed after the runs (`RESULTS.md`, DeepSeek tariff note).
