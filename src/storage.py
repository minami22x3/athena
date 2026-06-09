from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from markdown_utils import slugify
from models import Article


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def article_filename(article: Article) -> str:
    return f"{article.article_id}-{slugify(article.title)}.md"


def save_article_markdown(
    data_dir: str | Path, article: Article, markdown: str
) -> Path:
    ensure_dir(data_dir)
    path = Path(data_dir) / article_filename(article)
    path.write_text(markdown, encoding="utf-8")
    return path


def load_state(state_path: str | Path) -> dict[str, Any]:
    path = Path(state_path)
    if not path.exists():
        return {"articles": {}}

    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state_path: str | Path, state: dict[str, Any]) -> None:
    path = Path(state_path)
    ensure_dir(path.parent)

    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def get_article_state(state: dict[str, Any], article_id: str) -> dict[str, Any] | None:
    return state.get("articles", {}).get(article_id)


def set_article_state(
    state: dict[str, Any],
    article: Article,
    markdown_path: Path,
    content_hash: str,
    openai_file_id: str | None,
    vector_store_file_id: str | None,
    estimated_chunks: int,
) -> None:
    state.setdefault("articles", {})[article.article_id] = {
        "title": article.title,
        "html_url": article.html_url,
        "updated_at": article.updated_at,
        "markdown_path": str(markdown_path),
        "content_hash": content_hash,
        "openai_file_id": openai_file_id,
        "vector_store_file_id": vector_store_file_id,
        "estimated_chunks": estimated_chunks,
    }
