## Identity and access management

Grant least privilege access. Start with a minimum set of permissions and grant
additional permissions as necessary, rather than starting permissive and
restricting later. Define access requirements for each component and grant only
the actions those requirements need.

Reduce permissions continuously. Permissions granted during development
frequently exceed what production requires. Review and remove unused
permissions on an ongoing basis.

Define permission guardrails. Permissions boundaries set the maximum
permissions an administrator may delegate and are the mechanism that prevents
privilege escalation through self-granted policy changes. Service control
policies limit but never grant permissions.

Analyse public and cross-account access. Resource-based policies that name a
wildcard principal, or that permit access from outside the account or
organisation, expose the resource beyond its intended boundary.

Prefer identity federation and temporary credentials over long-lived static
credentials. Static access keys attached to users persist until manually
rotated and are a recurring source of credential compromise.

Wildcards in the Action or Resource element of a policy statement grant
substantially more than intended. A statement combining a wildcard action with
a wildcard resource is equivalent to administrative access.

Distinguish roles that assume other roles, and permissions that allow passing a
role to a service. Both can form privilege escalation paths that are not
visible from any single policy in isolation.

## Data protection

Enforce encryption at rest. Encryption should be the default state for stored
data rather than an option enabled per resource. Automate data-at-rest
protection so new resources inherit encryption without manual configuration.

Implement secure key management. Customer-managed keys give explicit control
over key policy, rotation, and revocation, which service-owned default keys do
not. Audit key usage to confirm access controls behave as intended.

Enforce access control on stored data in addition to encryption. Encryption
protects confidentiality against access to the underlying storage; it does not
substitute for authorisation on the service interface.

Enforce encryption in transit. All data transmitted between systems should be
encrypted, covering traffic between components inside a workload as well as
traffic to end users. Deprecated protocol versions should be disabled rather
than merely deprioritised.

Authenticate network communications. Verify the identity of communicating
systems to prevent unintended access.

## Infrastructure and network protection

Create network layers. Group components that share sensitivity requirements
into distinct layers, and place components that do not require inbound access
from the internet in private subnets without public addressing.

Control traffic flow within network layers. Apply a Zero Trust approach in
which components do not implicitly trust one another. Restrict inbound rules to
specific source ranges and ports required by the workload; a rule admitting
0.0.0.0/0 grants access to the entire internet.

Control egress as well as ingress. Unrestricted outbound access provides a
data exfiltration path and a channel to command-and-control infrastructure.

Default network constructs frequently permit more than intended. A default
security group that has not been explicitly restricted allows traffic that an
explicitly authored group would not.

Protect compute at every layer. Disable legacy instance metadata service
versions that permit unauthenticated credential retrieval, since a
server-side request forgery in an application then becomes credential theft.

Keep runtimes and platform versions current. Deprecated runtimes stop receiving
security patches while continuing to execute.

## Secrets

Never store confidential data — tokens, passwords, SSH keys, connection strings
— in plain text in source files or version control. Secrets committed to a
repository must be treated as compromised regardless of subsequent removal.

Secrets embedded in instance startup scripts, container environment variables,
or function configuration are readable by anyone with describe permissions on
the resource, which is a much wider audience than those with access to the
secret store.

Default administrative account names, and credentials carried in example or
template configuration, should not survive into deployed infrastructure.

## Infrastructure as code practice

Limit the permissions granted to resources created by IaC to what those
resources require. The permissions an IaC script assigns are the permissions
that reach production.

Build infrastructure to an exact specification and treat it as immutable.
Deviations introduced outside the code are invisible to review.

Enable security and audit logging when provisioning infrastructure.

Sign artefacts at build time and validate signatures before use, so that
tampering between build and deployment is detectable.

## CIS AWS Foundations Benchmark — control areas

The benchmark's prescriptive controls cluster around: identity and access
management hygiene including credential rotation and privilege minimisation;
logging and audit trail configuration; monitoring and alarm coverage for
security-relevant events; networking controls covering default security groups,
unrestricted ingress, and VPC configuration; and service-specific
configuration for storage, database, and key management resources.
