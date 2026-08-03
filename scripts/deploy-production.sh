#!/usr/bin/env bash
set -euo pipefail

: "${GHCR_PAT:?GHCR_PAT is required}"
: "${GHCR_USER:?GHCR_USER is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${PUBLIC_URL:?PUBLIC_URL is required}"

compose_file="docker-compose.prod.yml"
backend_image="ghcr.io/${GHCR_USER}/visionnaire-backend"
frontend_image="ghcr.io/${GHCR_USER}/visionnaire-frontend"

cd "$(dirname "$0")/.."

echo "${GHCR_PAT}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin
trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT

tag_current_for_rollback() {
  local service="$1"
  local image="$2"
  local container_id

  container_id="$(docker compose -f "${compose_file}" ps -q "${service}")"
  if [[ -n "${container_id}" ]]; then
    docker image tag "$(docker inspect --format '{{.Image}}' "${container_id}")" \
      "${image}:rollback"
  fi
}

verify_public_health() {
  curl --fail --silent --show-error \
    --retry 18 \
    --retry-delay 5 \
    --retry-all-errors \
    "${PUBLIC_URL%/}/" >/dev/null

  curl --fail --silent --show-error \
    --retry 18 \
    --retry-delay 5 \
    --retry-all-errors \
    "${PUBLIC_URL%/}/api/health/ready" >/dev/null
}

rollback() {
  echo "Deployment verification failed; restoring previous images." >&2

  if ! docker image inspect \
    "${backend_image}:rollback" \
    "${frontend_image}:rollback" >/dev/null 2>&1; then
    echo "No complete previous deployment is available for rollback." >&2
    return 1
  fi

  IMAGE_TAG=rollback docker compose -f "${compose_file}" up -d --remove-orphans
  if ! verify_public_health; then
    echo "The restored deployment also failed health verification." >&2
    return 1
  fi
}

tag_current_for_rollback backend "${backend_image}"
tag_current_for_rollback frontend "${frontend_image}"

export IMAGE_TAG
docker compose -f "${compose_file}" pull backend frontend
docker compose -f "${compose_file}" up -d --remove-orphans

if ! verify_public_health; then
  if ! rollback; then
    echo "Automatic rollback failed; manual recovery is required." >&2
  fi
  exit 1
fi

printf '%s\n' "${IMAGE_TAG}" >.deployed-image-tag
echo "Deployment ${IMAGE_TAG} verified successfully."
