#!/usr/bin/env bash
set -euo pipefail

: "${GHCR_PAT:?GHCR_PAT is required}"
: "${GHCR_USER:?GHCR_USER is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${PUBLIC_URL:?PUBLIC_URL is required}"

compose_file="docker-compose.prod.yml"
backend_image="ghcr.io/${GHCR_USER}/visionnaire-backend"
frontend_image="ghcr.io/${GHCR_USER}/visionnaire-frontend"
qdrant_backup=""

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

prepare_qdrant() {
  local target_image="qdrant/qdrant:v1.18.3"
  local migration_images=(
    "qdrant/qdrant:v1.9.7"
    "qdrant/qdrant:v1.10.1"
    "qdrant/qdrant:v1.11.5"
    "qdrant/qdrant:v1.12.6"
    "qdrant/qdrant:v1.13.6"
    "qdrant/qdrant:v1.14.1"
    "qdrant/qdrant:v1.15.5"
    "qdrant/qdrant:v1.16.3"
    "qdrant/qdrant:v1.17.1"
    "${target_image}"
  )
  local image
  local logs

  if start_qdrant "${target_image}"; then
    return 0
  fi

  logs="$(docker compose -f "${compose_file}" logs --no-color --tail 200 qdrant)"
  if [[ "${logs}" != *'unknown variant `on_disk`, expected `mmap` or `in_ram_mmap`'* ]]; then
    report_qdrant_failure
    return 1
  fi

  backup_qdrant_storage "${target_image}"
  echo "Detected Qdrant v1.9 storage; applying required sequential migrations."
  for image in "${migration_images[@]}"; do
    echo "Migrating Qdrant storage with ${image}."
    if ! start_qdrant "${image}"; then
      report_qdrant_failure
      return 1
    fi
    # Give startup migrations time to flush before replacing the container
    # with the next consecutive minor release.
    sleep 5
  done
  return 0
}

backup_qdrant_storage() {
  local image="$1"
  local container_id
  local backup_dir="${PWD}/.qdrant-backups"
  local backup_name="qdrant-before-v1.18.3-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"

  container_id="$(docker compose -f "${compose_file}" ps -aq qdrant)"
  if [[ -z "${container_id}" ]]; then
    echo "Cannot back up Qdrant storage without its container." >&2
    return 1
  fi

  docker compose -f "${compose_file}" stop qdrant
  mkdir -p "${backup_dir}"
  docker run --rm \
    --volumes-from "${container_id}" \
    --volume "${backup_dir}:/backup" \
    --entrypoint tar \
    "${image}" \
    -C /qdrant/storage -czf "/backup/${backup_name}" .
  docker run --rm \
    --volume "${backup_dir}:/backup:ro" \
    --entrypoint tar \
    "${image}" \
    -tzf "/backup/${backup_name}" >/dev/null

  qdrant_backup="${backup_dir}/${backup_name}"
  echo "Verified Qdrant storage backup at ${qdrant_backup}."
}

remove_qdrant_backup() {
  if [[ -n "${qdrant_backup}" ]]; then
    rm -f "${qdrant_backup}"
    rmdir "$(dirname "${qdrant_backup}")" 2>/dev/null || true
    echo "Removed temporary Qdrant migration backup after successful verification."
  fi
}

start_qdrant() {
  local image="$1"
  local container_id
  local health

  # Recreate Qdrant separately so Compose does not immediately reject a stale
  # unhealthy state while evaluating the backend's service_healthy dependency.
  if ! QDRANT_IMAGE="${image}" docker compose -f "${compose_file}" \
    up -d --no-deps --force-recreate qdrant; then
    return 1
  fi
  container_id="$(docker compose -f "${compose_file}" ps -q qdrant)"
  if [[ -z "${container_id}" ]]; then
    return 1
  fi

  for _ in {1..36}; do
    health="$(docker inspect --format '{{.State.Health.Status}}' "${container_id}")"
    if [[ "${health}" == "healthy" ]]; then
      return 0
    fi

    if [[ "$(docker inspect --format '{{.State.Running}}' "${container_id}")" != "true" ]]; then
      break
    fi

    sleep 5
  done

  return 1
}

report_qdrant_failure() {
  echo "Qdrant did not become healthy; recent logs follow." >&2
  docker compose -f "${compose_file}" logs --tail 200 qdrant >&2
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
prepare_qdrant
docker compose -f "${compose_file}" up -d --remove-orphans

if ! verify_public_health; then
  if ! rollback; then
    echo "Automatic rollback failed; manual recovery is required." >&2
  fi
  exit 1
fi

remove_qdrant_backup
printf '%s\n' "${IMAGE_TAG}" >.deployed-image-tag
echo "Deployment ${IMAGE_TAG} verified successfully."
