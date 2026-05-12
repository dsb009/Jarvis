# JARVIS Setup Guide

Follow these steps to set up your JARVIS AI system.

---

## Prerequisites Checklist

- [ ] Google Account (for GCP)
- [ ] Telegram Account (for bot)
- [ ] Email Address (for Supabase)

---

## Step 1: Google Cloud Platform (GCP)

### 1.1 Create Project
1. Go to https://console.cloud.google.com/
2. Click **Select a project** → **New Project**
3. Name: `jarvis-ai`
4. Click **Create**

### 1.2 Enable APIs
Run in terminal:
```bash
# Install gcloud CLI from https://cloud.google.com/sdk/docs/install

gcloud auth login
gcloud config set project jarvis-ai

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudtasks.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Configure Docker
gcloud auth configure-docker
```

### 1.3 Create Service Account (Optional - for CI/CD)
```bash
gcloud iam service-accounts create jarvis-deploy \
    --display-name="JARVIS Deploy"

# Grant permissions
gcloud projects add-iam-policy-binding jarvis-ai \
    --member="serviceAccount:jarvis-deploy@jarvis-ai.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding jarvis-ai \
    --member="serviceAccount:jarvis-deploy@jarvis-ai.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"
```

---

## Step 2: Supabase (Database + Auth + pgvector)

### 2.1 Create Account
1. Go to https://supabase.com/
2. Click **Start your project**
3. Sign up with email

### 2.2 Create Project
1. Click **New project**
2. Details:
   - Name: `jarvis-db`
   - Database Password: (create strong password, save it!)
   - Region: `Singapore (ap-southeast-1)` - closest to India
3. Click **Create new project**

### 2.3 Get Credentials
1. Go to **Project Settings** → **API**
2. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_ANON_KEY`

### 2.4 Enable pgvector
Go to **SQL Editor** and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2.5 Create Database Schema
Run the following SQL in **SQL Editor**:
```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Profile
CREATE TABLE user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name TEXT,
    timezone TEXT DEFAULT 'UTC',
    phone TEXT,
    notification_preferences JSONB DEFAULT '{"telegram": true, "email": false}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Preferences
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category, key)
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    status TEXT DEFAULT 'active',
    message_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation Messages
CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    metadata JSONB,
    token_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    input_payload JSONB,
    output_payload JSONB,
    error_info JSONB,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    title TEXT,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Step 3: Upstash (Serverless Redis)

### 3.1 Create Account
1. Go to https://upstash.com/
2. Click **Sign Up** → Use GitHub or email

### 3.2 Create Database
1. Click **Create Database**
2. Configuration:
   - Name: `jarvis-queue`
   - Region: `Asia (Singapore)` - closest to India
   - Type: `Redis`
3. Click **Create**

### 3.3 Get Credentials
1. In database overview, copy:
   - **REST URL** → `UPSTASH_REDIS_REST_URL`
   - **REST Token** → `UPSTASH_REDIS_REST_TOKEN`

---

## Step 4: Telegram Bot

### 4.1 Create Bot
1. Open Telegram → Search for **@BotFather**
2. Send `/newbot`
3. Follow prompts:
   - Bot name: `Jarvis AI`
   - Username: `yourname_jarvis_bot` (must end in `bot`)
4. Copy the **HTTP API token** → `TELEGRAM_BOT_TOKEN`

### 4.2 Get Chat ID (Your User ID)
1. Start a chat with your bot
2. Go to https://api.telegram.org/bot<TOKEN>/getUpdates
3. Replace `<TOKEN>` with your bot token
4. Find `"chat":{"id":123456789}` - this is your chat ID

---

## Step 5: LLM API Keys

### 5.1 Gemini (Simple Tasks - $0.075/1M tokens)
1. Go to https://console.cloud.google.com/apis/credentials
2. Click **Create Credentials** → **API Key**
3. Copy the key → `GEMINI_API_KEY`

### 5.2 OpenAI GPT-4o-mini (Complex Tasks - $0.15/1M tokens)
1. Go to https://platform.openai.com/api-keys
2. Click **Create new secret key**
3. Copy the key → `OPENAI_API_KEY`

---

## Step 6: Configure Environment

### 6.1 Create .env File
```bash
cd /path/to/jarvis
cp .env.example .env
```

### 6.2 Fill in .env
Edit `.env` with all the credentials you gathered:
```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJxxx...

# Upstash
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxx...

# LLM
GEMINI_API_KEY=AIzaxxx...
OPENAI_API_KEY=sk-xxx...

# Telegram
TELEGRAM_BOT_TOKEN=123456:xxx...

# GCP
GCP_PROJECT_ID=jarvis-ai
GCP_REGION=asia-south1
```

---

## Step 7: Deploy to GCP

### 7.1 Setup GCP
```bash
cd infrastructure/scripts
chmod +x gcp-setup.sh
./gcp-setup.sh
```

### 7.2 Deploy API
```bash
chmod +x deploy-api.sh
./deploy-api.sh
```

### 7.3 Deploy Worker
```bash
chmod +x deploy-worker.sh
./deploy-worker.sh
```

### 7.4 Setup Telegram Webhook
After deploying API, run:
```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -d "url=${CLOUD_RUN_API_URL}/webhook"
```

---

## Cost Summary

| Service | Free Tier | Cost |
|---------|-----------|------|
| Cloud Run | 180K requests/mo | $0 |
| Supabase | 500MB DB, 1GB Storage | $0 |
| Upstash | 10K commands/mo | $0 |
| Cloud Tasks | 100K actions/mo | $0 |
| Cloud Scheduler | 3 jobs/mo | $0 |
| **LLM APIs** | - | **~$5-10/mo** |
| **Total** | | **~$5-10/mo** |

---

## Troubleshooting

### Issue: "Service account not found"
```bash
gcloud auth application-default login
```

### Issue: "Permission denied"
Make sure your account has Owner or Editor role on the project.

### Issue: "Docker not found"
Install Docker Desktop from https://docker.com

---

## Next Steps

After deployment:
1. Test the bot by sending a message
2. Check Cloud Run logs in GCP Console
3. Monitor LLM costs in OpenAI/Google Cloud console

---

For help, check the logs:
```bash
gcloud logs read --project=jarvis-ai --filter="resource.type=cloud_run_revision"
```