# Task 3 — Service Mesh & Zero-Trust (Istio)

## Approach and Design Decisions

### Architecture

```
                    ┌──── Istio Ingress Gateway (TLS termination) ────┐
                    │  api.dodopayments.tech:443 → ledger-api:8080    │
                    └────────────────────┬───────────────────────────┘
                                         │ mTLS
┌─────────────────────────────────────────▼─────────────────────────────────┐
│  Namespace: payments   │  mTLS: STRICT  │  AuthzPolicy: default-deny     │
│                                                                           │
│  ┌───────────────────────────┐        ┌───────────────────────────┐       │
│  │ Pod: ledger-api           │        │ Pod: reporting             │       │
│  │ ┌────────┐ ┌────────────┐│        │ ┌────────┐ ┌────────────┐ │       │
│  │ │  App   │ │ Envoy      ││  mTLS  │ │  curl  │ │ Envoy      │ │       │
│  │ │ :8080  │ │ Sidecar    ││◄───────│ │        │ │ Sidecar    │ │       │
│  │ └────────┘ └────────────┘│        │ └────────┘ └────────────┘ │       │
│  │ SPIFFE ID:               │        │ SPIFFE ID:                │       │
│  │ spiffe://cluster.local/  │        │ spiffe://cluster.local/   │       │
│  │  ns/payments/sa/         │        │  ns/payments/sa/reporting  │       │
│  │  ledger-api-sa           │        │                            │       │
│  └───────────────────────────┘        └───────────────────────────┘       │
│                                                                           │
│  NetworkPolicy (L3/L4): default-deny + allow reporting→ledger:8080       │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1. mTLS STRICT

The `peer-auth.yaml` enforces `STRICT` mTLS on the entire `payments` namespace. This means:
- Every connection **must** present a valid mTLS client certificate
- Plaintext HTTP is **rejected** at the sidecar proxy level
- This is verified using `istioctl authn tls-check`

```bash
$ istioctl authn tls-check ledger-api-pod.payments
HOST:PORT                                  STATUS  SERVER  CLIENT  AUTHN POLICY      DESTINATION RULE
ledger-api.payments.svc.cluster.local:8080 OK      STRICT  STRICT  default/payments  -

# Plaintext request from outside the mesh → REJECTED
$ kubectl exec -it unmeshed-pod -- curl http://ledger-api.payments:8080/health
curl: (56) Recv failure: Connection reset by peer
```

### 2. Workload Certificate Lifecycle

| Step | Description |
|------|-------------|
| **Trust Root** | Istiod generates a self-signed root CA certificate at installation (or uses a plugged-in CA like Vault, cert-manager) |
| **CSR Generation** | When a pod starts, the Istio sidecar (Envoy) generates a private key and sends a Certificate Signing Request (CSR) to Istiod via the Secret Discovery Service (SDS) API |
| **Identity Validation** | Istiod validates the pod's Kubernetes ServiceAccount token (bound token projected into the pod) against the Kubernetes API server |
| **Certificate Issuance** | Istiod signs and returns an X.509 certificate containing the SPIFFE ID: `spiffe://cluster.local/ns/{namespace}/sa/{service-account}` |
| **Rotation** | Certificates are automatically rotated every **12–24 hours** (configurable). The sidecar handles this transparently — zero application downtime |
| **Revocation** | If a pod is deleted, its certificate is no longer valid. No CRL is needed because certificates are short-lived |

### 3. Authorization Policies (Identity-Based, Not IP-Based)

**Default-deny** is set first (empty `spec: {}`), which blocks all traffic in the namespace. Then explicit allows are added based on **SPIFFE workload identity**:

```bash
# Unauthorized service → BLOCKED (403)
$ kubectl exec -it unauthorized-pod -n payments -- curl -s http://ledger-api:8080/health
RBAC: access denied

# Authorized `reporting` service → ALLOWED (200)
$ kubectl exec -it reporting-pod -n payments -- curl -s http://ledger-api:8080/health
{"status":"ok"}
```

This is superior to IP-based rules because:
- IPs are ephemeral in Kubernetes (pods get new IPs on restart)
- IPs can be spoofed
- SPIFFE IDs are cryptographically bound to the ServiceAccount identity

### 4. Defense-in-Depth: NetworkPolicy + AuthorizationPolicy

| Layer | Enforced By | OSI Level | What It Catches | What It Misses |
|-------|-------------|-----------|-----------------|----------------|
| **NetworkPolicy** | CNI (Calico/Cilium) via iptables/eBPF | L3/L4 | Port scans, IP-based lateral movement, egress to external CIDRs | Cannot inspect HTTP headers, paths, or identity |
| **AuthorizationPolicy** | Envoy sidecar proxy (Istio) | L7 | Identity spoofing, unauthorized API access, path-based attacks | Cannot block traffic before it reaches the sidecar (raw IP scans) |

**Why both?** A compromised pod that somehow bypasses the Envoy sidecar (e.g., via a container escape) would still be blocked by the kernel-level NetworkPolicy. Conversely, a pod within the network that has IP-level access but lacks the correct cryptographic identity would be blocked by the AuthorizationPolicy.

### 5. Istio Ingress Gateway with TLS Termination (Bonus)

`gateway.yaml` terminates TLS at the mesh edge for `api.dodopayments.tech`. Traffic from the gateway to internal services is then re-encrypted via mTLS, ensuring:
- External clients get standard HTTPS
- Internal traffic never travels in plaintext
- This maps directly to **PCI DSS Requirement 4.1**: encrypt cardholder data in transit

### 6. Canary Release (Bonus)

`canary.yaml` implements a 90/10 traffic split:
- 90% → `stable` subset (current version)
- 10% → `canary` subset (new version)

This enables progressive rollouts with instant rollback by adjusting the weights.

### 7. PCI CDE Scope (Bonus)

The Istio mesh boundary defines the **Cardholder Data Environment (CDE)**:
- All services handling PAN data (`ledger-api`) are inside the mesh
- mTLS ensures encryption in transit (PCI DSS Req 4.1)
- AuthorizationPolicy restricts access to only authorized services (PCI DSS Req 7.1)
- NetworkPolicy provides network segmentation (PCI DSS Req 1.3)

### Files

| File | Purpose |
|---|---|
| `istio/peer-auth.yaml` | PeerAuthentication — mTLS STRICT enforcement |
| `istio/authz-policy.yaml` | Default-deny + explicit ALLOW by SPIFFE identity |
| `istio/network-policy.yaml` | Default-deny + explicit allows at L3/L4 |
| `istio/gateway.yaml` | Istio Ingress Gateway with TLS termination |
| `istio/canary.yaml` | VirtualService + DestinationRule for canary release |
