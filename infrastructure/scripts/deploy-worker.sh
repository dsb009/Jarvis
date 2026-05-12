#!/bin/bash
# ============================================
# Deploy Worker to Cloud Run Job
# ============================================

set -e

PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}
REGION=${GCP_REGION:-asia-south1}
JOB_NAME=jarvis-worker
IMAGE_NAME=gcr.io/$PROJECT_ID/$JOB_NAME

echo "🚀 Deploying JARVIS Worker to Cloud Run Job..."

# Load environment variables
if [ -f ../../.env ]; then
    source ../../.env
else
    echo "❌ .env file not found"
    exit 1
fi

# Build and push container
echo "📦 Building worker image..."
gcloud builds submit \
    --tag $IMAGE_NAME \
    --project $PROJECT_ID \
    --region $REGION \
    --config ../docker/cloudbuild-worker.yaml \
    ../../jarvis-backend/

# Create Cloud Run Job
echo "📋 Creating Cloud Run Job..."
gcloud run jobs deploy $JOB_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --set-env-vars="\
SUPABASE_URL=$SUPABASE_URL,\
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY,\
UPSTASH_REDIS_REST_URL=$UPSTASH_REDIS_REST_URL,\
UPSTASH_REDIS_REST_TOKEN=$UPSTASH_REDIS_REST_TOKEN,\
GEMINI_API_KEY=$GEMINI_API_KEY,\
OPENAI_API_KEY=$OPENAI_API_KEY" \
    --project $PROJECT_ID

echo ""
echo "✅ Worker deployed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Create Cloud Tasks queue:"
echo "   gcloud tasks queues create agent-queue --location=$REGION"
echo ""
echo "2. Setup Cloud Scheduler:"
echo "   ./deploy-scheduler.sh"
echo ""
echo "3. Test worker manually:"
echo "   gcloud run jobs execute $JOB_NAME --region $REGION"