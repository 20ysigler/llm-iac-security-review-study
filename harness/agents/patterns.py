"""
Orchestration pattern implementations.

Each pattern is a control-flow wrapper around the same provider calls the
single-agent path already makes. They share one contract: given the file under
review and a context variant, return a PatternResult that is shape-compatible
with providers.RunResult, so run_experiment.py records every pattern the same
way and score.py needs no changes.

Cost and latency are summed across every model call a pattern makes, so a
critic run reports the cost of both of its calls. `steps` preserves the
per-call detail for the practicality analysis, since a pattern that reaches the
same F1 for three times the tokens is a different recommendation.

Design notes that belong in the method section:

  * `debate` samples the SAME model twice rather than pairing two different
    models. The disagreement it reconciles is sampling variance within one
    arm, which the pilot measured as substantial (0 of 6 files produced
    identical finding sets across 5 runs). This is self-consistency style
    debate, not cross-model debate, and must be described that way.
  * `chunked` never splits a top-level block. Every chunk carries a manifest of
    the whole file's resources so cross-resource reasoning remains possible,
    and the prompt forbids reporting against resources not shown.
  * Chunk merging is deliberately conservative: only exact duplicates on
    (normalised resource, lowercased issue_category) collapse. Semantic
    deduplication is the matcher's job, and reimplementing it here would let
    the two drift apart.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import prompts
import providers
from match import normalise_resource

from . import hcl


@dataclass
class PatternResult(providers.RunResult):
    steps: list = field(default_factory=list)
    n_calls: int = 0
    chunks: int = 0


def _render_findings(findings: list[dict]) -> str:
    if not findings:
        return "(the reviewer reported no findings)"
    return json.dumps({"findings": findings}, indent=2)


def _merge(base: PatternResult, step_name: str, r: providers.RunResult) -> None:
    """Fold one provider call into the aggregate."""
    base.n_calls += 1
    base.input_tokens += r.input_tokens
    base.output_tokens += r.output_tokens
    base.latency_s = round(base.latency_s + r.latency_s, 3)
    base.thinking_chars += r.thinking_chars
    base.attempts = max(base.attempts, r.attempts)
    base.resolved_model = r.resolved_model or base.resolved_model
    for p in r.schema_problems:
        base.schema_problems.append(f"{step_name}: {p}")
    base.steps.append({
        "step": step_name,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "latency_s": r.latency_s,
        "n_findings": len(r.findings),
        "error": r.error,
        "cost_usd": round(r.cost_usd, 6),
    })


def _provider(model, temperature, reasoning):
    return providers.make_provider(model, temperature=temperature, reasoning=reasoning)


def run_single(*, model, context, source, filename, guidance, temperature,
               reasoning, max_tokens=4096, **_) -> PatternResult:
    res = PatternResult(model=model, reasoning=bool(reasoning))
    system, user = prompts.build(context, source, filename, guidance=guidance)
    r = _provider(model, temperature, reasoning).run(system, user, max_tokens)
    _merge(res, "review", r)
    res.findings, res.raw_text, res.error = r.findings, r.raw_text, r.error
    return res


def run_critic(*, model, context, source, filename, guidance, temperature,
               reasoning, max_tokens=4096, **_) -> PatternResult:
    """Review, then a second pass that critiques and corrects the first."""
    res = PatternResult(model=model, reasoning=bool(reasoning))
    prov = _provider(model, temperature, reasoning)

    system, user = prompts.build(context, source, filename, guidance=guidance)
    first = prov.run(system, user, max_tokens)
    _merge(res, "review", first)
    if first.error:
        res.findings, res.raw_text, res.error = first.findings, first.raw_text, first.error
        return res

    critique_user = "\n\n".join([
        prompts.TASK_INSTRUCTION,
        prompts.CRITIC_INSTRUCTION,
        f"Terraform configuration ({filename}):\n\n```hcl\n{source}\n```",
        "The review to critique:\n\n" + _render_findings(first.findings),
    ])
    second = prov.run(system, critique_user, max_tokens)
    _merge(res, "critique", second)
    res.findings = second.findings if not second.error else first.findings
    res.raw_text, res.error = second.raw_text, second.error
    return res


def run_debate(*, model, context, source, filename, guidance, temperature,
               reasoning, max_tokens=4096, **_) -> PatternResult:
    """Two independent reviews from the same model, then a reconciling pass."""
    res = PatternResult(model=model, reasoning=bool(reasoning))
    prov = _provider(model, temperature, reasoning)

    system, user = prompts.build(context, source, filename, guidance=guidance)
    a = prov.run(system, user, max_tokens)
    _merge(res, "reviewer_a", a)
    b = prov.run(system, user, max_tokens)
    _merge(res, "reviewer_b", b)

    if a.error and b.error:
        res.findings, res.raw_text, res.error = [], a.raw_text, a.error
        return res

    reconcile_user = "\n\n".join([
        prompts.TASK_INSTRUCTION,
        prompts.DEBATE_RECONCILER_INSTRUCTION,
        f"Terraform configuration ({filename}):\n\n```hcl\n{source}\n```",
        "Reviewer A reported:\n\n" + _render_findings(a.findings),
        "Reviewer B reported:\n\n" + _render_findings(b.findings),
    ])
    c = prov.run(system, reconcile_user, max_tokens)
    _merge(res, "reconciler", c)
    res.findings = c.findings if not c.error else (a.findings or b.findings)
    res.raw_text, res.error = c.raw_text, c.error
    return res


def run_chunked(*, model, context, source, filename, guidance, temperature,
                reasoning, max_tokens=4096, chunk_chars=2500, **_) -> PatternResult:
    """Review the file in whole-block chunks, then merge the findings locally."""
    res = PatternResult(model=model, reasoning=bool(reasoning))
    prov = _provider(model, temperature, reasoning)

    blocks = hcl.split_blocks(source)
    chunks = hcl.chunk_blocks(blocks, chunk_chars) or [source]
    res.chunks = len(chunks)
    inventory = hcl.manifest(blocks)

    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    last_raw, first_error = "", ""

    for i, chunk in enumerate(chunks, start=1):
        system, user = prompts.build(context, chunk, filename, guidance=guidance)
        header = prompts.CHUNK_HEADER.format(manifest=inventory)
        r = prov.run(system, header + "\n\n" + user, max_tokens)
        _merge(res, f"chunk_{i}", r)
        last_raw = r.raw_text or last_raw
        if r.error:
            first_error = first_error or r.error
            continue
        for f in r.findings:
            key = (normalise_resource(f.get("resource", "")),
                   (f.get("issue_category") or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(f)

    res.findings, res.raw_text, res.error = merged, last_raw, first_error
    return res


RUNNERS = {
    "single": run_single,
    "critic": run_critic,
    "debate": run_debate,
    "chunked": run_chunked,
}
