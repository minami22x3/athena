from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Protocol

import requests

from markdown_utils import slugify
from models import Article

DEFAULT_STATE = {"articles": {}}


class StateBackend(Protocol):
    def load(self) -> dict[str, Any]: ...
    def save(self, state: dict[str, Any]) -> None: ...


class FileStateBackend:
    def __init__(self, state_path: str | Path) -> None:
        self.state_path = Path(state_path)

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return DEFAULT_STATE.copy()

        content = self.state_path.read_text(encoding="utf-8").strip()

        if not content:
            return DEFAULT_STATE.copy()

        return json.loads(content)

    def save(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        os.replace(tmp_path, self.state_path)


class GistStateBackend:
    def __init__(
        self,
        token: str,
        gist_id: str,
        filename: str = "state.json",
        timeout: int = 30,
    ) -> None:
        self.token = token
        self.gist_id = gist_id
        self.filename = filename
        self.timeout = timeout
        self.base_url = f"https://api.github.com/gists/{gist_id}"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "Content-Type": "application/json",
        }

    def load(self) -> dict[str, Any]:
        response = requests.get(
            self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        )

        if response.status_code == 404:
            raise RuntimeError(
                f"Gist {self.gist_id} was not found. "
                "Please check GITHUB_GIST_ID and token permission."
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Failed to load state from Gist. "
                f"Status={response.status_code}, body={response.text[:300]}"
            )

        payload = response.json()
        files = payload.get("files", {})

        file_payload = files.get(self.filename)

        if not file_payload:
            return DEFAULT_STATE.copy()

        content = file_payload.get("content", "").strip()

        if not content:
            return DEFAULT_STATE.copy()

        try:
            state = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gist state file {self.filename} contains invalid JSON."
            ) from exc

        if "articles" not in state or not isinstance(state["articles"], dict):
            raise RuntimeError(
                f"Gist state file {self.filename} must contain an 'articles' object."
            )

        return state

    def save(self, state: dict[str, Any]) -> None:
        content = json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True)

        payload = {
            "description": "Athena Sync State",
            "files": {
                self.filename: {
                    "content": content,
                }
            },
        }

        response = requests.patch(
            self.base_url,
            headers=self.headers,
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Failed to save state to Gist. "
                f"Status={response.status_code}, body={response.text[:300]}"
            )


def get_state_backend(state_path: str | Path) -> StateBackend:
    backend = os.getenv("STATE_BACKEND", "file").strip().lower()

    if backend == "file":
        return FileStateBackend(state_path)

    if backend == "gist":
        token = os.getenv("GITHUB_GIST_TOKEN")
        gist_id = os.getenv("GITHUB_GIST_ID")
        filename = os.getenv("GITHUB_GIST_STATE_FILENAME", "state.json")

        if not token:
            raise RuntimeError("GITHUB_GIST_TOKEN is required when STATE_BACKEND=gist")

        if not gist_id:
            raise RuntimeError("GITHUB_GIST_ID is required when STATE_BACKEND=gist")

        return GistStateBackend(
            token=token,
            gist_id=gist_id,
            filename=filename,
        )

    raise RuntimeError(
        f"Unsupported STATE_BACKEND={backend}. Expected 'file' or 'gist'."
    )


def _ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _article_filename(article: Article) -> str:
    return f"{article.article_id}-{slugify(article.title)}.md"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_article_markdown(
    data_dir: str | Path, article: Article, markdown: str
) -> Path:
    _ensure_dir(data_dir)
    path = Path(data_dir) / _article_filename(article)
    path.write_text(markdown, encoding="utf-8")
    return path


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
