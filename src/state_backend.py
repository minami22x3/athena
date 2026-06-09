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
    def save_last_run(self, summary: dict[str, Any]) -> None: ...


class FileStateBackend:
    def __init__(
        self,
        state_path: str | Path,
        last_run_path: str | Path = "data/last-run.json",
    ) -> None:
        self.state_path = Path(state_path)
        self.last_run_path = Path(last_run_path)

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return DEFAULT_STATE.copy()

        content = self.state_path.read_text(encoding="utf-8").strip()

        if not content:
            return DEFAULT_STATE.copy()

        state = json.loads(content)
        self._validate_state(state)
        return state

    def save(self, state: dict[str, Any]) -> None:
        self._validate_state(state)
        self._write_json_atomic(self.state_path, state)

    def save_last_run(self, summary: dict[str, Any]) -> None:
        self.last_run_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(self.last_run_path, summary)

    @staticmethod
    def _validate_state(state: dict[str, Any]) -> None:
        if "articles" not in state or not isinstance(state["articles"], dict):
            raise RuntimeError("State must contain an 'articles' object.")

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        os.replace(tmp_path, path)


class GistStateBackend:
    def __init__(
        self,
        token: str,
        gist_id: str,
        state_filename: str = "state.json",
        last_run_filename: str = "last-run.json",
        timeout: int = 30,
    ) -> None:
        self.token = token
        self.gist_id = gist_id
        self.state_filename = state_filename
        self.last_run_filename = last_run_filename
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
        file_content = self._get_gist_file_content(self.state_filename)

        if not file_content:
            return DEFAULT_STATE.copy()

        try:
            state = json.loads(file_content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gist state file {self.state_filename} contains invalid JSON."
            ) from exc

        self._validate_state(state)
        return state

    def save(self, state: dict[str, Any]) -> None:
        self._validate_state(state)
        self._patch_gist_file(
            filename=self.state_filename,
            payload=state,
            description="Athena sync state and last run artifact",
        )

    def save_last_run(self, summary: dict[str, Any]) -> None:
        self._patch_gist_file(
            filename=self.last_run_filename,
            payload=summary,
            description="Athena sync state and last run artifact",
        )

    def _get_gist_file_content(self, filename: str) -> str | None:
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
                f"Failed to load Gist. "
                f"Status={response.status_code}, body={response.text[:300]}"
            )

        payload = response.json()
        files = payload.get("files", {})
        file_payload = files.get(filename)

        if not file_payload:
            return None

        return file_payload.get("content", "")

    def _patch_gist_file(
        self,
        filename: str,
        payload: dict[str, Any],
        description: str,
    ) -> None:
        content = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)

        response = requests.patch(
            self.base_url,
            headers=self.headers,
            json={
                "description": description,
                "files": {
                    filename: {
                        "content": content,
                    }
                },
            },
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Failed to save {filename} to Gist. "
                f"Status={response.status_code}, body={response.text[:300]}"
            )

    @staticmethod
    def _validate_state(state: dict[str, Any]) -> None:
        if "articles" not in state or not isinstance(state["articles"], dict):
            raise RuntimeError("State must contain an 'articles' object.")


def get_state_backend(state_path: str | Path) -> StateBackend:
    backend = os.getenv("STATE_BACKEND", "file").strip().lower()

    if backend == "file":
        return FileStateBackend(
            state_path=state_path,
            last_run_path=os.getenv("LAST_RUN_PATH", "artifacts/last-run.json"),
        )

    if backend == "gist":
        token = os.getenv("GITHUB_GIST_TOKEN")
        gist_id = os.getenv("GITHUB_GIST_ID")
        state_filename = os.getenv("GITHUB_GIST_STATE_FILENAME", "state.json")
        last_run_filename = os.getenv("GITHUB_GIST_LAST_RUN_FILENAME", "last-run.json")

        if not token:
            raise RuntimeError("GITHUB_GIST_TOKEN is required when STATE_BACKEND=gist")

        if not gist_id:
            raise RuntimeError("GITHUB_GIST_ID is required when STATE_BACKEND=gist")

        return GistStateBackend(
            token=token,
            gist_id=gist_id,
            state_filename=state_filename,
            last_run_filename=last_run_filename,
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
