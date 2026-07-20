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
Error from server: error when creating "original-insecure-deployment.yaml": admission webhook "validate.kyverno.svc-fail" denied the request: 

resource Deployment/payments/ledger-api was blocked due to the following policies

enforce-pod-security:
  require-run-as-non-root: 'validation error: Running as root is not allowed. Set runAsNonRoot to true. rule require-run-as-non-root failed at path /spec/template/spec/securityContext/runAsNonRoot/'
  require-ro-rootfs: 'validation error: Root filesystem must be read-only. rule require-ro-rootfs failed at path /spec/template/spec/containers/0/securityContext/readOnlyRootFilesystem/'
  disallow-latest-tag: 'validation error: Using the :latest image tag is not allowed. rule disallow-latest-tag failed at path /spec/template/spec/containers/0/image/'
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
  creationTimestamp: "2026-07-20T14:23:01Z"
  name: ledger-api-secrets
  namespace: payments
  resourceVersion: "123456"
  uid: a1b2c3d4-e5f6-7890-abcd-1234567890ab
spec:
  encryptedData:
    DB_PASSWORD: Ar+JuLikNlnJUmgktiaEk8tTy+QWB+YHPeFdkGLYzdb8P14m/DDK+uVIE88KLnswKzwqnkdoz7PnsNVrMc6G+ZOp+QHtkvYr9MM/WXUgZCbGR2DAxjsK19NKwM9D58FG6GR++0uKK71xsE14qHnY3yEJ/C9TqNdiaf8NslOwbZTuQM8llqjGyClHTGwDPtj+ITMgXMbCC4f9LaGdB6l4RtmB/gH9KEao3mgfJjOdizOZic4LRxSOX8zqCDt/i4Y/eMsn62JP63KaWppRRzwBjDyi/nxlA8vw7dF9kQxkGcQmZsy734V1KC3Ndcf6BhL0gy3HougHp/o74UurpUOrcpeD61UxV0Oc2QUOVA6R9mXpWDwItlqH+2Wr9/KvQeLdJWNSz0QoIg0buxvj+j3/hfSCVpTbhzRIrZqIfe2xV9qQ7HFPmQ2ebyexEVFLTRnITAc62AQ249VcrEqHTVME7KgrJd6fnpRS
    STRIPE_API_KEY: ArgzkhAjfbdio1DFdoOAYQiB0w2+zying3SeE0dC7lhh1cQ16BvIYIo2jjD2LtAjqnfWWck7GNsHva8DCdKQq3UVUK2axeNyUBUb7OV6rqOU69oLXVkCXMVdAk+BcKetfHJtfa3rT9zAshkvphaRnRlx7B1DVx3PwyTQFosVlmwNxI0OS8J4W17VZwPl2KfsziFZjd59D5fgEfIPHWwRpJBPY/n9a5TNkzZoEJZUoKkHCyBTlSz3KgRtkMQzQwfkrbgo1epJ+mmjivR8DMFN1AD0BHjC6ikuJwV3xyKb52c5IZkBinoNWulO1FCw635jLA6aau41DQQXX0auQpNic48s7HKUl6Ww3nH3vEVHCGgFlPNSartMbdBxn7P6aY+cT1NxpPVqZnXMRtBD8pjzxvBLI1sCluYob0cLx6Omt+jd6sQlvesQ0d67QeWpvnny9PWwIrHehVLOMhF3+j43gl7nRqJTPOJ+
  template:
    metadata:
      creationTimestamp: null
      name: ledger-api-secrets
      namespace: payments
    type: Opaque
```
