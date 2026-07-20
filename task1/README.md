# Task 1 — Deploy & Harden the Workload

## Approach & Design Decisions

### Overview
The original `ledger-api` deployment was shipped with critical security violations: running as root, plaintext secrets hardcoded in the manifest and committed to Git, no resource limits, no health probes, and no RBAC boundaries. This task transforms it into a production-grade, PCI DSS–compliant workload.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Namespace: payments                                                │
│  PSS: restricted │ Kyverno: Enforce │ istio-injection: enabled      │
│                                                                     │
│  ┌─────────────────────┐       ┌──────────────────────┐            │
│  │  Deployment:        │       │  Deployment:          │            │
│  │  ledger-api (×3)    │◄──────│  reporting (×1)       │            │
│  │  SA: ledger-api-sa  │       │  SA: reporting        │            │
│  │  Port: 8080         │       │  curlimages/curl:8.8.0│            │
│  └────────┬────────────┘       └──────────────────────┘            │
│           │                                                         │
│  ┌────────▼────────────┐       ┌──────────────────────┐            │
│  │  Service:           │       │  SealedSecret:        │            │
│  │  ledger-api:8080    │       │  ledger-api-secrets   │            │
│  └────────┬────────────┘       │  (STRIPE_API_KEY,     │            │
│           │                    │   DB_PASSWORD)        │            │
│  ┌────────▼────────────┐       └──────────────────────┘            │
│  │  Ingress:           │                                            │
│  │  api.dodopayments   │       ┌──────────────────────┐            │
│  │  .tech → :8080      │       │  Kyverno Policies:   │            │
│  └─────────────────────┘       │  • deny root         │            │
│                                │  • deny :latest      │            │
│                                │  • verify signatures │            │
│                                └──────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### Security Hardening Applied

| Control | Implementation | Rationale |
|---|---|---|
| **Non-root execution** | `runAsNonRoot: true`, `runAsUser: 10001` | Prevents privilege escalation if container is compromised |
| **Read-only root FS** | `readOnlyRootFilesystem: true` | Blocks attackers from writing backdoors or modifying binaries |
| **Drop all capabilities** | `capabilities.drop: ["ALL"]` | Removes all Linux capabilities (NET_RAW, SYS_ADMIN, etc.) |
| **Seccomp** | `seccompProfile.type: RuntimeDefault` | Restricts syscalls to a safe default set |
| **Resource limits** | CPU 100m–500m, Memory 128Mi–256Mi | Prevents resource abuse / noisy-neighbour DoS |
| **Health probes** | Liveness + Readiness on `/health` | Enables automatic restart on crash, traffic routing only to healthy pods |
| **Dedicated SA** | `ledger-api-sa` with Role scoped to `configmaps:get,list` | Drops the default ServiceAccount (which may have broader permissions) |
| **Secrets management** | Bitnami Sealed Secrets | Secrets encrypted at rest in Git; only the cluster controller can decrypt |
| **PSS Restricted** | Namespace labels enforce `restricted` profile | Kubernetes-native admission control as a second guardrail |
| **Kyverno policies** | `Enforce` mode: deny root, deny `:latest`, verify Cosign signatures | Prevents insecure workloads from ever reaching the cluster |

### Secrets Management: Sealed Secrets

The original deployment hardcoded `STRIPE_API_KEY` and `DB_PASSWORD` as plaintext environment variables. These have been removed and replaced with a `SealedSecret`:

```bash
# 1. Install Sealed Secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.5/controller.yaml

# 2. Create plaintext secret
kubectl create secret generic ledger-api-secrets \
  --from-literal=STRIPE_API_KEY='sk_live_...' \
  --from-literal=DB_PASSWORD='<real-password>' \
  --dry-run=client -o yaml > secret.yaml

# 3. Encrypt with kubeseal (cluster's public key)
kubeseal --format yaml < secret.yaml > task1/manifests/sealed-secret.yaml

# 4. Delete plaintext, commit only the sealed version
rm secret.yaml
```

### RBAC Personas (Bonus)

| Persona | Role | Permissions |
|---|---|---|
| **Developer** | `dev-role` | Read-only: pods, logs, deployments, services |
| **Operator** | `operator-role` | Read + update/patch: pods, deployments, services, configmaps |
| **Admin** | `admin-role` | Full access within `payments` namespace only (namespace-scoped, not cluster-admin) |

### Admission Policy Rejection Demo (Bonus)

When the original insecure deployment is applied with Kyverno policies active:

```
$ kubectl apply -f original-insecure-deployment.yaml

Error from server: error when creating "deployment.yaml":
admission webhook "validate.kyverno.svc-fail" denied the request:

resource Deployment/payments/ledger-api was blocked due to the following policies:

enforce-pod-security:
  require-run-as-non-root: 'Running as root is not allowed. Set runAsNonRoot to true.'
  require-ro-rootfs: 'Root filesystem must be read-only.'
  disallow-latest-tag: 'Using the :latest image tag is not allowed.'
```

### Files

| File | Purpose |
|---|---|
| `manifests/namespace.yaml` | Namespace with PSS restricted labels |
| `manifests/deployment.yaml` | Hardened Deployment + Service |
| `manifests/neighbour.yaml` | Reporting service (neighbour) with full hardening |
| `manifests/serviceaccount.yaml` | Dedicated least-privilege ServiceAccount |
| `manifests/rbac.yaml` | Role + RoleBinding for ledger-api-sa |
| `manifests/rbac-personas.yaml` | Developer / Operator / Admin roles |
| `manifests/configmap.yaml` | Non-sensitive config (environment, log level) |
| `manifests/sealed-secret.yaml` | Encrypted secrets (SealedSecret) |
| `manifests/ingress.yaml` | Ingress with forced TLS redirect |
| `manifests/network-policy.yaml` | Default-deny + explicit allow NetworkPolicy |
| `kyverno-policies/policies.yaml` | Admission guardrails (deny root, latest, unsigned) |
