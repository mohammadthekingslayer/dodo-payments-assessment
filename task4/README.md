# Task 4 — Reconnaissance & Penetration Testing

## Approach

This task covers two parts:
- **Part A**: Passive OSINT reconnaissance of `dodopayments.tech` using only public data sources
- **Part B**: Active penetration testing of the `ledger-api` vulnerable application (authorized target)

## Methodology

- **OWASP Testing Guide v4.2** for web application testing
- **PTES (Penetration Testing Execution Standard)** for overall methodology
- **CVSS v3.1** for severity scoring

## Tools Used

| Tool | Purpose |
|------|---------|
| `dig` | DNS enumeration |
| `openssl s_client` | TLS certificate analysis |
| `curl` | HTTP header fingerprinting and PoC requests |
| `crt.sh` | Certificate Transparency log search |
| Manual code review | Source code analysis of `app.py` |

## Scope

| In Scope | Out of Scope |
|----------|-------------|
| `dodopayments.tech` (passive recon only) | Any active attacks on `.tech`/`.com` hosts |
| `ledger-api` app (local, active testing) | Third-party services |
| Public DNS/CT/TLS data | DoS, stress testing, social engineering |

## Findings Summary

| # | Finding | Severity | CVSS | Endpoint |
|---|---------|----------|------|----------|
| 1 | Unsafe YAML Deserialization (RCE) | **Critical** | 10.0 | `POST /import` |
| 2 | Server-Side Request Forgery (SSRF) | **High** | 8.6 | `GET /fetch` |
| 3 | Hardcoded Secrets in Git History | **High** | 9.1 | `deployment.yaml` |
| 4 | PAN Data Exposure (PCI DSS Violation) | **High** | 7.5 | `GET /transactions` |
| 5 | Missing Authentication on All Endpoints | **High** | 7.5 | All routes |
| 6 | EOL Runtime & Known CVEs | **High** | 7.5 | Dockerfile |
| 7 | Weak Tokenization (Unsalted SHA-256) | **Medium** | 5.9 | `POST /tokenize` |
| 8 | Container Runs as Root | **Medium** | 5.3 | Dockerfile |

→ Full details in [report.md](report.md)

## Files

| File | Purpose |
|------|---------|
| `README.md` | This file — overview and methodology |
| `report.md` | Full standalone penetration test report with PoCs, CVSS vectors, and remediation |
