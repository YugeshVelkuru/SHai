# Deploy SmartAssist webhook to Google Cloud Functions
# Usage: bash deploy.sh

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="${GCP_REGION:-asia-south1}"
FUNCTION_NAME="smartassist-webhook"

echo "Deploying ${FUNCTION_NAME} to ${PROJECT_ID} (${REGION})..."

gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime=python312 \
  --region="${REGION}" \
  --source=.. \
  --entry-point=smartassist_webhook \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=sqlite+aiosqlite:///tmp/smartassist.db" \
  --memory=512MB \
  --timeout=60s

echo ""
echo "Deployment complete. Webhook URL:"
gcloud functions describe "${FUNCTION_NAME}" \
  --gen2 \
  --region="${REGION}" \
  --format="value(serviceConfig.uri)"
