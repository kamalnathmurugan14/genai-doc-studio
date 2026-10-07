"""Application settings: one class, read from backend/.env (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
DEFAULT_PROMPTS = Path(__file__).resolve().parent / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    docs_root: Path = Path("./sample_docs")
    data_dir: Path = Path("./data")
    max_upload_mb: int = 25
    allowed_extensions: str = "pdf,docx,txt,md"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    default_temperature: float = 0.3
    default_max_tokens: int = 800
    context_tokens: int = 4096
    chunk_tokens: int = 1500
    chunk_overlap_tokens: int = 150
    json_max_retries: int = 2
    llm_timeout_s: float = 300.0
    prompts_dir: Path = DEFAULT_PROMPTS
    cors_origins: str = "http://localhost:5173"

    @property
    def extensions(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()}

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studio.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
