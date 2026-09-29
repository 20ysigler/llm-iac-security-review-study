# Provenance for data/rag_guidance.md

This file documents how the retrieval corpus was assembled. It is NOT injected into any prompt.

# Security guidance corpus (RAG context variant)

Assembled 2026-08-16 from three sources independent of Checkov, per the
circularity rule in the method section: ground truth descends from Checkov, so
injecting Checkov rule definitions as retrieval context would score the oracle
against itself. Tool-name lists have been stripped from the OWASP material —
they are not security guidance and one of them names Checkov.

Sources:
  - AWS Well-Architected Framework, Security Pillar (Amazon Web Services, n.d.)
  - OWASP Infrastructure as Code Security Cheat Sheet (OWASP, n.d.)
  - CIS Amazon Web Services Foundations Benchmark v7.0.0 (CIS, 2026) —
    control themes only; the benchmark itself is registration-gated, so the
    prescriptive control areas are represented rather than reproduced.
