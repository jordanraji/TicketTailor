#!/usr/bin/env bash
# Build the SPA against the deployed API and publish it to the S3 website bucket
# (ADR-0020). Run AFTER `terraform apply` with enable_frontend_website = true:
# the build bakes NEXT_PUBLIC_API_URL (the ALB URL, known only post-apply).
#
# Usage (from infra/): ./scripts/deploy-web.sh   (or: make web)
# Requires: node/npm, awscli, terraform, an active Learner Lab session.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${INFRA_DIR}/.." && pwd)"
cd "${INFRA_DIR}"

API_URL="$(terraform output -raw api_url)"
BUCKET="$(terraform output -raw frontend_website_bucket)"
SITE_URL="$(terraform output -raw frontend_website_url)"

if [ -z "${BUCKET}" ]; then
  echo "ERROR: frontend_website_bucket is empty." >&2
  echo "Set 'enable_frontend_website = true' in terraform.tfvars and run 'make apply' first." >&2
  exit 1
fi

echo ">> Building SPA with NEXT_PUBLIC_API_URL=${API_URL}"
cd "${REPO_ROOT}/web"
NEXT_PUBLIC_API_URL="${API_URL}" npm run build

echo ">> Publishing web/out to s3://${BUCKET}"
aws s3 sync out "s3://${BUCKET}/" --delete

echo ">> Done. The SPA is live at: ${SITE_URL}"
echo "   If you recreate the bucket, re-run 'make apply' so the API CORS origin"
echo "   follows the new website URL, then re-run this script."
