#!/usr/bin/env bash
# Logical backup of the RDS database to S3 (encrypted with SSE-KMS).
# RDS also keeps automated 7-day snapshots; this adds a portable pg_dump copy.
set -euo pipefail
source /opt/studyrag/deploy/.deploy-env
: "${AWS_REGION:?}"
S3_BUCKET=$(grep '^S3_BUCKET=' /opt/studyrag/.env | cut -d= -f2)

DB_URL=$(aws ssm get-parameter --region "$AWS_REGION" --name /studyrag/DATABASE_URL \
  --with-decryption --query Parameter.Value --output text)
DB_URL=${DB_URL/postgresql+psycopg:/postgresql:}   # pg_dump wants a plain libpq URL

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE=/tmp/studyrag-$STAMP.sql.gz
docker run --rm --network host postgres:16-alpine pg_dump "$DB_URL" --no-owner | gzip > "$FILE"
aws s3 cp "$FILE" "s3://$S3_BUCKET/backups/studyrag-$STAMP.sql.gz" --sse aws:kms --region "$AWS_REGION"
rm -f "$FILE"
echo "backup ok: s3://$S3_BUCKET/backups/studyrag-$STAMP.sql.gz"
