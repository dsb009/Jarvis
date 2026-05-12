#!/bin/bash
# ============================================
# Deploy API to Cloud Run
# ============================================

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}
REGION=${GCP_REGION:-asia-south1}
SERVICE_NAME=jarvis-api
IMAGE_NAME=gcr.io/$PROJECT_ID/$SERVICE_NAME

echo "🚀 Deploying JARVIS API to Cloud Run..."

# Load environment variables
if [ -f ../../.env ]; then
    source ../../.env
else
    echo "❌ .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi

# Build and push container
echo "📦 Building container image..."
gcloud builds submit \
    --tag $IMAGE_NAME \
    --project $PROJECT_ID \
    --region $REGION \
    --config ../docker/cloudbuild.yaml \
    ../../jarvis-backend/

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="\
SUPABASE_URL=$SUPABASE_URL,\
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY,\
UPSTASH_REDIS_REST_URL=$UPSTASH_REDIS_REST_URL,\
UPSTASH_REDIS_REST_TOKEN=$UPSTASH_REDIS_REST_TOKEN,\
GEMINI_API_KEY=$GEMINI_API_KEY,\
OPENAI_API_KEY=$OPENAI_API_KEY,\
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN,\
GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=$REGION" \
    --project $PROJECT_ID

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format='value(status.url)' --project $PROJECT_ID)

echo ""
echo "✅ API deployed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "📋 Next steps:"
echo "1. Register Telegram webhook:"
echo "   curl -X POST \"https://api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/setWebhook\" -d \"url=$SERVICE_URL/webhook\""
echo ""
echo "2. Update .env with CLOUD_RUN_API_URL=$SERVICE_URL"
echo ""
echo "3. Deploy worker: ./deploy-worker.sh"