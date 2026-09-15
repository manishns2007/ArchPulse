"""
ArchScale — Module 1: Communication Ingestion Layer
Application configuration via environment variables.
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

    # Storage
    storage_root: str = "storage"
    raw_storage_dir: str = "raw"
    processed_storage_dir: str = "processed"

    # Upload limits
    max_upload_size_bytes: int = 20 * 1024 * 1024  # 20 MB

    # Allowed file extensions
    allowed_extensions: str = ".txt,.pdf"

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
