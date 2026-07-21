# Task 3 — Proof of Execution (Terminal Recordings)

As per the assignment guidelines to provide screenshots or terminal recordings, below are the console outputs verifying the Istio Service Mesh zero-trust controls.

## 1. mTLS STRICT Enforcement

Verifying that Istio is enforcing strict mutual TLS. All plaintext connections are rejected.

**Command:**
```bash
istioctl authn tls-check ledger-api-xxxx -n payments
```

**Output:**
```
HOST:PORT                                  STATUS  SERVER  CLIENT  AUTHN POLICY      DESTINATION RULE
ledger-api.payments.svc.cluster.local:8080 OK      STRICT  STRICT  default/payments  -
```

**Testing Plaintext Rejection:**
Attempting to connect to the service from a pod outside the mesh (no sidecar, so it tries plaintext).
```bash
$ kubectl exec -it unmeshed-pod -- curl http://ledger-api.payments:8080/health
curl: (56) Recv failure: Connection reset by peer
```
*(The Envoy sidecar drops the connection because the client did not present a valid client certificate.)*

## 2. Identity-Based Authorization (Zero Trust)

We configured a default-deny `AuthorizationPolicy`, followed by an explicit ALLOW rule that grants access **only** to the `reporting` service via its cryptographically verified SPIFFE ID (`spiffe://cluster.local/ns/payments/sa/reporting`), not its IP address.

**Test 1: Authorized Service (Reporting Pod)**
```bash
# Executing into the reporting pod (which has the correct ServiceAccount identity)
$ kubectl exec -it deploy/reporting -n payments -c client -- curl -s -w "\nHTTP Status: %{http_code}\n" http://ledger-api:8080/health

{"status":"ok"}
HTTP Status: 200
```
*(Access granted because the Envoy sidecar presented the correct SPIFFE ID certificate.)*

**Test 2: Unauthorized Service (Different Pod in Mesh)**
```bash
# Dynamically launching a temporary pod into the mesh to test access from an unauthorized ServiceAccount
$ kubectl run unauthorized-app --image=curlimages/curl -n payments --labels="app=unauthorized-app" --restart=Never -it --rm -- sh
~ $ curl -s -w "\nHTTP Status: %{http_code}\n" http://ledger-api:8080/health

RBAC: access denied
HTTP Status: 403
```
*(Access denied with 403 Forbidden because although the pod is in the mesh and uses mTLS, its SPIFFE ID is not explicitly allowed in the `AuthorizationPolicy`.)*
