#!/bin/bash
# ============================================
# GCP Setup Script
# Run this to enable required APIs
# ============================================

set -e

echo "🔧 Setting up Google Cloud Platform..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "Enter your GCP Project ID:"
    read GCP_PROJECT_ID
fi

gcloud config set project $GCP_PROJECT_ID

echo "📦 Enabling required APIs..."

# Enable Cloud Run
gcloud services enable run.googleapis.com

# Enable Cloud Tasks
gcloud services enable cloudtasks.googleapis.com

# Enable Cloud Scheduler
gcloud services enable cloudscheduler.googleapis.com

# Enable Artifact Registry
gcloud services enable artifactregistry.googleapis.com

# Enable Cloud Build (for CI/CD)
gcloud services enable cloudbuild.googleapis.com

echo "✅ GCP APIs enabled successfully!"

echo ""
echo "📋 Next steps:"
echo "1. Configure Docker authentication:"
echo "   gcloud auth configure-docker"
echo ""
echo "2. Create a service account for deployments (optional but recommended):"
echo "   gcloud iam service-accounts create jarvis-deploy \\"
echo "     --display-name='JARVIS Deploy'"
echo ""
echo "3. Grant permissions to service account:"
echo "   gcloud projects add-iam-policy-binding \$GCP_PROJECT_ID \\"
echo "     --member='serviceAccount:jarvis-deploy@\$GCP_PROJECT_ID.iam.gserviceaccount.com' \\"
echo "     --role='roles/run.admin'"
echo "   gcloud projects add-iam-policy-binding \$GCP_PROJECT_ID \\"
echo "     --member='serviceAccount:jarvis-deploy@\$GCP_PROJECT_ID.iam.gserviceaccount.com' \\"
echo "     --role='roles/iam.serviceAccountUser'"
echo ""
echo "4. Create .env file from .env.example and fill in your credentials"
echo ""
echo "5. Run: ./deploy-api.sh"