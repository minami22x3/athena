import json

from state_backend import FileStateBackend, GistStateBackend, sha256_text


def test_sha256_text_changes_when_content_changes():
    first = sha256_text("hello")
    second = sha256_text("hello world")

    assert first != second


def test_sha256_text_is_stable():
    assert sha256_text("same") == sha256_text("same")


def test_file_state_backend_returns_default_when_missing(tmp_path):
    state_path = tmp_path / "state.json"
    backend = FileStateBackend(state_path)

    assert backend.load() == {"articles": {}}


def test_file_state_backend_save_and_load(tmp_path):
    state_path = tmp_path / "state.json"
    backend = FileStateBackend(state_path)

    state = {
        "articles": {
            "123": {
                "title": "Test article",
                "content_hash": "abc",
            }
        }
    }

    backend.save(state)

    assert backend.load() == state


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_gist_state_backend_load(monkeypatch):
    gist_payload = {
        "files": {
            "state.json": {
                "content": json.dumps(
                    {
                        "articles": {
                            "123": {
                                "title": "Test article",
                                "content_hash": "abc",
                            }
                        }
                    }
                )
            }
        }
    }

    def fake_get(*args, **kwargs):
        return FakeResponse(200, gist_payload)

    monkeypatch.setattr("requests.get", fake_get)

    backend = GistStateBackend(
        token="fake-token",
        gist_id="fake-gist-id",
        filename="state.json",
    )

    state = backend.load()

    assert state["articles"]["123"]["content_hash"] == "abc"


def test_gist_state_backend_save(monkeypatch):
    calls = {}

    def fake_patch(url, headers, json, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        calls["timeout"] = timeout
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr("requests.patch", fake_patch)

    backend = GistStateBackend(
        token="fake-token",
        gist_id="fake-gist-id",
        filename="state.json",
    )

    backend.save({"articles": {"123": {"content_hash": "abc"}}})

    assert calls["url"] == "https://api.github.com/gists/fake-gist-id"
    assert calls["json"]["files"]["state.json"]["content"]
    assert "Bearer fake-token" == calls["headers"]["Authorization"]
