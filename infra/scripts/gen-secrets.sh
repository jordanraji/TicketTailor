#!/usr/bin/env bash
# Generate the app secrets for terraform.tfvars: a random SECRET_KEY (JWT signing,
# ADR-0014) and a VAPID key pair (web push, ADR-0011) in the exact base64url form
# pywebpush expects. Prints tfvars-ready lines - paste them into terraform.tfvars
# and add your own db_password.
#
# Usage (from infra/):  ./scripts/gen-secrets.sh
# Requires: openssl, and the worker's uv environment (for the VAPID keys).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SECRET_KEY="$(openssl rand -base64 48)"

# VAPID keys: generated + verified to load through pywebpush, in the worker venv.
read -r VAPID_PUBLIC VAPID_PRIVATE < <(
  cd "${REPO_ROOT}/worker" && uv run python - <<'PY'
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

priv = ec.generate_private_key(ec.SECP256R1())
der = priv.private_bytes(
    serialization.Encoding.DER,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
pub = priv.public_key().public_bytes(
    serialization.Encoding.X962,
    serialization.PublicFormat.UncompressedPoint,
)
priv_b64 = b64url(der)
Vapid.from_string(private_key=priv_b64)  # verify the format loads
print(b64url(pub), priv_b64)
PY
)

cat <<EOF

# ---- paste into infra/terraform.tfvars ----
secret_key = "${SECRET_KEY}"

vapid_public_key  = "${VAPID_PUBLIC}"
vapid_private_key = "${VAPID_PRIVATE}"
# (also set db_password, and email_from_address / resend_api_key if using email)
EOF
