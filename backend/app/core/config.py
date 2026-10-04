"""Centralized, validated configuration. The single place environment
variables are read (PRD §8.3 Settings; §7.1 "constants centralized")."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repository root next to .env.example. Anchor it to the
# project instead of the process CWD so the app finds it whether uvicorn is
# launched from the repo root or from backend/.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- PRD §17 keys ---
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"
    groq_api_key: str = ""
    groq_chat_model: str = "qwen/qwen3.8-27b"
    embedding_provider: str = "local"  # "local" | "remote"
    qwen_embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    vector_store: str = "chroma"
    database_url: str = "sqlite:///./incidentgraph.db"
    max_upload_bytes: int = 10_485_760
    max_repository_files: int = 3_000
    max_file_bytes: int = 500_000
    max_total_extracted_bytes: int = 100_000_000
    chunk_token_limit: int = 900
    retrieval_top_k: int = 8
    retrieval_min_score: float = 0.05
    max_context_tokens: int = 12_000

    # --- Operational extensions (documented in .env.example / README) ---
    data_dir: Path = Path("./data")
    embedding_remote_base_url: str = ""
    embedding_remote_api_key: str = ""
    embedding_remote_model: str = ""
    embedding_batch_size: int = 64
    embedding_max_retries: int = 4
    github_timeout_seconds: float = 30.0
    llm_timeout_seconds: float = 60.0
    chroma_persist_dir: Path = Path("./data/chroma")
    llm_max_output_tokens: int = 1_500
    chat_history_window: int = 8
    upload_dir: Path = Path("./data/uploads")
    tmp_dir: Path = Path("./data/tmp")

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    def resolve_within_data(self, relative: str | Path) -> Path:
        """Resolve *relative* inside DATA_DIR (used for uploads/tmp/chroma)."""
        path = Path(relative)
        if not path.is_absolute():
            path = self.data_dir / path
        return path

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.upload_dir, self.tmp_dir, self.chroma_persist_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
