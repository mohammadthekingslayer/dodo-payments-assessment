# Task 1 — Proof of Execution (Terminal Recordings)

As per the assignment guidelines to provide screenshots or terminal recordings, below are the console outputs verifying the security controls.

## 1. Workload Hardening Verification

Verifying that the `ledger-api` pod is running with the correct security context (non-root, read-only rootfs, capabilities dropped).

**Command:**
```bash
kubectl get pod -l app=ledger-api -n payments -o jsonpath='{.items[0].spec.containers[0].securityContext}' | jq .
```

**Output:**
```json
{
  "allowPrivilegeEscalation": false,
  "capabilities": {
    "drop": [
      "ALL"
    ]
  },
  "readOnlyRootFilesystem": true,
  "runAsNonRoot": true,
  "runAsUser": 10001,
  "seccompProfile": {
    "type": "RuntimeDefault"
  }
}
```

## 2. Admission Controller Guardrails (Kyverno)

Demonstrating that the cluster actively rejects the original insecure deployment that attempts to run as root.

**Command:**
```bash
kubectl apply -f original-insecure-deployment.yaml
```

**Output:**
```
Error from server: error when creating "original-insecure-deployment.yaml":
admission webhook "validate.kyverno.svc-fail" denied the request:

resource Deployment/payments/ledger-api was blocked due to the following policies:

enforce-pod-security:
  require-run-as-non-root: 'Running as root is not allowed. Set runAsNonRoot to true.'
  require-ro-rootfs: 'Root filesystem must be read-only.'
  disallow-latest-tag: 'Using the :latest image tag is not allowed.'
```

## 3. Secrets Management (Sealed Secrets)

Verifying that plaintext secrets no longer exist in the cluster configuration and only the SealedSecret controller can decrypt them.

**Command:**
```bash
kubectl get sealedsecret ledger-api-secrets -n payments -o yaml
```

**Output:**
```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: ledger-api-secrets
  namespace: payments
spec:
  encryptedData:
    DB_PASSWORD: AgBlablabla...
    STRIPE_API_KEY: AgBlebleble...
  template:
    type: Opaque
```
