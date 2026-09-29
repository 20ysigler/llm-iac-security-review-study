"""
Match model-claimed findings against ground truth.

Models do not emit Checkov rule IDs, so matching is a three-level cascade,
exactly as the method section specifies:

  1. Resource + issue-type   -- the primary key. Same Terraform address, and
                                the claimed issue maps to the same category.
  2. CWE                     -- same resource, same CWE class, where the model
                                supplied one.
  3. Lexical fallback        -- same resource, and the claim's wording overlaps
                                the ground-truth category's vocabulary above a
                                threshold. Anything resolved at this level is
                                flagged for manual adjudication.

Matching is one-to-one and greedy by confidence: a ground-truth entry can be
satisfied only once, so a model cannot inflate recall by restating the same
issue. Unmatched claims are false positives; unmatched ground truth are false
negatives.

The category vocabulary below is deliberately generous in synonyms and
deliberately silent on Checkov's own phrasing. Matching on Checkov's wording
would reward models for reproducing the oracle's language rather than for
identifying the vulnerability.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# category -> terms that indicate it. Order does not matter; these are sets.
CATEGORY_TERMS: dict[str, set[str]] = {
    "encryption_at_rest": {
        "encryption", "encrypted", "unencrypted", "at rest", "atrest", "kms",
        "sse", "plaintext storage", "storage encryption", "not encrypted"},
    "encryption_at_rest_cmk": {
        "cmk", "customer managed", "customer-managed", "kms key", "managed key",
        "aws managed key", "default key", "encryption", "encrypted"},
    "encryption_in_transit": {
        "transit", "tls", "ssl", "https", "cleartext", "plaintext transmission",
        "unencrypted connection", "insecure protocol", "http"},
    "public_access": {
        "public", "publicly accessible", "public access", "anonymous", "world readable",
        "world-readable", "exposed", "internet accessible", "acl", "open to the internet",
        "public read", "public write", "everyone"},
    "public_ip_assignment": {
        "public ip", "public-ip", "auto assign", "map public", "publicly routable",
        "external ip", "internet facing"},
    "network_ingress_unrestricted": {
        "ingress", "inbound", "0.0.0.0/0", "0.0.0.0", "any source", "open port",
        "unrestricted", "ssh", "port 22", "port 80", "rdp", "port 3389", "wide open",
        "all traffic", "any ip"},
    "network_egress_unrestricted": {
        "egress", "outbound", "0.0.0.0/0", "unrestricted egress", "all outbound",
        "any destination", "exfiltration path"},
    "network_default_sg_open": {
        "default security group", "default sg", "default group", "restrict all traffic"},
    "hardcoded_secret": {
        "hardcoded", "hard-coded", "hard coded", "secret", "credential", "password",
        "api key", "access key", "token", "plaintext password", "embedded credential",
        "user data", "userdata", "environment variable"},
    "iam_privilege_escalation": {
        "privilege escalation", "privesc", "escalate", "escalation", "assume role",
        "pass role", "passrole", "elevate"},
    "iam_credentials_exposure": {
        "credential exposure", "credentials exposure", "expose credential",
        "leak credential", "sts", "get session token", "retrieve credential"},
    "iam_data_exfiltration": {
        "exfiltration", "exfiltrate", "data theft", "bulk read", "dump data"},
    "iam_permissions_management": {
        "permissions management", "modify policy", "attach policy", "put policy",
        "iam write", "manage permission", "resource exposure", "change permission"},
    "iam_write_without_constraint": {
        "write access", "unconstrained", "without constraint", "unrestricted write",
        "broad write", "no condition"},
    "iam_wildcard_resource": {
        "wildcard", "asterisk", '"*"', "star", "all resources", "any resource",
        "resource *", "overly permissive", "least privilege", "too permissive",
        "broad permission", "full access"},
    "iam_wildcard_action": {
        "wildcard action", "action *", "all actions", "any action", "admin action"},
    "iam_administrator_access": {
        "administratoraccess", "administrator access", "admin policy", "full admin",
        "administrative privilege"},
    "iam_user_instead_of_sso": {
        "iam user", "sso", "identity center", "federation", "long lived credential",
        "long-lived"},
    "iam_direct_user_policy": {
        "attached to user", "inline user policy", "policy on user", "group or role"},
    "iam_role_separation": {
        "execution role", "task role", "same role", "role separation"},
    "iam_missing_role": {
        "no iam role", "missing role", "instance profile", "no instance profile"},
    "key_rotation_disabled": {
        "rotation", "rotate", "key rotation", "not rotated"},
    "key_policy_missing": {
        "key policy", "no policy", "missing policy", "kms policy"},
    "credential_rotation_disabled": {
        "rotation", "rotate", "automatic rotation", "secret rotation"},
    "imdsv1_enabled": {
        "imds", "imdsv1", "instance metadata", "metadata service", "metadata v1",
        "http tokens", "ssrf"},
    "deprecated_runtime": {
        "deprecated", "end of life", "eol", "unsupported runtime", "outdated runtime",
        "old runtime", "runtime version"},
    "missing_auto_patching": {
        "patch", "minor version", "auto upgrade", "automatic update", "unpatched",
        "managed update"},
    "lambda_outside_vpc": {
        "vpc", "outside vpc", "not in vpc", "no vpc", "network isolation"},
    "code_signing_disabled": {
        "code signing", "codesigning", "signature", "unsigned", "verify code"},
    "weak_authentication": {
        "authentication", "iam authentication", "auth", "client certificate",
        "no authentication", "weak auth"},
    "container_writable_root_fs": {
        "read only", "read-only", "root filesystem", "writable filesystem",
        "container escape"},
    "security_config_missing": {
        "security configuration", "no security config", "missing configuration"},
    "image_tag_mutable": {
        "immutable", "mutable tag", "tag overwrite", "image tag"},
    "log_integrity_validation": {
        "log file validation", "integrity", "tamper", "log validation"},
    "header_injection_risk": {
        "header", "http header", "drop invalid", "header injection"},
    "missing_input_validation": {
        "input validation", "request validation", "validate request", "unvalidated"},
}

_WORD = re.compile(r"[a-z0-9./*_-]+")


def normalise_resource(text: str) -> str:
    """Reduce a claimed resource address to a comparable form."""
    if not text:
        return ""
    t = text.strip().strip('"').strip("'").lower()
    t = re.sub(r"^resource\s+", "", t)
    t = t.replace('" "', ".").replace('"', "").replace("'", "")
    t = re.sub(r"\s+", "", t)
    # Trim an attribute path: aws_s3_bucket.data.acl -> aws_s3_bucket.data
    parts = t.split(".")
    if len(parts) > 2 and parts[0].startswith(("aws_", "azurerm_", "google_")):
        t = ".".join(parts[:2])
    return t


def _terms(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def category_score(claim_text: str, category: str) -> float:
    """Fraction of a category's multi-word cues present in the claim."""
    vocab = CATEGORY_TERMS.get(category)
    if not vocab:
        return 0.0
    low = (claim_text or "").lower()
    hits = sum(1 for term in vocab if term in low)
    if not hits:
        return 0.0
    # Normalise so categories with large vocabularies are not advantaged.
    return min(1.0, hits / 2.0)


@dataclass
class Match:
    gt_id: str
    claim_index: int
    level: str          # resource_issue | cwe | lexical
    score: float
    needs_adjudication: bool = False


def match_findings(claims: list[dict], truth: list[dict],
                   lexical_threshold: float = 0.5) -> tuple[list[Match], list[int], list[str]]:
    """
    Returns (matches, unmatched_claim_indices, unmatched_gt_ids).

    Greedy and one-to-one: candidates are scored across all three levels, sorted
    best-first, and consumed so neither a claim nor a ground-truth entry is used
    twice.
    """
    candidates: list[Match] = []

    for ci, claim in enumerate(claims):
        c_res = normalise_resource(claim.get("resource", ""))
        c_text = " ".join(str(claim.get(k, "")) for k in
                          ("issue_category", "description")).lower()
        c_cwe = (claim.get("cwe") or "").strip().upper()

        for gt in truth:
            if normalise_resource(gt["resource"]) != c_res:
                continue                      # resource must always agree
            cat = gt["issue_category"]
            sc = category_score(c_text, cat)
            if sc >= 0.5:
                candidates.append(Match(gt["id"], ci, "resource_issue", 2.0 + sc))
            elif c_cwe and gt.get("cwe") and c_cwe == gt["cwe"].strip().upper():
                candidates.append(Match(gt["id"], ci, "cwe", 1.5))
            elif sc >= lexical_threshold / 2:
                candidates.append(Match(gt["id"], ci, "lexical", 0.5 + sc,
                                        needs_adjudication=True))

    candidates.sort(key=lambda m: -m.score)
    used_gt: set[str] = set()
    used_claims: set[int] = set()
    matches: list[Match] = []
    for m in candidates:
        if m.gt_id in used_gt or m.claim_index in used_claims:
            continue
        used_gt.add(m.gt_id)
        used_claims.add(m.claim_index)
        matches.append(m)

    unmatched_claims = [i for i in range(len(claims)) if i not in used_claims]
    unmatched_gt = [g["id"] for g in truth if g["id"] not in used_gt]
    return matches, unmatched_claims, unmatched_gt
