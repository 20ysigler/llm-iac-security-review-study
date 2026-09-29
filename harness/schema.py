"""
Structured output contract for model responses.

Every model under test must return findings in this shape. Automated scoring
depends on it, and the method section commits to it, so the schema is defined
once here and consumed by every provider adapter rather than restated per model.

Design notes:
  - `resource` is the Terraform address (type.name). It is the primary matching
    key, so the prompt must make its expected form unambiguous.
  - `issue_category` is free text on purpose. Forcing models to choose from our
    internal category enum would leak the ground truth taxonomy into the prompt
    and inflate matching accuracy. The matcher normalises free text instead.
  - `cwe` is optional. Smaller models frequently omit or hallucinate it, so it
    is a secondary matching signal, never a required field.
  - `confidence` is captured but not used in primary scoring. It supports the
    qualitative failure-mode analysis: a model that is confidently wrong is a
    different practitioner risk from one that is uncertainly wrong.
"""
from __future__ import annotations

SEVERITIES = ["critical", "high", "medium", "low", "informational"]

FINDING_SCHEMA = {
    "type": "object",
    "required": ["resource", "issue_category", "description", "severity"],
    "additionalProperties": False,
    "properties": {
        "resource": {
            "type": "string",
            "description": (
                "The Terraform resource address exactly as written in the file, "
                "in the form <resource_type>.<resource_name>, "
                "for example aws_s3_bucket.financials. Do not abbreviate, "
                "quote, or add the surrounding resource keyword."
            ),
        },
        "issue_category": {
            "type": "string",
            "description": (
                "A short noun phrase naming the vulnerability class, for example "
                "'missing encryption at rest' or 'unrestricted ingress'. "
                "Three to six words."
            ),
        },
        "description": {
            "type": "string",
            "description": (
                "One or two sentences explaining what is wrong and why it is a "
                "security risk in this specific configuration."
            ),
        },
        "severity": {
            "type": "string",
            "enum": SEVERITIES,
            "description": "Your severity assessment for this finding.",
        },
        "cwe": {
            "type": "string",
            "description": (
                "The CWE identifier in the form CWE-nnn if you are confident of "
                "the mapping. Omit this field entirely rather than guessing."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Your confidence that this is a genuine vulnerability.",
        },
    },
}

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["findings"],
    "additionalProperties": False,
    "properties": {
        "findings": {
            "type": "array",
            "description": (
                "Every security vulnerability you identify. Return an empty "
                "array if the configuration is secure. Do not pad the list with "
                "operational, cost, or reliability observations."
            ),
            "items": FINDING_SCHEMA,
        }
    },
}

# The tool/function form, used by providers that expose structured output as a
# forced tool call rather than a response-format parameter.
RESPONSE_TOOL = {
    "name": "report_findings",
    "description": "Report every security vulnerability found in the Terraform configuration.",
    "input_schema": RESPONSE_SCHEMA,
}

# Appended to prompts for models with no structured-output support at all
# (notably local Gemma via Ollama). Kept deliberately terse: long format
# instructions crowd out the security task in small-context local models.
JSON_FALLBACK_INSTRUCTION = """\
Respond with a single JSON object and nothing else. No prose before or after, \
no markdown fences. Shape:

{"findings": [{"resource": "<type>.<name>", "issue_category": "<3-6 words>", \
"description": "<1-2 sentences>", "severity": "critical|high|medium|low|informational", \
"cwe": "CWE-nnn", "confidence": "high|medium|low"}]}

Omit "cwe" if unsure. Return {"findings": []} if nothing is wrong."""


def empty_response() -> dict:
    """Canonical empty result, used when a model returns nothing parseable."""
    return {"findings": []}


def validate(payload: dict) -> tuple[bool, list[str]]:
    """
    Lightweight structural check.

    Returns (ok, problems). We deliberately do not raise: a malformed response
    is itself a datum. The runner records the problem list against the run so
    the error-rate metric in the method section has something to count.
    """
    problems: list[str] = []
    if not isinstance(payload, dict):
        return False, ["response is not an object"]
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return False, ["'findings' missing or not an array"]

    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            problems.append(f"finding[{i}] is not an object")
            continue
        for field in ("resource", "issue_category", "description", "severity"):
            if not f.get(field):
                problems.append(f"finding[{i}] missing required field '{field}'")
        sev = f.get("severity")
        if sev and sev not in SEVERITIES:
            problems.append(f"finding[{i}] severity '{sev}' outside enum")
        res = f.get("resource")
        if isinstance(res, str) and res and "." not in res:
            problems.append(f"finding[{i}] resource '{res}' is not type.name")
    return (not problems), problems
