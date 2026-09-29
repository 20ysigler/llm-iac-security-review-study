#!/usr/bin/env python3
"""
Mutation control corpus.

Rewrites the six TerraGoat files under review so that every surface feature a
model could have memorised is changed, and nothing that constitutes a
vulnerability is changed. The point is to test whether detection rates on the
original corpus reflect reasoning or recall of a public, static repository.

Changed (surface):
  - every resource / data / output label, and every reference to it, including
    references inside strings and heredocs
  - the `local.resource_prefix` local, and every reference
  - identifier string literals that embed a label ("...-data", "rds-...", the
    policy name "excess_policy")
  - the Yor/git provenance tags in every tags block (git_*, yor_trace), and the
    now-empty second argument of merge() they leave behind
  - comments outside heredocs (several are literal answer keys)
  - top-level block order within each file
  - order of single-line attributes at the top level of each block

Kept (vulnerabilities):
  - resource types
  - every attribute value and every absent attribute
  - nested blocks (ingress {}, versioning {}, ...) and their contents
  - heredoc bodies except for the reference renames above
  - inter-resource relationships (these are references, renamed consistently)

Deterministic: seeded shuffles, explicit rename table. Output is a full copy of
terragoat/terraform/aws with the six files rewritten, so Checkov's graph checks
see the same neighbouring files as the original scan did.

    python3 harness/mutate_corpus.py            # writes terragoat_mut/ and data/rename_map.json
"""
from __future__ import annotations

import json
import random
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agents.hcl import split_blocks, Block  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "terragoat" / "terraform" / "aws"
DST = ROOT / "terragoat_mut" / "terraform" / "aws"
FILES = ["s3.tf", "ec2.tf", "db-app.tf", "iam.tf", "kms.tf", "lambda.tf"]
SEED = 20260908

# ---------------------------------------------------------------------------
# Rename table. Plausible names, consistent theme per file. Keyed by the full
# address so two resources sharing a label ("default") stay distinct.
# ---------------------------------------------------------------------------
RENAMES: dict[str, str] = {
    # s3.tf
    "aws_s3_bucket.data": "reports_archive",
    "aws_s3_bucket_object.data_object": "reports_seed_object",
    "aws_s3_bucket.financials": "ledger_exports",
    "aws_s3_bucket.operations": "ops_runbooks",
    "aws_s3_bucket.data_science": "model_artifacts",
    "aws_s3_bucket.logs": "audit_trail",
    # ec2.tf
    "aws_instance.web_host": "portal_server",
    "aws_ebs_volume.web_host_storage": "portal_server_disk",
    "aws_ebs_snapshot.example_snapshot": "portal_disk_backup",
    "aws_volume_attachment.ebs_att": "portal_disk_attach",
    "aws_security_group.web-node": "portal_sg",
    "aws_vpc.web_vpc": "portal_vpc",
    "aws_subnet.web_subnet": "portal_subnet_a",
    "aws_subnet.web_subnet2": "portal_subnet_b",
    "aws_internet_gateway.web_igw": "portal_igw",
    "aws_route_table.web_rtb": "portal_routes",
    "aws_route_table_association.rtbassoc": "portal_routes_a",
    "aws_route_table_association.rtbassoc2": "portal_routes_b",
    "aws_route.public_internet_gateway": "portal_default_route",
    "aws_network_interface.web-eni": "portal_nic",
    "aws_flow_log.vpcflowlogs": "portal_vpc_flowlog",
    "aws_s3_bucket.flowbucket": "netflow_archive",
    "output.ec2_public_dns": "portal_public_dns",
    "output.vpc_id": "portal_vpc_id",
    "output.public_subnet": "portal_subnet_a_id",
    "output.public_subnet2": "portal_subnet_b_id",
    # db-app.tf
    "aws_db_instance.default": "catalog_db",
    "aws_db_option_group.default": "catalog_db_options",
    "aws_db_parameter_group.default": "catalog_db_params",
    "aws_db_subnet_group.default": "catalog_db_subnets",
    "aws_security_group.default": "catalog_db_sg",
    "aws_security_group_rule.ingress": "catalog_db_inbound",
    "aws_security_group_rule.egress": "catalog_db_outbound",
    "aws_iam_instance_profile.ec2profile": "catalog_app_profile",
    "aws_iam_role.ec2role": "catalog_app_role",
    "aws_iam_role_policy.ec2policy": "catalog_app_policy",
    "data.aws_ami.amazon-linux-2": "base_image",
    "aws_instance.db_app": "catalog_app_server",
    "output.db_app_public_dns": "catalog_app_public_dns",
    "output.db_endpoint": "catalog_db_endpoint",
    # iam.tf
    "aws_iam_user.user": "svc_deploy",
    "aws_iam_access_key.user": "svc_deploy_key",
    "aws_iam_user_policy.userpolicy": "svc_deploy_policy",
    "output.username": "svc_deploy_username",
    "output.secret": "svc_deploy_key_material",
    # kms.tf
    "aws_kms_key.logs_key": "audit_trail_key",
    "aws_kms_alias.logs_key_alias": "audit_trail_key_alias",
    # lambda.tf
    "aws_iam_role.iam_for_lambda": "analytics_fn_role",
    "aws_lambda_function.analysis_lambda": "analytics_fn",
}

LOCAL_RENAMES = {"local.resource_prefix": "local.env_prefix"}

# Identifier string fragments that embed an old label. Ordered longest-first
# at apply time. Matched only inside double-quoted strings.
STRING_FRAGMENTS = {
    "-primary_network_interface": "-portal-nic",
    "-flowlogs": "-netflow",
    "-analysis": "-analytics",
    "-profile": "-catalog-profile",
    "-policy": "-catalog-policy",
    "-dbapp": "-catalog-app",
    "-subnet": "-portal-subnet",
    "-role": "-catalog-role",
    "-user": "-svc-deploy",
    "-data_science": "-model-artifacts",
    "-financials": "-ledger",
    "-operations": "-runbooks",
    "-flowlogs-": "-netflow-",
    "-logs": "-audit",
    "customer-master": "vendor-roster",
    "-data": "-reports",
    "-ebs": "-portal-disk",
    "-igw": "-portal-igw",
    "-rtb": "-portal-routes",
    "-vpc": "-portal-vpc",
    "-rds": "-catalog",
    "-og": "-catalogopts",
    "-pg": "-catalogparams",
    "-sg": "-portal-sg",
    "rds-": "catalog-",
    "og-": "catalogopts-",
    "pg-": "catalogparams-",
    "sg-": "catalogsg-",
    "excess_policy": "svc_deploy_access",
}

PROVENANCE_KEYS = ("git_commit", "git_file", "git_last_modified_at", "git_last_modified_by",
                   "git_modifiers", "git_org", "git_repo", "yor_trace")

_HEREDOC = re.compile(r"<<-?\s*([A-Za-z_][A-Za-z0-9_]*)")


def _line_kinds(text: str):
    """Yield (line, in_heredoc) so transformations can skip heredoc bodies."""
    heredoc = None
    for line in text.splitlines(keepends=True):
        if heredoc is not None:
            yield line, True
            if line.strip() == heredoc:
                heredoc = None
            continue
        yield line, False
        m = _HEREDOC.search(line)
        if m:
            heredoc = m.group(1)


# ---------------------------------------------------------------- transforms
def rename_references(text: str) -> str:
    """type.label -> type.newlabel everywhere, including in strings/heredocs."""
    # Longest addresses first so aws_s3_bucket.data does not clip aws_s3_bucket.data_science.
    for addr, new in sorted(RENAMES.items(), key=lambda kv: -len(kv[0])):
        kind_type, label = addr.rsplit(".", 1)
        if addr.startswith("output."):
            continue  # outputs are never referenced; header handled separately
        if addr.startswith("data."):
            # data.aws_ami.amazon-linux-2  ->  data.aws_ami.base_image
            text = re.sub(rf"\b{re.escape(addr)}(?![A-Za-z0-9_-])", f"{kind_type}.{new}", text)
            continue
        text = re.sub(rf"\b{re.escape(kind_type)}\.{re.escape(label)}(?![A-Za-z0-9_-])",
                      f"{kind_type}.{new}", text)
    for old, new in LOCAL_RENAMES.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text


def rename_headers(block: Block) -> Block:
    """resource "type" "label" {  ->  resource "type" "newlabel" {"""
    addr = block.address
    if block.kind == "output":
        key = f"output.{block.labels[0]}"
    elif block.kind == "data":
        key = addr
    else:
        key = addr
    if key not in RENAMES:
        if block.kind in ("resource", "data", "output"):
            raise SystemExit(f"no rename for {key}")
        return block
    new = RENAMES[key]
    old_label = block.labels[-1]
    head, rest = block.text.split("\n", 1)
    head = re.sub(rf'"{re.escape(old_label)}"(\s*\{{)$', f'"{new}"\\1', head)
    assert new in head, f"header rename failed for {key}"
    return Block(kind=block.kind, labels=block.labels[:-1] + [new], text=head + "\n" + rest,
                 start_line=block.start_line)


def _fragment_pattern() -> "re.Pattern[str]":
    """
    One alternation over every fragment, longest first, applied in a single
    pass. A fragment that begins with a letter or digit must start at a token
    boundary (start of string, or after a non-alphanumeric), so "og-" cannot
    match inside "log-delivery-write". Single-pass application also stops a
    replacement's output from being re-matched by a later fragment
    ("-dbapp" -> "-catalog-app" must not then feed "og-").
    """
    parts = []
    for old in sorted(STRING_FRAGMENTS, key=len, reverse=True):
        anchor = r"(?<![A-Za-z0-9])" if old[0].isalnum() else ""
        parts.append(anchor + re.escape(old))
    return re.compile("|".join(parts))


_FRAGMENT_RE = _fragment_pattern()


def rename_string_fragments(text: str) -> str:
    """Rewrite identifier fragments inside double-quoted strings only."""
    def fix(m):
        return _FRAGMENT_RE.sub(lambda f: STRING_FRAGMENTS[f.group(0)], m.group(0))
    out = []
    for line, in_heredoc in _line_kinds(text):
        out.append(line if in_heredoc else re.sub(r'"[^"\n]*"', fix, line))
    return "".join(out)


def strip_provenance_tags(text: str) -> str:
    lines = [l for l in text.splitlines(keepends=True)
             if not re.match(rf"^\s*({'|'.join(PROVENANCE_KEYS)})\s*=", l)]
    text = "".join(lines)
    # merge({ ...first map... }, {\n  })  ->  { ...first map... }
    # The first map may contain ${...} interpolations, so match on the shape
    # of the now-empty second argument instead of on brace balance.
    text = re.sub(r"merge\(\{(.*?)\n(\s*)\},\s*\{\s*\}\s*\)", r"{\1\n\2}", text, flags=re.S)
    return text


def strip_comments(text: str) -> str:
    out = []
    for line, in_heredoc in _line_kinds(text):
        if in_heredoc:
            out.append(line); continue
        if re.match(r"^\s*(#|//)", line):
            continue                                  # whole-line comment
        if ('"' not in line) and re.search(r"\s(#|//).*$", line):
            line = re.sub(r"\s(#|//).*$", "", line).rstrip("\n") + "\n"
        out.append(line)
    return "".join(out)


def shuffle_attributes(block_text: str, rng: random.Random) -> str:
    """Shuffle runs of single-line `key = value` attributes at depth 1, outside heredocs."""
    lines = block_text.splitlines(keepends=True)
    if len(lines) < 4:
        return block_text
    head, body, tail = lines[0], lines[1:-1], lines[-1]
    # depth tracking within body; only depth-1 simple attributes are candidates
    depth, heredoc, runs, cur = 1, None, [], []
    simple = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^{<\n]*$')
    for i, l in enumerate(body):
        if heredoc is not None:
            if l.strip() == heredoc: heredoc = None
            if cur: runs.append(cur); cur = []
            continue
        m = _HEREDOC.search(l)
        if m:
            heredoc = m.group(1)
            if cur: runs.append(cur); cur = []
            continue
        opens, closes = l.count("{"), l.count("}")
        if depth == 1 and simple.match(l) and opens == 0 and closes == 0:
            cur.append(i)
        else:
            if cur: runs.append(cur); cur = []
        depth += opens - closes
    if cur: runs.append(cur)
    for run in runs:
        if len(run) > 1:
            vals = [body[i] for i in run]; rng.shuffle(vals)
            for i, v in zip(run, vals): body[i] = v
    return head + "".join(body) + tail


def mutate_file(text: str, rng: random.Random) -> str:
    text = strip_comments(text)
    text = strip_provenance_tags(text)
    text = rename_references(text)
    text = rename_string_fragments(text)
    blocks = [rename_headers(b) for b in split_blocks(text)]
    blocks = [Block(b.kind, b.labels, shuffle_attributes(b.text, rng), b.start_line) for b in blocks]
    rng.shuffle(blocks)
    parts = [b.text.strip("\n") + "\n" for b in blocks]
    return "\n".join(parts)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"corpus not found at {SRC}; clone TerraGoat at the pinned commit first")
    if DST.parent.parent.exists():
        shutil.rmtree(DST.parent.parent)
    # Only terraform/aws/*.tf: the six reviewed files are rewritten below; the
    # other eight are copied unchanged so Checkov's graph checks see the same
    # neighbours the original scan did. Nothing else from the repo is needed.
    DST.mkdir(parents=True)
    for tf in SRC.glob("*.tf"):
        shutil.copy(tf, DST / tf.name)
    (DST.parent.parent / "README.md").write_text(
        "Mutation-control corpus derived from bridgecrewio/terragoat at commit "
        f"{(ROOT / 'data' / 'terragoat_commit.txt').read_text().strip()} (Apache-2.0; LICENSE retained).\n"
        "The six files under review (s3, ec2, db-app, iam, kms, lambda) are rewritten by "
        "harness/mutate_corpus.py; the other eight are unchanged. Rename map: data/rename_map.json. "
        "Semantic-preservation proof: data/mutation_checkov_diff.txt (harness/validate_mutation.py).\n")
    rng = random.Random(SEED)
    for f in FILES:
        src = (SRC / f).read_text()
        (DST / f).write_text(mutate_file(src, rng))
        print(f"  {f:12} {len(src):6} -> {len((DST / f).read_text()):6} chars")
    rename_map = {**RENAMES, **LOCAL_RENAMES}
    (ROOT / "data" / "rename_map.json").write_text(json.dumps(
        {"seed": SEED, "source_commit": (ROOT / "data" / "terragoat_commit.txt").read_text().strip(),
         "renames": {k: (k.rsplit(".", 1)[0] + "." + v if not k.startswith("local.") else v)
                     for k, v in rename_map.items()}}, indent=1))
    print(f"wrote {DST} and data/rename_map.json ({len(rename_map)} renames)")
    translate_ground_truth()
    shutil.copy(SRC.parent.parent / "LICENSE", DST.parent.parent / "LICENSE")  # Apache-2.0; derivative retains it


def translate_ground_truth() -> None:
    """ground_truth.json -> ground_truth_mut.json with resource addresses renamed.

    Categories, CWEs, severities, and Checkov IDs are untouched. Only the
    address changes, and only through the same rename map the corpus used, so
    the scorer matches mutated claims against the same findings."""
    gt = json.loads((ROOT / "data" / "ground_truth.json").read_text())
    out = {"meta": dict(gt["meta"], derived_from="ground_truth.json", corpus="terragoat_mut",
                        rename_map="data/rename_map.json"), "findings": {}}
    n = 0
    for key, findings in gt["findings"].items():
        if not key.startswith("terragoat::"):
            continue
        new_key = key.replace("terragoat::", "terragoat_mut::", 1)
        rows = []
        for f in findings:
            addr = f["resource"]
            if addr not in RENAMES:
                raise SystemExit(f"ground truth resource {addr} has no rename")
            g = dict(f, corpus="terragoat_mut", resource=f"{addr.rsplit('.', 1)[0]}.{RENAMES[addr]}",
                     original_resource=addr)
            rows.append(g); n += 1
        out["findings"][new_key] = rows
    (ROOT / "data" / "ground_truth_mut.json").write_text(json.dumps(out, indent=1))
    print(f"wrote data/ground_truth_mut.json ({n} findings across {len(out['findings'])} files)")


if __name__ == "__main__":
    main()
