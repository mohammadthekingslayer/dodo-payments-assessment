# Task 2: Secure CI/CD Pipeline & Supply Chain

## Approach and Design Decisions
1. **Pipeline Triggers**: The GitHub Actions pipeline runs on every push and pull request to the `main` branch.
2. **Shift-Left Security Scans**:
   - **Gitleaks**: Runs first to hard block any accidental commits containing plaintext secrets.
   - **Semgrep**: Configured for SAST to block on high/critical vulnerabilities. Results are uploaded as **SARIF** to the GitHub Security tab.
   - **Trivy**: Scans the container image. It is configured to fail (hard block) exclusively on `CRITICAL` vulnerabilities. For CVEs with no fix available yet, it uses `ignore-unfixed: true`, ensuring the pipeline is not indefinitely blocked by vulnerabilities the maintainer cannot patch. Results are uploaded as **SARIF**.
3. **Image Provenance and Integrity**:
   - Uses Sigstore's **Cosign (Keyless mode)** to cryptographically sign the container image.
   - Generates an **SLSA provenance attestation** via `cosign attest` to prove the image was built securely in GitHub Actions.
   - Output of a verification run is demonstrated below.
4. **GitOps Deployment**:
   - **ArgoCD** is configured with `selfHeal: true`. Any manual unauthorized changes (e.g., via `kubectl`) are immediately detected as drift and automatically reverted.

## Cosign Verification Proof
```bash
$ cosign verify \
  --certificate-identity "https://github.com/bhabani-dodo/ledger-api-assignment/.github/workflows/pipeline.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/bhabani-dodo/ledger-api:13cf209

Verification for ghcr.io/bhabani-dodo/ledger-api:13cf209 --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - Existence of the claims in the transparency log was verified offline
  - The code-signing certificate was verified using trusted certificate authority certificates
```
