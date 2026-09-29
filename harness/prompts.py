"""
Prompt templates for the five context-engineering variants.

The method section commits to publishing exact prompts, so this module is the
canonical record: nothing here is generated at runtime beyond substituting the
file under review and, for the RAG variant, the retrieved guidance.

Two constraints shape every template:

  1. Prompt wording is a confound within each variant (Threats to Validity).
     The task instruction is therefore held IDENTICAL across all five variants;
     only the surrounding context changes. `TASK_INSTRUCTION` is the shared
     core, and each variant adds to it without rewording it.

  2. The scored ground truth contains security findings only, with operational
     and reliability controls deliberately excluded. Every variant therefore
     carries the same scope sentence. Without it, models are penalised for
     correctly declining to report EBS optimisation as a vulnerability, which
     would measure prompt design rather than security capability.
"""
from __future__ import annotations

VARIANTS = ["zero_shot", "few_shot", "system_enriched", "rag", "chain_of_thought"]

# --------------------------------------------------------------------------
# Shared core. Identical in every variant. Do not reword per variant.
# --------------------------------------------------------------------------

TASK_INSTRUCTION = """\
Review the Terraform configuration below and identify every security \
vulnerability it contains.

Report security vulnerabilities only: misconfigurations that expose data, \
weaken access control, disable encryption, leak credentials, or otherwise \
create attack surface. Do not report operational, cost, performance, or \
reliability observations such as missing tags, absent lifecycle rules, \
disabled monitoring, backup retention, or instance sizing. These are real \
findings in other contexts but are out of scope here.

Identify each finding by the Terraform resource address exactly as it appears \
in the file."""

BASE_SYSTEM = "You are reviewing Terraform infrastructure-as-code for security vulnerabilities."

# --------------------------------------------------------------------------
# Variant 2: few-shot.
#
# Examples are hand-written for this study and deliberately use Azure and GCP
# resources. TerraGoat's AWS files are the test corpus, so AWS examples risk
# both train-on-test contamination and priming specific resource types. The
# vulnerability CLASSES (public exposure, missing encryption, wildcard IAM)
# transfer; the provider syntax does not overlap the corpus.
# --------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = """\
Here are three worked examples showing the expected reasoning and output.

Example 1 — vulnerable

    resource "azurerm_storage_account" "reports" {
      name                     = "orgreports"
      resource_group_name      = azurerm_resource_group.main.name
      location                 = "eastus"
      account_tier             = "Standard"
      account_replication_type = "LRS"
      allow_blob_public_access = true
      min_tls_version          = "TLS1_0"
    }

Findings: azurerm_storage_account.reports permits anonymous blob access, so \
any unauthenticated caller can enumerate and read stored objects. It also \
accepts TLS 1.0, allowing downgrade to a deprecated protocol.

Example 2 — secure counterpart

    resource "azurerm_storage_account" "reports" {
      name                     = "orgreports"
      resource_group_name      = azurerm_resource_group.main.name
      location                 = "eastus"
      account_tier             = "Standard"
      account_replication_type = "LRS"
      allow_blob_public_access = false
      min_tls_version          = "TLS1_2"
    }

Findings: none. Public access is disabled and the minimum TLS version is current.

Example 3 — vulnerable

    resource "google_project_iam_member" "ci" {
      project = var.project_id
      role    = "roles/owner"
      member  = "serviceAccount:${google_service_account.ci.email}"
    }

Findings: google_project_iam_member.ci grants the project owner role to a CI \
service account. Owner confers full administrative control including IAM \
modification, so a compromised pipeline credential yields complete project \
takeover. The role should be scoped to the specific permissions the pipeline needs."""

# --------------------------------------------------------------------------
# Variant 3: system-prompt enrichment.
#
# Encodes a reviewer persona and domain vocabulary. Names vulnerability CLASSES
# and CWE families but deliberately no Checkov rule IDs and no AWS-specific
# control list, which would hand the model the ground truth taxonomy.
# --------------------------------------------------------------------------

ENRICHED_SYSTEM = """\
You are a senior cloud security architect performing infrastructure-as-code \
review. You have a decade of experience auditing Terraform in regulated \
enterprise environments and you assess configurations against established \
security architecture principles: least privilege, defence in depth, \
encryption at rest and in transit, network segmentation, and secure defaults.

You reason about the classes of weakness that recur in cloud infrastructure:

- Broken access control and overly permissive policy (CWE-284, CWE-732), \
including wildcard principals, wildcard resources, and privilege escalation \
paths through role assumption or policy modification.
- Missing encryption of stored data (CWE-311) and cleartext transmission \
(CWE-319).
- Hard-coded credentials and secrets embedded in configuration or startup \
scripts (CWE-798).
- Exposure of services to untrusted networks through unrestricted ingress, \
public IP assignment, or absent network boundaries.
- Insecure default configuration and deprecated protocol or runtime versions \
(CWE-1104, CWE-441).

You reason about relationships between resources, not only individual blocks: \
a permissive policy attached to a role assumed by a publicly reachable compute \
instance is a different risk from the same policy in isolation.

You are precise and conservative. You do not report findings you cannot \
substantiate from the configuration in front of you, and you do not inflate \
your findings list with operational or cost observations."""

# --------------------------------------------------------------------------
# Variant 4: RAG.
#
# Guidance is drawn from CIS AWS Foundations Benchmark, AWS Well-Architected
# Security Pillar, and the OWASP IaC Security Cheat Sheet. Checkov rule
# definitions are excluded by the circularity rule: ground truth descends from
# Checkov, so injecting its rules would score the oracle against itself.
# Passages are loaded at runtime from data/rag_corpus/ and injected here.
# --------------------------------------------------------------------------

RAG_PREAMBLE = """\
The following security guidance is drawn from the CIS Amazon Web Services \
Foundations Benchmark, the AWS Well-Architected Framework Security Pillar, and \
the OWASP Infrastructure as Code Security Cheat Sheet. Use it to inform your \
review. The guidance is general; the configuration below is specific. Apply \
the guidance where it is relevant and disregard passages that do not bear on \
this configuration.

--- BEGIN SECURITY GUIDANCE ---
{guidance}
--- END SECURITY GUIDANCE ---"""

# --------------------------------------------------------------------------
# Variant 5: chain-of-thought.
# --------------------------------------------------------------------------

COT_INSTRUCTION = """\
Work through the configuration methodically before reporting.

First, enumerate every resource the file declares and note its type. Second, \
for each resource, consider what an attacker could reach or do if that \
resource were misconfigured, and check the specific attributes that govern \
access, encryption, and network exposure. Third, examine how the resources \
reference one another, since a weakness may only be visible in the \
relationship between two blocks. Fourth, review your candidate findings and \
discard any you cannot substantiate from the configuration itself.

Reason step by step through those four stages, then report your final findings."""


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def _wrap_code(terraform: str, filename: str) -> str:
    return f"Terraform configuration ({filename}):\n\n```hcl\n{terraform}\n```"


def build(variant: str, terraform: str, filename: str,
          guidance: str | None = None) -> tuple[str, str]:
    """
    Return (system_prompt, user_prompt) for a context variant.

    `guidance` is required for the rag variant and ignored otherwise.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected one of {VARIANTS}")

    system = BASE_SYSTEM
    parts: list[str] = []

    if variant == "zero_shot":
        parts = [TASK_INSTRUCTION, _wrap_code(terraform, filename)]

    elif variant == "few_shot":
        parts = [TASK_INSTRUCTION, FEW_SHOT_EXAMPLES,
                 "Now review the following configuration.",
                 _wrap_code(terraform, filename)]

    elif variant == "system_enriched":
        system = ENRICHED_SYSTEM
        parts = [TASK_INSTRUCTION, _wrap_code(terraform, filename)]

    elif variant == "rag":
        if not guidance:
            raise ValueError("the rag variant requires retrieved guidance")
        parts = [RAG_PREAMBLE.format(guidance=guidance.strip()),
                 TASK_INSTRUCTION, _wrap_code(terraform, filename)]

    elif variant == "chain_of_thought":
        parts = [TASK_INSTRUCTION, COT_INSTRUCTION, _wrap_code(terraform, filename)]

    return system, "\n\n".join(parts)


# --------------------------------------------------------------------------
# Orchestration-pattern prompts (used by harness/agents/)
# --------------------------------------------------------------------------

CRITIC_INSTRUCTION = """\
A colleague reviewed the Terraform configuration below and produced the \
findings that follow. Your job is to critique that review, not to repeat it.

Assess each reported finding: is it a genuine security vulnerability, \
correctly attributed to the right resource? Remove findings that are wrong, \
duplicated, or out of scope under the criteria above. Then identify any \
security vulnerability the review missed.

Return the corrected, complete findings list."""

DEBATE_RECONCILER_INSTRUCTION = """\
Two reviewers independently examined the Terraform configuration below and \
reached the conclusions that follow. They disagree in places.

Reconcile the two reviews into one authoritative findings list. Where they \
agree, carry the finding forward. Where they differ, decide which reviewer is \
correct based on the configuration itself rather than on how confidently \
either wrote. Where both missed something, add it.

Return the reconciled findings list."""

CHUNK_HEADER = """\
This is one excerpt from a larger Terraform file. For context, the complete \
file declares the following resources:

{manifest}

Review only the excerpt below. Other resources are listed above so you can \
reason about references between them, but do not report findings against \
resources whose definitions you cannot see."""

TOOL_AGENT_INSTRUCTION = """\
You have access to a static analysis scanner via the run_scanner tool. Use it \
to analyse the Terraform configuration, then interpret its output.

The scanner is a starting point, not an oracle. It reports findings that are \
not security vulnerabilities under the criteria above, and it misses issues \
that require reasoning about relationships between resources. Filter its \
output to genuine security vulnerabilities, and add anything it missed that \
your own reading of the configuration reveals."""
