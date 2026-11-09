# G4 WRITE — owner-only READ-ONLY SonarQube Cloud permission inventory

**Date:** 2026-10-31. **Status:** NOT EXECUTED BY OWNER. Intended for metadata inspection only. **No real POST, token generation, token revocation, token read/copy/export, scope change, secret submission, G2/G4 upgrade or Docker action is authorized.** This inventory addresses privileged-token **custody and residual exposure**, Gate G4-W1 in [`G4-WRITE-SECURITY-REVIEW.md`](G4-WRITE-SECURITY-REVIEW.md), under the owner-selected [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](G4-WRITE-PRIVILEGED-TOKEN-ADR.md).

## Owner clarification: cross-organization credential reach

The owner reports that the installed token is **not bound to one organization**.
The practical risk is its ability to authenticate across the accessible
organizations/projects of the **issuing user**, if it is an account PAT.
The token type (PAT vs SOT) itself is **not yet independently verified**.
`FORTIS_G4_ORGANIZATIONS=alexpastukhh` restricts current G4 application
requests, **not** stolen-token permissions. For future WRITE, inspect the actual issuer authority and token expiry **for host custody and incident response**, not to demand a low-privilege user. The owner chose a broadly privileged token, with **Fortis ASK as the required policy layer**; a narrow identity is optional defense in depth, not mandatory. The application limit is not a constraint on stolen token bytes. G4 WRITE remains NO-GO pending implementation and verification of non-bypassable ASK, token isolation, race/uncertain handling and fresh authorization, **not merely because the token is broad**.

## Safe browser-only inspection

1. On the trusted Windows machine, open the existing **EU** SonarQube Cloud account at <https://sonarcloud.io> and sign in yourself. Do not use the Fortis Repo environment, PowerShell or AI tools to handle the credential.
2. In your account menu go to **My Account → Security**. Under personal access tokens (PAT), **inspect metadata only**: whether a current token is listed, if an expiry is visible, and whether this account is an administrator. Do **not** click Generate, Revoke, Copy, or show the token value. Do not post token names, raw keys, screenshot of account details, emails, usernames or account ID to chat.
3. Inspect project permissions **across each organization accessible to the issuing identity** (without sending organization names to chat); then open a known project in SonarCloud → **Administration → Permissions** (if available). Read current permissions for the relevant account/groups: **Browse Project** (for private projects) and **Administer Issues**. Do not edit checkboxes, templates or project visibility. A missing permissions page is `UNKNOWN`, **not** proof of no permission.
4. If your SonarCloud plan offers organization **Scoped Organization Tokens**, the organization admin may inspect their non-secret metadata using **Scoped Organization Tokens → Actions → View details**. The current official Cloud documentation lists only **Execute analysis** as an available token permission. It does **not** establish an `Administer Issues` scope for these tokens; do not infer WRITE eligibility from a scoped token.
5. For a **future** isolated test, determine whether a disposable project and single exact Issue can be nominated, and identify the host boundary that keeps the broad credential out of AI/Repo/other untrusted containers. **Do not create** an identity, project, or token, copy secret bytes or change grants during this read-only review. Narrow-token availability is not an eligibility gate.

## What can safely be reported back (without secrets)

Only give *category-level* answers, e.g. `PAT / SOT / UNKNOWN`, `expiry visible: YES / NO / UNKNOWN`, `project-level Administer Issues: YES / NO / UNKNOWN`, `owner-only executor/volume isolation feasible: YES / NO / UNKNOWN`, `isolated disposable Issue feasible: YES / NO / UNKNOWN`. Avoid names, token suffix/prefix, user identifiers, emails, credential values, screenshots of credentials, issue bodies, or WebAuthn invitations. Use `UNKNOWN` whenever a value cannot be verified; never guess from a successful read-only GET.

| Gate G4-W1 item | Current safe status | Owner evidence required later |
| --- | --- | --- |
| Existing READ token issuer reach | **CROSS-ORGANIZATION (owner-reported)** | Inspect only permission categories across all accessible organizations; token type remains unverified |
| Existing READ token type | **UNKNOWN** | PAT vs SOT from account metadata, no token bytes |
| Existing READ token expiry/revocation plan | **UNKNOWN** | Human-confirmed expiry metadata; no copy/export |
| Account/project `Administer Issues` permissions | **UNKNOWN** | Project permissions screen, no change |
| Fortis privileged executor + mandatory ASK boundary | **NOT RELEASED** | Independent code/negative-test review; one exact decision and one-shot dispatch |
| Disposable WRITE test project/Issue | **NOT NOMINATED** | Future explicit owner-selected nonproduction target; optional restriction is at Fortis policy/executor layer |
| Custody and rotation for broad token | **OPEN** | Owner-controlled isolation, incident revocation, exposure/backup review; may retain broad-token architecture |
| Authenticated WRITE test permission | **NOT GRANTED** | Separate explicit authorization after all gates |

## Why this matters

SonarQube Cloud documents that **Administer Issues** allows both Accept and False Positive actions. Accept may change metrics and Quality Gate. A PAT uses the issuing user's project privileges; it is not automatically restricted to a single transition or Issue. Scoped Organization Tokens currently document only `Execute analysis`. Therefore neither the current G4 successful GET nor a list of offered transitions proves WRITE access. The owner's architecture intentionally gives a trusted Fortis executor a broadly authorized credential while enforcing which actions execute through ASK. This must be implemented in the trusted policy and dispatch boundary, **not** assumed from a token scope. Anyone with stolen token bytes can bypass the Fortis ASK boundary; token custody, backups, host administrators, rotation/revocation and explicit risk acceptance remain separate controls. The existing G4 token remains unchanged and stored unencrypted in its G4-only Docker volume.

## References (official SonarQube Cloud, checked 2026-10-31)

- Account → Security and PATs: <https://docs.sonarsource.com/sonarqube-cloud/managing-your-account/managing-tokens>
- Project → Administration → Permissions and `Administer Issues`: <https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/administering-your-projects/setting-permissions>
- Scoped Organization Tokens → View details: <https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-organization/scoped-organization-tokens>
- Accept and Quality Gate side effects: <https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/editing>

**Return criteria:** only non-secret, category-level observations needed for privileged-token custody and Fortis ASK release review. A narrowly privileged Sonar token is optional. WRITE remains **NO-GO** until the new trusted executor and mandatory ASK are implemented, tested and separately authorized.
