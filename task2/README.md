# Task 2 — Secure CI/CD Pipeline & Supply Chain

## Approach and Design Decisions

### Pipeline Architecture

```
┌────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐    ┌───────────┐
│  Git Push   │───▶│ Secrets Scan │───▶│  SAST Scan   │───▶│  Build   │───▶│ CVE Scan  │
│  (trigger)  │    │  (Gitleaks)  │    │  (Semgrep)   │    │ (Docker) │    │  (Trivy)  │
└────────────┘    └──────────────┘    └──────────────┘    └──────────┘    └─────┬─────┘
                                                                                │
                  ┌──────────────┐    ┌──────────────┐    ┌──────────┐          │
                  │   ArgoCD     │◄───│  Push GHCR   │◄───│  Cosign  │◄─────────┘
                  │  (GitOps)    │    │  (Registry)  │    │  (Sign)  │
                  └──────────────┘    └──────────────┘    └──────────┘
```

### Security Gate Fail Policies

| Gate | Tool | Severity Threshold | Action on Fail | Rationale |
|------|------|--------------------|----------------|-----------|
| **Secrets Scan** | Gitleaks | Any secret found | **Hard block** — pipeline fails | Zero tolerance. Even one leaked key can compromise the entire system. |
| **SAST** | Semgrep | Critical / High | **Hard block** — pipeline fails | Code-level vulnerabilities (SQLi, RCE, SSRF patterns) must be fixed before merge. |
| **SAST** | Semgrep | Medium / Low | **Warn** — pipeline continues | Logged as SARIF in GitHub Security tab for triage. |
| **CVE Scan** | Trivy | Critical | **Hard block** — pipeline fails | Known critical CVEs with available fixes must be patched. |
| **CVE Scan** | Trivy | High | **Warn** — pipeline continues | Logged for review; `ignore-unfixed: true` prevents blocking on CVEs with no upstream patch yet. |
| **Image Signing** | Cosign (keyless) | Signing failure | **Hard block** — pipeline fails | Unsigned images must never reach production. |

### Handling CVEs With No Fix Available

When Trivy finds a CVE classified as CRITICAL but no upstream fix exists:
- `ignore-unfixed: true` is set — the pipeline **does not block** on unfixable vulnerabilities
- The finding is still recorded in the SARIF output and surfaces in the GitHub Security tab
- A `.trivyignore` file can be used to explicitly acknowledge and suppress known-unfixable CVEs with a justification comment
- These are reviewed in the weekly security triage meeting

### Image Provenance & Signing

```bash
# Keyless signing via OIDC (GitHub Actions identity)
cosign sign --yes ghcr.io/$IMAGE:$SHA

# SLSA provenance attestation
cosign attest --yes --predicate predicate.json --type slsaprovenance ghcr.io/$IMAGE:$SHA

# Verification (anyone can run this)
$ cosign verify \
  --certificate-identity "https://github.com/mohammadthekingslayer/dodo-payments-assessment/.github/workflows/pipeline.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/mohammadthekingslayer/dodo-payments-assessment:$SHA

Verification for ghcr.io/mohammadthekingslayer/dodo-payments-assessment:$SHA --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - Existence of the claims in the transparency log was verified offline
  - The code-signing certificate was verified using trusted certificate authority certificates
```

### GitOps with ArgoCD

ArgoCD is configured with:
- **`selfHeal: true`** — any manual `kubectl edit` or `kubectl set image` is automatically reverted
- **`prune: true`** — resources deleted from Git are pruned from the cluster
- Git repository is the **single source of truth**

#### Drift Detection Demo

```bash
# 1. Attacker/operator manually changes the image
$ kubectl set image deployment/ledger-api ledger-api=ledger-api:compromised -n payments
deployment.apps/ledger-api image updated

# 2. ArgoCD detects drift within sync interval
$ argocd app get ledger-api
Sync Status:  OutOfSync from main
Health Status: Progressing

# 3. selfHeal triggers automatic revert (no human intervention)
$ argocd app wait ledger-api --sync
# Image reverts to the Git-declared value
```

### SARIF Integration (Bonus)

Both Semgrep and Trivy results are uploaded as SARIF to the GitHub Security tab via `github/codeql-action/upload-sarif@v3`, enabling:
- Centralized vulnerability dashboard
- PR-level security annotations
- Historical tracking of security posture

### Files

| File | Purpose |
|---|---|
| `.github/workflows/pipeline.yml` | Root CI/CD pipeline (builds, scans, signs, deploys) |
| `task2/.github/workflows/pipeline.yml` | Reference copy with full build pipeline |
| `task2/manifests/argocd-app.yaml` | ArgoCD Application manifest with selfHeal |
