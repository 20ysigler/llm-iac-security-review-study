"""
Agent orchestration patterns for the third leg of the study.

`PATTERNS` is the authoritative list. run_experiment.py validates --pattern
against it, so a typo can no longer produce runs that are labelled as one
pattern and executed as another.

`tool_calling` is declared but not yet implemented: it needs an external
scanner (Trivy primary, KICS fallback — never Checkov, which would break the
circularity rule). It is listed here so the gap is explicit rather than
silent, and requesting it raises instead of quietly falling back to a
single-agent run.
"""
from __future__ import annotations

PATTERNS = ["single", "chunked", "critic", "debate", "tool_calling"]
IMPLEMENTED = ["single", "chunked", "critic", "debate"]


def run_pattern(pattern: str, **kw):
    from .patterns import RUNNERS
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern {pattern!r}; expected one of {PATTERNS}")
    if pattern not in RUNNERS:
        raise NotImplementedError(
            f"pattern {pattern!r} is declared but not implemented. "
            f"Implemented: {IMPLEMENTED}. tool_calling requires an external "
            f"scanner (Trivy/KICS) that is not yet wired up."
        )
    return RUNNERS[pattern](**kw)
