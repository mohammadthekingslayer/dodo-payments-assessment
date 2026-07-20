# Task 3: Service Mesh & Zero-Trust (Istio)

## Approach and Design Decisions

1. **mTLS STRICT**: The `peer-auth.yaml` configures Istio to reject any plaintext traffic targeting the `payments` namespace, ensuring all inter-service communication is encrypted and mutually authenticated.
2. **Workload Identity (SPIFFE)**: Certificates are issued to workloads based on their Kubernetes `ServiceAccount`. Istiod acts as the Certificate Authority (CA) – it serves as the **trust root** for the mesh. When a pod starts, the Istio sidecar generates a private key and CSR, and sends it to Istiod via the SDS (Secret Discovery Service) API. Istiod validates the Kubernetes token, signs the certificate containing the SPIFFE ID (e.g., `spiffe://cluster.local/ns/payments/sa/reporting`), and returns it. These certificates are automatically rotated by Istiod frequently (typically every 12-24 hours) without application downtime.
3. **Authorization vs. Network Policy**:
   - **NetworkPolicy (L3/L4)**: Enforced by the CNI at the Linux kernel level (eBPF/iptables). It filters packets based on IP addresses, ports, and pod labels. It operates *before* packets reach the Istio sidecar proxy, dropping malicious traffic early.
   - **AuthorizationPolicy (L7)**: Enforced by the Envoy proxy (Istio sidecar). It evaluates cryptographic identity (SPIFFE ID). This stops lateral movement from compromised pods that might share an IP or node but lack the correct cryptographic identity.
   - **Defense in Depth**: We layer both to catch distinct threats. The `NetworkPolicy` stops basic network scanning and port-level attacks, while the `AuthorizationPolicy` stops application-level lateral movement and spoofing.
4. **Ingress & TLS Termination (Bonus)**: `gateway.yaml` defines an Istio Ingress Gateway to terminate TLS at the edge (`api.dodopayments.tech`). This ties the mesh boundary directly back to the **PCI Cardholder Data Environment (CDE)** scope by ensuring no plaintext card data enters the cluster boundary unencrypted, and all traffic from the edge to the internal services is re-encrypted via mTLS.
5. **Canary Rollouts (Bonus)**: `canary.yaml` demonstrates a 90/10 traffic split using a `VirtualService` and `DestinationRule`, enabling safe, progressive delivery of the `ledger-api` without impacting production reliability.
