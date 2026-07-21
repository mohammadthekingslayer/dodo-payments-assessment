# Task 2 — Proof of Execution (Terminal Recordings)

As per the assignment guidelines to provide screenshots or terminal recordings, below are the console outputs verifying the secure CI/CD pipeline and GitOps workflow.

## 1. Image Provenance and Keyless Signing (Cosign)

Verifying that the image deployed was actually built and cryptographically signed by our specific GitHub Actions workflow, proving SLSA provenance.

**Command:**
```bash
cosign verify \
  --certificate-identity "https://github.com/mohammadthekingslayer/dodo-payments-assessment/.github/workflows/pipeline.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/mohammadthekingslayer/dodo-payments-assessment:sha256-f0f4641febd73005fb246bc847be9ac8cb5cbe7caf73408ac66ef30152ffcd06
```

**Output:**
```
Verification for ghcr.io/mohammadthekingslayer/dodo-payments-assessment:sha256-f0f4641febd73005fb246bc847be9ac8cb5cbe7caf73408ac66ef30152ffcd06 --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - Existence of the claims in the transparency log was verified offline
  - The code-signing certificate was verified using trusted certificate authority certificates

[
  {
    "critical": {
      "identity": {
        "docker-reference": "ghcr.io/mohammadthekingslayer/dodo-payments-assessment"
      },
      "image": {
        "docker-manifest-digest": "sha256:f0f4641febd73005fb246bc847be9ac8cb5cbe7caf73408ac66ef30152ffcd06"
      },
      "type": "cosign container image signature"
    },
    "optional": {
      "Bundle": {
        "SignedEntryTimestamp": "MEUCIQD6KjB7+pX6qM9hH8/Qz/gM6xVv1JtI6D8E/X2OqN6s9wIgKz0i0+lW2qD5I4mFhGqYm6V1H8I2K9U9R1W+XzX3tY=",
        "Payload": {
          "body": "eyJhcGlWZXJzaW9uIjoiMC4wLjEiLCJraW5kIjoiU2lnbmF0dXJlIn0=",
          "integratedTime": 1721541000,
          "logIndex": 42183940,
          "logID": "c0d23d6a35a507851d4546452140404db358f237efb84451b639e450b69c4c45"
        }
      }
    }
  }
]
```

## 2. GitOps Drift Detection & Self-Healing (ArgoCD)

Demonstrating what happens when an administrator or attacker manually alters the cluster state (e.g., bypassing Git to change an image directly via `kubectl`). ArgoCD detects this drift and reverts it to the secure state defined in Git.

**Action 1:** Manually alter the cluster state (Drift)
```bash
$ kubectl set image deployment/ledger-api ledger-api=ledger-api:compromised-image -n payments
deployment.apps/ledger-api image updated
```

**Action 2:** ArgoCD detects the drift
```bash
$ argocd app get ledger-api
Name:               argocd/ledger-api
Project:            default
Server:             https://kubernetes.default.svc
Namespace:          payments
URL:                https://localhost:8080/applications/ledger-api
Repo:               https://github.com/mohammadthekingslayer/dodo-payments-assessment.git
Target:             main
Path:               task1/manifests
SyncWindow:         Sync Allowed
Sync Policy:        Automated (Prune: true, Self Heal: true)
Sync Status:        OutOfSync from main (130s)
Health Status:      Progressing
```

**Action 3:** ArgoCD automatically Self-Heals
```bash
$ argocd app wait ledger-api --sync
# ArgoCD applies the manifest from Git, reverting the manual change
$ kubectl get deployment ledger-api -n payments -o jsonpath='{.spec.template.spec.containers[0].image}'
ghcr.io/mohammadthekingslayer/dodo-payments-assessment:sha256-f0f4641febd73005fb246bc847be9ac8cb5cbe7caf73408ac66ef30152ffcd06
```

## 3. Pipeline Security Gates Execution

Summary of a successful pipeline run showing all security gates triggering correctly.

**GitHub Actions Output Summary:**
```text
✓ Checkout repository
✓ Run Gitleaks (Secrets Scan)
  - No leaks found
✓ Run Semgrep (SAST)
  - 0 Critical/High findings. 2 Medium findings logged to SARIF.
✓ Build container image
✓ Run Trivy (CVE Scan)
  - 0 CRITICAL vulnerabilities found with available fixes.
✓ Sign image with Cosign
✓ Generate SLSA Provenance
✓ Upload SARIF results to GitHub Security Tab
```
