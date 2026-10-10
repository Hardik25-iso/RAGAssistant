#!/usr/bin/env bash
# Pull the latest images and restart the containers on THIS instance, then wait
# until it is healthy. Run by GitHub Actions through SSM Run Command, one
# instance at a time, so the ALB always has a healthy target (zero downtime).
#   IMAGE_TAG=<git sha> bash deploy/scripts/deploy.sh
set -euo pipefail

APP_DIR=/opt/studyrag
cd "$APP_DIR"
# shellcheck disable=SC1091
source deploy/.deploy-env
export IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "[deploy] $(date -Is) instance=$INSTANCE_ID tag=$IMAGE_TAG"
git fetch --quiet origin main && git reset --quiet --hard origin/main   # compose/nginx/scripts updates

COMPOSE="docker compose -f deploy/docker-compose.prod.yml"
$COMPOSE pull --quiet
$COMPOSE up -d --remove-orphans

echo "[deploy] waiting for health check..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/api/health | grep -q '"status":"ok"'; then
    echo "[deploy] healthy after $((i * 3))s"
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 3
done

echo "[deploy] FAILED: instance not healthy after 90s" >&2
$COMPOSE logs --tail=50 backend >&2 || true
exit 1
