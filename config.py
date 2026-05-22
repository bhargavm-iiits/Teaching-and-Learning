"""
Configuration settings for the AI-Driven Personalized VR Teaching System.
Loads environment variables and provides centralized config access.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    """Centralized configuration for the application."""

    # Qwen (DashScope) Settings
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = os.getenv("QWEN_MODEL")

    # Supabase Settings
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")  # anon/public key
    SUPABASE_SERVICE_KEY: str = os.getenv(
        "SUPABASE_SERVICE_KEY", ""
    )  # service role key

    # Pinecone Settings (existing)
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_HOST: str = os.getenv("PINECONE_HOST", "")

    # Azure OpenAI (legacy, for existing modules)
    AZURE_OPENAI_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = os.getenv(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", ""
    )

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of missing keys."""
        missing = []
        if not cls.DASHSCOPE_API_KEY:
            missing.append("DASHSCOPE_API_KEY")
        if not cls.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not cls.SUPABASE_KEY:
            missing.append("SUPABASE_KEY")
        return missing


config = Config()
