#!/usr/bin/env bash
# One-time setup for an EC2 instance (Ubuntu 24.04). Paste into "User data" when
# launching, or run as root over SSM Session Manager:
#   sudo GHCR_OWNER=<github-user-lowercase> REPO_URL=https://github.com/<user>/RAGAssistant.git \
#        S3_BUCKET=studyrag-docs-<team> CORS_ORIGINS=https://<your-cloudfront-domain> bash setup_ec2.sh
set -euo pipefail

: "${GHCR_OWNER:?set GHCR_OWNER}"
: "${REPO_URL:?set REPO_URL}"
: "${S3_BUCKET:?set S3_BUCKET}"
CORS_ORIGINS="${CORS_ORIGINS:-*}"
APP_DIR=/opt/studyrag

echo "== packages & automatic security updates =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git unattended-upgrades unzip jq
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== Docker Engine + Compose plugin =="
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
fi

echo "== AWS CLI (for backups) =="
command -v aws >/dev/null || snap install aws-cli --classic

echo "== 2 GB swap (t3.micro has 1 GB RAM) =="
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 && echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
fi

echo "== instance metadata (IMDSv2) =="
TOKEN=$(curl -sX PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
md() { curl -sH "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/$1"; }
INSTANCE_ID=$(md instance-id)
REGION=$(md placement/region)

echo "== app checkout =="
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

# Non-secret settings only. Secrets come from SSM Parameter Store at app start.
cat > "$APP_DIR/.env" <<EOF
AWS_REGION=$REGION
SSM_PREFIX=/studyrag/
S3_BUCKET=$S3_BUCKET
CORS_ORIGINS=$CORS_ORIGINS
ENABLE_RESILIENCE=true
LLM_PROVIDER=groq
LLM_FALLBACK_PROVIDER=gemini
EOF
chmod 600 "$APP_DIR/.env"

cat > /etc/profile.d/studyrag.sh <<EOF
export GHCR_OWNER=$GHCR_OWNER
export INSTANCE_ID=$INSTANCE_ID
export AWS_REGION=$REGION
EOF
cp /etc/profile.d/studyrag.sh "$APP_DIR/deploy/.deploy-env"

echo "== daily DB backup at 02:30 =="
echo "30 2 * * * root $APP_DIR/deploy/scripts/backup_db.sh >> /var/log/studyrag-backup.log 2>&1" > /etc/cron.d/studyrag-backup

echo "== first deploy =="
bash "$APP_DIR/deploy/scripts/deploy.sh"
echo "Done. Instance $INSTANCE_ID is serving on port 80."
