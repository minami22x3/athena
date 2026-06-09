import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    openai_api_key: str | None
    openai_vector_store_id: str | None
    support_base_url: str
    zendesk_locale: str
    max_articles: int
    data_dir: str
    state_path: str
    state_backend: str
    github_gist_id: str | None
    github_gist_state_filename: str
    dry_run: bool
    delete_stale_vector_files: bool


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_config() -> Config:
    load_dotenv()

    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_vector_store_id=os.getenv("OPENAI_VECTOR_STORE_ID"),
        support_base_url=os.getenv(
            "SUPPORT_BASE_URL", "https://support.optisigns.com"
        ).rstrip("/"),
        zendesk_locale=os.getenv("ZENDESK_LOCALE", "en-us"),
        max_articles=int(os.getenv("MAX_ARTICLES", "50")),
        data_dir=os.getenv("DATA_DIR", "data/articles"),
        state_path=os.getenv("STATE_PATH", "data/state.json"),
        state_backend=os.getenv("STATE_BACKEND", "file"),
        github_gist_id=os.getenv("GITHUB_GIST_ID"),
        github_gist_state_filename=os.getenv(
            "GITHUB_GIST_STATE_FILENAME", "state.json"
        ),
        dry_run=_bool_env("DRY_RUN", False),
        delete_stale_vector_files=_bool_env("DELETE_STALE_VECTOR_FILES", True),
    )
