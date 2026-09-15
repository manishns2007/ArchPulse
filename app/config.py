"""
ArchScale — Communication Agent
Application configuration via environment variables.
Covers Module 1 (ingestion) and Module 2 (understanding).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Module 1 — Storage
    # ------------------------------------------------------------------
    storage_root: str = "storage"
    raw_storage_dir: str = "raw"
    processed_storage_dir: str = "processed"

    # Upload limits
    max_upload_size_bytes: int = 20 * 1024 * 1024  # 20 MB

    # Allowed file extensions
    allowed_extensions: str = ".txt,.pdf"

    # ------------------------------------------------------------------
    # Module 2 — LLM Provider
    # ------------------------------------------------------------------

    # Which provider to use: "gemini" | "openai" | "fake"
    # Set to "fake" in tests so no real API calls are made.
    llm_provider: str = "gemini"

    # Model identifier (interpreted by the selected provider)
    llm_model: str = "gemini-2.5-flash"

    # API key — read from env, never hard-coded
    llm_api_key: str = ""

    # Request timeout in seconds
    llm_timeout_seconds: int = 30

    # Number of retry attempts on transient failures
    llm_max_retries: int = 2

    # -------------------------------------------------------------------
    # Derived helpers (not env vars)
    # -------------------------------------------------------------------

    @property
    def storage_root_path(self) -> Path:
        return Path(self.storage_root)

    @property
    def raw_path(self) -> Path:
        return self.storage_root_path / self.raw_storage_dir

    @property
    def processed_path(self) -> Path:
        return self.storage_root_path / self.processed_storage_dir

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",")}


# Singleton instance used throughout the application
settings = Settings()
