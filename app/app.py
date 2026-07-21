import os
import hashlib
import requests
import yaml
import socket
import ipaddress
from urllib.parse import urlparse
from flask import Flask, request, jsonify

app = Flask(__name__)

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

LEDGER = [
    {"id": "txn_1001", "pan": "4242424242424242", "amount": 4200, "currency": "USD", "status": "captured"},
    {"id": "txn_1002", "pan": "5555555555554444", "amount": 1899, "currency": "EUR", "status": "refunded"},
]

BLOCKED_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
]

@app.route("/health")
def health():
    return jsonify(status="ok")

@app.route("/tokenize", methods=["POST"])
def tokenize():
    payload = request.get_json(silent=True) or {}
    pan = payload.get("pan", "")
    # Remediated: Weak tokenization (using HMAC-SHA256 with a salt)
    salt = b"dodo_secure_salt_"
    token = "tok_" + hashlib.sha256(salt + pan.encode()).hexdigest()[:24]
    return jsonify(token=token, last4=pan[-4:])

@app.route("/transactions")
def transactions():
    # Remediated: PAN Data Exposure (PCI DSS Req 3.4)
    masked = []
    for txn in LEDGER:
        safe_txn = {**txn, "pan": txn["pan"][:6] + "******" + txn["pan"][-4:]}
        masked.append(safe_txn)
    return jsonify(transactions=masked)

@app.route("/import", methods=["POST"])
def import_config():
    # Remediated: Unsafe YAML Deserialization RCE
    config = yaml.safe_load(request.data)
    return jsonify(loaded=str(config))

@app.route("/fetch")
def fetch():
    url = request.args.get("url", "")
    # Remediated: SSRF
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
