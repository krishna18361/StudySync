from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://studysync:studysync@localhost:5432/studysync"
    jwt_secret: str = "change-this-to-a-long-random-secret"
    jwt_expire_minutes: int = 60 * 24 * 7
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"
    # performance tuning: bound the context window and set worker threads so the
    # local model responds faster on CPU-only machines (0 threads = auto-detect).
    ollama_num_ctx: int = 8192
    ollama_num_thread: int = 0
    max_upload_mb: int = 25
    chroma_dir: str = str(ROOT_DIR / "chroma_db")
    upload_dir: str = str(ROOT_DIR / "uploads")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def resolved(self, path: str) -> str:
        candidate = Path(path)
        if candidate.is_absolute():
            return str(candidate)
        return str((ROOT_DIR / candidate).resolve())


settings = Settings()
