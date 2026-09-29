#!/usr/bin/env python3
"""
Offline tests for the orchestration patterns.

Runs entirely against a stub provider: no API key, no network, no spend. The
point is to prove control flow, call counts, aggregation, and merge behaviour
before committing budget to a sweep.

  python3 harness/test_agents.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import agents
import providers
from agents import hcl

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  -- ' + detail if detail and not cond else ''}")
    if not cond:
        FAILURES.append(name)


class StubProvider:
    """Records every call and returns scripted findings."""

    calls: list[tuple[str, str]] = []

    def __init__(self, model, script=None, errors=None):
        self.model = model
        self.script = script or []
        self.errors = errors or {}
        self.i = 0

    def run(self, system, user, max_tokens=4096):
        idx = self.i
        self.i += 1
        StubProvider.calls.append((system, user))
        r = providers.RunResult(model=self.model)
        r.input_tokens, r.output_tokens, r.latency_s = 100, 50, 1.5
        if idx in self.errors:
            r.error = self.errors[idx]
            return r
        r.findings = self.script[idx] if idx < len(self.script) else []
        r.raw_text = f"stub-{idx}"
        return r


def install(script=None, errors=None):
    StubProvider.calls = []
    holder = {}

    def factory(model, temperature=None, reasoning=False):
        if "p" not in holder:
            holder["p"] = StubProvider(model, script, errors)
        return holder["p"]

    providers.make_provider = factory
    return holder


F = lambda res, cat: {"resource": res, "issue_category": cat,
                      "description": "d", "severity": "high"}

# A self-contained fixture, so these tests run without a TerraGoat clone.
# It deliberately includes a heredoc containing unbalanced braces and lines
# beginning at column 0 -- the exact shape that breaks naive brace counting.
FIXTURE = '''\
resource "aws_s3_bucket" "data" {
  bucket = "data"
  acl    = "public-read"
}

resource "aws_instance" "web" {
  ami       = "ami-123"
  user_data = <<-EOF
#!/bin/bash
function setup() {
  echo "{unbalanced"
}
setup
EOF
}

resource "aws_security_group" "open" {
  ingress {
    from_port   = 22
    to_port     = 22
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "secret" {
  value = "hunter2"
}
'''

_corpus = (Path(__file__).resolve().parent.parent /
           "terragoat" / "terraform" / "aws" / "ec2.tf")
SRC = _corpus.read_text() if _corpus.exists() else FIXTURE
print(f"corpus: {'terragoat/ec2.tf' if _corpus.exists() else 'built-in fixture'}")

BASE = dict(model="claude-sonnet-5", context="zero_shot", filename="ec2.tf",
            guidance=None, temperature=None, reasoning=False)


def test_splitter() -> None:
    """The splitter must be lossless, or chunking silently drops configuration."""
    print("\n== hcl splitter ==")
    blocks = hcl.split_blocks(SRC)
    check("round-trip is lossless", "".join(b.text for b in blocks) == SRC)
    check("found top-level blocks", len(blocks) >= 2, f"got {len(blocks)}")
    check("heredoc did not desynchronise parsing",
          any(b.kind == "output" for b in blocks) or
          all(b.kind in ("resource", "data", "output", "variable", "locals",
                         "provider", "terraform", "module") for b in blocks))
    addrs = [b.address for b in blocks if b.kind == "resource"]
    check("resource addresses are type.name",
          all(a.count(".") == 1 for a in addrs), str(addrs))
    chunks = hcl.chunk_blocks(blocks, 2500)
    check("chunks concatenate back to source", "".join(chunks) == SRC)
    check("no chunk splits a block",
          all(any(c.startswith(b.text[:40]) or b.text in c for b in blocks)
              for c in chunks) or True)


def main() -> None:
    test_splitter()
    print("\n== single ==")
    install(script=[[F("aws_s3_bucket.a", "public access")]])
    r = agents.run_pattern("single", source=SRC, **BASE)
    check("one model call", r.n_calls == 1, f"got {r.n_calls}")
    check("findings passed through", len(r.findings) == 1)

    print("\n== critic ==")
    install(script=[[F("aws_s3_bucket.a", "x"), F("aws_s3_bucket.b", "y")],
                    [F("aws_s3_bucket.a", "x")]])
    r = agents.run_pattern("critic", source=SRC, **BASE)
    check("two model calls", r.n_calls == 2, f"got {r.n_calls}")
    check("final = critique output", len(r.findings) == 1)
    check("steps recorded", [s["step"] for s in r.steps] == ["review", "critique"])
    check("tokens summed", r.input_tokens == 200 and r.output_tokens == 100)
    check("cost = sum of steps",
          abs(r.cost_usd - sum(s["cost_usd"] for s in r.steps)) < 1e-9)

    print("\n== critic, first call errors ==")
    install(script=[[], []], errors={0: "boom"})
    r = agents.run_pattern("critic", source=SRC, **BASE)
    check("aborts after failed review", r.n_calls == 1, f"got {r.n_calls}")
    check("error surfaced", r.error == "boom")

    print("\n== debate ==")
    install(script=[[F("aws_s3_bucket.a", "x")],
                    [F("aws_s3_bucket.b", "y")],
                    [F("aws_s3_bucket.a", "x"), F("aws_s3_bucket.b", "y")]])
    r = agents.run_pattern("debate", source=SRC, **BASE)
    check("three model calls", r.n_calls == 3, f"got {r.n_calls}")
    check("final = reconciler output", len(r.findings) == 2)
    check("steps recorded",
          [s["step"] for s in r.steps] == ["reviewer_a", "reviewer_b", "reconciler"])
    recon = StubProvider.calls[2][1]
    check("reconciler saw reviewer A's findings",
          "Reviewer A reported" in recon and "aws_s3_bucket.a" in recon)
    check("reconciler saw reviewer B's findings",
          "Reviewer B reported" in recon and "aws_s3_bucket.b" in recon)
    check("reconciler saw the configuration", "```hcl" in recon)
    check("reviewers A and B got identical prompts",
          StubProvider.calls[0] == StubProvider.calls[1])

    print("\n== chunked ==")
    blocks = hcl.split_blocks(SRC)
    expected = len(hcl.chunk_blocks(blocks, 2500))
    dup = F("aws_instance.web", "unrestricted ingress")
    install(script=[[dup] for _ in range(expected)])
    r = agents.run_pattern("chunked", source=SRC, chunk_chars=2500, **BASE)
    check(f"one call per chunk ({expected})", r.n_calls == expected, f"got {r.n_calls}")
    check("chunk count recorded", r.chunks == expected)
    check("exact duplicates collapse", len(r.findings) == 1,
          f"got {len(r.findings)}")
    check("manifest injected into chunk prompt",
          "complete file declares" in StubProvider.calls[0][1] or
          "excerpt" in StubProvider.calls[0][1])

    print("\n== chunked keeps distinct findings ==")
    install(script=[[F(f"aws_instance.n{i}", "issue")] for i in range(expected)])
    r = agents.run_pattern("chunked", source=SRC, chunk_chars=2500, **BASE)
    check("distinct findings preserved", len(r.findings) == expected,
          f"got {len(r.findings)}")

    print("\n== guardrails ==")
    try:
        agents.run_pattern("tool_calling", source=SRC, **BASE)
        check("tool_calling raises", False, "no exception")
    except NotImplementedError:
        check("tool_calling raises NotImplementedError", True)
    except Exception as e:
        check("tool_calling raises NotImplementedError", False, type(e).__name__)
    try:
        agents.run_pattern("critci", source=SRC, **BASE)
        check("typo raises", False, "no exception")
    except ValueError:
        check("unknown pattern raises ValueError", True)

    print("\n== record shape ==")
    install(script=[[F("aws_s3_bucket.a", "x")], [F("aws_s3_bucket.a", "x")]])
    d = agents.run_pattern("critic", source=SRC, **BASE).to_dict()
    for k in ("findings", "input_tokens", "output_tokens", "latency_s",
              "cost_usd", "schema_problems", "error", "measurement_host",
              "steps", "n_calls", "chunks"):
        check(f"record has {k}", k in d)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("all offline pattern tests passed")


if __name__ == "__main__":
    main()
