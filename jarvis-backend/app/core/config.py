"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"

    # ============================================
    # Supabase (Database + Auth + pgvector)
    # ============================================
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""

    # ============================================
    # Upstash (Serverless Redis Queue)
    # ============================================
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    # ============================================
    # LLM Providers
    # ============================================
    # Gemini 1.5 Flash - Simple tasks ($0.075/1M input)
    GEMINI_API_KEY: str = ""

    # GPT-4o-mini - Complex tasks ($0.15/1M input)
    OPENAI_API_KEY: str = ""

    # ============================================
    # Telegram Bot
    # ============================================
    TELEGRAM_BOT_TOKEN: str = ""

    # ============================================
    # Google Cloud Platform
    # ============================================
    GCP_PROJECT_ID: str = ""
    GCP_REGION: str = "asia-south1"
    CLOUD_RUN_API_URL: str = ""
    CLOUD_RUN_WORKER_URL: str = ""
    CLOUD_TASKS_QUEUE: str = "agent-queue"
    CLOUD_TASKS_LOCATION: str = "asia-south1"

    # ============================================
    # Optional
    # ============================================
    TAVILY_API_KEY: str = ""
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()