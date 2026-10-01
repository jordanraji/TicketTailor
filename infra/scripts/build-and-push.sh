#!/usr/bin/env bash
# Build the three deployable images and push them to the ECR repositories
# created by Terraform. Run AFTER `terraform apply` has created the repos
# (the repos must exist before the compute module can reference the images).
#
# Usage (from infra/): ./scripts/build-and-push.sh [TAG]
#   TAG defaults to the current git short SHA (immutable, traceable) so you can
#   be certain which commit is under load. Set *_image_tag in terraform.tfvars
#   to the SAME tag, then `terraform apply` to roll onto it. A mutable "latest"
#   alias is also pushed for convenience, but do not load-test against it - it
#   says nothing about which code is running.
#
# Requires: docker, awscli, terraform, git, and an active Learner Lab session.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${INFRA_DIR}/.." && pwd)"

# Default to the git short SHA so the build is pinned to a known commit. A dirty
# tree is flagged so an untracked change under test is obvious.
DEFAULT_TAG="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)"
if [ -n "$(git -C "${REPO_ROOT}" status --porcelain 2>/dev/null)" ]; then
  DEFAULT_TAG="${DEFAULT_TAG}-dirty"
fi
TAG="${1:-$DEFAULT_TAG}"
echo ">> Building and pushing tag: ${TAG}"
echo ">> Set api_image_tag/relay_image_tag/worker_image_tag = \"${TAG}\" in terraform.tfvars"

cd "${INFRA_DIR}"

# Read the ECR repo URLs from Terraform outputs and derive the registry host.
# `terraform output -json <name>` returns the value directly (no value/type
# envelope), so index the map keys straight away.
REPOS_JSON="$(terraform output -json ecr_repositories)"
API_REPO="$(echo "${REPOS_JSON}"   | python3 -c 'import sys,json;print(json.load(sys.stdin)["api"])')"
RELAY_REPO="$(echo "${REPOS_JSON}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["relay"])')"
WORKER_REPO="$(echo "${REPOS_JSON}"| python3 -c 'import sys,json;print(json.load(sys.stdin)["worker"])')"
REGISTRY_HOST="${API_REPO%%/*}"
REGION="$(echo "${REGISTRY_HOST}" | cut -d. -f4)"

echo ">> Logging in to ECR ${REGISTRY_HOST} (${REGION})"
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY_HOST}"

# --provenance=false: stop buildx attaching an attestation manifest, which turns
# the image into an OCI image index that AWS Lambda rejects ("image manifest ...
# not supported"). --load imports the single-arch image into the local docker so
# `docker push` sends a plain Docker v2 schema2 manifest. amd64 = Fargate/Lambda.
BUILD="docker buildx build --provenance=false --platform linux/amd64 --load"

echo ">> Building api"
${BUILD} -t "${API_REPO}:${TAG}" -f "${REPO_ROOT}/api/Dockerfile" "${REPO_ROOT}/api"

echo ">> Building relay (context = repo root; needs api + relay trees)"
${BUILD} -t "${RELAY_REPO}:${TAG}" -f "${REPO_ROOT}/relay/Dockerfile" "${REPO_ROOT}"

echo ">> Building worker (Lambda image)"
${BUILD} -t "${WORKER_REPO}:${TAG}" -f "${REPO_ROOT}/worker/Dockerfile" "${REPO_ROOT}/worker"

for IMG in "${API_REPO}" "${RELAY_REPO}" "${WORKER_REPO}"; do
  echo ">> Pushing ${IMG}:${TAG}"
  docker push "${IMG}:${TAG}"
  # Convenience alias only; the SHA tag is the one to deploy/load-test against.
  if [ "${TAG}" != "latest" ]; then
    docker tag "${IMG}:${TAG}" "${IMG}:latest"
    docker push "${IMG}:latest"
  fi
done

echo ">> Done. Re-run 'terraform apply' to roll services onto the new images, or"
echo "   force a new deployment: aws ecs update-service --force-new-deployment ..."
