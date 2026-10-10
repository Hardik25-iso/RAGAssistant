#!/usr/bin/env bash
# Called from GitHub Actions (authenticated to AWS with OIDC, no stored keys).
# Runs deploy.sh on every instance tagged App=studyrag, ONE AT A TIME, through
# SSM Run Command (no SSH port needs to be open). Stops at the first failure.
#   IMAGE_TAG=<sha> AWS_REGION=ap-south-1 bash deploy/scripts/rolling_deploy.sh
set -euo pipefail
: "${IMAGE_TAG:?}" "${AWS_REGION:?}"

IDS=$(aws ec2 describe-instances --region "$AWS_REGION" \
  --filters "Name=tag:App,Values=studyrag" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -z "$IDS" ]; then
  echo "::warning::no running instances tagged App=studyrag yet; images were pushed, nothing to deploy"
  exit 0
fi

for ID in $IDS; do
  echo "=== deploying $IMAGE_TAG to $ID ==="
  CMD_ID=$(aws ssm send-command --region "$AWS_REGION" --instance-ids "$ID" \
    --document-name AWS-RunShellScript --comment "studyrag deploy $IMAGE_TAG" \
    --parameters "commands=[\"IMAGE_TAG=$IMAGE_TAG bash /opt/studyrag/deploy/scripts/deploy.sh\"],executionTimeout=[\"600\"]" \
    --query Command.CommandId --output text)
  for _ in $(seq 1 60); do
    STATUS=$(aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$ID" \
      --query Status --output text 2>/dev/null || echo Pending)
    case "$STATUS" in
      Success) echo "$ID ok"; break ;;
      Failed|Cancelled|TimedOut)
        aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$ID" \
          --query '[StandardOutputContent,StandardErrorContent]' --output text
        echo "deploy failed on $ID, stopping rollout"; exit 1 ;;
    esac
    sleep 5
  done
  [ "$STATUS" = "Success" ] || { echo "timed out waiting for $ID"; exit 1; }
done
echo "rollout complete"
